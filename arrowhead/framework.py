"""Main Framework class for Arrowhead applications."""

import logging
import os
import ssl
import tempfile
from typing import Optional

import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .rpc.client import ArrowheadClient
from .rpc.config import HTTPMethod
from .rpc.utils import build_orchestration_request
from .service import Params, Service

logger = logging.getLogger(__name__)


class Framework:
    """Main framework class for Arrowhead applications."""

    def __init__(self) -> None:
        """Initialize the Framework."""
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.system_name: Optional[str] = None
        self.address: Optional[str] = None
        self.port: Optional[int] = None
        self.client: Optional[ArrowheadClient] = None
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.ssl_keyfile: Optional[str] = None
        self.ssl_certfile: Optional[str] = None
        self.ssl_truststore: Optional[str] = None

        # Configure logging
        verbose = os.getenv("ARROWHEAD_VERBOSE", "false").lower()
        if verbose in ("true", "1"):
            logging.basicConfig(level=logging.DEBUG)
        elif verbose in ("false", "0"):
            logging.basicConfig(level=logging.WARNING)

    @classmethod
    def create_framework(cls) -> "Framework":
        """Create and configure a Framework instance from environment variables."""
        framework = cls()

        # Load configuration from environment
        from .rpc.config import Config
        config = Config(
            tls=os.getenv("ARROWHEAD_TLS", "true").lower() in ("true", "1"),
            authorization_host=os.getenv("ARROWHEAD_AUTHORIZATION_HOST", "c1-authorization"),
            authorization_port=int(os.getenv("ARROWHEAD_AUTHORIZATION_PORT", "8445")),
            service_registry_host=os.getenv(
                "ARROWHEAD_SERVICEREGISTRY_HOST", "c1-serviceregistry"
            ),
            service_registry_port=int(
                os.getenv("ARROWHEAD_SERVICEREGISTRY_PORT", "8443")
            ),
            orchestrator_host=os.getenv("ARROWHEAD_ORCHESTRATOR_HOST", "c1-orchestrator"),
            orchestrator_port=int(os.getenv("ARROWHEAD_ORCHESTRATOR_PORT", "8441")),
            keystore_path=os.getenv("ARROWHEAD_KEYSTORE_PATH"),
            truststore_path=os.getenv("ARROWHEAD_TRUSTSTORE"),
            password=os.getenv("ARROWHEAD_KEYSTORE_PASSWORD"),
        )

        framework.system_name = os.getenv("ARROWHEAD_SYSTEM_NAME")
        framework.address = os.getenv("ARROWHEAD_SYSTEM_ADDRESS", "localhost")
        framework.port = int(os.getenv("ARROWHEAD_SYSTEM_PORT", "8080"))

        logger.debug(f"Arrowhead configuration: {config}")

        # Create RPC client
        framework.client = ArrowheadClient(config)

        # Setup TLS if enabled
        if config.tls and config.keystore_path and config.truststore_path:
            framework._setup_tls(
                config.keystore_path, config.password, config.truststore_path
            )

        return framework

    def _setup_tls(
        self, keystore_path: str, password: Optional[str], truststore_path: str
    ) -> None:
        """Setup TLS configuration for the Uvicorn server."""
        with open(keystore_path, "rb") as f:
            p12_data = f.read()

        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
            p12_data, password.encode() if password else None
        )

        if private_key is None or cert is None:
            raise ValueError("Failed to load private key or certificate from keystore")

        cert_chain = [cert]
        if additional_certs:
            cert_chain.extend(additional_certs)

        self._temp_dir = tempfile.TemporaryDirectory()
        temp_dir_path = self._temp_dir.name
        
        from pathlib import Path
        self.ssl_certfile = str(Path(temp_dir_path) / "cert.pem")
        self.ssl_keyfile = str(Path(temp_dir_path) / "key.pem")
        self.ssl_truststore = truststore_path

        with open(self.ssl_certfile, "wb") as cert_file:
            for certificate in cert_chain:
                cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))

        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_fd = os.open(self.ssl_keyfile, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(key_fd, "wb") as key_file:
            key_file.write(key_bytes)

    def handle_service(
        self,
        service: Service,
        http_method: HTTPMethod,
        service_definition: str,
        service_uri: str,
    ) -> None:
        """Register a service handler with the framework."""
        logger.debug(f"Registering service: {service_definition} at {service_uri}")

        async def service_handler(request: Request):
            """FastAPI route handler for the service."""
            try:
                query_params = dict(request.query_params)
                if "token" in query_params:
                    # TODO: Verify token
                    del query_params["token"]

                payload = await request.body()
                params = Params(query_params=query_params, payload=payload if payload else None)
                
                # Await the async handler
                response_data = await service.handle_request(params)

                return Response(content=response_data, media_type="application/json")

            except Exception as e:
                logger.error(f"Service handler error: {e}", exc_info=True)
                return Response(content=f'{{"error": "{str(e)}"}}', status_code=500, media_type="application/json")

        self.app.add_api_route(
            path=service_uri,
            endpoint=service_handler,
            methods=[str(http_method)]
        )

    async def send_request(self, service_def: str, params: Optional[Params] = None) -> bytes:
        """Send a request to a service via orchestration (asynchronously)."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        if params is None:
            params = Params.empty()

        orchestration_request = build_orchestration_request(
            self.system_name or "unknown",
            self.address or "localhost",
            self.port or 8080,
            service_def,
        )

        orchestration_response = await self.client.orchestrate(orchestration_request)

        if not orchestration_response.response:
            raise RuntimeError(f"No providers found for service: {service_def}")

        matched_service = orchestration_response.response[0]
        # Use the async version of send_request
        return await self.client.send_request(
            matched_service, params.query_params, params.payload
        )

    def serve_forever(self) -> None:
        """Start the Uvicorn server and block."""
        host = self.address or "0.0.0.0"
        port = self.port or 8080

        uvicorn_config = uvicorn.Config(
            self.app, 
            host=host, 
            port=port,
            log_level="info",
        )

        if self.ssl_keyfile and self.ssl_certfile and self.ssl_truststore:
            logger.info(f"Starting HTTPS server with mTLS on {host}:{port}")
            uvicorn_config.ssl_keyfile = self.ssl_keyfile
            uvicorn_config.ssl_certfile = self.ssl_certfile
            
            # Use the truststore to verify client certificates
            uvicorn_config.ssl_ca_certs = self.ssl_truststore
            
            # Enforce that clients MUST present a valid certificate
            uvicorn_config.ssl_cert_reqs = ssl.CERT_REQUIRED
        else:
            logger.info(f"Starting HTTP server on {host}:{port}")

        server = uvicorn.Server(uvicorn_config)
        server.run()

    def start_server(self) -> None:
        """Uvicorn manages its own event loop and workers. 
        Directly calling serve_forever is the standard way.
        Running in a background thread is not the typical async pattern,
        but can be kept for compatibility if needed.
        """
        self.serve_forever()

    async def aclose(self) -> None: # <--- New async close method
        """Clean up resources asynchronously."""
        if self.client:
            await self.client.aclose()

        if hasattr(self, "_temp_dir"):
            try:
                self._temp_dir.cleanup()
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")
