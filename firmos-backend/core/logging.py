"""Structured JSON logging via structlog."""
import logging

import structlog

from core.redaction import RedactingFilter, redact_log_event


def setup_logging() -> None:
    """Call once at app startup."""
    _install_redaction_filter()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_log_event,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _install_redaction_filter() -> None:
    loggers = [logging.getLogger()]
    loggers.extend(value for value in logging.Logger.manager.loggerDict.values() if isinstance(value, logging.Logger))
    for logger in loggers:
        for handler in logger.handlers:
            if not any(isinstance(item, RedactingFilter) for item in handler.filters):
                handler.addFilter(RedactingFilter())


log = structlog.get_logger()
