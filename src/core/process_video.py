import subprocess
import tempfile
from src.core.config import STREAM_URL, CHUNK_DURATION

def record_livestream_segment(output_path, duration=CHUNK_DURATION):
    cmd = [
        "ffmpeg", "-y", "-i", STREAM_URL,
        "-t", str(duration),
        "-c", "copy", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def extract_audio_segment(video_path, output_audio_path, start_time=0, duration=CHUNK_DURATION):
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ss", str(start_time),
        "-t", str(duration),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
