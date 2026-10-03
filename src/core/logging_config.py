import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s [pid:%(process)d] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level=None):
    """
    Configure root logging for this process.

    Must be called in every process, including multiprocessing children: `spawn`
    starts a fresh interpreter, so a config applied in the parent is not inherited.

    StreamHandler.emit() flushes on every record, so output reaches supervisor's
    log immediately instead of sitting in the 8KB stdout block buffer that plain
    print() uses when stdout is a pipe.
    """
    global _configured
    if _configured:
        return logging.getLogger()

    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    # Replace any pre-existing handlers so records are not emitted twice.
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)

    # These libraries log a record per HTTP request at INFO; too noisy for a loop
    # that polls the HLS playlist once a second.
    for noisy in ("urllib3", "botocore", "boto3", "s3transfer", "openai", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    return root


def get_logger(name):
    """Return a module logger, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)
