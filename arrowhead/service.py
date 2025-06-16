"""Service interface and parameter classes for Arrowhead Framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Params:
    """Parameters for service requests."""

    query_params: Dict[str, str]
    payload: Optional[bytes] = None

    @classmethod
    def empty(cls) -> "Params":
        """Create empty parameters."""
        return cls(query_params={}, payload=None)


class Service(ABC):
    """Abstract base class for Arrowhead services."""

    @abstractmethod
    async def handle_request(self, params: Params) -> bytes:
        """Handle incoming service request.

        Args:
            params: Request parameters including query params and payload

        Returns:
            Response data as bytes

        Raises:
            Exception: If request handling fails
        """
        pass
