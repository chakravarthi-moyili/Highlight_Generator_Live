import requests
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Without a timeout a hung callback endpoint blocks the detection loop forever.
CALLBACK_TIMEOUT_SECONDS = 30


def send_callback_to_server(job_id: str, highlight_data: list):
    # callback_url = "http://13.212.112.213:3000/api/callback"
    callback_url = "http://multiviewbackend.apisaranyu.in/api/callback"
    payload = {
        "service": "highlights",
        "jobId": job_id,
        "status": "completed",
        "data": {
            "highlights": highlight_data
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            callback_url, json=payload, headers=headers, timeout=CALLBACK_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        logger.info("Callback sent successfully for job_id: %s", job_id)
        logger.info("Status Code: %s", response.status_code)
        logger.info("Response Body: %s", response.text)
    except requests.RequestException as e:
        logger.error("Failed to send callback for job_id %s: %s", job_id, e)
