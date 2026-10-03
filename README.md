# Highlight Generator Live

An automated video highlight detection system that processes live streams, transcribes audio using OpenAI's Whisper, identifies highlights using GPT, and stores them in cloud storage.

## Overview

This FastAPI-based application continuously monitors video streams, extracts audio in chunks, transcribes the content, and uses AI to automatically detect and save highlight clips. The generated highlights are uploaded to AWS S3 and made accessible via CloudFront.

### Key Features

- **Live Stream Processing**: Monitors and processes HLS/DASH streams in real-time
- **Audio Transcription**: Uses OpenAI's Whisper for accurate speech-to-text conversion
- **AI Highlight Detection**: Leverages GPT to intelligently identify highlight moments
- **Cloud Storage**: Automatically uploads highlights to AWS S3
- **Thumbnail Generation**: Creates preview images for each highlight
- **REST API**: Provides endpoints to start/stop detection and manage jobs
- **Callback Integration**: Sends highlight data back to external servers

## Quick Start

```bash
# 1. Clone and setup
git clone <repository-url>
cd Highlight_Generator_Live
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment
cp .env.example .env  # Edit with your credentials
# Edit config/config.yaml with your stream URL and S3 details

# 4. Run locally (Choose one option)

# Option A: Direct Python
python src/api/main.py

# Option B: Uvicorn with reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 7858

# Option C: Docker
docker-compose up -d

# 5. Verify
curl http://localhost:7858/docs
```

## Prerequisites

- Python 3.8+
- ffmpeg (for video/audio processing)
- Docker (optional, for containerized deployment)
- CUDA support (optional, for faster Whisper processing on GPU)
- AWS S3 credentials
- OpenAI API key

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Highlight_Generator_Live
```

### 2. Create a Virtual Environment

```bash
# Using venv
python -m venv venv

# Activate the virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html or use:
```bash
choco install ffmpeg
```

## Configuration

### 1. Set Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-api-key-here

# AWS S3 Configuration
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket-name
S3_REGION=us-east-1
S3_PREFIX=live-highlights/generated

# CloudFront Configuration
CLOUDFRONT_URL=https://your-cloudfront-url.cloudfront.net

# Application Configuration
PORT=7858
RELOAD=false

# Optional: Whisper Model
# Options: tiny, base, small, medium (default), large
WHISPER_MODEL=medium

# Optional: Callback Server
CALLBACK_SERVER_URL=https://your-callback-server.com/callback
```

**Note:** Keep your `.env` file secure. Never commit it to version control. Add `.env` to `.gitignore`.

### 2. Configure Stream Settings

Edit `config/config.yaml`:

```yaml
# Stream Processing
chunk_duration: 10  # Duration of each audio chunk in seconds
stream_url: https://your-stream-url.com/stream.m3u8

# Storage
highlights_dir: highlights  # Local directory for highlights
s3_bucket: your-bucket-name
s3_prefix: live-highlights/generated

# Job Management
job_id: unique-job-identifier

# Access
cloudfront_url: https://your-cloudfront-url.cloudfront.net
```

### 3. Configure Prompt Templates

Edit `src/gpt/prompt_templates.yaml` to customize how highlights are identified:

```yaml
highlight_detection:
  system_prompt: "Your system prompt for highlight detection..."
  user_template: "Template for user messages..."
```

## Project Structure

```
Highlight_Generator_Live/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
├── config/
│   └── config.yaml          # Application configuration
├── src/
│   ├── api/
│   │   ├── main.py          # FastAPI application
│   │   ├── endpoints.py      # API endpoints
│   │   ├── app_controller.py # Application logic
│   │   └── callback_api.py   # External callbacks
│   ├── core/
│   │   ├── highlight_detector.py   # Main detection logic
│   │   ├── process_video.py        # Video processing
│   │   ├── thumbnail.py            # Thumbnail generation
│   │   ├── config.py               # Config management
│   │   ├── logging_config.py       # Logging setup
│   │   └── __init__.py
│   ├── gpt/
│   │   ├── openai_client.py        # OpenAI API client
│   │   └── prompt_templates.yaml   # GPT prompts
│   └── utils/
│       └── s3_utils.py             # AWS S3 operations
└── highlights/              # Local highlight storage
```

## Usage

### Running Locally with Uvicorn

#### Development Mode (with Auto-reload)

```bash
# Activate virtual environment first
source venv/bin/activate

