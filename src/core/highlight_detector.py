import tempfile
import time
import datetime
import re
from collections import deque
from moviepy.editor import *
from src.core.config import *
from src.core.process_video import record_livestream_segment, extract_audio_segment, fetch_and_save_new_chunks
from src.core.thumbnail import generate_thumbnail
from src.gpt.openai_client import is_highlight
from src.utils.s3_utils import CloudStorageClient
from src.core.config import JOB_ID
from src.api.endpoints import send_callback_to_server

import json

import whisper
whisper_model = whisper.load_model("base")
highlight_count = 0
job_id = JOB_ID

def transcribe_audio(audio_path):
    result = whisper_model.transcribe(audio_path)
    print (f"Transcription result: {result['text']}")
    return result['text']

def concatenate_highlight(prev_path, curr_path, next_path, title, description):
    global highlight_count
    global job_id
    s3_cloud = CloudStorageClient()
    clips = []
    try:
        if prev_path:
            prev_clip_full = VideoFileClip(prev_path)
            prev_duration = prev_clip_full.duration
            # Only extract last 10 seconds if possible
            start = max(0, prev_duration - 10)
            end = prev_duration
            if end - start > 0.5:  # Only add if duration is reasonable
                prev_clip = prev_clip_full.subclip(start, end)
                clips.append(prev_clip)
    except Exception as e:
        print(f"Prev clip error: {e}")
    try:
        curr_clip = VideoFileClip(curr_path)
        clips.append(curr_clip)
    except Exception as e:
        print(f"Curr clip error: {e}")
    try:
        if next_path:
            next_clip_full = VideoFileClip(next_path)
            next_duration = next_clip_full.duration
            # Only extract first 10 seconds if possible
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
        # Generate thumbnail
        thumbnail_path = output_path.replace('.mp4', '.jpg')
        generate_thumbnail(output_path, thumbnail_path)

        highlight_count += 1
        highlight_folder = f"{S3_PREFIX}/{job_id}/highlights_{highlight_count}"
        s3_key = f"{highlight_folder}/{filename}"
        print(f"Uploading highlight to S3: {s3_key}")
        # Upload to S3
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
        return highlight_url, thumbnail_url, metadata_url, filename
    return None, None, None

def main_loop():
    print("Starting highlight detection...")
    s3_cloud = CloudStorageClient()
    s3_cloud.delete_old_live_highlights(age_days=7)
    total_time = 0
    video_queue = deque(maxlen=10)  # Increase maxlen to avoid overflow
    chunk_id = 1
    last_seen_chunks = []
    try:
        while True:
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
                extract_audio_segment(curr_path, tmp_audio.name, 0, CHUNK_DURATION)
                transcript = transcribe_audio(tmp_audio.name)
                highlight, title, description = is_highlight(transcript)
                if highlight:
                    highlight_url, thumbnail_url, metadata_url, fname = concatenate_highlight(prev_path, curr_path, next_path, title, description)
                    print(f"Highlight detected: {title} ({highlight_url})")
                    if highlight_url and thumbnail_url and metadata_url:
                        send_callback_to_server(job_id, highlight_url, thumbnail_url, metadata_url)
                else:
                    print("No highlight detected.")
                total_time += CHUNK_DURATION

                # Remove the oldest chunk (slide window)
                video_queue.popleft()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped by user.")
