import os
from fastapi import FastAPI
from src.api.endpoints import router
import uvicorn
from contextlib import asynccontextmanager
from src.api.app_controller import stop_detection
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# No custom SIGINT/SIGTERM handlers here. Uvicorn installs its own and unwinds the
# event loop cleanly; calling sys.exit(0) from a handler raised SystemExit inside
# the running loop, which surfaced as the SystemExit -> CancelledError traceback
# on every restart. The lifespan shutdown below already stops detection.


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    yield
    logger.info("Stopping application...")
    stop_detection()

app = FastAPI(lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    # reload=True is a development convenience: it runs an extra reloader process
    # and restarts the server on file changes. Off by default so it is not enabled
    # in deployment by accident; set RELOAD=true locally if you want it.
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7858")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )











# from fastapi import FastAPI
# from src.api.endpoints import router
# import uvicorn

# app = FastAPI()
# app.include_router(router)

# if __name__ == "__main__":
#     uvicorn.run("src.api.main:app", port=7858, reload=True)