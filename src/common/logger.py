import logging
import sys

import structlog


def setup_logging():
    """
    Configures structured logging with rich console output.
    """
    if sys.stderr.isatty():
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        # JSON renderer for production/non-interactive
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog
    # This captures logs from other libraries (like google-adk if it uses stdlib logging)
    # and formats them with structlog
    if sys.stderr.isatty():
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stderr,
            level=logging.INFO,
        )


def get_logger(name=None):
    """
    Returns a configured structlog logger.
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
