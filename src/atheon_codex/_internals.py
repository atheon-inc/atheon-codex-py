from http import HTTPStatus

from httpx import Response

from ._utils import Err, Ok
from .exceptions import (
    APIException,
    BadRequestException,
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
    RateLimitException,
    UnauthorizedException,
    UnprocessableEntityException,
)


def _handle_common_3xx_4xx_5xx_status_code(
    status_code: int, response_text: str
) -> Ok[None] | Err[APIException]:
    match status_code:
        case HTTPStatus.BAD_REQUEST:
            return Err(
                error=BadRequestException(detail=f"Bad Request: {response_text}")
            )
        case HTTPStatus.UNAUTHORIZED:
            return Err(
                error=UnauthorizedException(detail=f"Unauthorized: {response_text}"),
            )
        case HTTPStatus.FORBIDDEN:
            return Err(
                error=ForbiddenException(detail=f"Forbidden: {response_text}"),
            )
        case HTTPStatus.NOT_FOUND:
            return Err(
                error=NotFoundException(detail=f"Not Found: {response_text}"),
            )
        case HTTPStatus.UNPROCESSABLE_ENTITY:
            return Err(
                error=UnprocessableEntityException(
                    detail=f"Unprocessable Entity: {response_text}"
                ),
            )
        case HTTPStatus.TOO_MANY_REQUESTS:
            return Err(
                error=RateLimitException(
                    detail=f"Rate Limit Exceeded: {response_text}"
                ),
            )
        case HTTPStatus.INTERNAL_SERVER_ERROR:
            return Err(
                error=InternalServerErrorException(
                    detail=f"Internal Server Error: {response_text}"
                ),
            )
        case _:
            return Err(
                error=APIException(
                    status_code=status_code,
                    detail=f"Unexpected Error: {response_text}",
                ),
            )


def _handle_response(response: Response) -> Ok[dict] | Err[APIException]:
    match response.status_code:
        case HTTPStatus.OK | HTTPStatus.CREATED | HTTPStatus.ACCEPTED:
            return Ok(value=response.json())
        case _:
            return _handle_common_3xx_4xx_5xx_status_code(
                response.status_code, response.text
            )
