"""
High-level decorator-based API for Arrowhead Framework providers.

This module provides a simple, decorator-based way to create Arrowhead service providers
without dealing with the underlying Framework complexity.
"""

import functools
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from .framework import Framework
from .rpc.config import HTTPMethod
from .service import Params, Service

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ServiceInfo:
    """Information about a registered service."""

    name: Optional[str]
    method: HTTPMethod
    endpoint: Optional[str]
    service_definition: str
    handler: Callable


class ArrowheadProvider:
    """Base class for Arrowhead providers using decorators."""

    def __init__(self, system_name: Optional[str] = None) -> None:
        """Initialize the provider.

        Args:
            system_name: Name of the Arrowhead system. If None, converts class name to kebab-case.
        """
        self.system_name = system_name or _camel_to_kebab(self.__class__.__name__)
        self.base_name = self.system_name
        self.services: List[ServiceInfo] = []
        self.framework: Optional[Framework] = None
        self._discover_services()

    def _discover_services(self) -> None:
        """Discover services marked with @service decorator."""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "_arrowhead_service_info"):
                service_info = attr._arrowhead_service_info

                # Generate endpoint if not explicitly provided
                if service_info.endpoint is None:
                    # Use provider name + function name: /carprovider/create-car
                    func_part = _snake_to_kebab(attr_name)
                    service_info.endpoint = f"/{self.system_name}/{func_part}"

                # Update handler to be bound method
                service_info.handler = attr
                self.services.append(service_info)
                logger.debug(
                    f"Discovered service: {service_info.service_definition} at {service_info.endpoint}"
                )

    def start(self) -> None:
        """Start the Arrowhead provider and register all services."""
        try:
            # Create framework
            self.framework = Framework.create_framework()
            
            # Override system name to match this decorator system
            self.framework.system_name = self.system_name

            # Register all discovered services
            for service_info in self.services:
                # Create a service wrapper
                service_wrapper = self._create_service_wrapper(service_info)

                assert (
                    service_info.endpoint is not None
                ), "Service info should be known at this point"

                # Register with framework
                self.framework.handle_service(
                    service_wrapper,
                    service_info.method,
                    service_info.service_definition,
                    service_info.endpoint,
                )

                logger.info(
                    f"Registered service: {service_info.service_definition} at {service_info.endpoint}"
                )

            logger.info(
                f"Provider '{self.system_name}' started with {len(self.services)} services"
            )

            # Start the server
            self.framework.serve_forever()

        except KeyboardInterrupt:
            logger.info("Provider stopped by user")
        except Exception as e:
            logger.error(f"Provider error: {e}")
            raise
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the provider and clean up resources."""
        if self.framework:
            self.framework.close()
            logger.info("Provider stopped")

    def send_request(
        self,
        service_definition: str,
        payload: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a request to another Arrowhead service.

        This allows providers to consume from other providers within their service handlers.

        Args:
            service_definition: Name of the service to call
            payload: Optional payload data to send
            query_params: Optional query parameters

        Returns:
            Response from the service as a dictionary

        Raises:
            RuntimeError: If framework is not initialized or request fails
        """
        if not self.framework:
            raise RuntimeError(
                "Framework not initialized. Cannot send requests before calling start()."
            )

        try:
            # Create params object
            params = Params(
                query_params=query_params or {},
                payload=json.dumps(payload).encode("utf-8") if payload else None,
            )

            # Send request via framework
            response_bytes = self.framework.send_request(service_definition, params)

            # Parse JSON response
            return json.loads(response_bytes.decode("utf-8"))

        except Exception as e:
            logger.error(f"Service request to '{service_definition}' failed: {e}")
            raise RuntimeError(
                f"Failed to send request to service '{service_definition}': {e}"
            )

    def _create_service_wrapper(self, service_info: ServiceInfo) -> Service:
        """Create a Service wrapper for the handler function."""

        class ServiceWrapper(Service):
            def __init__(self, handler: Callable[..., Any]) -> None:
                self.handler = handler

            def handle_request(self, params: Params) -> bytes:
                try:
                    # Parse payload if it exists
                    payload_data = {}
                    if params.payload:
                        try:
                            payload_data = json.loads(params.payload.decode("utf-8"))
                        except json.JSONDecodeError:
                            # If not JSON, wrap as raw data
                            payload_data = {"raw": params.payload.decode("utf-8")}

                    # Inspect the handler signature to determine how to call it
                    sig = inspect.signature(self.handler)
                    param_items = list(sig.parameters.items())

                    # Skip 'self' parameter
                    if param_items and param_items[0][0] == "self":
                        param_items = param_items[1:]

                    # Prepare available data
                    available_data = {
                        "payload": payload_data,
                        "query_params": params.query_params,
                        "params": params,  # Full Params object
                        "request_params": params.query_params,  # Alias for query_params
                        "data": payload_data,  # Alias for payload
                        "body": payload_data,  # Alias for payload
                        "query": params.query_params,  # Alias for query_params
                    }

                    # Build arguments based on parameter names and types
                    args = []
                    kwargs = {}

                    for param_name, param in param_items:
                        if param.kind == param.VAR_POSITIONAL:  # *args
                            # For *args, we don't add anything special
                            continue
                        elif param.kind == param.VAR_KEYWORD:  # **kwargs
                            # For **kwargs, we don't add anything special
                            continue
                        elif param.kind in (
                            param.POSITIONAL_ONLY,
                            param.POSITIONAL_OR_KEYWORD,
                            param.KEYWORD_ONLY,
                        ):
                            # Try to match parameter name to available data
                            if param_name in available_data:
                                if param.kind == param.KEYWORD_ONLY:
                                    kwargs[param_name] = available_data[param_name]
                                else:
                                    args.append(available_data[param_name])
                            else:
                                # Unknown parameter - use default if available
                                if param.default is not param.empty:
                                    if param.kind == param.KEYWORD_ONLY:
                                        kwargs[param_name] = param.default
                                    else:
                                        args.append(param.default)
                                else:
                                    # Required parameter we don't recognize
                                    logger.warning(
                                        f"Unknown required parameter '{param_name}' in service handler"
                                    )
                                    args.append(None)

                    # Call handler with determined arguments
                    if not param_items:
                        # No parameters except self
                        result = self.handler()
                    elif kwargs:
                        # Has keyword arguments
                        result = self.handler(*args, **kwargs)
                    else:
                        # Only positional arguments
                        result = self.handler(*args)

                    # Convert result to bytes
                    if isinstance(result, bytes):
                        return result
                    elif isinstance(result, str):
                        return result.encode("utf-8")
                    elif isinstance(result, (dict, list)):
                        return json.dumps(result).encode("utf-8")
                    else:
                        return str(result).encode("utf-8")

                except Exception as e:
                    logger.error(f"Service handler error: {e}")
                    error_response = {"error": str(e)}
                    return json.dumps(error_response).encode("utf-8")

        return ServiceWrapper(service_info.handler)


