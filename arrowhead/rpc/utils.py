"""Utility functions for RPC operations."""

from typing import Dict, List, Optional

from ..core.models import (
    OrchestrationFlags,
    OrchestrationRequest,
    PreferredProvider,
    RequestedService,
    RequesterSystem,
)


def build_orchestration_request(
    system_name: str,
    address: str,
    port: int,
    service_definition: str,
    interface_requirements: Optional[List[str]] = None,
    security_requirements: Optional[List[str]] = None,
    metadata_requirements: Optional[Dict[str, str]] = None,
    preferred_providers: Optional[List[PreferredProvider]] = None,
    orchestration_flags: Optional[OrchestrationFlags] = None,
) -> OrchestrationRequest:
    """Build an orchestration request."""

    if interface_requirements is None:
        interface_requirements = ["HTTP-SECURE-JSON"]

    if security_requirements is None:
        security_requirements = ["TOKEN"]

    if metadata_requirements is None:
        metadata_requirements = {}

    if preferred_providers is None:
        preferred_providers = []

    if orchestration_flags is None:
        # This is the fix: set matchmaking and overrideStore to True
        # to match the Go implementation's behavior.
        orchestration_flags = OrchestrationFlags(
            matchmaking=True,
            overrideStore=True
        )

    requester_system = RequesterSystem(
        systemName=system_name, address=address, port=port
    )

    requested_service = RequestedService(
        interfaceRequirements=interface_requirements,
        securityRequirements=security_requirements,
        serviceDefinitionRequirement=service_definition,
        metadataRequirements=metadata_requirements,
    )

    return OrchestrationRequest(
        commands={},
        orchestrationFlags=orchestration_flags,
        preferredProviders=preferred_providers,
        qosRequirements={},
        requestedService=requested_service,
        requesterSystem=requester_system,
    )
