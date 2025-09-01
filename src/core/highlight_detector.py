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

whisper_model = whisper.load_model("tiny")
highlight_count = 0
highlight_data = []
job_id = JOB_ID

def transcribe_audio(audio_path):
    result = whisper_model.transcribe(audio_path)
    print (f"Transcription result: {result['text']}")
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
        print(f"[FFmpeg Remux Error] {input_path}: {e}")
        return input_path  # fallback to original
        

def concatenate_highlight(prev_path, curr_path, next_path, title, description):
    global highlight_count
    global job_id
    s3_cloud = CloudStorageClient()
    clips = []

    try:
        if prev_path:
            prev_path = fix_mp4(prev_path)
            prev_clip_full = VideoFileClip(prev_path)
            prev_duration = prev_clip_full.duration
            start = max(0, prev_duration - 10)
            end = prev_duration
            if end - start > 0.5:
                prev_clip = prev_clip_full.subclip(start, end)
                clips.append(prev_clip)
    except Exception as e:
        print(f"Prev clip error: {e}")

    try:
        curr_path = fix_mp4(curr_path)
        curr_clip = VideoFileClip(curr_path)
        clips.append(curr_clip)
    except Exception as e:
        print(f"Curr clip error: {e}")

    try:
        if next_path:
            next_path = fix_mp4(next_path)
            next_clip_full = VideoFileClip(next_path)
            next_duration = next_clip_full.duration
            end = min(10, next_duration)
            if end > 0.5:
                next_clip = next_clip_full.subclip(0, end)
                clips.append(next_clip)
    except Exception as e:
        print(f"Next clip error: {e}")

    if clips:
        final = concatenate_videoclips(clips)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title.strip()) or "highlight"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.mp4"
        output_path = os.path.join(HIGHLIGHTS_DIR, filename)
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)

        # --- thumbnail + upload + cleanup (same as your code) ---
        thumbnail_path = output_path.replace('.mp4', '.jpg')
        generate_thumbnail(output_path, thumbnail_path)

        highlight_count += 1
        highlight_folder = f"{S3_PREFIX}/{job_id}/highlights_{highlight_count}"
        s3_key = f"{highlight_folder}/{filename}"
        print(f"Uploading highlight to S3: {s3_key}")
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
        print(f"Highlight saved: {highlight_url}")
        print(f"Thumbnail saved: {thumbnail_url}")
        print(f"Metadata saved: {metadata_url}")

        try:
            os.remove(output_path)
            os.remove(thumbnail_path)
            os.remove(metadata_path)
            print(f"Deleted local files: {output_path}, {thumbnail_path}, {metadata_path}")
        except Exception as e:
            print(f"Error deleting local files: {e}")

        return highlight_url, thumbnail_url, metadata_url, filename

    return None, None, None


def main_loop(stop_event: Event = None):
    own_event = False
    if stop_event is None:
        stop_event = Event()
        own_event = True  #If we run it locally
    print(f"//***************** Starting highlight detection for Job ID: {job_id} *****************//")
    s3_cloud = CloudStorageClient()
    s3_cloud.delete_old_live_highlights(age_days=7)
    total_time = 0
    video_queue = deque(maxlen=10)  # Increase maxlen to avoid overflow
    chunk_id = 1
    last_seen_chunks = []
    try:
        while not stop_event.is_set():
            # Download new chunks and add to queue
            chunk_files, last_seen_chunks, chunk_id = fetch_and_save_new_chunks(STREAM_URL, last_seen_chunks, chunk_id)
            for tmp_video_path in chunk_files:
                video_queue.append(tmp_video_path)

            # Process the oldest chunk if enough are available
            while len(video_queue) >= 3:
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
                    print(f"Removed temporary audio file: {wav_audio_path}")
                highlight, title, description = is_highlight(transcript)
                if highlight:
                    highlight_url, thumbnail_url, metadata_url, fname = concatenate_highlight(prev_path, curr_path, next_path, title, description)
                    print(f"Highlight detected: {title} ({highlight_url})")
                    if highlight_url and thumbnail_url and metadata_url:
                        highlight_key = f"highlight_{highlight_count}"
                        highlight_data.append({
                            highlight_key: [highlight_url, thumbnail_url, title, description]
                        })
                        send_callback_to_server(job_id, highlight_data)
                else:
                    print("No highlight detected.")
                total_time += CHUNK_DURATION

                # Remove the oldest chunk (slide window)
                removed_video_path = video_queue.popleft()
                try:
                    if os.path.exists(removed_video_path):
                        os.remove(removed_video_path)
                except Exception as e:
                    print(f"Error deleting old chunk {removed_video_path}: {e}")

            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped by user.")
        if own_event:
            stop_event.set()
    finally:
        print("[Highlight Detector] Stopping & Cleaning up...")
        while video_queue:
            leftover_path = video_queue.popleft()
            try:
                if os.path.exists(leftover_path):
                    os.remove(leftover_path)
                if os.path.exists(wav_audio_path):
                    os.remove(wav_audio_path)
            except Exception as e:
                print(f"Error deleting chunk {leftover_path}: {e}")