# Run with auto-reload on file changes
RELOAD=true python src/api/main.py
```

#### Using Uvicorn Directly (Recommended)

```bash
# Basic development server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 7858

# With custom workers (for production-like behavior)
uvicorn src.api.main:app --host 0.0.0.0 --port 7858 --workers 4

# With logging level
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 7858 --log-level info
```

#### Using Gunicorn + Uvicorn (Production-Ready)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:7858 \
  --access-logfile - \
  --error-logfile -
```

### Running with Docker

#### Option 1: Using Dockerfile (Build & Run)

**Create a `Dockerfile` in the project root:**

```dockerfile
FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 7858

# Set environment variables
ENV PORT=7858
ENV RELOAD=false

# Run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7858"]
```

**Build the Docker image:**

```bash
docker build -t highlight-generator:latest .
```

**Run the container:**

```bash
# Basic run
docker run -d \
  -p 7858:7858 \
  --env-file .env \
  --name highlight-generator \
  highlight-generator:latest

# With volume mounts for local development
docker run -d \
  -p 7858:7858 \
  --env-file .env \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/highlights:/app/highlights \
  --name highlight-generator \
  highlight-generator:latest

# With custom configuration
docker run -d \
  -p 7858:7858 \
  -e OPENAI_API_KEY=your-key \
  -e S3_ACCESS_KEY=your-access \
  -e S3_SECRET_KEY=your-secret \
  -e S3_BUCKET_NAME=your-bucket \
  -e CLOUDFRONT_URL=your-cloudfront-url \
  --name highlight-generator \
  highlight-generator:latest
```

#### Option 2: Using Docker Compose

**Create a `docker-compose.yml` file:**

```yaml
version: '3.8'

services:
  highlight-generator:
    build: .
    container_name: highlight-generator
    ports:
      - "7858:7858"
    environment:
      PORT: 7858
      RELOAD: "false"
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      S3_BUCKET_NAME: ${S3_BUCKET_NAME}
      S3_REGION: ${S3_REGION}
      S3_PREFIX: ${S3_PREFIX}
      CLOUDFRONT_URL: ${CLOUDFRONT_URL}
      WHISPER_MODEL: ${WHISPER_MODEL:-medium}
    volumes:
      - ./highlights:/app/highlights
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Run with Docker Compose:**

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f highlight-generator

# Stop the service
docker-compose down

# Rebuild the image
docker-compose up -d --build
```

#### Option 3: Development Docker Setup with Hot Reload

**Create a `Dockerfile.dev` file:**

```dockerfile
FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code (will be overridden by volume mount)
COPY . .

EXPOSE 7858

# Run with reload enabled for development
CMD ["uvicorn", "src.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "7858"]
```

**Run development container with volume mount:**

```bash
docker build -f Dockerfile.dev -t highlight-generator:dev .

docker run -d \
  -p 7858:7858 \
  --env-file .env \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/config:/app/config \
  --name highlight-generator-dev \
  highlight-generator:dev
```

### Useful Docker Commands

```bash
# Container Management
docker ps                           # List running containers
docker ps -a                        # List all containers
docker logs highlight-generator     # View container logs
docker logs -f highlight-generator  # Follow logs in real-time
docker stop highlight-generator     # Stop container
docker start highlight-generator    # Start container
docker restart highlight-generator  # Restart container
docker rm highlight-generator       # Remove container

# Image Management
docker images                       # List images
docker rmi highlight-generator      # Remove image
docker tag highlight-generator:latest highlight-generator:v1.0

# Debugging
docker exec -it highlight-generator bash  # Enter container shell
docker inspect highlight-generator        # View container details
docker stats highlight-generator          # View resource usage

# Docker Compose
docker-compose ps                   # List services
docker-compose logs -f              # Follow all service logs
docker-compose restart              # Restart all services
docker-compose pull                 # Update images
docker-compose up -d --build        # Rebuild and start
```

### Verifying the Application

```bash
# Check if API is running
curl http://localhost:7858/docs

# Check health endpoint
curl http://localhost:7858/ -v

# Test highlight detection endpoint
curl -X POST http://localhost:7858/detect_highlight \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/stream.m3u8","job_id":"test-123","start":true}'

# Check container logs (Docker)
docker logs highlight-generator
docker logs -f highlight-generator  # Follow logs
```

The API will be available at `http://localhost:7858`  
API documentation (Swagger UI) at `http://localhost:7858/docs`  
ReDoc documentation at `http://localhost:7858/redoc`

### API Endpoints

#### Start Highlight Detection

