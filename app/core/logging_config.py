import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings


def setup_logging() -> None:
    """Initialize sweeping logging configuration for the app."""
    # Create logs directory if not exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Filename with daily rotation format (e.g. app-20260417.log)
    date_str = datetime.now().strftime("%Y%m%d")
    log_filename = os.path.join(log_dir, f"app-{date_str}.log")

    # Get log level from env config, defaults to INFO
    log_level_str = getattr(settings, "log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 2. File Handler (Rotates every midnight)
    file_handler = TimedRotatingFileHandler(
        log_filename, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Setup the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Lower third-party spam
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info(f"Application logging setup complete at {log_level_str} level. Output: {log_filename}")
