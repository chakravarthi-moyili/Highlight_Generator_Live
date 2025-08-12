from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.core.highlight_detector import main_loop
import yaml
from pathlib import Path

router = APIRouter()
CONFIG_PATH = Path('config/config.yaml')

class HighlightDetector(BaseModel):
    url: str
    job_id: str
    start: bool

@router.post("/detect_highlight")
async def detect_highlight_endpoint(url: str, job_id: str, start: bool):
    """
    Endpoint to start highlight detection.
    :param url: The URL of the livestream.
    :param job_id: Unique identifier for the job.
    :param start: Flag to start the detection process.
    :return: Status message.
    """
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        config['stream_url'] = url
        config['job_id'] = job_id

        with open(CONFIG_PATH, 'w') as f:
            yaml.safe_dump(config, f)

        if start:
            main_loop()
            return {"status": "Highlight detection started", "job_id": job_id}
        else:
            return {"status": "Highlight detection stopped", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
