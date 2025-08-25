import subprocess
import tempfile
from src.core.config import STREAM_URL, CHUNK_DURATION
import urllib.parse
import requests
import os

ACCEPTED_SEGMENT_EXTENSIONS = ('.ts', '.m4s', '.mp4', '.mkv')

def fetch_and_save_new_chunks(stream_url, last_seen_chunks, chunk_id_start=1):
    response = requests.get(stream_url)
    lines = response.text.splitlines()

    # Extract init segment and media segments
    init_segment = None
    segment_urls = []

    # Determine stream type
    is_fmp4 = False
    for line in lines:
        if line.startswith("#EXT-X-MAP"):
            is_fmp4 = True
            # Example: #EXT-X-MAP:URI="init.mp4"
            init_segment = line.split("URI=")[1].strip('"')
        elif line and not line.startswith("#") and line.strip().endswith(ACCEPTED_SEGMENT_EXTENSIONS):
            segment_urls.append(line.strip())

    if is_fmp4 and not init_segment:
        raise ValueError("Init segment (#EXT-X-MAP) not found in playlist.")

    # Find new segments
    new_segments = [s for s in segment_urls if s not in last_seen_chunks]
    chunk_files = []
    chunk_id = chunk_id_start

    # Base URL (stream_url without the last part)
    base_url = stream_url.rsplit('/', 1)[0]

    for seg in new_segments:
        print(f"[INFO] Processing segment: {seg}")
        ext = os.path.splitext(seg)[1]

        if is_fmp4 and ext in ('.m4s', '.mp4', '.mkv'):
            output_path = os.path.join(tempfile.gettempdir(), f"chunk{chunk_id}.mp4")
            try:
                # Download init + segment(s) and combine
                assemble_fmp4_stream(base_url, init_segment, [seg], output_path)
                print(f"[CHUNK] Saved as {output_path}")
                chunk_files.append(output_path)
                chunk_id += 1
            except Exception as e:
                print(f"[ERROR] Failed to process segment {seg}: {e}")

        elif not is_fmp4 and ext == '.ts':
            full_url = urllib.parse.urljoin(base_url + '/', seg)
            try:
                r = requests.get(full_url)
                r.raise_for_status()
                tmp_file = tempfile.NamedTemporaryFile(suffix=f"_chunk{chunk_id}.ts", delete=False)
                tmp_file.write(r.content)
                tmp_file.close()
                print(f"[CHUNK] Saved as {tmp_file.name}")
                chunk_files.append(tmp_file.name)
                chunk_id += 1
            except Exception as e:
                print(f"[ERROR] Failed to download segment {seg}: {e}")

    return chunk_files, segment_urls, chunk_id


def download_file(url):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    with open(tmp.name, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp.name


def assemble_fmp4_stream(base_url, init_filename, segment_filenames, output_filename):
    # Download init.mp4
    init_url = urllib.parse.urljoin(base_url + '/', init_filename)
    init_path = download_file(init_url)

    # Download .m4s segments
    segment_paths = []
    for seg in segment_filenames:
        seg_url = urllib.parse.urljoin(base_url + '/', seg)
        seg_path = download_file(seg_url)
        segment_paths.append(seg_path)

    # Combine binary data into one .mp4 file
    with open(output_filename, 'wb') as out_f:
        with open(init_path, 'rb') as f:
            out_f.write(f.read())
        for seg_path in segment_paths:
            with open(seg_path, 'rb') as f:
                out_f.write(f.read())

    # Cleanup temp files
    os.unlink(init_path)
    for p in segment_paths:
        os.unlink(p)
def extract_audio_segment(video_path, output_audio_path, start_time=0):
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ss", str(start_time),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
