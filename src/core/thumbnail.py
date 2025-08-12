from moviepy.editor import VideoFileClip
from PIL import Image

def generate_thumbnail(video_path, thumbnail_path, time=2):
    with VideoFileClip(video_path) as clip:
        frame = clip.get_frame(time)
        img = Image.fromarray(frame)
        img.save(thumbnail_path)
