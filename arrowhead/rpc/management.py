"""Management API for Arrowhead Framework."""

import logging
import os
from typing import TYPE_CHECKING, List, Optional

from ..core.models import (
    AddAuthorizationRequest,
    Authorization,
    AuthorizationsResponse,
    Service,
    ServiceRegistrationRequest,
    ServicesResponse,
    System,
    SystemRegistration,
    SystemsResponse,
)

if TYPE_CHECKING:
    from .client import Client

logger = logging.getLogger(__name__)


class ManagementAPI:
    """Management API for administrative operations."""

    client: "Client"  # A reference back to the main `Client` instance to perform the actual HTTP requests.
    _systems_cache: Optional[List[System]] = None  # A cache storing the list of systems to avoid redundant API calls
    _services_cache: Optional[List[Service]] = None  # A cache storing the list of services to avoid redundant API calls.

    def __init__(self, client: "Client") -> None:
        """Initialize with client reference."""
        self.client = client
        self._systems_cache: Optional[List[System]] = None
        self._services_cache: Optional[List[Service]] = None

    async def register_system(self, system_reg: SystemRegistration) -> System:
        """Register a system via management API."""
        url = self.client._build_url("serviceregistry", "/mgmt/systems")
        data = system_reg.model_dump(by_alias=True)

        response = await self.client._make_request(
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
        url = self.client._build_url("serviceregistry", f"/mgmt/systems/{system_id}")
        await self.client._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister system",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._systems_cache = None  # Invalidate cache

    async def get_systems(self) -> List[System]:
        """Get all registered systems."""
        if self._systems_cache is None:
            url = self.client._build_url("serviceregistry", "/mgmt/systems?direction=ASC&sort_field=id")
            response = await self.client._make_request("GET", url, error_msg="Failed to get systems", headers={"Accept": "*/*"})
            systems_response = SystemsResponse.model_validate(response.json())
            self._systems_cache = systems_response.systems
        return self._systems_cache

    async def get_system_by_id(self, system_id: int) -> System:
        """Get system by ID."""
        url = self.client._build_url("serviceregistry", f"/mgmt/systems/{system_id}")
        response = await self.client._make_request(
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
        from ..core.models import ProviderSystem

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

        url = self.client._build_url("serviceregistry", "/mgmt/services")
        data = service_reg.model_dump(by_alias=True)

        response = await self.client._make_request(
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
        url = self.client._build_url("serviceregistry", f"/mgmt/services/{service_id}")
        await self.client._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister service",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._services_cache = None

    async def get_services(self) -> List[Service]:
        """Get all registered services."""
        if self._services_cache is None:
            url = self.client._build_url("serviceregistry", "/mgmt/services?direction=ASC&sort_field=id")
            response = await self.client._make_request(
                "GET", url, error_msg="Failed to get services", headers={"Accept": "*/*"}
            )
            services_response = ServicesResponse.model_validate(response.json())
            self._services_cache = services_response.services
        return self._services_cache

    async def get_service_by_id(self, service_id: int) -> Service:
        """Get service by ID."""
        url = self.client._build_url("serviceregistry", f"/mgmt/services/{service_id}")
        response = await self.client._make_request(
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

        url = self.client._build_url("authorization", "/mgmt/intracloud")
        data = auth_req.model_dump(by_alias=True)

        response = await self.client._make_request(
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
        url = self.client._build_url("authorization", "/mgmt/intracloud?direction=ASC&sort_field=id")
        response = await self.client._make_request(
            "GET",
            url,
            error_msg="Failed to get authorizations",
            headers={"Accept": "application/json"},
        )
        auth_response = AuthorizationsResponse.model_validate(response.json())
        return auth_response.authorizations

    async def remove_authorization(self, auth_id: int) -> None:
        """Remove authorization rule by ID."""
        url = self.client._build_url("authorization", f"/mgmt/intracloud/{auth_id}")
        await self.client._make_request(
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
        from ..core.models import SystemRegistration
        from ..security.cert_manager import load_cert_manager, generate_subject_alternative_name

        config = self.client.config
        root_keystore = config.root_keystore_path
        root_alias = config.root_keystore_alias
        cloud_keystore = config.cloud_keystore_path
        cloud_alias = config.cloud_keystore_alias
        password = config.keystore_password
        
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

        cert_manager = load_cert_manager()
        cert_manager.create_system_keystore(
            root_keystore=root_keystore,
            root_alias=root_alias,
            cloud_keystore=cloud_keystore,
            cloud_alias=cloud_alias,
            system_keystore=system_keystore,
            system_dname=f"CN={name}",
            system_alias=name,
            san=generate_subject_alternative_name(name),
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
        url = self.client._build_url("serviceregistry", "/mgmt/systems/batch")
        data = [reg.model_dump(by_alias=True) for reg in system_regs]

        response = await self.client._make_request(
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
        url = self.client._build_url("serviceregistry", "/mgmt/services/batch")
        data = [reg.model_dump(by_alias=True) for reg in service_regs]

        response = await self.client._make_request(
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
        url = self.client._build_url("authorization", "/mgmt/intracloud/batch")
        data = [req.model_dump(by_alias=True) for req in auth_reqs]

        response = await self.client._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to batch add authorization rules",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        auth_response = AuthorizationsResponse.model_validate(response.json())
        return auth_response.authorizations
