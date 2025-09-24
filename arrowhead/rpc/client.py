"""Main RPC client for Arrowhead Framework."""

import logging
import ssl
import shutil
import tempfile
import os
from typing import Optional, List
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from arrowhead.security.cert_manager import CertManager

from .model import (AddAuthorizationRequest, Authorization, AuthorizationsResponse, OrchestrationRequest, OrchestrationResponse, ProviderSystem, ServiceRegistrationRequest, ServicesResponse, System, Service, SystemRegistration, SystemsResponse)
from .config import Config


logger = logging.getLogger(__name__)



class Client:
    """Main client for Arrowhead Framework communication."""

    config: Config
    _temp_dir: Optional[str]
    client: httpx.AsyncClient
    _systems_cache: Optional[List[System]] = None  # A cache storing the list of systems to avoid redundant API calls
    _services_cache: Optional[List[Service]] = None  # A cache storing the list of services to avoid redundant API calls.
    ssl_certfile: str
    ssl_keyfile: str

    def __init__(self, config: Config) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self._temp_dir: Optional[str] = None
        self._systems_cache: Optional[List[System]] = None
        self._services_cache: Optional[List[Service]] = None

        # Load keystore and truststore for TLS  
        with open(self.config.keystore_path, "rb") as f:
            p12_data = f.read()

        password = self.config.keystore_password.encode() if self.config.keystore_password else None
        pvkey, certificate, additional_certs = pkcs12.load_key_and_certificates(p12_data, password)

        if pvkey is None or certificate is None:
            raise ValueError("Failed to load private key or certificate from keystore")

        temp_dir = tempfile.mkdtemp()
        ssl_certfile = str(Path(temp_dir) / "cert.pem")
        ssl_keyfile = str(Path(temp_dir) / "key.pem")

        with open(ssl_certfile, "wb") as cert_file:
            for c in [certificate] + additional_certs:
                cert_file.write(c.public_bytes(serialization.Encoding.PEM))

        with open(ssl_keyfile, "wb") as key_file:
            key_file.write(pvkey.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        self._temp_dir = temp_dir
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile

        # Setup HTTP client with TLS
        if not (self.config.keystore_path and self.config.truststore_path):
            raise ValueError("Keystore and truststore paths are required for TLS.")

        logger.debug("TLS enabled. Keystore: %s, Truststore: %s",
                    self.config.keystore_path,
                    self.config.truststore_path)
        
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=self.config.truststore_path)
        context.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
        logger.debug("SSLContext created for httpx client with explicit cert chain.")

        self.client = httpx.AsyncClient(verify=context, http2=True, timeout=10.0)

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

    async def send(self, request: httpx.Request) -> httpx.Response:
        """
        Sends an HTTP request.
        """
        try:
            response = await self.client.send(request)
            response.raise_for_status()
            return response
        except httpx.ConnectError as e:
            logger.error(f"Connection to {e.request.url} failed. Is the server running and accessible?")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to send request: {e}")
            raise

    async def request(
        self,
        method: str,
        url: str,
        expected_status: int = 200,
        error_msg: str = "Request failed",
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with error handling."""
        logger.debug(f"Sending {method} request to {url}")
        try:
            response = await self.client.request(method, url, **kwargs)
            if response.status_code != expected_status:
                logger.error(f"{error_msg}: {response.status_code} - {response.text}")
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

        response = await self.request(
            "POST",
            url,
            error_msg="Failed to orchestrate",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        return OrchestrationResponse(**response.json())

    async def register_system(self, system_reg: SystemRegistration) -> System:
        """Register a system via management API."""
        url = self._build_url("serviceregistry", "/mgmt/systems")
        data = system_reg.model_dump(by_alias=True)

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register system",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        self._systems_cache = None
        return System.model_validate(response.json())

    async def unregister_system_by_id(self, system_id: int) -> None:
        """Unregister a system by ID."""
        url = self._build_url("serviceregistry", f"/mgmt/systems/{system_id}")
        await self.request(
            "DELETE",
            url,
            error_msg="Failed to unregister system",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._systems_cache = None  # Invalidate cache

    async def get_systems(self) -> List[System]:
        """Get all registered systems."""
        if self._systems_cache is None:
            url = self._build_url("serviceregistry", "/mgmt/systems?direction=ASC&sort_field=id")
            response = await self.request("GET", url, error_msg="Failed to get systems", headers={"Accept": "*/*"})
            systems_response = SystemsResponse.model_validate(response.json())
            self._systems_cache = systems_response.systems
        return self._systems_cache

    async def get_system_by_id(self, system_id: int) -> System:
        """Get system by ID."""
        url = self._build_url("serviceregistry", f"/mgmt/systems/{system_id}")
        response = await self.request(
            "GET", url, error_msg="Failed to get system", headers={"Accept": "*/*"}
        )

        return System.model_validate(response.json())

    async def get_system_by_name(self, name: str) -> System:
        """Get system by name."""
        systems = await self.get_systems()

        for system in systems:
            if system.name == name:
                return system
        
        raise ValueError(f"System with name {name} not found")

    async def register_service(
        self,
        system: System,
        http_method: str,
        service_definition: str,
        service_uri: str,
    ) -> Service:
        """Register a service via management API."""

        provider_system = ProviderSystem(
            systemName=system.name,
            address=system.address,
            port=system.port,
            authenticationInfo=system.authentication_info or "",
            metadata=system.metadata,
        )

        service_reg = ServiceRegistrationRequest(
            endOfValidity="",
            interfaces=["HTTP-SECURE-JSON"],
            metadata={"http-method": str(http_method)},
            providerSystem=provider_system,
            secure="TOKEN",
            serviceDefinition=service_definition,
            serviceUri=service_uri,
            version="1",
        )

        url = self._build_url("serviceregistry", "/mgmt/services")
        data = service_reg.model_dump(by_alias=True)

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register service",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._services_cache = None
        return Service.model_validate(response.json())

    async def unregister_service(self, service_id: int) -> None:
        """Unregister service by ID."""
        url = self._build_url("serviceregistry", f"/mgmt/services/{service_id}")
        await self.request(
            "DELETE",
            url,
            error_msg="Failed to unregister service",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._services_cache = None

    async def get_services(self) -> List[Service]:
        """Get all registered services."""
        if self._services_cache is None:
            url = self._build_url("serviceregistry", "/mgmt/services?direction=ASC&sort_field=id")
            response = await self.request(
                "GET", url, error_msg="Failed to get services", headers={"Accept": "*/*"}
            )
            services_response = ServicesResponse.model_validate(response.json())
            self._services_cache = services_response.services
        return self._services_cache

    async def get_service_by_id(self, service_id: int) -> Service:
        """Get service by ID."""
        url = self._build_url("serviceregistry", f"/mgmt/services/{service_id}")
        response = await self.request(
            "GET", url, error_msg="Failed to get service", headers={"Accept": "*/*"}
        )
        return Service.model_validate(response.json())

    async def get_service_definition_ids_for_provider(
        self, provider_id: int, service_def: str
    ) -> List[int]:
        """Get service definition IDs for a provider."""
        services = await self.get_services()
        service_definition_ids = []
        for service in services:
            if (
                service.provider.id == provider_id
                and service.service_definition.service_definition == service_def
            ):
                service_definition_ids.append(service.service_definition.id)
        return service_definition_ids

    async def get_interface_ids_for_provider(self, provider_id: int) -> List[int]:
        """Get interface IDs for a provider."""
        services = await self.get_services()
        interface_ids = []
        for service in services:
            if service.provider.id == provider_id:
                for interface in service.interfaces:
                    if interface.id not in interface_ids:
                        interface_ids.append(interface.id)
        return interface_ids

    async def add_authorization(
        self, consumer_name: str, provider_name: str, service_def: str
    ) -> Authorization:
        """Add authorization rule."""
        consumer = await self.get_system_by_name(consumer_name)
        provider = await self.get_system_by_name(provider_name)

        service_definition_ids = await self.get_service_definition_ids_for_provider(
            provider.id, service_def
        )
        if not service_definition_ids:
            raise ValueError(f"No service definition '{service_def}' found for provider '{provider_name}'")

        interface_ids = await self.get_interface_ids_for_provider(provider.id)
        if not interface_ids:
            raise ValueError(f"No interfaces found for provider '{provider_name}'")


        auth_req = AddAuthorizationRequest(
            consumerId=consumer.id,
            providerIds=[provider.id],
            serviceDefinitionIds=service_definition_ids,
            interfaceIds=interface_ids,
        )

        url = self._build_url("authorization", "/mgmt/intracloud")
        data = auth_req.model_dump(by_alias=True)

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to add authorization rule",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        auth_response = AuthorizationsResponse.model_validate(response.json())

        if not auth_response.authorizations:
            raise ValueError("Failed to add authorization rule: API returned empty list.")

        return auth_response.authorizations[0]

    async def get_authorizations(self) -> List[Authorization]:
        """Get all authorization rules."""
        url = self._build_url("authorization", "/mgmt/intracloud?direction=ASC&sort_field=id")
        response = await self.request(
            "GET",
            url,
            error_msg="Failed to get authorizations",
            headers={"Accept": "application/json"},
        )
        auth_response = AuthorizationsResponse.model_validate(response.json())
        return auth_response.authorizations

    async def remove_authorization(self, auth_id: int) -> None:
        """Remove authorization rule by ID."""
        url = self._build_url("authorization", f"/mgmt/intracloud/{auth_id}")
        await self.request(
            "DELETE",
            url,
            error_msg="Failed to remove authorization rule",
            headers={"Accept": "application/json"},
        )

    async def _create_and_register_system(
        self,
        name: str,
        address: str,
        port: int,
    ) -> System:
        """
        Private helper that performs the full cert generation and registration for one system.
        """
        root_keystore = self.config.root_keystore_path
        root_alias = self.config.root_keystore_alias
        cloud_keystore = self.config.cloud_keystore_path
        cloud_alias = self.config.cloud_keystore_alias
        password = self.config.keystore_password
        
        if not all([root_keystore, root_alias, cloud_keystore, cloud_alias, password]):
            raise ValueError("Missing required certificate configuration in environment for registration.")

        system_keystore = f"{name}.p12"
        if os.path.exists(system_keystore):
            logger.warning(f"Keystore {system_keystore} already exists, skipping certificate generation.")
            return await self.get_system_by_name(name)

        assert root_keystore
        assert root_alias
        assert cloud_keystore
        assert cloud_alias
        assert password

        cert_manager = CertManager()
        cert_manager.create_system_keystore(
            root_keystore=root_keystore,
            root_alias=root_alias,
            cloud_keystore=cloud_keystore,
            cloud_alias=cloud_alias,
            system_keystore=system_keystore,
            system_dname=f"CN={name}",
            system_alias=name,
            san=CertManager.generate_subject_alternative_name(name),
            password=password,
        )
        auth_info = cert_manager.get_public_key(system_keystore, password)

        system_reg = SystemRegistration(
            address=address,
            authenticationInfo=auth_info,
            port=port,
            systemName=name,
        )

        registered_system = await self.register_system(system_reg)
        
        env_content = f"""export ARROWHEAD_KEYSTORE_PATH=./{name}.p12
export ARROWHEAD_SYSTEM_NAME={name}
export ARROWHEAD_SYSTEM_ADDRESS={address}
export ARROWHEAD_SYSTEM_PORT={port}
"""
        with open(f"{name}.env", "w") as f:
            f.write(env_content)
        
        return registered_system

    async def register_systems_batch(self, system_regs: List["SystemRegistration"]) -> List[System]:
        """Register multiple systems in a single batch request."""
        url = self._build_url("serviceregistry", "/mgmt/systems/batch")
        data = [reg.model_dump(by_alias=True) for reg in system_regs]

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to batch register systems",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._systems_cache = None
        return [System.model_validate(item) for item in response.json()]

    async def register_services_batch(self, service_regs: List["ServiceRegistrationRequest"]) -> List[Service]:
        """Register multiple services in a single batch request."""
        url = self._build_url("serviceregistry", "/mgmt/services/batch")
        data = [reg.model_dump(by_alias=True) for reg in service_regs]

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to batch register services",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._services_cache = None
        return [Service.model_validate(item) for item in response.json()]

    async def add_authorizations_batch(self, auth_reqs: List["AddAuthorizationRequest"]) -> List[Authorization]:
        """Add multiple authorization rules in a single batch request."""
        url = self._build_url("authorization", "/mgmt/intracloud/batch")
        data = [req.model_dump(by_alias=True) for req in auth_reqs]

        response = await self.request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to batch add authorization rules",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        auth_response = AuthorizationsResponse.model_validate(response.json())
        return auth_response.authorizations

    async def aclose(self) -> None:
        """Asynchronously close the client and clean up resources."""
        await self.client.aclose()
        if self._temp_dir:
            try:
                shutil.rmtree(self._temp_dir)
            except OSError:
                pass
            self._temp_dir = None
        
    async def __aenter__(self) -> "Client":
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del exc_type
        del exc_val
        del exc_tb
        await self.aclose()
