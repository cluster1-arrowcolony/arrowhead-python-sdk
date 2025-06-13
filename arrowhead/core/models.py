"""Core data models for the Arrowhead Framework."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SystemRegistration(BaseModel):
    """System registration request model."""

    address: str
    authentication_info: str = Field(alias="authenticationInfo")
    metadata: Dict[str, str] = {}
    port: int
    system_name: str = Field(alias="systemName")


class System(BaseModel):
    """Arrowhead system model."""

    id: int
    system_name: str = Field(alias="systemName")
    address: str
    port: int
    authentication_info: Optional[str] = Field(None, alias="authenticationInfo")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    metadata: Optional[Dict[str, str]] = None


class SystemsResponse(BaseModel):
    """Response containing multiple systems."""

    systems: List[System] = Field(alias="data")
    count: int


class ProviderSystem(BaseModel):
    """Provider system for service registration."""

    system_name: str = Field(alias="systemName")
    address: str
    port: int
    authentication_info: str = Field(alias="authenticationInfo")
    metadata: Optional[Dict[str, str]] = None


class ServiceDefinition(BaseModel):
    """Service definition model."""

    id: int
    service_definition: str = Field(alias="serviceDefinition")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class Provider(BaseModel):
    """Service provider model."""

    id: int
    system_name: str = Field(alias="systemName")
    address: str
    port: int
    authentication_info: str = Field(alias="authenticationInfo")
    metadata: Optional[Dict[str, str]] = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class Interface(BaseModel):
    """Service interface model."""

    id: int
    interface_name: str = Field(alias="interfaceName")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ServiceRegistrationRequest(BaseModel):
    """Service registration request model."""

    end_of_validity: str = Field(alias="endOfValidity")
    interfaces: List[str]
    metadata: Dict[str, str] = {}
    provider_system: ProviderSystem = Field(alias="providerSystem")
    secure: str
    service_definition: str = Field(alias="serviceDefinition")
    service_uri: str = Field(alias="serviceUri")
    version: str


class Service(BaseModel):
    """Service model."""

    id: int
    service_definition: ServiceDefinition = Field(alias="serviceDefinition")
    provider: Provider
    service_uri: str = Field(alias="serviceUri")
    secure: str
    version: int
    interfaces: List[Interface]
    metadata: Optional[Dict[str, str]] = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    end_of_validity: Optional[datetime] = Field(None, alias="endOfValidity")


class ServicesResponse(BaseModel):
    """Response containing multiple services."""

    services: List[Service] = Field(alias="data")
    count: int


class AddAuthorizationRequest(BaseModel):
    """Authorization request model."""

    consumer_id: int = Field(alias="consumerId")
    provider_ids: List[int] = Field(alias="providerIds")
    interface_ids: List[int] = Field(alias="interfaceIds")
    service_definition_ids: List[int] = Field(alias="serviceDefinitionIds")


class Authorization(BaseModel):
    """Authorization model."""

    id: int
    consumer_system: System = Field(alias="consumerSystem")
    provider_system: Provider = Field(alias="providerSystem")
    service_definition: ServiceDefinition = Field(alias="serviceDefinition")
    interfaces: List[Interface]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AuthorizationsResponse(BaseModel):
    """Response containing multiple authorizations."""

    authorizations: List[Authorization] = Field(alias="data")
    count: int


class RequesterSystem(BaseModel):
    """Requester system for orchestration."""

    system_name: str = Field(alias="systemName")
    address: str
    port: int
    authentication_info: Optional[str] = Field(None, alias="authenticationInfo")
    metadata: Optional[Dict[str, str]] = None


class OrchestrationFlags(BaseModel):
    """Orchestration flags."""

    only_preferred: bool = Field(False, alias="onlyPreferred")
    override_store: bool = Field(False, alias="overrideStore")
    external_service_request: bool = Field(False, alias="externalServiceRequest")
    enable_inter_cloud: bool = Field(False, alias="enableInterCloud")
    enable_qos: bool = Field(False, alias="enableQoS")
    matchmaking: bool = Field(False, alias="matchmaking")
    metadata_search: bool = Field(False, alias="metadataSearch")
    trigger_inter_cloud: bool = Field(False, alias="triggerInterCloud")
    ping_providers: bool = Field(False, alias="pingProviders")


class Cloud(BaseModel):
    """Cloud model."""

    authentication_info: str = Field(alias="authenticationInfo")
    gatekeeper_relay_ids: List[int] = Field(alias="gatekeeperRelayIds")
    gateway_relay_ids: List[int] = Field(alias="gatewayRelayIds")
    name: str
    neighbor: bool
    operator: str
    secure: bool


class PreferredProvider(BaseModel):
    """Preferred provider for orchestration."""

    provider_cloud: Cloud = Field(alias="providerCloud")
    provider_system: System = Field(alias="providerSystem")


class RequestedService(BaseModel):
    """Requested service for orchestration."""

    interface_requirements: List[str] = Field(alias="interfaceRequirements")
    max_version_requirement: Optional[int] = Field(None, alias="maxVersionRequirement")
    metadata_requirements: Dict[str, str] = Field(
        default_factory=dict, alias="metadataRequirements"
    )
    min_version_requirement: Optional[int] = Field(None, alias="minVersionRequirement")
    ping_providers: bool = Field(False, alias="pingProviders")
    security_requirements: List[str] = Field(alias="securityRequirements")
    service_definition_requirement: str = Field(alias="serviceDefinitionRequirement")
    version_requirement: Optional[int] = Field(None, alias="versionRequirement")


class OrchestrationRequest(BaseModel):
    """Orchestration request model."""

    commands: Dict[str, str] = {}
    orchestration_flags: OrchestrationFlags = Field(alias="orchestrationFlags")
    preferred_providers: List[PreferredProvider] = Field(
        default_factory=list, alias="preferredProviders"
    )
    qos_requirements: Dict[str, str] = Field(
        default_factory=dict, alias="qosRequirements"
    )
    requested_service: RequestedService = Field(alias="requestedService")
    requester_cloud: Optional[Cloud] = Field(None, alias="requesterCloud")
    requester_system: RequesterSystem = Field(alias="requesterSystem")


class MatchedService(BaseModel):
    """Matched service from orchestration."""

    provider: Provider
    service_definition: ServiceDefinition = Field(alias="service")
    service_uri: str = Field(alias="serviceUri")
    secure: str
    metadata: Dict[str, str] = {}
    interfaces: List[Interface]
    version: int
    authorization_tokens: Dict[str, str] = Field(
        default_factory=dict, alias="authorizationTokens"
    )
    warnings: List[str] = []


class OrchestrationResponse(BaseModel):
    """Orchestration response model."""

    response: List[MatchedService]