```bash
curl -X POST http://localhost:7858/detect_highlight \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://stream-url.com/stream.m3u8",
    "job_id": "unique-job-123",
    "start": true
  }'
```

**Response:**
```json
{
  "status": "Highlight detection started",
  "job_id": "unique-job-123",
  "pid": 12345
}
```

#### Stop Highlight Detection

```bash
curl -X POST http://localhost:7858/detect_highlight \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "unique-job-123",
    "start": false
  }'
```

**Response:**
```json
{
  "status": "Highlight detection stopped",
  "job_id": "unique-job-123"
}
```

## AWS S3 Setup

### 1. Create an S3 Bucket

```bash
aws s3 mb s3://your-bucket-name --region us-east-1
```

### 2. Create IAM User with S3 Access

1. Go to AWS IAM Console
2. Create a new user with programmatic access
3. Attach policy `AmazonS3FullAccess` (or more restrictive policy)
4. Save the Access Key ID and Secret Access Key
5. Update your `.env` file with these credentials

### 3. Optional: Set Up CloudFront Distribution

For efficient content delivery:

1. Create a CloudFront distribution pointing to your S3 bucket
2. Update `CLOUDFRONT_URL` in `.env`
3. Highlights will be accessible via CloudFront instead of direct S3 URLs

## Logging

Logs are written to:
- **Console**: Real-time application logs
- **File**: `mhighlights.log` (main process logs)
- **File**: `server.log` (API server logs)

Adjust logging level in `src/core/logging_config.py` or via environment variables.

## Troubleshooting

### Issue: "No module named 'moviepy'"

**Solution:**
```bash
pip install moviepy==1.0.3
```

### Issue: Whisper model not loading / CUDA out of memory

**Solution:** Use a smaller Whisper model:
```bash
WHISPER_MODEL=tiny python src/api/main.py
# or
WHISPER_MODEL=base python src/api/main.py
```

### Issue: S3 authentication errors

**Solution:** Verify credentials:
```bash
aws s3 ls --profile default  # Test with AWS CLI
```

Ensure IAM user has `s3:PutObject`, `s3:GetObject` permissions.

### Issue: Stream connection errors

**Solution:**
- Verify the stream URL is accessible and correct format (HLS/DASH)
- Check network connectivity to the stream source
- Verify `stream_url` in `config/config.yaml`

### Issue: Highlights not generating

**Solution:**
- Check OpenAI API key is valid and has sufficient credits
- Review logs for GPT API errors: `tail -f mhighlights.log`
- Verify Whisper transcription is working
- Check prompt templates in `src/gpt/prompt_templates.yaml`

## Performance Optimization

### 1. GPU Acceleration

Ensure CUDA is properly installed for Whisper:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. Model Selection

Balance speed vs. accuracy:
- `tiny`: Fastest, ~40x real-time
- `small`: Balanced, ~10x real-time
- `medium`: Slower, ~2x real-time (default)
- `large`: Slowest, ~0.5x real-time

### 3. Chunk Duration

Adjust `chunk_duration` in `config/config.yaml`:
- Smaller chunks: More responsive detection, higher API costs
- Larger chunks: Better context, lower API costs (default: 10 seconds)

## Development

### Running Tests

```bash
# Create test environment
python -m pytest tests/ -v
```

### Code Style

Follow PEP 8 conventions. Format code with:

```bash
black src/
```

### Git Workflow

1. Create feature branch: `git checkout -b feature/description`
2. Make changes and commit: `git commit -m "Description"`
3. Push and create PR: `git push origin feature/description`

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.8-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/api/main.py"]
```

Build and run:
```bash
docker build -t highlight-generator .
docker run -d -p 7858:7858 --env-file .env highlight-generator
```

### Production Checklist

- [ ] Set `RELOAD=false`
- [ ] Use a production-grade ASGI server (gunicorn + uvicorn)
- [ ] Set up log rotation
- [ ] Configure monitoring/alerting
- [ ] Use environment-specific configurations
- [ ] Secure API with authentication if exposed publicly
- [ ] Set up automated backups for local highlights
- [ ] Monitor S3 costs and implement lifecycle policies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with descriptive commits
4. Submit a pull request

## Support

For issues or questions:
1. Check logs: `tail -f mhighlights.log`
2. Review API responses for error details
3. Check AWS credentials and S3 permissions
4. Verify OpenAI API key and rate limits

## License

[Add your license here]

## Authors

- Development Team

## Changelog

See `CHANGELOG.md` for version history and updates.
