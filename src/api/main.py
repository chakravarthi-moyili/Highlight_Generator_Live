import signal
import sys
from fastapi import FastAPI
from src.api.endpoints import router
import uvicorn
from contextlib import asynccontextmanager
from src.api.app_controller import stop_detection

# Optional, for manual signals (won't fire in --reload mode)
def graceful_shutdown(signum, frame):
    print(f"Received signal {signum}, stopping detection...")
    stop_detection()
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting application...")
    yield
    print("Stopping application...")
    stop_detection()

app = FastAPI(lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=7858, reload=True)











# from fastapi import FastAPI
# from src.api.endpoints import router
# import uvicorn

# app = FastAPI()
# app.include_router(router)

# if __name__ == "__main__":
#     uvicorn.run("src.api.main:app", port=7858, reload=True)