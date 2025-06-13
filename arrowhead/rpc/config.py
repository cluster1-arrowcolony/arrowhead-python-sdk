"""Configuration for RPC client."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class HTTPMethod(IntEnum):
    """HTTP methods for service registration."""

    GET = 0
    POST = 1
    PUT = 2
    DELETE = 3

    def __str__(self) -> str:
        """Convert to string representation."""
        return {
            HTTPMethod.GET: "GET",
            HTTPMethod.POST: "POST",
            HTTPMethod.PUT: "PUT",
            HTTPMethod.DELETE: "DELETE",
        }[self]


@dataclass
class Config:
    """Configuration for Arrowhead RPC client."""

    tls: bool = True
    authorization_host: str = "c1-authorization"
    authorization_port: int = 8445
    service_registry_host: str = "c1-serviceregistry"
    service_registry_port: int = 8443
    orchestrator_host: str = "c1-orchestrator"
    orchestrator_port: int = 8441
    keystore_path: Optional[str] = None
    truststore_path: Optional[str] = None
    password: Optional[str] = None
    verify_ssl: bool = True
