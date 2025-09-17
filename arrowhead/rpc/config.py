"""Configuration for RPC client."""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration for Arrowhead RPC client."""

    authorization_host: str # Host for the Arrowhead Authorization Service
    authorization_port: int # Port for the Arrowhead Authorization Service
    service_registry_host: str # Host for the Arrowhead Service Registry
    service_registry_port: int # Port for the Arrowhead Service Registry
    orchestrator_host: str # Host for the Arrowhead Orchestrator
    orchestrator_port: int # Port for the Arrowhead Orchestrator
    keystore_path: str # Path to the keystore for client authentication
    keystore_password: str # Password for the keystore
    truststore_path: str # Path to the truststore for server certificate validation

    # The following fields are only required for `arrowhead certs gen` and `arrowhead systems register`
    root_keystore_path: Optional[str] # Path to the root keystore for certificate management
    root_keystore_alias: Optional[str] # Alias for the root keystore
    cloud_keystore_path: Optional[str] # Path to the cloud keystore for cloud services
    cloud_keystore_alias: Optional[str] # Alias for the cloud keystore

    @staticmethod
    def load_from_env(privileged: bool = False) -> "Config":
        """
        Load configuration from environment variables.

        Args:
            privileged: If True, uses the sysop keystore for management tasks.
        """

        return Config(
            authorization_host=read("ARROWHEAD_AUTHORIZATION_HOST", "localhost"),
            authorization_port=int(read("ARROWHEAD_AUTHORIZATION_PORT", "8443")),
            service_registry_host=read( "ARROWHEAD_SERVICEREGISTRY_HOST", "localhost"),
            service_registry_port=int(read("ARROWHEAD_SERVICEREGISTRY_PORT", "8443")),
            orchestrator_host=read("ARROWHEAD_ORCHESTRATOR_HOST", "localhost"),
            orchestrator_port=int(read("ARROWHEAD_ORCHESTRATOR_PORT", "8443")),
            keystore_path=read("ARROWHEAD_SYSOPS_KEYSTORE") if privileged else read("ARROWHEAD_KEYSTORE_PATH"),
            keystore_password=read("ARROWHEAD_KEYSTORE_PASSWORD"),
            truststore_path=read("ARROWHEAD_TRUSTSTORE"),
            root_keystore_path=os.getenv("ARROWHEAD_ROOT_KEYSTORE"),
            root_keystore_alias=os.getenv("ARROWHEAD_ROOT_KEYSTORE_ALIAS"),
            cloud_keystore_path=os.getenv("ARROWHEAD_CLOUD_KEYSTORE"),
            cloud_keystore_alias=os.getenv("ARROWHEAD_CLOUD_KEYSTORE_ALIAS"),
        )

def read(var: str, default = None) -> str:
    """Helper function to assert that an environment variable is set."""
    value = os.getenv(var)
    if value:
        return value
    if default:
        return default
    raise ValueError(f"Environment variable {var} must be set. Have you sourced the .env file?")
