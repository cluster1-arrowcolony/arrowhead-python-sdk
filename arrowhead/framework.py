"""Main Framework class for Arrowhead applications."""

import logging
import os
import ssl
import tempfile
from threading import Thread
from typing import Any, Callable, Dict, List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from flask import Flask, jsonify, request
from flask_cors import CORS

from .core.models import System, SystemRegistration
from .rpc.client import ArrowheadClient
from .rpc.config import Config, HTTPMethod
from .rpc.utils import build_orchestration_request
from .service import Params, Service

logger = logging.getLogger(__name__)


class Framework:
    """Main framework class for Arrowhead applications."""

    def __init__(self) -> None:
        """Initialize the Framework."""
        self.app = Flask(__name__)
        CORS(self.app)

        self.system_name: Optional[str] = None
        self.address: Optional[str] = None
        self.port: Optional[int] = None
        self.client: Optional[ArrowheadClient] = None
        self.server_thread: Optional[Thread] = None
        self.ssl_context: Optional[ssl.SSLContext] = None

        # Configure logging
        verbose = os.getenv("ARROWHEAD_VERBOSE", "false").lower()
        if verbose in ("true", "1"):
            logging.basicConfig(level=logging.DEBUG)
        elif verbose in ("false", "0"):
            logging.basicConfig(level=logging.WARNING)
            self.app.logger.setLevel(logging.WARNING)

    @classmethod
    def create_framework(cls) -> "Framework":
        """Create and configure a Framework instance from environment variables."""
        framework = cls()

        # Load configuration from environment
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
        """Setup TLS configuration for the Flask server."""
        # Load client certificate from PKCS#12
        with open(keystore_path, "rb") as f:
            p12_data = f.read()

        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
            p12_data, password.encode() if password else None
        )

        # Ensure we have valid key and certificate
        if private_key is None or cert is None:
            raise ValueError("Failed to load private key or certificate from keystore")

        # Create cert chain
        cert_chain = [cert]
        if additional_certs:
            cert_chain.extend(additional_certs)

        # Use secure temporary directory for SSL files
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_dir_path = self._temp_dir.name
        
        from pathlib import Path
        cert_path = Path(temp_dir_path) / "cert.pem" 
        key_path = Path(temp_dir_path) / "key.pem"

        # Write cert file
        with open(cert_path, "wb") as cert_file:
            for certificate in cert_chain:
                cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))

        # Write key file securely with restricted permissions
        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_fd = os.open(key_path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(key_fd, "wb") as key_file:
            key_file.write(key_bytes)

        # Create SSL context
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_context.load_cert_chain(str(cert_path), str(key_path))

        # Load CA certificates
        self.ssl_context.load_verify_locations(truststore_path)

    def handle_service(
        self,
        service: Service,
        http_method: HTTPMethod,
        service_definition: str,
        service_uri: str,
    ) -> None:
        """Register a service handler with the framework."""
        logger.debug(f"Registering service: {service_definition} at {service_uri}")

        # Create a unique function name for Flask endpoint
        safe_name = service_definition.replace("-", "_").replace("/", "_")
        endpoint_name = f"service_handler_{safe_name}_{id(service)}"

        def service_handler():
            """Flask route handler for the service."""
            try:
                # Extract query parameters (excluding token)
                query_params = {}
                token = None
                for key, value in request.args.items():
                    if key == "token":
                        token = value
                        # TODO: Verify token
                    else:
                        query_params[key] = value

                # Get request payload
                payload = request.get_data() if request.data else None

                # Create parameters object
                params = Params(query_params=query_params, payload=payload)

                # Call service handler
                response_data = service.handle_request(params)

                # Return response
                if isinstance(response_data, bytes):
                    return response_data.decode("utf-8")
                return str(response_data)

            except Exception as e:
                logger.error(f"Service handler error: {e}")
                return jsonify({"error": str(e)}), 400

        # Set a unique function name for Flask
        service_handler.__name__ = endpoint_name

        # Register with Flask based on HTTP method
        if http_method == HTTPMethod.GET:
            self.app.route(service_uri, methods=["GET"], endpoint=endpoint_name)(
                service_handler
            )
        elif http_method == HTTPMethod.POST:
            self.app.route(service_uri, methods=["POST"], endpoint=endpoint_name)(
                service_handler
            )
        elif http_method == HTTPMethod.PUT:
            self.app.route(service_uri, methods=["PUT"], endpoint=endpoint_name)(
                service_handler
            )
        elif http_method == HTTPMethod.DELETE:
            self.app.route(service_uri, methods=["DELETE"], endpoint=endpoint_name)(
                service_handler
            )

    def send_request(self, service_def: str, params: Optional[Params] = None) -> bytes:
        """Send a request to a service via orchestration."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        if params is None:
            params = Params.empty()

        # Build orchestration request
        orchestration_request = build_orchestration_request(
            self.system_name or "unknown",
            self.address or "localhost",
            self.port or 8080,
            service_def,
        )

        # Orchestrate
        orchestration_response = self.client.orchestrate(orchestration_request)

        if not orchestration_response.response:
            raise RuntimeError(f"Failed to send request to service: {service_def}")

        # Send request to the first matched service
        matched_service = orchestration_response.response[0]
        return self.client.send_request(
            matched_service, params.query_params, params.payload
        )

    def serve_forever(self) -> None:
        """Start the Flask server and block."""
        host = self.address or "0.0.0.0"
        port = self.port or 8080

        if self.ssl_context:
            logger.info(f"Starting HTTPS server on {host}:{port}")
            self.app.run(
                host=host,
                port=port,
                ssl_context=self.ssl_context,
                debug=False,
                threaded=True,
            )
        else:
            logger.info(f"Starting HTTP server on {host}:{port}")
            self.app.run(host=host, port=port, debug=False, threaded=True)

    def start_server(self) -> None:
        """Start the Flask server in a background thread."""
        if self.server_thread and self.server_thread.is_alive():
            logger.warning("Server is already running")
            return

        self.server_thread = Thread(target=self.serve_forever, daemon=True)
        self.server_thread.start()
        logger.info("Server started in background thread")

    def stop_server(self) -> None:
        """Stop the Flask server."""
        # Flask doesn't have a built-in way to stop gracefully
        # This would require additional implementation with werkzeug
        logger.warning("Server stop not implemented - use Ctrl+C to stop")

    def close(self) -> None:
        """Clean up resources."""
        if self.client:
            self.client.close()

        # Clean up temporary SSL directory
        if hasattr(self, "_temp_dir"):
            try:
                self._temp_dir.cleanup()
            except:
                pass
