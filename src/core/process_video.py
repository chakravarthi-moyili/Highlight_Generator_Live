import subprocess
import tempfile
from src.core.config import STREAM_URL, CHUNK_DURATION
import urllib.parse
import requests

def record_livestream_segment(output_path, duration=CHUNK_DURATION):
    cmd = [
        "ffmpeg", "-y", "-i", STREAM_URL,
        "-t", str(duration),
        "-c", "copy", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_and_save_new_chunks(stream_url, last_seen_chunks, chunk_id_start=1):
    response = requests.get(stream_url)
    lines = response.text.splitlines()
    segment_urls = [line for line in lines if line.endswith('.ts')]
    new_chunks = [url for url in segment_urls if url not in last_seen_chunks]
    chunk_files = []
    chunk_id = chunk_id_start

    # Get base URL from m3u8_url
    base_url = stream_url.rsplit('/', 1)[0]

    for url in new_chunks:
        # If url is relative, prepend base_url
        if not url.startswith("http"):
            full_url = urllib.parse.urljoin(base_url + '/', url)
        else:
            full_url = url
        r = requests.get(full_url)
        tmp_file = tempfile.NamedTemporaryFile(suffix=f"_chunk{chunk_id}.ts", delete=False)
        tmp_file.write(r.content)
        tmp_file.close()
        print(f"[CHUNK] Downloaded: {full_url} as {tmp_file.name}")
        chunk_files.append(tmp_file.name)
        chunk_id += 1
    return chunk_files, segment_urls, chunk_id

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