def system(
    cls_or_name: Optional[Union[Type[T], str]] = None,
) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """Decorator to mark a class as an Arrowhead system.

    Can be used with or without parentheses:
    - @system (without parentheses)
    - @system() (with empty parentheses)
    - @system("custom-name") (with custom name)

    Args:
        cls_or_name: Either a class (when used without parentheses) or a system name string.
                    If not provided, converts class name from CamelCase to kebab-case.

    Returns:
        Decorated class that inherits from ArrowheadProvider, or a decorator function.
    """

    def create_system_class(cls: Type[T], system_name: str) -> Type[T]:
        """Create the system class with the given name."""

        # Create a new class that inherits from both the original class and ArrowheadProvider
        class ProviderClass(cls, ArrowheadProvider):  # type: ignore
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                # Initialize the original class
                cls.__init__(self, *args, **kwargs)  # type: ignore
                # Initialize ArrowheadProvider with the determined name
                ArrowheadProvider.__init__(self, system_name)

        # Copy class attributes
        ProviderClass.__name__ = cls.__name__
        ProviderClass.__qualname__ = cls.__qualname__
        ProviderClass.__module__ = cls.__module__

        return ProviderClass  # type: ignore

    # Case 1: @system (used directly on class without parentheses)
    if cls_or_name is not None and isinstance(cls_or_name, type):
        cls = cls_or_name
        system_name = _camel_to_kebab(cls.__name__)
        return create_system_class(cls, system_name)

    # Case 2: @system() or @system("name") (used with parentheses)
    def decorator(cls: Type[T]) -> Type[T]:
        # Determine system name
        if isinstance(cls_or_name, str):
            system_name = cls_or_name
        else:
            system_name = _camel_to_kebab(cls.__name__)

        return create_system_class(cls, system_name)

    return decorator


