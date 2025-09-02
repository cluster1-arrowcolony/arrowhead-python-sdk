import json

from dataclasses import dataclass
from typing import Any, Dict, Optional
from fastapi import Request as FastAPIRequest, Response as FastAPIResponse

@dataclass
class Request:
    """
    Represents an incoming request to a service handler.
    
    Attributes:
        payload: The raw request body as bytes.
        query_params: A dictionary of URL query parameters.
        path_params: A dictionary of URL path parameters.
        headers: A dictionary of request headers.
    """
    payload: Optional[bytes]
    query_params: Dict[str, str]
    path_params: Dict[str, Any]
    headers: Dict[str, str]

    @staticmethod
    async def from_fastapi(fastapi_request: FastAPIRequest, method: str) -> 'Request':
        """
        Converts a FastAPI request to an Arrowhead SDK Request.
        """
        return Request(
            payload=await fastapi_request.body() if method in ["POST", "PUT"] else None,
            query_params=dict(fastapi_request.query_params),
            path_params=dict(fastapi_request.path_params),
            headers=dict(fastapi_request.headers))

@dataclass
class Response:
    """
    Represents an outgoing response from a service handler.
    
    Args:
        content: The response body. Can be bytes, str, dict, or list.
        status_code: The HTTP status code for the response.
        media_type: The MIME type of the response. If None, it will be auto-detected.
    """
    content: Any
    status_code: int = 200
    media_type: Optional[str] = None

    def into_fastapi(self) -> FastAPIResponse:
        """
        Converts an Arrowhead SDK Response to a FastAPI Response.
        """
        if isinstance(self.content, (dict, list)):
            content = json.dumps(self.content).encode("utf-8")
            media_type = self.media_type or "application/json"
        elif isinstance(self.content, str):
            content = self.content.encode("utf-8")
            media_type = self.media_type or "text/plain"
        elif isinstance(self.content, bytes):
            content = self.content
            media_type = self.media_type or "application/octet-stream"
        else:
            content = str(self.content).encode("utf-8")
            media_type = self.media_type or "text/plain"

        return FastAPIResponse(content=content, status_code=self.status_code, media_type=media_type)

