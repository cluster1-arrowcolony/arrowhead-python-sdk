"""Main RPC client for Arrowhead Framework."""

import logging
import ssl
import shutil
import tempfile
from typing import Dict, Optional, Tuple

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from ..core.models import (MatchedService, OrchestrationRequest, OrchestrationResponse)
from .config import Config
from .management import ManagementAPI


logger = logging.getLogger(__name__)



class Client:
    """Main client for Arrowhead Framework communication."""

    config: Config
    _temp_dir: Optional[str]
    client: httpx.AsyncClient
    management: ManagementAPI

    def __init__(self, config: Config) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self._temp_dir: Optional[str] = None
        self.client = self._create_async_http_client()
        self.management = ManagementAPI(self)

    @staticmethod
    def setup_tls(keystore_path: str, password: Optional[str]) -> Tuple[str, str, str]:
        """
        Helper to extract certs from a PKCS#12 file into temporary PEM files.
        Returns a tuple of (temp_directory, cert_file_path, key_file_path).
        """
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

        temp_dir = tempfile.mkdtemp()
        from pathlib import Path
        cert_path = str(Path(temp_dir) / "cert.pem")
        key_path = str(Path(temp_dir) / "key.pem")

        with open(cert_path, "wb") as cert_file:
            for certificate in cert_chain:
                cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))

        with open(key_path, "wb") as key_file:
            key_file.write(private_key.private_bytes(serialization.Encoding.PEM,
                                                    serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()))

        return temp_dir, cert_path, key_path

    def _create_async_http_client(self) -> httpx.AsyncClient:
        """Create an async HTTP client with TLS configuration."""
        if not (self.config.keystore_path and self.config.truststore_path):
            raise ValueError("Keystore and truststore paths are required for TLS.")

        logger.debug("TLS enabled. Keystore: %s, Truststore: %s",
                    self.config.keystore_path,
                    self.config.truststore_path)
        
        self._temp_dir, cert_path, key_path = Client.setup_tls(self.config.keystore_path, self.config.keystore_password)
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=self.config.truststore_path)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        logger.debug("SSLContext created for httpx client with explicit cert chain.")

        return httpx.AsyncClient(verify=context, http2=True)

    def _build_url(self, service: str, path: str) -> str:
        """Build URL for a core service API."""
        if service == "serviceregistry":
            host = self.config.service_registry_host
            port = self.config.service_registry_port
        elif service == "orchestrator":
            host = self.config.orchestrator_host
            port = self.config.orchestrator_port
        elif service == "authorization":
            host = self.config.authorization_host
            port = self.config.authorization_port
        else:
            raise ValueError(f"Unknown core service: {service}")
        return f"https://{host}:{port}/{service}{path}"

    async def _make_request(
        self,
        method: str,
        url: str,
        expected_status: int = 200,
        error_msg: str = "Request failed",
        **kwargs,
    ) -> httpx.Response:
        """Make an async HTTP request with error handling."""
        logger.debug(f"Sending async {method} request to {url}")
        try:
            # We must set a timeout, otherwise requests can hang indefinitely.
            response = await self.client.request(method, url, timeout=10.0, **kwargs)
            if response.status_code != expected_status:
                logger.error(f"{error_msg}: {response.status_code} - {response.text}")
                # Try to parse and log a more specific error from the body if possible
                try:
                    error_json = response.json()
                    logger.error(f"Server error details: {error_json}")
                except Exception:
                    pass
                response.raise_for_status()
            return response
        except httpx.ConnectError as e:
            logger.error(f"Connection to {e.request.url} failed. Is the server running and accessible?")
            raise
        except httpx.RequestError as e:
            logger.error(f"{error_msg}: {e}")
            raise

    async def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """Request service orchestration."""
        url = self._build_url("orchestrator", "/orchestration")
        data = request.model_dump(by_alias=True)

        response = await self._make_request(
            "POST",
            url,
            error_msg="Failed to orchestrate",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        return OrchestrationResponse(**response.json())

    async def send_request(
        self,
        service: MatchedService,
        payload: Optional[bytes] = None,
        query_params: Dict[str, str] = {},
    ) -> bytes:
        """Send an async request to a matched service."""
        address = service.provider.address
        port = service.provider.port
        token = service.authorization_tokens.get("HTTP-SECURE-JSON")
        if not token:
            raise ValueError("No authorization token found")

        request_params = query_params.copy() if query_params else {}
        request_params["token"] = token
        
        method = service.metadata.get("http-method")
        if not method:
            raise ValueError("No HTTP method found in service metadata")
        
        response = await self._make_request(
            method,
            f"https://{address}:{port}{service.service_uri}",
            error_msg="Failed to send service request",
            params=request_params,
            content=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        return response.content

    async def aclose(self) -> None:
        """Asynchronously close the client and clean up resources."""
        await self.client.aclose()
        if self._temp_dir:
            try:
                shutil.rmtree(self._temp_dir)
            except OSError:
                pass
            self._temp_dir = None
        
    # Implement async context manager protocol
    async def __aenter__(self) -> "Client":
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del exc_type
        del exc_val
        del exc_tb
        await self.aclose()
