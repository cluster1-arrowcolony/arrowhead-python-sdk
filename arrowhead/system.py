import json
import logging
import os
import ssl
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Awaitable

import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse

from .rpc.model import OrchestrationRequest
from .http import Request, Response
from .rpc.client import Client
from .rpc.config import Config

logger = logging.getLogger(__name__)


@dataclass
class Service:
    """Holds the configuration for a registered service endpoint."""
    handler: Callable[[Request], Awaitable[Response]] # The function that handles requests for this service
    name: str  # The service definition string (e.g., "my-service")
    method: str  # The HTTP method used for this service (GET, POST, etc.)
    endpoint: str  # The endpoint path for this service (e.g., "/my-service/endpoint")

class System:
    """
    Main class for Arrowhead applications.
    An instance of this class can act as both a service provider and a service consumer.
    """
    name: str  # Name of the system
    address: str  # Network address for the system
    port: int  # Network address and port for the system
    config: Config  # Configuration loaded from environment variables
    running: bool  # Flag to prevent registering services after server start
    services: List[Service]  # Registry of service endpoints
    ssl_certfile: str  # Path to the SSL certificate file
    ssl_keyfile: str  # Path to the SSL key file
    temp_dir: str  # Temporary directory for TLS setup
    client: Client  # The Arrowhead client for orchestrating requests
    _main: Optional[Callable[[], Awaitable[None]]] # For the @system.main() decorator

    def __init__(
        self,
        name: Optional[str],
        port: Optional[int],
        address: Optional[str],
        config: Optional[Config] = None
    ):
        name = name or os.getenv("ARROWHEAD_SYSTEM_NAME")

        if not name:
            raise ValueError("System name must be provided or set by ARROWHEAD_SYSTEM_NAME.")

        self.name = name
        self.port = int(port or os.getenv("ARROWHEAD_SYSTEM_PORT", "8080"))
        self.address = address or os.getenv("ARROWHEAD_SYSTEM_ADDRESS", "localhost")

        """Initializes a new System instance, loading configuration from environment variables."""
        self.app = FastAPI(docs_url=None, redoc_url=None)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.services: List[Service] = []
        self._main: Optional[Callable[[], Awaitable[None]]] = None
        self.running = False
        self.config = config or Config.load_from_env(privileged=False)
        self.temp_dir, self.ssl_certfile, self.ssl_keyfile = \
            Client.setup_tls(self.config.keystore_path, self.config.keystore_password)
        self.client = Client(self.config)

    def service(self, name: str, method: str, endpoint: str) -> Callable:
        """Decorator to register a function as an Arrowhead service provider."""
        def decorator(handler: Callable) -> Callable:
            if self.running:
                raise RuntimeError("Cannot register new services after the server has started.")
            self.services.append(Service(handler, name, method.upper(), endpoint))
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

    async def _build_routes(self) -> None:
        """Internal method to configure all FastAPI routes from the service registry."""
        for service in self.services:
            logger.debug(f"Building route for service '{service.name}' at {service.endpoint}")

            def _create_route_handler(service: Service) -> Callable:
                """Creates a handler for a specific service, correctly capturing it in a closure."""

                async def handler(fastapi_request: FastAPIRequest) -> FastAPIResponse:
                    try:
                        request = await Request.from_fastapi(fastapi_request, service.method)
                        response = await service.handler(request)
                        return response.into_fastapi()
                    except Exception as e:
                        logger.error(f"Handler for '{service.name}' failed: {e}", exc_info=True)
                        error_content = json.dumps({"error": "An internal server error occurred."})
                        return FastAPIResponse(content=error_content, status_code=500, media_type="application/json")

                return handler

            route_handler = _create_route_handler(service)
            self.app.add_api_route(path=service.endpoint, endpoint=route_handler, methods=[service.method])

    async def send_request(self, service_def: str, payload: Optional[bytes] = None, params: Dict[str, str] = {}) -> bytes:
        """Sends a request to another service. Performs an orchestration request to lookup the service provider."""
        request = OrchestrationRequest(self.name, self.address, self.port, service_def)
        response = await self.client.orchestrate(request)
        if not response.matches:
            raise RuntimeError(f"No providers found for service: {service_def}")
        matched_service = response.matches[0]
        return await self.client.send_request(matched_service, payload, params)


    def run(self, verbose: bool=False) -> None:
        """Starts the Uvicorn server to listen for requests (Provider role)."""
        import asyncio
        asyncio.run(self.arun(verbose))

    async def arun(self, verbose: bool=False) -> None:
        """Starts the Uvicorn server to listen for requests (Provider role)."""
        if self._main and self.services:
            raise RuntimeError("@System.main(...) and @System.service(...) cannot be used at the same time.")
        if self._main:
            logger.info("Starting consumer system main function.")
            async with self:
                await self._main()
        elif self.services:
            await self._build_routes()
            self.running = True
            verbose = verbose or os.getenv("ARROWHEAD_VERBOSE") == "1"
            logger.info(f"Starting server with mTLS on {self.address}:{self.port}")
            server = uvicorn.Server(uvicorn.Config(
                self.app,
                host=self.address,
                port=self.port,
                log_level="info" if verbose else "warning",
                ssl_keyfile=self.ssl_keyfile,
                ssl_certfile=self.ssl_certfile,
                ssl_ca_certs=self.config.truststore_path,
                ssl_cert_reqs=ssl.CERT_REQUIRED,
            ))
            await server.serve()
        else:
            logger.warning("No services registered and no main function defined. Nothing to run.")

    async def aclose(self) -> None:
        """Clean up resources."""
        if self.client:
            await self.client.aclose()
        if self.temp_dir:
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")

    async def __aenter__(self) -> "System":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb
        await self.aclose()
