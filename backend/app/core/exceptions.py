from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error that can be mapped to an HTTP response."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def to_http_exception(self) -> HTTPException:
        return HTTPException(status_code=self.status_code, detail=self.message)


class InvalidYouTubeURLError(AppError):
    def __init__(self, message: str = "Invalid YouTube URL.") -> None:
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class VideoNotFoundError(AppError):
    def __init__(self, message: str = "Video was not found, is private, or has been deleted.") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class TranscriptUnavailableError(AppError):
    def __init__(self, message: str = "A timestamped transcript is not available for this video.") -> None:
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class ExternalServiceError(AppError):
    def __init__(self, message: str = "An external service request failed.") -> None:
        super().__init__(message, status.HTTP_502_BAD_GATEWAY)


class YouTubeTimeoutError(ExternalServiceError):
    def __init__(self, message: str = "YouTube took too long to respond. Please try again.") -> None:
        super().__init__(message)
        self.status_code = status.HTTP_504_GATEWAY_TIMEOUT


class YouTubeQuotaError(ExternalServiceError):
    def __init__(self, message: str = "The YouTube API quota has been exceeded. Please try again later.") -> None:
        super().__init__(message)
        self.status_code = status.HTTP_429_TOO_MANY_REQUESTS


class DatabaseError(AppError):
    def __init__(self, message: str = "Unable to save video information. Please try again.") -> None:
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotFoundError(AppError):
    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, message: str = "That record already exists.") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)
