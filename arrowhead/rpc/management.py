"""Management API for Arrowhead Framework."""

import logging
from typing import TYPE_CHECKING, List

from ..core.models import (
    AddAuthorizationRequest,
    Authorization,
    AuthorizationsResponse,
    Service,
    ServicesResponse,
    System,
    SystemRegistration,
    SystemsResponse,
)
from .config import HTTPMethod

if TYPE_CHECKING:
    from .client import ArrowheadClient

logger = logging.getLogger(__name__)


class ManagementAPI:
    """Management API for administrative operations."""

    def __init__(self, client: "ArrowheadClient") -> None:
        """Initialize with client reference."""
        self.client = client

    def register_system(self, system_reg: SystemRegistration) -> System:
        """Register a system via management API."""
        url = self.client._build_service_registry_url("/mgmt/systems")
        data = system_reg.model_dump(by_alias=True)

        response = self.client._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register system",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return System(**response.json())

    def unregister_system(self, system: System) -> None:
        """Unregister a system by object."""
        self.unregister_system_by_id(system.id)

    def unregister_system_by_id(self, system_id: int) -> None:
        """Unregister a system by ID."""
        url = self.client._build_service_registry_url(f"/mgmt/systems/{system_id}")

        self.client._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister system",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    def get_systems(self) -> List[System]:
        """Get all registered systems."""
        url = self.client._build_service_registry_url(
            "/mgmt/systems?direction=ASC&sort_field=id"
        )

        response = self.client._make_request(
            "GET", url, error_msg="Failed to get systems", headers={"Accept": "*/*"}
        )

        systems_response = SystemsResponse(**response.json())
        return systems_response.systems

    def get_system_by_id(self, system_id: int) -> System:
        """Get system by ID."""
        url = self.client._build_service_registry_url(f"/mgmt/systems/{system_id}")

        response = self.client._make_request(
            "GET", url, error_msg="Failed to get system", headers={"Accept": "*/*"}
        )

        return System(**response.json())

    def get_system_by_name(self, system_name: str) -> System:
        """Get system by name."""
        systems = self.get_systems()

        for system in systems:
            if system.system_name == system_name:
                return system

        raise ValueError(f"System with name {system_name} not found")

    def register_service(
        self,
        system: System,
        http_method: HTTPMethod,
        service_definition: str,
        service_uri: str,
    ) -> Service:
        """Register a service via management API."""
        # Create provider system object
        from ..core.models import ProviderSystem, ServiceRegistrationRequest

        provider_system = ProviderSystem(
            systemName=system.system_name,
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

        url = self.client._build_service_registry_url("/mgmt")
        data = service_reg.model_dump(by_alias=True)

        response = self.client._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to register service",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        return Service(**response.json())

    def unregister_service(self, service_id: int) -> None:
        """Unregister service by ID."""
        url = self.client._build_service_registry_url(f"/mgmt/{service_id}")

        self.client._make_request(
            "DELETE",
            url,
            error_msg="Failed to unregister service",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    def get_services(self) -> List[Service]:
        """Get all registered services."""
        url = self.client._build_service_registry_url(
            "/mgmt?direction=ASC&sort_field=id"
        )

        response = self.client._make_request(
            "GET", url, error_msg="Failed to get services", headers={"Accept": "*/*"}
        )

        services_response = ServicesResponse(**response.json())
        return services_response.services

    def get_service_definition_ids_for_provider(
        self, provider_id: int, service_def: str
    ) -> List[int]:
        """Get service definition IDs for a provider."""
        services = self.get_services()

        service_definition_ids = []
        for service in services:
            if (
                service.provider.id == provider_id
                and service.service_definition.service_definition == service_def
            ):
                service_definition_ids.append(service.service_definition.id)

        return service_definition_ids

    def get_interface_ids_for_provider(self, provider_id: int) -> List[int]:
        """Get interface IDs for a provider."""
        services = self.get_services()

        interface_ids = []
        for service in services:
            if service.provider.id == provider_id:
                for interface in service.interfaces:
                    interface_ids.append(interface.id)
                break

        return interface_ids

    def get_service_by_id(self, service_id: int) -> Service:
        """Get service by ID."""
        url = self.client._build_service_registry_url(f"/mgmt/{service_id}")

        response = self.client._make_request(
            "GET", url, error_msg="Failed to get service", headers={"Accept": "*/*"}
        )

        return Service(**response.json())

    def add_authorization(
        self, consumer_name: str, provider_name: str, service_def: str
    ) -> Authorization:
        """Add authorization rule."""
        consumer = self.get_system_by_name(consumer_name)
        provider = self.get_system_by_name(provider_name)

        service_definition_ids = self.get_service_definition_ids_for_provider(
            provider.id, service_def
        )
        interface_ids = self.get_interface_ids_for_provider(provider.id)

        auth_req = AddAuthorizationRequest(
            consumerId=consumer.id,
            providerIds=[provider.id],
            serviceDefinitionIds=service_definition_ids,
            interfaceIds=interface_ids,
        )

        url = self.client._build_authorization_url("/mgmt/intracloud")
        data = auth_req.model_dump(by_alias=True)

        response = self.client._make_request(
            "POST",
            url,
            expected_status=201,
            error_msg="Failed to add authorization rule",
            json=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        auth_response = AuthorizationsResponse(**response.json())

        if not auth_response.authorizations:
            raise ValueError("Failed to add authorization rule")

        if len(auth_response.authorizations) > 1:
            raise ValueError("More than one authorization rule added")

        return auth_response.authorizations[0]

    def get_authorizations(self) -> List[Authorization]:
        """Get all authorization rules."""
        url = self.client._build_authorization_url(
            "/mgmt/intracloud?direction=ASC&sort_field=id"
        )

        response = self.client._make_request(
            "GET",
            url,
            error_msg="Failed to get authorizations",
            headers={"Accept": "application/json"},
        )

        auth_response = AuthorizationsResponse(**response.json())
        return auth_response.authorizations

    def remove_authorization(self, auth_id: int) -> None:
        """Remove authorization rule by ID."""
        url = self.client._build_authorization_url(f"/mgmt/intracloud/{auth_id}")

        self.client._make_request(
            "DELETE",
            url,
            error_msg="Failed to remove authorization rule",
            headers={"Accept": "application/json"},
        )
