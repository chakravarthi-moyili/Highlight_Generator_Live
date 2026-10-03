import os
from dotenv import load_dotenv
import yaml

load_dotenv(override=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/config.yaml')

with open(CONFIG_PATH, 'r') as f:
    config_yaml = yaml.safe_load(f)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME') or config_yaml.get('s3_bucket')
S3_REGION = os.getenv('S3_REGION') or config_yaml.get('s3_region', 'us-east-1')
S3_PREFIX = os.getenv('S3_PREFIX') or config_yaml.get('s3_prefix', 'live-highlights/generated')
CLOUDFRONT_URL = os.getenv('CLOUDFRONT_URL') or config_yaml.get('cloudfront_url', 'https://your-cloudfront-url.cloudfront.net')
STREAM_URL = config_yaml['stream_url']
JOB_ID = config_yaml['job_id']
CHUNK_DURATION = config_yaml['chunk_duration']
HIGHLIGHTS_DIR = config_yaml['highlights_dir']

os.makedirs(HIGHLIGHTS_DIR, exist_ok=True)
