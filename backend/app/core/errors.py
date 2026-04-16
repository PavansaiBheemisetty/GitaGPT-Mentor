from fastapi import HTTPException, status


class GitaGPTError(Exception):
    def __init__(self, message: str, *, cause: str | None = None, fix: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.fix = fix


def service_unavailable(message: str, *, cause: str, fix: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"message": message, "cause": cause, "fix": fix},
    )
