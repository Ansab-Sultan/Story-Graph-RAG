"""Custom application errors and FastAPI exception wiring."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class StoryGraphError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "story_graphrag_error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class DuplicateFilenameError(StoryGraphError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "duplicate_filename"


class ActiveIngestionError(StoryGraphError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "active_ingestion"


class UnsupportedFileTypeError(StoryGraphError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "unsupported_file_type"


class StoryNotFoundError(StoryGraphError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "story_not_found"


class StoryNotReadyError(StoryGraphError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "story_not_ready"


class EmptyGraphResultError(StoryGraphError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "empty_graph_result"


class InfrastructureError(StoryGraphError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "infrastructure_error"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StoryGraphError)
    async def handle_story_graph_error(
        request: Request,
        exc: StoryGraphError,
    ) -> JSONResponse:
        logger.warning("Handled application error: %s", exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "error_code": "validation_error",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled application error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Unexpected internal server error",
                "error_code": "internal_server_error",
            },
        )
