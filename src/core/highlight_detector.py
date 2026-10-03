import tempfile
import time
from multiprocessing import Event
import datetime
import re
from collections import deque
from moviepy.editor import *
from src.core.config import *
from src.core.process_video import extract_audio_segment, fetch_and_save_new_chunks
from src.core.thumbnail import generate_thumbnail
from src.gpt.openai_client import is_highlight
from src.utils.s3_utils import CloudStorageClient
from src.core.config import JOB_ID
from src.api.callback_api import send_callback_to_server
import json
import whisper
import os
import subprocess
from src.core.logging_config import get_logger, setup_logging

logger = get_logger(__name__)

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "medium")

# Loaded lazily by _get_whisper_model(). Loading at import time put a copy of the
# model on the GPU in every process that imports this module - including the API
# server, which only serves HTTP and never transcribes - and that was exhausting
# the GPU before main_loop() could start.
whisper_model = None
highlight_count = 0
highlight_data = []
job_id = JOB_ID


def _get_whisper_model():
    """Load the Whisper model on first use, in the process that transcribes."""
    global whisper_model
    if whisper_model is None:
        logger.info("Loading Whisper model '%s'...", WHISPER_MODEL_NAME)
        whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
        logger.info("Whisper model '%s' loaded.", WHISPER_MODEL_NAME)
    return whisper_model

def transcribe_audio(audio_path):
    result = _get_whisper_model().transcribe(audio_path)
    logger.info("Transcription result: %s", result['text'])
    return result['text']

def fix_mp4(input_path):
    """Re-mux MP4 to make it MoviePy-compatible without re-encoding."""
    if not input_path or not os.path.exists(input_path):
        return input_path
    output_path = input_path.replace(".mp4", "_fixed.mp4")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-c", "copy", "-movflags", "faststart", output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception as e:
        logger.error("[FFmpeg Remux Error] %s: %s", input_path, e)
        return input_path  # fallback to original
        

