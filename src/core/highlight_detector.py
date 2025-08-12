import tempfile
import time
import datetime
import re
from collections import deque
from moviepy.editor import *
from src.core.config import *
from core.process_video import record_livestream_segment, extract_audio_segment
from src.core.thumbnail import generate_thumbnail
from src.gpt.openai_client import is_highlight
from src.utils.s3_utils import CloudStorageClient
from src.core.config import JOB_ID

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
    # from moviepy.editor import VideoFileClip, concatenate_videoclips
    global highlight_count
    global job_id
    s3_cloud = CloudStorageClient()
    clips = []
    try:
        if prev_path:
            prev_clip = VideoFileClip(prev_path).subclip(max(0, CHUNK_DURATION - 10), CHUNK_DURATION)
            clips.append(prev_clip)
    except: pass
    try:
        clips.append(VideoFileClip(curr_path))
    except: pass
    try:
        if next_path:
            next_clip = VideoFileClip(next_path).subclip(0, min(10, CHUNK_DURATION))
            clips.append(next_clip)
    except: pass
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
        return highlight_url, thumbnail_url, filename
    return None, None, None

def main_loop():
    print("Starting highlight detection...")
    # s3_cloud = CloudStorageClient()
    # Clear S3 highlights folder on startup/reset
    # s3_cloud.delete_prefix(S3_PREFIX)
    total_time = 0
    video_queue = deque(maxlen=3)
    try:
        while True:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
                record_livestream_segment(tmp_video.name, CHUNK_DURATION)
                video_queue.append(tmp_video.name)
                if len(video_queue) < 2:
                    total_time += CHUNK_DURATION
                    continue
                current_chunk_path = video_queue[-2]
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                    extract_audio_segment(current_chunk_path, tmp_audio.name, 0, CHUNK_DURATION)
                    transcript = transcribe_audio(tmp_audio.name)
                    highlight, title, description = is_highlight(transcript)
                    if highlight:
                        if len(video_queue) < 3:
                            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as next_chunk:
                                record_livestream_segment(next_chunk.name, CHUNK_DURATION)
                                video_queue.append(next_chunk.name)
                        prev_path = video_queue[-3] if len(video_queue) == 3 else None
                        curr_path = video_queue[-2]
                        next_path = video_queue[-1] if len(video_queue) == 3 else None
                        highlight_url, thumbnail_url, fname = concatenate_highlight(prev_path, curr_path, next_path, title, description)
                        print(f"Highlight detected: {title} ({highlight_url})")
                    else:
                        print("No highlight detected.")
            total_time += CHUNK_DURATION
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped by user.")
