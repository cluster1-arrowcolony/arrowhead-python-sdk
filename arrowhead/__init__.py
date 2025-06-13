"""
Python SDK for the Arrowhead Framework.

The Arrowhead Framework is an Industrial IoT platform for service-oriented architecture.
This package provides both a Python SDK for developing Arrowhead-compatible applications
and a Python CLI tool for managing Arrowhead systems.
"""

# High-level decorator API
from .decorators import ArrowheadProvider, service, system
from .framework import Framework
from .service import Params, Service

__version__ = "0.1.0"
__all__ = ["Framework", "Service", "Params", "system", "service", "ArrowheadProvider"]
