import signal
from multiprocessing import Event, Process
from src.core.logging_config import get_logger
from src.core.highlight_detector import main_loop

logger = get_logger(__name__)

# How long to wait after start() before deciding the child came up. The child
# loads the Whisper model before entering its loop, so this only confirms it did
# not die immediately (e.g. CUDA OOM) - it is not a readiness check.
STARTUP_GRACE_SECONDS = 3

# How long to wait for a graceful stop before escalating to SIGTERM. The loop
# now checks stop_event between chunks, but a pass already inside an S3 upload
# still needs room to unwind; 5s was too short and every single stop in the logs
# escalated to terminate().
GRACEFUL_STOP_SECONDS = 20

stop_event = Event()
process = None
current_job_id = None


class DetectionStartError(RuntimeError):
    """Raised when the detection process dies immediately after starting."""


class JobConflictError(RuntimeError):
    """Raised when a start is requested while a different job is still running."""

    def __init__(self, running_job_id, requested_job_id):
        self.running_job_id = running_job_id
        self.requested_job_id = requested_job_id
        super().__init__(
            f"Job {running_job_id} is already running; refusing to start "
            f"{requested_job_id}. Stop the running job first."
        )


def _run_main_loop(stop_event, job_id, stream_url):
    # Ignore SIGINT in child so parent handles it
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    main_loop(stop_event, job_id, stream_url)


def _reap():
    """
    Join an already-exited child so it does not linger as a zombie.

    stop_detection() only joins while is_alive() is true, so a child that crashed
    on its own was never reaped and stayed <defunct> until the server restarted.
    """
    global process, current_job_id
    if process is not None and not process.is_alive():
        process.join(timeout=1)
        process = None
        current_job_id = None


def get_running_job_id():
    """Return the job_id of the live detection process, or None."""
    _reap()
    return current_job_id


def start_detection(job_id, stream_url):
    """
    Start detection for `job_id`.

    Only one detection process runs at a time (each one holds a Whisper model on
    the GPU). A start for a *different* job used to silently terminate the
    running one, so jobs died without anyone calling stop; that now raises
    JobConflictError instead. Re-starting the job that is already running is a
    no-op, which makes client retries safe.
    """
    global process, stop_event, current_job_id
    _reap()

    if process and process.is_alive():
        if current_job_id == job_id:
            logger.info("Job %s is already running in process %s; no-op.", job_id, process.pid)
            return process.pid
        raise JobConflictError(current_job_id, job_id)

    stop_event.clear()
    # Passed as arguments rather than read from config/config.yaml in the child:
    # the API rewrites that file on every request, so a request landing during
    # the startup window made the child pick up another job's id and stream.
    process = Process(target=_run_main_loop, args=(stop_event, job_id, stream_url))
    process.start()
    current_job_id = job_id
    logger.info("Detection starting for job %s in process %s", job_id, process.pid)

    # Process.start() succeeding only means the fork happened. The child used to
    # die milliseconds later (CUDA OOM while loading Whisper) while the API still
    # reported success, so surface that instead of reporting a false start.
    process.join(timeout=STARTUP_GRACE_SECONDS)
    if not process.is_alive():
        exitcode = process.exitcode
        pid = process.pid
        _reap()
        raise DetectionStartError(
            f"Detection process {pid} for job {job_id} exited immediately with "
            f"code {exitcode}. See the stderr log for the traceback."
        )

    logger.info("Detection started for job %s in process %s", job_id, process.pid)
    return process.pid


def stop_detection(job_id=None):
    """
    Stop the running detection process.

    `job_id` scopes the stop to that job: a stop for a job that is not the one
    running is ignored. Without it the call used to kill whatever happened to be
    alive, so a stale or retried stop for a long-finished job terminated an
    unrelated healthy job. Pass None only to force a stop regardless of job
    (server shutdown).

    Returns True if a process was stopped.
    """
    global process, stop_event, current_job_id

    if not (process and process.is_alive()):
        _reap()
        logger.info("No detection process running.")
        return False

    if job_id is not None and job_id != current_job_id:
        logger.warning(
            "Ignoring stop for job %s: the running job is %s.", job_id, current_job_id
        )
        return False

    stopped_job_id = current_job_id
    logger.info("Stopping detection for job %s (pid %s)...", stopped_job_id, process.pid)
    stop_event.set()
    process.join(timeout=GRACEFUL_STOP_SECONDS)
    if process.is_alive():
        logger.warning("Process did not stop gracefully, terminating...")
        process.terminate()
        process.join()
    logger.info("Detection stopped for job %s.", stopped_job_id)
    process = None
    current_job_id = None
    return True
