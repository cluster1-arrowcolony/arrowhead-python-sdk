"""Main RPC client for Arrowhead Framework."""

import logging
import os
import tempfile
from typing import Dict, Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from ..core.models import (
    MatchedService,
    OrchestrationRequest,
    OrchestrationResponse,
)
from .config import Config
from .management import ManagementAPI


logger = logging.getLogger(__name__)


class ArrowheadClient:
    """Main client for Arrowhead Framework communication."""

    def __init__(self, config: Config) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self._temp_files = []
        self.client = self._create_async_http_client()
        self.management = ManagementAPI(self)

    def _create_async_http_client(self) -> httpx.AsyncClient:
        """Create an async HTTP client with TLS configuration."""
        if not self.config.tls:
            logger.debug("TLS disabled. Creating insecure httpx client.")
            return httpx.AsyncClient(verify=False)

        if not (self.config.keystore_path and self.config.truststore_path):
            raise ValueError("Keystore and truststore paths are required for TLS.")

        logger.debug(
            f"TLS enabled. Keystore: {self.config.keystore_path}, Truststore: {self.config.truststore_path}"
        )

        with open(self.config.keystore_path, "rb") as f:
            p12_data = f.read()

        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
            p12_data, self.config.password.encode() if self.config.password else None
        )

        if private_key is None or cert is None:
            raise ValueError("Failed to load private key or certificate from keystore")

        cert_chain = [cert]
        if additional_certs:
            cert_chain.extend(additional_certs)

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as cert_file:
            for certificate in cert_chain:
                cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))
            cert_path = cert_file.name
            self._temp_files.append(cert_path)

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".key") as key_file:
            key_file.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            key_path = key_file.name
            self._temp_files.append(key_path)

        certs = (cert_path, key_path)
        verify = self.config.truststore_path if self.config.verify_ssl else False

        return httpx.AsyncClient(cert=certs, verify=verify)

    def _build_url(self, service: str, path: str) -> str:
        """Build URL for a core service API."""
        protocol = "https" if self.config.tls else "http"
        if service == "serviceregistry":
            return f"{protocol}://{self.config.service_registry_host}:{self.config.service_registry_port}/serviceregistry{path}"
        elif service == "orchestrator":
            return f"{protocol}://{self.config.orchestrator_host}:{self.config.orchestrator_port}/orchestrator{path}"
        elif service == "authorization":
            return f"{protocol}://{self.config.authorization_host}:{self.config.authorization_port}/authorization{path}"
        raise ValueError(f"Unknown core service: {service}")

    async def _make_request(
        self,
        method: str,
        url: str,
        expected_status: int = 200,
        error_msg: str = "Request failed",
        **kwargs,
    ) -> httpx.Response:
        """Make an async HTTP request with error handling."""
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

    async def orchestrate(
        self, orchestration_req: OrchestrationRequest
    ) -> OrchestrationResponse:
        """Request service orchestration."""
        url = self._build_url("orchestrator", "/orchestration")
        data = orchestration_req.model_dump(by_alias=True)

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
        matched_service: MatchedService,
        query_params: Optional[Dict[str, str]] = None,
        payload: Optional[bytes] = None,
    ) -> bytes:
        """Send an async request to a matched service."""
        address = matched_service.provider.address
        port = matched_service.provider.port
        token = matched_service.authorization_tokens.get("HTTP-SECURE-JSON")
        if not token:
            raise ValueError("No authorization token found")

        protocol = "https" if self.config.tls else "http"
        base_url = f"{protocol}://{address}:{port}"
        
        request_params = query_params.copy() if query_params else {}
        request_params["token"] = token
        
        method = matched_service.metadata.get("http-method")
        if not method:
            raise ValueError("No HTTP method found in service metadata")

        logger.debug(f"Sending async {method} request to {base_url}{matched_service.service_uri}")
        
        response = await self._make_request(
            method,
            f"{base_url}{matched_service.service_uri}",
            error_msg="Failed to send service request",
            params=request_params,
            content=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        return response.content

    async def aclose(self) -> None:
        """Asynchronously close the client and clean up resources."""
        await self.client.aclose()
        for temp_file in self._temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
        self._temp_files.clear()
        
    # Implement async context manager protocol
    async def __aenter__(self) -> "ArrowheadClient":
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del exc_type
        del exc_val
        del exc_tb
        await self.aclose()