def service(
    func_or_name: Optional[Union[Callable, str]] = None,
    method: Optional[Union[str, HTTPMethod]] = None,
    endpoint: Optional[str] = None,
) -> Union[Callable, Callable[[Any], Any]]:
    """Decorator to mark a method as an Arrowhead service.

    Can be used with or without parentheses:
    - @service (without parentheses)
    - @service() (with empty parentheses)
    - @service("custom-name") (with custom name)
    - @service(method="GET") (with specific options)

    Args:
        func_or_name: Either a function (when used without parentheses) or a service name string.
        method: HTTP method (GET, POST, PUT, DELETE). If not provided, auto-detects:
                - GET if function has no payload parameter
                - POST if function has payload parameter
        endpoint: Service endpoint path. If not provided, uses provider name + function name.

    Returns:
        Decorated function with service metadata, or a decorator function.
    """

    def create_service_wrapper(func: Any, service_name: Optional[str]) -> Any:
        """Create the service wrapper with the given name."""
        # Auto-detect HTTP method if not provided
        if method is None:
            detected_method = _detect_http_method(func)
        else:
            # Convert string method to HTTPMethod enum
            if isinstance(method, str):
                detected_method = {
                    "GET": HTTPMethod.GET,
                    "POST": HTTPMethod.POST,
                    "PUT": HTTPMethod.PUT,
                    "DELETE": HTTPMethod.DELETE,
                }.get(method.upper(), HTTPMethod.POST)
            else:
                detected_method = method

        # Generate service definition name from function name
        service_definition = service_name or _snake_to_kebab(func.__name__)

        # Store info for later endpoint generation (we need provider name)
        service_info = ServiceInfo(
            name=service_name,
            method=detected_method,
            endpoint=endpoint,  # Will be set later when we know provider name
            service_definition=service_definition,
            handler=func,  # Will be updated to bound method during discovery
        )

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Attach service info to the function
        wrapper._arrowhead_service_info = service_info  # type: ignore
        wrapper._arrowhead_endpoint_override = endpoint  # type: ignore

        return wrapper

    # Case 1: @service (used directly on function without parentheses)
    if func_or_name is not None and callable(func_or_name):
        func = func_or_name
        return create_service_wrapper(func, None)

    # Case 2: @service() or @service("name") or @service(method="GET") (used with parentheses)
    def decorator(func: Any) -> Any:
        # Determine service name
        if isinstance(func_or_name, str):
            service_name = func_or_name
        else:
            service_name = None

        return create_service_wrapper(func, service_name)

    return decorator


def _detect_http_method(func: Callable) -> HTTPMethod:
    """Auto-detect HTTP method based on function signature.

    Returns GET if function doesn't use payload, POST if it does.
    """
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    # Skip 'self' parameter
    if param_names and param_names[0] == "self":
        param_names = param_names[1:]

    # Check if function uses any payload-related parameters
    payload_params = {"payload", "data", "body"}
    has_payload = any(param_name in payload_params for param_name in param_names)

    if has_payload:
        return HTTPMethod.POST
    else:
        return HTTPMethod.GET


def _snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case."""
    return name.replace("_", "-")


def _camel_to_kebab(name: str) -> str:
    """Convert CamelCase to kebab-case."""
    import re

    # Insert hyphens before uppercase letters (except at start)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    # Insert hyphens before uppercase letters that follow lowercase letters
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()
