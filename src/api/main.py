from fastapi import FastAPI
from src.api.endpoints import router
import uvicorn

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=7858, reload=True)