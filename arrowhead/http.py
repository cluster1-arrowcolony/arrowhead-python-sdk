import json

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from fastapi import Request as FastAPIRequest, Response as FastAPIResponse
from httpx import Response as HttpxResponse, Request as HttpxRequest

@dataclass
class Request:
    """
    Represents an incoming request to a service handler.
    
    Attributes:
        payload: The request body. For outgoing requests, this can be a dict,
                 list, str, or bytes. For incoming requests, the framework
                 will automatically parse a JSON body into a dict or list,
                 otherwise it will be bytes.
        query_params: A dictionary of URL query parameters.
        path_params: A dictionary of URL path parameters.
        headers: A dictionary of request headers.
    """
    payload: Any = None
    query_params: Dict[str, str] = field(default_factory=dict)
    path_params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    async def from_fastapi(fastapi_request: FastAPIRequest, method: str) -> 'Request':
        """
        Converts a FastAPI request to an Arrowhead SDK Request.
        Automatically parses JSON payloads.
        """
        payload = None
        if method in ["POST", "PUT"]:
            content_type = fastapi_request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    payload = await fastapi_request.json()
                except json.JSONDecodeError:
                    payload = await fastapi_request.body()
            else:
                payload = await fastapi_request.body()

        return Request(
            payload=payload,
            query_params=dict(fastapi_request.query_params),
            path_params=dict(fastapi_request.path_params),
            headers=dict(fastapi_request.headers))

    def into_httpx(self, method: str, url: str) -> HttpxRequest:
        """
        Converts this Arrowhead Request into a transport-specific httpx.Request object.
        """
        headers = self.headers.copy()
        content_bytes = None

        if isinstance(self.payload, (dict, list)):
            content_bytes = json.dumps(self.payload).encode("utf-8")
            if 'Content-Type' not in headers:
                headers['Content-Type'] = "application/json"
        elif isinstance(self.payload, str):
            content_bytes = self.payload.encode("utf-8")
            if 'Content-Type' not in headers:
                headers['Content-Type'] = "text/plain"
        elif isinstance(self.payload, bytes):
            content_bytes = self.payload
            if 'Content-Type' not in headers:
                headers['Content-Type'] = "application/octet-stream"
        elif self.payload is not None:
            content_bytes = str(self.payload).encode("utf-8")
            if 'Content-Type' not in headers:
                headers['Content-Type'] = "text/plain"

        return HttpxRequest(
            method,
            url,
            content=content_bytes,
            params=self.query_params,
            headers=headers
        )

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
    headers: Dict[str, str] = field(default_factory=dict)

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

        return FastAPIResponse(content=content, status_code=self.status_code, media_type=media_type, headers=self.headers)

    @staticmethod
    def from_httpx(response: HttpxResponse) -> "Response":
        """
        Creates an Arrowhead SDK Response from an httpx.Response.
        Automatically parses JSON content.
        """
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                content = response.json()
            except json.JSONDecodeError:
                # Fallback for empty or invalid JSON body
                content = response.content
        else:
            content = response.content

        return Response(
            content=content,
            status_code=response.status_code,
            media_type=content_type,
            headers=dict(response.headers)
        )
