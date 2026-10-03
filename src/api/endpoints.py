from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yaml
from pathlib import Path
import src.api.app_controller as app_controller
from src.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
CONFIG_PATH = Path('config/config.yaml')

class HighlightDetector(BaseModel):
    url: str
    job_id: str
    start: bool

@router.post("/detect_highlight")
async def detect_highlight_endpoint(detector: HighlightDetector):
    """
    Start or stop highlight detection.
    """
    try:
        if detector.start:
            logger.info("Start requested for job_id=%s url=%s", detector.job_id, detector.url)

            # config.yaml is written on start only. Writing it on every request,
            # including stops, mutated the job_id/stream_url that a starting
            # child was about to read.
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, 'r') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            config['stream_url'] = detector.url
            config['job_id'] = detector.job_id
            with open(CONFIG_PATH, 'w') as f:
                yaml.safe_dump(config, f)

            pid = app_controller.start_detection(detector.job_id, detector.url)
            return {"status": "Highlight detection started", "job_id": detector.job_id, "pid": pid}

        logger.info("Stop requested for job_id=%s", detector.job_id)
        stopped = app_controller.stop_detection(detector.job_id)
        if stopped:
            return {"status": "Highlight detection stopped", "job_id": detector.job_id}
        return {
            "status": "Highlight detection not running",
            "job_id": detector.job_id,
            "running_job_id": app_controller.get_running_job_id(),
        }

    except app_controller.JobConflictError as e:
        # 409 rather than evicting: a start for another job used to terminate the
        # live one, which is why jobs stopped without anyone calling stop.
        logger.warning("Start rejected for job_id=%s: %s", detector.job_id, e)
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e),
                "running_job_id": e.running_job_id,
                "requested_job_id": e.requested_job_id,
            },
        )
    except app_controller.DetectionStartError as e:
        # Distinct from a bad request: the worker failed to come up.
        logger.error("Detection failed to start for job_id=%s: %s", detector.job_id, e)
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("detect_highlight failed for job_id=%s", detector.job_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detection_status")
async def detection_status():
    """Which job, if any, detection is currently running for."""
    running_job_id = app_controller.get_running_job_id()
    return {
        "running": running_job_id is not None,
        "job_id": running_job_id,
        "pid": app_controller.process.pid if app_controller.process else None,
    }







# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from src.core.highlight_detector import main_loop
# import yaml
# from pathlib import Path
# import requests

# router = APIRouter()
# CONFIG_PATH = Path('config/config.yaml')

# class HighlightDetector(BaseModel):
#     url: str
#     job_id: str
#     start: bool

# @router.post("/detect_highlight")
# async def detect_highlight_endpoint(url: str, job_id: str, start: bool):
#     """
#     Endpoint to start highlight detection.
#     :param url: The URL of the livestream.
#     :param job_id: Unique identifier for the job.
#     :param start: Flag to start the detection process.
#     :return: Status message.
#     """
#     try:
#         if CONFIG_PATH.exists():
#             with open(CONFIG_PATH, 'r') as f:
#                 config = yaml.safe_load(f) or {}
#         else:
#             config = {}

#         config['stream_url'] = url
#         config['job_id'] = job_id

#         with open(CONFIG_PATH, 'w') as f:
#             yaml.safe_dump(config, f)

#         if start:
#             main_loop()
#             return {"status": "Highlight detection started", "job_id": job_id}
#         else:
#             return {"status": "Highlight detection stopped", "job_id": job_id}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

















    
# def send_callback_to_server(job_id: str, highlight_url: str, thumbnail_url: str, metadata_url: str):
#     callback_url = "http://13.212.112.213:3000/api/callback"
#     payload = {
#         "service": "highlights",
#         "jobId": job_id,
#         "status": "completed",
#         "data": {
#             "highlight_video": highlight_url,
#             "highlight_thumbnail": thumbnail_url,
#             "highlight_metadata": metadata_url
#         }
#     }
#     headers = {"Content-Type": "application/json"}
#     try:
#         response = requests.post(callback_url, json=payload, headers=headers)
#         response.raise_for_status()
#         print(f"Callback sent successfully for job_id: {job_id}")
#         print(f"Status Code: {response.status_code}")
#         print(f"Responce Body: {response.text}")
#     except requests.RequestException as e:
#         print(f"Failed to send callback for job_id {job_id}: {e}")
