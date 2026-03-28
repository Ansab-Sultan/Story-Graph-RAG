"""Logging helpers and request correlation middleware."""

from __future__ import annotations

import logging
import warnings
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
_NOISY_LOGGERS = (
    "httpcore",
    "httpx",
    "huggingface_hub",
    "huggingface_hub.file_download",
    "huggingface_hub.utils._http",
    "neo4j.io",
    "neo4j.notifications",
    "neo4j.pool",
    "qdrant_client",
    "qdrant_client.http",
    "sentence_transformers",
    "transformers",
    "urllib3.connectionpool",
)
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def get_request_id() -> str:
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _set_logger_level(name: str, level: int) -> None:
    logger = logging.getLogger(name)
    logger.setLevel(level)


def _resolve_level(level: str | int, default: int = logging.INFO) -> int:
    if isinstance(level, int):
        return level
    return logging.getLevelNamesMapping().get(level.upper(), default)


def _configure_library_noise(verbose_third_party: bool, third_party_level: int) -> None:
    effective_level = logging.NOTSET if verbose_third_party else third_party_level
    for logger_name in _NOISY_LOGGERS:
        _set_logger_level(logger_name, effective_level)

    if verbose_third_party:
        return

    warnings.filterwarnings(
        "ignore",
        message=r"The class `HuggingFaceBgeEmbeddings` was deprecated in LangChain.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"You are sending unauthenticated requests to the HF Hub.*",
    )

    try:
        from transformers.utils import logging as transformers_logging

        transformers_logging.disable_progress_bar()
        transformers_logging.set_verbosity_error()
    except Exception:
        pass


def _configure_uvicorn_handlers(formatter: logging.Formatter) -> None:
    request_id_filter = RequestIdFilter()
    for logger_name in _UVICORN_LOGGERS:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if not any(isinstance(existing, RequestIdFilter) for existing in handler.filters):
                handler.addFilter(request_id_filter)
            handler.setFormatter(formatter)


def setup_logging(
    level: str = "INFO",
    third_party_level: str = "WARNING",
    verbose_third_party: bool = False,
) -> None:
    from rich.logging import RichHandler
    from rich.console import Console

    root_logger = logging.getLogger()
    if getattr(root_logger, "_story_graphrag_configured", False):
        return

    # Use a custom console for rich
    console = Console(force_terminal=True, width=140)
    
    root_logger.handlers.clear()
    
    # High-density Rich Handler
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_path=True,
    )
    handler.addFilter(RequestIdFilter())
    
    # Custom format for rich that includes request_id
    rich_formatter = logging.Formatter("req=%(request_id)s | %(message)s")
    handler.setFormatter(rich_formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(_resolve_level(level))
    logging.captureWarnings(True)
    _configure_library_noise(
        verbose_third_party=verbose_third_party,
        third_party_level=_resolve_level(third_party_level, default=logging.WARNING),
    )
    
    # Apply to uvicorn as well
    _configure_uvicorn_handlers(rich_formatter)
    root_logger._story_graphrag_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestContextMiddleware:
    """Attach a request id to all logs emitted during a request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("X-Request-ID", str(uuid4()))
        token = _request_id_ctx.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id_ctx.reset(token)
