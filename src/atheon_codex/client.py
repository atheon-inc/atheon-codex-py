from typing import Literal

import httpx

from ._internals import _handle_response
from ._utils import Result
from .exceptions import APIException
from .models import AtheonUnitCreateModel


class AtheonCodexClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.atheon.ad/v1",
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        if headers is None:
            headers = {}

        self.base_url = base_url
        self.headers = {
            "x-atheon-api-key": api_key,
            "Content-Type": "application/json",
            **headers,
        }
        self.kwargs = kwargs  # TODO: Come up with better name for this

    def _make_request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        endpoint: str,
        json_payload: dict | None = None,
        is_streaming_request: bool = False,
    ):
        with httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(timeout=45),
            **self.kwargs,
        ) as client:
            if is_streaming_request:
                match method:
                    case "GET":
                        with client.stream(
                            method,
                            endpoint,
                            headers={"Accept": "text/event-stream"},
                            timeout=httpx.Timeout(timeout=45),
                        ) as stream_response:
                            return _handle_response(
                                stream_response, is_streaming_response=True
                            )
                    case _:
                        return Result(
                            value=None,
                            error=APIException(
                                "Streaming requests only support GET method"
                            ),
                        )
            else:
                match method:
                    case "GET":
                        response = client.get(endpoint)
                    case "POST":
                        response = client.post(endpoint, json=json_payload)
                    case "PUT":
                        response = client.put(endpoint, json=json_payload)
                    case "DELETE":
                        if json_payload is not None:
                            response = client.request(
                                method, endpoint, json=json_payload
                            )
                        else:
                            response = client.delete(endpoint)

                return _handle_response(response)

    def create_atheon_unit(self, payload: AtheonUnitCreateModel):
        response = self._make_request(
            "POST",
            endpoint="/track-units/create",
            json_payload=payload.model_dump(mode="json"),
            is_streaming_request=False,
        )

        if response.error is not None:
            raise response.error

        return response.value
