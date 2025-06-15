"""Main RPC client for Arrowhead Framework."""

import logging
from typing import Dict, Optional

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from ..core.models import (
    MatchedService,
    OrchestrationRequest,
    OrchestrationResponse,
    ProviderSystem,
    Service,
    ServiceRegistrationRequest,
    System,
    SystemRegistration,
)
from .config import Config, HTTPMethod
from .management import ManagementAPI

logger = logging.getLogger(__name__)


class ArrowheadClient:
    """Main client for Arrowhead Framework communication."""

    def __init__(self, config: Config) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self.session = self._create_http_session()
        self.management = ManagementAPI(self)

    def _create_http_session(self) -> requests.Session:
        """Create HTTP session with TLS configuration."""
        session = requests.Session()

        if self.config.tls:
            logger.debug(
                f"TLS enabled. Keystore: {self.config.keystore_path}, Truststore: {self.config.truststore_path}"
            )

            if self.config.keystore_path and self.config.truststore_path:
                # Load client certificate from PKCS#12
                with open(self.config.keystore_path, "rb") as f:
                    p12_data = f.read()

                private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
                    p12_data,
                    self.config.password.encode() if self.config.password else None,
                )

                # Ensure we have valid key and certificate
                if private_key is None or cert is None:
                    raise ValueError(
                        "Failed to load private key or certificate from keystore"
                    )

                # Create cert chain
                cert_chain = [cert]
                if additional_certs:
                    cert_chain.extend(additional_certs)

                # Save to temporary files for requests
                import os
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="wb", delete=False, suffix=".pem"
                ) as cert_file:
                    for certificate in cert_chain:
                        cert_file.write(
                            certificate.public_bytes(serialization.Encoding.PEM)
                        )
                    cert_path = cert_file.name

                with tempfile.NamedTemporaryFile(
                    mode="wb", delete=False, suffix=".key"
                ) as key_file:
                    key_file.write(
                        private_key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption(),
                        )
                    )
                    key_path = key_file.name

                session.cert = (cert_path, key_path)

                # Setup certificate verification - requests library handles PEM files directly
                if self.config.verify_ssl:
                    session.verify = self.config.truststore_path
                    logger.debug(f"CA certificate bundle: {self.config.truststore_path}")
                else:
                    session.verify = False
                    logger.warning(
                        "SSL certificate verification is DISABLED - this should only be used in development"
                    )

                # Log certificate setup
                logger.debug(f"Client certificate: {cert_path}")

                # Clean up temp files when session is closed
                def cleanup():
                    try:
                        os.unlink(cert_path)
                        os.unlink(key_path)
                    except:
                        pass

                session._cleanup = cleanup  # type: ignore
        else:
            logger.debug("TLS disabled")
            session.verify = False

        return session

    def _build_service_registry_url(self, path: str) -> str:
        """Build URL for service registry API."""
        protocol = "https" if self.config.tls else "http"
        return f"{protocol}://{self.config.service_registry_host}:{self.config.service_registry_port}/serviceregistry{path}"

    def _build_orchestrator_url(self, path: str) -> str:
        """Build URL for orchestrator API."""
        protocol = "https" if self.config.tls else "http"
        return f"{protocol}://{self.config.orchestrator_host}:{self.config.orchestrator_port}/orchestrator{path}"

    def _build_authorization_url(self, path: str) -> str:
        """Build URL for authorization API."""
        protocol = "https" if self.config.tls else "http"
        return f"{protocol}://{self.config.authorization_host}:{self.config.authorization_port}/authorization{path}"

    def _make_request(
        self,
        method: str,
        url: str,
        expected_status: int = 200,
        error_msg: str = "Request failed",
        **kwargs,
    ) -> requests.Response:
        """Make HTTP request with error handling."""
        try:
            response = self.session.request(method, url, **kwargs)

            if response.status_code != expected_status:
                logger.error(f"{error_msg}: {response.status_code} - {response.text}")
                response.raise_for_status()

            return response
        except requests.RequestException as e:
            logger.error(f"{error_msg}: {e}")
            raise

    def register_system(self, system_reg: SystemRegistration) -> System:
        """Register a system with the service registry."""
        url = self._build_service_registry_url("/register-system")
        data = system_reg.model_dump(by_alias=True)

        response = self._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register system",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return System(**response.json())

    def unregister_system(self, system: System) -> None:
        """Unregister a system from the service registry."""
        url = self._build_service_registry_url(
            f"/unregister-system?address={system.address}&port={system.port}&system_name={system.system_name}"
        )

        self._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister system",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    def register_service(
        self,
        system: System,
        http_method: HTTPMethod,
        service_definition: str,
        service_uri: str,
    ) -> Service:
        """Register a service with the service registry."""
        service_reg = ServiceRegistrationRequest(
            endOfValidity="",
            interfaces=["HTTP-SECURE-JSON"],
            metadata={"http-method": str(http_method)},
            providerSystem=ProviderSystem(
                systemName=system.system_name,
                address=system.address,
                port=system.port,
                authenticationInfo=system.authentication_info or "",
            ),
            secure="TOKEN",
            serviceDefinition=service_definition,
            serviceUri=service_uri,
            version="1",
        )

        url = self._build_service_registry_url("/register")
        data = service_reg.model_dump(by_alias=True)

        response = self._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register service",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return Service(**response.json())

    def unregister_service(
        self,
        system_name: str,
        service_uri: str,
        service_definition: str,
        address: str,
        port: int,
    ) -> None:
        """Unregister a service from the service registry."""
        url = self._build_service_registry_url(
            f"/unregister?system_name={system_name}&service_uri={service_uri}"
            f"&service_definition={service_definition}&address={address}&port={port}"
        )

        self._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister service",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    def orchestrate(
        self, orchestration_req: OrchestrationRequest
    ) -> OrchestrationResponse:
        """Request service orchestration."""
        url = self._build_orchestrator_url("/orchestration")
        data = orchestration_req.model_dump(by_alias=True)

        response = self._make_request(
            "POST",
            url,
            error_msg="Failed to orchestrate",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return OrchestrationResponse(**response.json())

    def send_request(
        self,
        matched_service: MatchedService,
        query_params: Optional[Dict[str, str]] = None,
        payload: Optional[bytes] = None,
    ) -> bytes:
        """Send request to a matched service."""
        address = matched_service.provider.address
        port = matched_service.provider.port

        token = matched_service.authorization_tokens.get("HTTP-SECURE-JSON")
        if not token:
            raise ValueError("No authorization token found")

        protocol = "https" if self.config.tls else "http"
        url = (
            f"{protocol}://{address}:{port}{matched_service.service_uri}?token={token}"
        )

        # Add query parameters
        if query_params:
            params = "&".join([f"{k}={v}" for k, v in query_params.items()])
            url += f"&{params}"

        method = matched_service.metadata.get("http-method")
        if not method:
            raise ValueError("No HTTP method found in service metadata")

        logger.debug(f"Sending {method} request to {url}")

        response = self._make_request(
            method,
            url,
            error_msg="Failed to send service request",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return response.content

    def close(self) -> None:
        """Close the client and clean up resources."""
        if hasattr(self.session, "_cleanup"):
            self.session._cleanup()  # type: ignore
        self.session.close()


# Re-export Config and HTTPMethod for convenience
from .config import Config, HTTPMethod
