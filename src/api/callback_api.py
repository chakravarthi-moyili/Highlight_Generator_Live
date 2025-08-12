import requests
from fastapi import APIRouter, HTTPException

def send_callback_to_server(job_id: str, highlight_url: str, thumbnail_url: str, metadata_url: str):
    callback_url = "http://13.212.112.213:3000/api/callback"
    payload = {
        "service": "highlights",
        "jobId": job_id,
        "status": "completed",
        "data": {
            "highlight_video": highlight_url,
            "highlight_thumbnail": thumbnail_url,
            "highlight_metadata": metadata_url
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(callback_url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"Callback sent successfully for job_id: {job_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Responce Body: {response.text}")
    except requests.RequestException as e:
        print(f"Failed to send callback for job_id {job_id}: {e}")
