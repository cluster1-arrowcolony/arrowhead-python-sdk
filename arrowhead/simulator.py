from collections import defaultdict
from types import CoroutineType
from typing import Any, Callable, Dict, List, Set
import functools

import httpx

from .http import Request, Response
from .system import System


class Simulator:
    """
    Manages end-to-end tests for multiple interacting Arrowhead systems.

    All system communication is done in-memory, instead of over the network.
    """
    systems: Dict[str, System]
    service_map: Dict[str, List[System]]
    original_send: Dict[str, Callable[..., CoroutineType[Any, Any, Response]]]
    clients: Dict[str, httpx.AsyncClient]
    crashed_systems: Set[str]
    partitions: Dict[str, Set[str]]

    def __init__(self, systems: List[System]):
        self.systems: Dict[str, System] = {s.name: s for s in systems}
        self.service_map: Dict[str, List[System]] = defaultdict(list)
        self.original_send: Dict[str, Callable[..., CoroutineType[Any, Any, Response]]] = {}
        self.clients: Dict[str, httpx.AsyncClient] = {}
        self.crashed_systems = set()
        self.partitions = defaultdict(set)

        for system in systems:
            if system.services:
                self.clients[system.name] = httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=system._app()),
                    base_url=f"https://{system.address}:{system.port}",
                    timeout=10.0
                )
            for name in system.services.keys():
                self.service_map[name].append(system)

    def crash(self, system: str) -> None:
        """Simulates a system node crashing. It will no longer respond to requests."""
        if system not in self.systems:
            raise ValueError(f"System '{system}' is not part of this simulation.")
        self.crashed_systems.add(system)

    def recover(self, system: str) -> None:
        """Recovers a previously crashed system."""
        self.crashed_systems.discard(system)
        
    def disconnect(self, system_a: str, system_b: str) -> None:
        """
        Creates a network partition between two systems.
        Communication will be blocked in both directions.
        """
        if system_a not in self.systems or system_b not in self.systems:
            raise ValueError("Both systems must be part of this simulation to create a partition.")
        self.partitions[system_a].add(system_b)
        self.partitions[system_b].add(system_a)

    def reconnect(self, system_a: str, system_b: str) -> None:
        """Removes a network partition, restoring connectivity."""
        self.partitions[system_a].discard(system_b)
        self.partitions[system_b].discard(system_a)

    async def send(self, service_name: str, request: Request) -> Response:
        """Sends a request to a service from the Simulator itself."""
        return await self._send("simulator", service_name, request)

    async def _send(self, consumer_name: str, service_name: str, request: Request) -> Response:
        """Finds providers and routes the request, checking for simulated faults."""
        providers = self.service_map.get(service_name)
        if not providers:
            raise RuntimeError(f"Simulator: No provider system registered for service '{service_name}'")

        provider = providers[0]
        
        if provider.name in self.crashed_systems:
            raise httpx.ConnectError(f"Simulated node crash: System '{provider.name}' is down.")
        
        if provider.name in self.partitions[consumer_name]:
            raise httpx.ConnectError(f"Simulated network partition between '{consumer_name}' and '{provider.name}'.")

        service = provider.services[service_name]
        assert service, "Service should exist for system"

        client = self.clients[provider.name]
        url = f"{client.base_url}{service.endpoint}"

        httpx_request = request.into_httpx(method=service.method, url=url)
        httpx_response = await client.send(httpx_request)
        httpx_response.raise_for_status()

        return Response.from_httpx(httpx_response)

    async def __aenter__(self) -> "Simulator":
        for name, system in self.systems.items():
            self.original_send[name] = system.send
            system.send = functools.partial(self._send, name)
        for system in self.systems.values():
            if system._main is not None:
                await system._main()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        del exc_type, exc_val, exc_tb
        # Restore original send methods to systems
        for name, system in self.systems.items():
            if name in self.original_send:
                system.send = self.original_send[name]
        # Close HTTP clients
        for client in self.clients.values():
            await client.aclose()