def _get_duration(path):
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def _trim_clip(input_path, output_path, start=None, end=None):
    """Trim a video clip using ffmpeg."""
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-t", str(end - (start or 0))]
    cmd += ["-c", "copy", output_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def concatenate_highlight(prev_path, curr_path, next_path, title, description, job_id=JOB_ID):
    global highlight_count
    s3_cloud = CloudStorageClient()
    segments = []
    tmp_files = []

    try:
        if prev_path and os.path.exists(prev_path):
            dur = _get_duration(prev_path)
            start = max(0, dur - 10)
            if dur - start > 0.5:
                tmp = tempfile.NamedTemporaryFile(suffix=".ts", delete=False)
                tmp.close()
                _trim_clip(prev_path, tmp.name, start=start, end=dur)
                segments.append(tmp.name)
                tmp_files.append(tmp.name)
    except Exception as e:
        logger.error("Prev clip error: %s", e)

    try:
        if curr_path and os.path.exists(curr_path):
            segments.append(curr_path)
    except Exception as e:
        logger.error("Curr clip error: %s", e)

    try:
        if next_path and os.path.exists(next_path):
            dur = _get_duration(next_path)
            end = min(10, dur)
            if end > 0.5:
                tmp = tempfile.NamedTemporaryFile(suffix=".ts", delete=False)
                tmp.close()
                _trim_clip(next_path, tmp.name, start=0, end=end)
                segments.append(tmp.name)
                tmp_files.append(tmp.name)
    except Exception as e:
        logger.error("Next clip error: %s", e)

    if segments:
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title.strip()) or "highlight"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.mp4"
        output_path = os.path.join(HIGHLIGHTS_DIR, filename)

        # Concatenate using ffmpeg concat protocol (works natively with .ts files)
        concat_input = "|".join(segments)
        subprocess.run([
            "ffmpeg", "-y", "-i", f"concat:{concat_input}",
            "-c:v", "libx264", "-c:a", "aac", "-movflags", "faststart",
            output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Clean up temp trimmed files
        for f in tmp_files:
            if os.path.exists(f):
                os.remove(f)

        # --- thumbnail + upload + cleanup (same as your code) ---
        thumbnail_path = output_path.replace('.mp4', '.jpg')
        generate_thumbnail(output_path, thumbnail_path)

        highlight_count += 1
        highlight_folder = f"{S3_PREFIX}/{job_id}/highlights_{highlight_count}"
        s3_key = f"{highlight_folder}/{filename}"
        logger.info("Uploading highlight to S3: %s", s3_key)
        highlight_url = s3_cloud.upload_to_s3(output_path, s3_key)
        thumbnail_url = s3_cloud.upload_to_s3(thumbnail_path, s3_key.replace('.mp4', '.jpg'))

        metadata = {
            "title": title,
            "description": description,
            "timestamp": timestamp,
        }
        metadata_path = output_path.replace('.mp4', '.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        metadata_s3_key = s3_key.replace('.mp4', '.json')
        metadata_url = s3_cloud.upload_to_s3(metadata_path, metadata_s3_key)
        logger.info("Highlight saved: %s", highlight_url)
        logger.info("Thumbnail saved: %s", thumbnail_url)
        logger.info("Metadata saved: %s", metadata_url)

        try:
            os.remove(output_path)
            os.remove(thumbnail_path)
            os.remove(metadata_path)
            logger.info("Deleted local files: %s, %s, %s", output_path, thumbnail_path, metadata_path)
        except Exception as e:
            logger.error("Error deleting local files: %s", e)

        return highlight_url, thumbnail_url, metadata_url, filename

    # Must match the 4-tuple above: the caller unpacks four names, so returning a
    # 3-tuple here raised "not enough values to unpack" whenever no usable
    # segments were found.
    logger.warning("No usable segments for highlight '%s'; nothing produced.", title)
    return None, None, None, None


def main_loop(stop_event: Event = None, job_id: str = None, stream_url: str = None):
    # `spawn` starts a fresh interpreter, so the parent's logging config is not
    # inherited - configure it here or this process logs nothing.
    setup_logging()
    own_event = False
    if stop_event is None:
        stop_event = Event()
        own_event = True  #If we run it locally

    # Take the job identity from the caller rather than the module-level constants.
    # Those are read from config/config.yaml at import time, and the API rewrites
    # that file on every request - so a request arriving while this process was
    # still starting up made it adopt the wrong job_id and upload to the wrong
    # S3 prefix.
    if job_id is None:
        job_id = JOB_ID
    if stream_url is None:
        stream_url = STREAM_URL
    logger.info("//***************** Starting highlight detection for Job ID: %s *****************//", job_id)
    s3_cloud = CloudStorageClient()

    # Optional: Clean up old highlights (with timeout to prevent startup blocking)
    # This runs synchronously but with a 30-second timeout
    try:
        result = s3_cloud.delete_old_live_highlights(age_days=7, timeout_seconds=30)
        if result >= 0:
            logger.info("S3 cleanup completed: deleted %d old objects", result)
        else:
            logger.warning("S3 cleanup failed or timed out, continuing without cleanup")
    except Exception as e:
        logger.warning("S3 cleanup encountered error: %s, continuing without cleanup", e)

    total_time = 0
    video_queue = deque(maxlen=10)  # Increase maxlen to avoid overflow
    chunk_id = 1
    last_seen_chunks = []
    # Bound up front: the cleanup block below references it, and it stayed
    # undefined (NameError) if the loop exited before the first chunk was processed.
    wav_audio_path = None
    try:
        # Fail fast and visibly if the model cannot be loaded (e.g. CUDA OOM),
        # rather than dying on an uncaught import-time exception.
        _get_whisper_model()
        while not stop_event.is_set():
            # Download new chunks and add to queue
            chunk_files, last_seen_chunks, chunk_id = fetch_and_save_new_chunks(stream_url, last_seen_chunks, chunk_id)
            for tmp_video_path in chunk_files:
                video_queue.append(tmp_video_path)

            # Process the oldest chunk if enough are available. The stop_event is
            # re-checked here, not just in the outer loop: one pass through this
            # body runs transcription, an OpenAI call, ffmpeg concat and three S3
            # uploads - 20s or more - so a stop arriving mid-pass always blew past
            # the parent's join timeout and got escalated to SIGTERM.
            while len(video_queue) >= 3 and not stop_event.is_set():
                # Always process the second oldest chunk (center of window)
                prev_path = video_queue[0]
                curr_path = video_queue[1]
                next_path = video_queue[2]

                tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_audio.close()
                wav_audio_path = tmp_audio.name
                extract_audio_segment(curr_path, wav_audio_path, 0)
                transcript = transcribe_audio(wav_audio_path)
                if os.path.exists(wav_audio_path):
                    os.remove(wav_audio_path)
                    logger.debug("Removed temporary audio file: %s", wav_audio_path)
                if stop_event.is_set():
                    logger.info("Stop requested; abandoning chunk before highlight production.")
                    break
                highlight, title, description = is_highlight(transcript)
                if highlight:
                    highlight_url, thumbnail_url, metadata_url, fname = concatenate_highlight(prev_path, curr_path, next_path, title, description, job_id)
                    logger.info("Highlight detected: %s (%s)", title, highlight_url)
                    if highlight_url and thumbnail_url and metadata_url:
                        highlight_key = f"highlight_{highlight_count}"
                        callback_data = {
                            "video_url": highlight_url,
                            "thumbnail_img": thumbnail_url,
                            "title": title,
                            "description": description
                        }
                        # highlight_data.append({
                        #     highlight_key: [highlight_url, thumbnail_url, title, description]
                        # })
                        highlight_data.append({
                            highlight_key: callback_data
                        })
                        logger.info("Highlight data to updated: %s", highlight_data)
                        send_callback_to_server(job_id, highlight_data)
                else:
                    logger.info("No highlight detected.")
                total_time += CHUNK_DURATION

                # Remove the oldest chunk (slide window)
                removed_video_path = video_queue.popleft()
                try:
                    if os.path.exists(removed_video_path):
                        os.remove(removed_video_path)
                except Exception as e:
                    logger.error("Error deleting old chunk %s: %s", removed_video_path, e)

            # Interruptible sleep: wait() returns as soon as a stop is requested
            # instead of burning the full second first.
            stop_event.wait(1)
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
        if own_event:
            stop_event.set()
    except Exception:
        # Without this the process died silently as far as stdout was concerned -
        # the traceback went to stderr and the run just stopped producing output.
        logger.exception("[Highlight Detector] Fatal error; detection is stopping.")
        raise
    finally:
        logger.info("[Highlight Detector] Stopping & Cleaning up...")
        while video_queue:
            leftover_path = video_queue.popleft()
            try:
                if os.path.exists(leftover_path):
                    os.remove(leftover_path)
            except Exception as e:
                logger.error("Error deleting chunk %s: %s", leftover_path, e)
        try:
            if wav_audio_path and os.path.exists(wav_audio_path):
                os.remove(wav_audio_path)
        except Exception as e:
            logger.error("Error deleting temp audio %s: %s", wav_audio_path, e)
