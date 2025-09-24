import json
import logging
import os
import ssl
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Awaitable

import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse

from .rpc.model import OrchestrationRequest
from .http import Request, Response
from .rpc.client import Client
from .rpc.config import Config

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("ARROWHEAD_VERBOSE") == "1"


@dataclass
class Service:
    """Holds the configuration for a registered service endpoint."""
    handler: Callable[[Request], Awaitable[Response]] # The function that handles requests for this service
    method: str  # The HTTP method used for this service (GET, POST, etc.)
    endpoint: str  # The endpoint path for this service (e.g., "/my-service/endpoint")

class System:
    """
    Main class for Arrowhead applications.
    An instance of this class can act as both a service provider and a service consumer.
    """
    name: str  # Name of the system
    address: str  # Network address of the system
    port: int  # Network address and port of the system
    running: bool  # Flag to prevent registering services after system is started
    services: Dict[str, Service]  # Registry of service endpoints
    config: Optional[Config]  # Optional configuration
    client: Optional[Client]  # The Arrowhead client for orchestrating requests
    _main: Optional[Callable[[], Awaitable[None]]] # For the @system.main() decorator

    def __init__(
        self,
        name: Optional[str] = None,
        port: Optional[int] = None,
        address: Optional[str] = None,
        config: Optional[Config] = None
    ):
        name = name or os.getenv("ARROWHEAD_SYSTEM_NAME")

        if not name:
            raise ValueError("System name must be provided or set by ARROWHEAD_SYSTEM_NAME.")

        self.name = name
        self.port = int(port or os.getenv("ARROWHEAD_SYSTEM_PORT", "8080"))
        self.address = address or os.getenv("ARROWHEAD_SYSTEM_ADDRESS", "localhost")
        self.services = {}
        self._main = None
        self.running = False
        self.config = config
        self.client = None

    def service(self, name: str, method: str, endpoint: str) -> Callable:
        """Decorator to register a function as an Arrowhead service provider."""
        def decorator(handler: Callable) -> Callable:
            if self.running:
                raise RuntimeError("Cannot register new services after the server has started.")
            self.services[name] = Service(handler, method.upper(), endpoint)
            return handler
        return decorator

    def main(self) -> Callable:
        """Decorator to register a function as the main entry point for a consumer system."""
        def decorator(handler: Callable[[], Awaitable[None]]) -> Callable:
            if self._main:
                raise RuntimeError("A @system.main() handler has already been registered.")
            self._main = handler
            return handler
        return decorator

    def _app(self) -> FastAPI:
        """Internal method to configure all FastAPI routes from the service registry."""
        fastapi = FastAPI(docs_url=None, redoc_url=None)
        fastapi.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        for name, service in self.services.items():
            logger.debug(f"Building route for service '{name}' at {service.endpoint}")

            def _create_route_handler(service: Service) -> Callable:
                """Creates a handler for a specific service, correctly capturing it in a closure."""

                async def handler(fastapi_request: FastAPIRequest) -> FastAPIResponse:
                    try:
                        request = await Request.from_fastapi(fastapi_request, service.method)
                        response = await service.handler(request)
                        return response.into_fastapi()
                    except Exception as e:
                        logger.error(f"Handler for '{name}' failed: {e}", exc_info=True)
                        error_content = json.dumps({"error": "An internal server error occurred."})
                        return FastAPIResponse(content=error_content, status_code=500, media_type="application/json")

                return handler

            route_handler = _create_route_handler(service)
            fastapi.add_api_route(path=service.endpoint, endpoint=route_handler, methods=[service.method])
        return fastapi

    def _server(self) -> uvicorn.Server:
        """Internal method to create a Uvicorn server instance."""
        app = self._app()
        client = self._client()
        return uvicorn.Server(uvicorn.Config(
            app,
            host=self.address,
            port=self.port,
            log_level="info" if VERBOSE else "warning",
            ssl_keyfile=client.ssl_keyfile,
            ssl_certfile=client.ssl_certfile,
            ssl_ca_certs=client.config.truststore_path,
            ssl_cert_reqs=ssl.CERT_REQUIRED,
        ))

    def _client(self) -> Client:
        """Lazily creates and returns the Arrowhead client."""
        if not self.client:
            self.config = self.config or Config.load_from_env(privileged=False)
            self.client = Client(self.config)
        return self.client

    async def send(self, service_def: str, request: Request) -> Response:
        """
        Sends a request to another service.
        Performs orchestration, converts the Arrowhead Request to an HTTPX Request,
        sends it, and converts the HTTPX Response back to an Arrowhead Response.
        """
        client = self._client()

        orchestration_response = await client.orchestrate(OrchestrationRequest(self.name, self.address, self.port, service_def))
        if not orchestration_response.matches:
            raise RuntimeError(f"No providers found for service: {service_def}")

        service = orchestration_response.matches[0]
        token = service.authorization_tokens.get("HTTP-SECURE-JSON")
        if not token:
            raise ValueError("No authorization token found for service")

        method = service.metadata.get("http-method")
        if not method:
            raise ValueError("No HTTP method found in service metadata")
        
        url = f"https://{service.provider.address}:{service.provider.port}{service.service_uri}"

        httpx_request = request.into_httpx(method=method, url=url)
        httpx_request.url = httpx_request.url.copy_merge_params({"token": token})
        httpx_response = await client.send(httpx_request)

        return Response.from_httpx(httpx_response)


    def run(self) -> None:
        """Starts the Uvicorn server to listen for requests (Provider role)."""
        import asyncio
        self.running = True
        asyncio.run(self.arun())

    async def arun(self) -> None:
        """Starts the Uvicorn server to listen for requests (Provider role)."""
        if self._main and self.services:
            raise RuntimeError("@System.main(...) and @System.service(...) cannot be used at the same time.")
        if self._main:
            logger.info("Starting consumer system main function.")
            async with self:
                await self._main()
        elif self.services:
            logger.info(f"Starting server with mTLS on {self.address}:{self.port}")
            await self._server().serve()
        else:
            logger.warning("No services registered and no main function defined. Nothing to run.")

    async def aclose(self) -> None:
        """Clean up resources."""
        if self.client:
            await self.client.aclose()

    async def __aenter__(self) -> "System":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb
        await self.aclose()
