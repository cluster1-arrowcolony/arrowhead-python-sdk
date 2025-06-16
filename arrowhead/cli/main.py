"""Main CLI entry point for Arrowhead Framework."""

import asyncio
import logging
import os
import re
import sys
from typing import Optional

import click
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from ..core.models import SystemRegistration
from ..rpc.client import ArrowheadClient
from ..rpc.config import Config, HTTPMethod
from ..security.cert_manager import generate_subject_alternative_name, load_cert_manager

console = Console()
logger = logging.getLogger(__name__)


def is_valid_system_name(system_name: str) -> bool:
    """
    Validate system name - should only contain letters and numbers and not be empty.

    Args:
        system_name: The system name to validate

    Returns:
        True if valid, False otherwise
    """
    if not system_name:
        return False

    # Only letters and numbers allowed
    return bool(re.match(r"^[a-zA-Z0-9]+$", system_name))


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_config() -> Config:
    """Load configuration from environment variables for applications."""
    return Config(
        tls=os.getenv("ARROWHEAD_TLS", "true").lower() in ("true", "1"),
        authorization_host=os.getenv("ARROWHEAD_AUTHORIZATION_HOST", "c1-authorization"),
        authorization_port=int(os.getenv("ARROWHEAD_AUTHORIZATION_PORT", "8445")),
        service_registry_host=os.getenv("ARROWHEAD_SERVICEREGISTRY_HOST", "c1-serviceregistry"),
        service_registry_port=int(os.getenv("ARROWHEAD_SERVICEREGISTRY_PORT", "8443")),
        orchestrator_host=os.getenv("ARROWHEAD_ORCHESTRATOR_HOST", "c1-orchestrator"),
        orchestrator_port=int(os.getenv("ARROWHEAD_ORCHESTRATOR_PORT", "8441")),
        keystore_path=os.getenv("ARROWHEAD_KEYSTORE_PATH"),
        truststore_path=os.getenv("ARROWHEAD_TRUSTSTORE"),
        password=os.getenv("ARROWHEAD_KEYSTORE_PASSWORD"),
        verify_ssl=os.getenv("ARROWHEAD_VERIFY_SSL", "true").lower() in ("true", "1"),
    )


def load_sysops_config() -> Config:
    """Load configuration for CLI management operations using sysops certificate."""
    return Config(
        tls=os.getenv("ARROWHEAD_TLS", "true").lower() in ("true", "1"),
        authorization_host=os.getenv("ARROWHEAD_AUTHORIZATION_HOST", "c1-authorization"),
        authorization_port=int(os.getenv("ARROWHEAD_AUTHORIZATION_PORT", "8445")),
        service_registry_host=os.getenv("ARROWHEAD_SERVICEREGISTRY_HOST", "c1-serviceregistry"),
        service_registry_port=int(os.getenv("ARROWHEAD_SERVICEREGISTRY_PORT", "8443")),
        orchestrator_host=os.getenv("ARROWHEAD_ORCHESTRATOR_HOST", "c1-orchestrator"),
        orchestrator_port=int(os.getenv("ARROWHEAD_ORCHESTRATOR_PORT", "8441")),
        keystore_path=os.getenv("ARROWHEAD_SYSOPS_KEYSTORE", os.getenv("ARROWHEAD_KEYSTORE_PATH")),
        truststore_path=os.getenv("ARROWHEAD_TRUSTSTORE"),
        password=os.getenv("ARROWHEAD_KEYSTORE_PASSWORD"),
        verify_ssl=os.getenv("ARROWHEAD_VERIFY_SSL", "true").lower() in ("true", "1"),
        root_keystore_path=os.getenv("ARROWHEAD_ROOT_KEYSTORE"),
        root_keystore_alias=os.getenv("ARROWHEAD_ROOT_KEYSTORE_ALIAS"),
        cloud_keystore_path=os.getenv("ARROWHEAD_CLOUD_KEYSTORE"),
        cloud_keystore_alias=os.getenv("ARROWHEAD_CLOUD_KEYSTORE_ALIAS"),
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Python CLI to interact with Arrowhead Core Systems."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
def version() -> None:
    """Show version information."""
    from .. import __version__

    table = Table(title="Arrowhead Python CLI")
    table.add_column("Component", style="cyan")
    table.add_column("Version", style="green")

    table.add_row("py-arrowhead", __version__)
    table.add_row(
        "Python",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    console.print(table)


@cli.command()
def env() -> None:
    """Show environment configuration."""
    config = load_sysops_config()

    table = Table(title="Environment Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("TLS", str(config.tls))
    table.add_row("Authorization Host", config.authorization_host)
    table.add_row("Authorization Port", str(config.authorization_port))
    table.add_row("Service Registry Host", config.service_registry_host)
    table.add_row("Service Registry Port", str(config.service_registry_port))
    table.add_row("Orchestrator Host", config.orchestrator_host)
    table.add_row("Orchestrator Port", str(config.orchestrator_port))
    table.add_row("Keystore Path", config.keystore_path or "Not set")
    table.add_row("Truststore Path", config.truststore_path or "Not set")

    console.print(table)


@cli.group()
def systems() -> None:
    """Manage Arrowhead systems."""
    pass


@systems.command("ls")
@click.option("--filter", "-f", help="Filter systems by name")
def list_systems(filter: Optional[str]) -> None:
    """List available systems."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            systems_list = await client.management.get_systems()

            if not systems_list:
                rprint("[yellow]No systems found[/yellow]")
                return

            if filter:
                systems_list = [
                    s for s in systems_list if filter.lower() in s.system_name.lower()
                ]

            table = Table(title="Registered Systems")
            table.add_column("ID", style="cyan")
            table.add_column("System Name", style="green")
            table.add_column("Address", style="blue")
            table.add_column("Port", style="magenta")
            table.add_column("Created", style="dim")

            for system in systems_list:
                table.add_row(
                    str(system.id),
                    system.system_name,
                    system.address,
                    str(system.port),
                    (
                        system.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if system.created_at
                        else "N/A"
                    ),
                )

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@systems.command("get")
@click.option("--id", "-i", type=int, required=True, help="System ID")
def get_system(id: int) -> None:
    """Get info about a system."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            system = await client.management.get_system_by_id(id)

            table = Table(title=f"System Details - {system.system_name}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("ID", str(system.id))
            table.add_row("System Name", system.system_name)
            table.add_row("Address", system.address)
            table.add_row("Port", str(system.port))
            table.add_row("Authentication Info", system.authentication_info or "N/A")
            table.add_row(
                "Created",
                (
                    system.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if system.created_at
                    else "N/A"
                ),
            )
            table.add_row(
                "Updated",
                (
                    system.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                    if system.updated_at
                    else "N/A"
                ),
            )

            if system.metadata:
                for key, value in system.metadata.items():
                    table.add_row(f"Metadata.{key}", value)

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@systems.command("register")
@click.option("--name", "-n", required=True, help="System name")
@click.option("--address", "-a", required=True, help="System address")
@click.option("--port", "-p", type=int, required=True, help="System port")
def register_system(name: str, address: str, port: int) -> None:
    """Register a system."""
    async def _main() -> None:
        # Validate system name
        if not is_valid_system_name(name):
            rprint(
                "[red]Error: System name is invalid. Only letters and numbers are allowed.[/red]"
            )
            sys.exit(1)

        # Generate certificate for the new system
        config = load_sysops_config()
        root_keystore = config.root_keystore_path
        root_alias = config.root_keystore_alias
        cloud_keystore = config.cloud_keystore_path
        cloud_alias = config.cloud_keystore_alias
        password = config.password or click.prompt("Keystore password", hide_input=True, confirmation_prompt=True)

        if not root_keystore:
            rprint(f"[red]Error: ARROWHEAD_ROOT_KEYSTORE environment variable is required.[/red]")
            sys.exit(1)

        if not root_alias:
            rprint(f"[red]Error: ARROWHEAD_ROOT_KEYSTORE_ALIAS environment variable is required.[/red]")
            sys.exit(1)

        if not cloud_keystore:
            rprint(f"[red]Error: ARROWHEAD_CLOUD_KEYSTORE environment variable is required.[/red]")
            sys.exit(1)

        if not cloud_alias:
            rprint(f"[red]Error: ARROWHEAD_CLOUD_KEYSTORE_ALIAS environment variable is required.[/red]")
            sys.exit(1)

        if not os.path.exists(root_keystore):
            rprint(f"[red]Error: Root keystore file '{root_keystore}' not found.[/red]")
            sys.exit(1)

        if not os.path.exists(cloud_keystore):
            rprint(f"[red]Error: Cloud keystore file '{cloud_keystore}' not found.[/red]")
            sys.exit(1)

        system_keystore = f"{name}.p12"
        system_dname = f"{name}.{cloud_alias}"
        san = generate_subject_alternative_name(name)

        # Check if system keystore already exists
        if os.path.exists(system_keystore):
            rprint(f"[red]Error: System keystore '{system_keystore}' already exists[/red]")
            sys.exit(1)

        # Load certificate manager and create keystore
        cert_manager = load_cert_manager()

        with console.status(f"Generating certificate for system '{name}'..."):
            cert_manager.create_system_keystore(
                root_keystore=root_keystore,
                root_alias=root_alias,
                cloud_keystore=cloud_keystore,
                cloud_alias=cloud_alias,
                system_keystore=system_keystore,
                system_dname=system_dname,
                system_alias=name,
                san=san,
                password=password,
            )

        # Get public key for authentication info from the newly created certificate
        auth_info = cert_manager.get_public_key(system_keystore, password)

        system_reg = SystemRegistration(
            address=address,
            authenticationInfo=auth_info,
            metadata={},
            port=port,
            systemName=name,
        )

        # Network I/O happens here
        async with ArrowheadClient(config) as client:
            system = await client.management.register_system(system_reg)

        rprint(f"[green]✓ Certificate generated successfully: {system_keystore}[/green]")
        rprint(f"[blue]✓ Public key file created: {name}.pub[/blue]")
        rprint(f"[green]✓ System '{name}' registered successfully with ID {system.id}[/green]")

        # Create environment file with same format as Go SDK
        tls_str = "true" if config.tls else "false"
        truststore_path = config.truststore_path or "./truststore.pem"
        
        env_content = f"""export ARROWHEAD_TLS={tls_str}
export ARROWHEAD_VERBOSE=false
export ARROWHEAD_AUTHORIZATION_HOST={config.authorization_host}
export ARROWHEAD_AUTHORIZATION_PORT={config.authorization_port}
export ARROWHEAD_SERVICEREGISTRY_HOST={config.service_registry_host}
export ARROWHEAD_SERVICEREGISTRY_PORT={config.service_registry_port}
export ARROWHEAD_ORCHESTRATOR_HOST={config.orchestrator_host}
export ARROWHEAD_ORCHESTRATOR_PORT={config.orchestrator_port}
export ARROWHEAD_KEYSTORE_PATH=./{name}.p12
export ARROWHEAD_KEYSTORE_PASSWORD={config.password or '123456'}
export ARROWHEAD_TRUSTSTORE={truststore_path}
export ARROWHEAD_SYSTEM_NAME={name}
export ARROWHEAD_SYSTEM_ADDRESS={address}
export ARROWHEAD_SYSTEM_PORT={port}
"""

        with open(f"{name}.env", "w") as f:
            f.write(env_content)

        rprint(f"[blue]Configuration saved to {name}.env[/blue]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@systems.command("unregister")
@click.option("--id", "-i", type=int, required=True, help="System ID")
def unregister_system(id: int) -> None:
    """Unregister a system."""

    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            await client.management.unregister_system_by_id(id)
            rprint(f"[green]Successfully unregistered system with ID {id}[/green]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.group()
def services() -> None:
    """Manage Arrowhead services."""
    pass


@services.command("ls")
def list_services() -> None:
    """List available services."""

    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            services_list = await client.management.get_services()

            if not services_list:
                rprint("[yellow]No services found[/yellow]")
                return

            table = Table(title="Registered Services")
            table.add_column("ID", style="cyan")
            table.add_column("Service Definition", style="green")
            table.add_column("Provider", style="blue")
            table.add_column("URI", style="magenta")
            table.add_column("Method", style="yellow")

            for service in services_list:
                method = service.metadata.get("http-method", "N/A") if service.metadata else "N/A"
                table.add_row(
                    str(service.id),
                    service.service_definition.service_definition,
                    service.provider.system_name,
                    service.service_uri,
                    method,
                )

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@services.command("register")
@click.option("--system", required=True, help="Provider system name")
@click.option("--definition", required=True, help="Service definition name")
@click.option("--uri", required=True, help="Service URI path")
@click.option(
    "--method",
    "-m",
    type=click.Choice(["GET", "POST", "PUT", "DELETE"]),
    default="POST",
    help="HTTP method",
)
def register_service(system: str, definition: str, uri: str, method: str) -> None:
    """Register a service for a system."""

    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            try:
                provider_system = await client.management.get_system_by_name(system)
            except ValueError:
                rprint(f"[red]Error: System '{system}' not found. Please register the system first.[/red]")
                sys.exit(1)

            http_method = getattr(HTTPMethod, method)
            with console.status(f"Registering service '{definition}' for system '{system}'..."):
                service = await client.management.register_service(
                    system=provider_system,
                    http_method=http_method,
                    service_definition=definition,
                    service_uri=uri,
                )

            rprint(f"[green]✓ Service '{definition}' registered successfully with ID {service.id}[/green]")

            table = Table(title="Registered Service Details")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Service ID", str(service.id))
            table.add_row("Service Definition", service.service_definition.service_definition)
            table.add_row("Provider System", service.provider.system_name)
            table.add_row("Service URI", service.service_uri)
            table.add_row("HTTP Method", method)
            table.add_row("Security", service.secure)
            table.add_row("Version", str(service.version))

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Service registration failed")
        sys.exit(1)


@services.command("unregister")
@click.option("--id", "-i", type=int, required=True, help="Service ID to unregister")
def unregister_service(id: int) -> None:
    """Unregister a service by ID."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            try:
                service = await client.management.get_service_by_id(id)
                service_name = service.service_definition.service_definition
                provider_name = service.provider.system_name
            except Exception:
                rprint(f"[red]Error: Service with ID {id} not found[/red]")
                sys.exit(1)

            with console.status(f"Unregistering service '{service_name}' (ID: {id})..."):
                await client.management.unregister_service(id)

            rprint(f"[green]✓ Service '{service_name}' from system '{provider_name}' unregistered successfully[/green]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Service unregistration failed")
        sys.exit(1)


@services.command("get")
@click.option("--id", "-i", type=int, required=True, help="Service ID")
@click.option("--authinfo", is_flag=True, help="Include authentication info")
def get_service(id: int, authinfo: bool) -> None:
    """Get detailed information about a service."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            service = await client.management.get_service_by_id(id)

            table = Table(title=f"Service Details - {service.service_definition.service_definition}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Service ID", str(service.id))
            table.add_row("Service Definition", service.service_definition.service_definition)
            table.add_row("Service URI", service.service_uri)
            table.add_row("Provider System", service.provider.system_name)
            table.add_row("Provider Address", f"{service.provider.address}:{service.provider.port}")
            table.add_row("Security", service.secure)
            table.add_row("Version", str(service.version))
            table.add_row("Created", (service.created_at.strftime("%Y-%m-%d %H:%M:%S") if service.created_at else "N/A"))
            table.add_row("Updated", (service.updated_at.strftime("%Y-%m-%d %H:%M:%S") if service.updated_at else "N/A"))
            table.add_row("End of Validity", (service.end_of_validity.strftime("%Y-%m-%d %H:%M:%S") if service.end_of_validity else "N/A"))

            if service.interfaces:
                interfaces_str = ", ".join([iface.interface_name for iface in service.interfaces])
                table.add_row("Interfaces", interfaces_str)

            if service.metadata:
                for key, value in service.metadata.items():
                    table.add_row(f"Metadata.{key}", value)

            if authinfo and service.provider.authentication_info:
                auth_info_str = service.provider.authentication_info
                if len(auth_info_str) > 100:
                    auth_info_str = auth_info_str[:100] + "..."
                table.add_row("Authentication Info", auth_info_str)

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.group()
def auths() -> None:
    """Manage authorization rules."""
    pass


@auths.command("ls")
def list_authorizations() -> None:
    """List authorization rules."""

    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            auth_list = await client.management.get_authorizations()

            if not auth_list:
                rprint("[yellow]No authorization rules found[/yellow]")
                return

            table = Table(title="Authorization Rules")
            table.add_column("ID", style="cyan")
            table.add_column("Consumer", style="green")
            table.add_column("Provider", style="blue")
            table.add_column("Service", style="magenta")

            for auth in auth_list:
                table.add_row(
                    str(auth.id),
                    auth.consumer_system.system_name,
                    auth.provider_system.system_name,
                    auth.service_definition.service_definition,
                )

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@auths.command("add")
@click.option("--consumer", required=True, help="Consumer system name")
@click.option("--provider", required=True, help="Provider system name")
@click.option("--service", required=True, help="Service definition")
def add_authorization(consumer: str, provider: str, service: str) -> None:
    """Add authorization rule."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            auth = await client.management.add_authorization(consumer, provider, service)
            rprint(f"[green]Authorization rule added with ID {auth.id}[/green]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@auths.command("remove")
@click.option(
    "--id", "-i", type=int, required=True, help="Authorization rule ID to remove"
)
def remove_authorization(id: int) -> None:
    """Remove an authorization rule by ID."""
    async def _main() -> None:
        config = load_sysops_config()
        async with ArrowheadClient(config) as client:
            try:
                auth_list = await client.management.get_authorizations()
                auth_to_remove = next((auth for auth in auth_list if auth.id == id), None)
                if not auth_to_remove:
                    rprint(f"[red]Error: Authorization rule with ID {id} not found[/red]")
                    sys.exit(1)

                consumer_name = auth_to_remove.consumer_system.system_name
                provider_name = auth_to_remove.provider_system.system_name
                service_name = auth_to_remove.service_definition.service_definition

            except Exception:
                rprint(f"[red]Error: Authorization rule with ID {id} not found[/red]")
                sys.exit(1)

            with console.status(f"Removing authorization rule (ID: {id})..."):
                await client.management.remove_authorization(id)

            rprint("[green]✓ Authorization rule removed successfully[/green]")
            rprint(f"[blue]Removed: {consumer_name} → {provider_name} → {service_name}[/blue]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Authorization removal failed")
        sys.exit(1)


@cli.group()
def certs() -> None:
    """Manage Arrowhead PKCS#12 certificates."""
    pass


@certs.command("gen")
@click.option("--name", "-n", required=True, help="System name for certificate generation")
@click.option("--root-keystore", help="Root keystore path (default: from env)")
@click.option("--root-alias", help="Root keystore alias (default: from env)")
@click.option("--cloud-keystore", help="Cloud keystore path (default: from env)")
@click.option("--cloud-alias", help="Cloud keystore alias (default: from env)")
@click.option("--password", help="Keystore password (default: from env or prompt)")
def generate_certificate(
    name: str,
    root_keystore: Optional[str],
    root_alias: Optional[str],
    cloud_keystore: Optional[str],
    cloud_alias: Optional[str],
    password: Optional[str],
) -> None:
    """Generate a system certificate. This is a local operation and does not require async."""
    if not is_valid_system_name(name):
        rprint("[red]Error: System name is invalid. Only letters and numbers are allowed.[/red]")
        sys.exit(1)

    try:
        config = load_sysops_config()
        root_keystore = root_keystore or config.root_keystore_path
        root_alias = root_alias or config.root_keystore_alias
        cloud_keystore = cloud_keystore or config.cloud_keystore_path
        cloud_alias = cloud_alias or config.cloud_keystore_alias
        password = password or config.password or click.prompt("Keystore password", hide_input=True, confirmation_prompt=True)

        if not root_keystore:
            rprint(f"[red]Error: Root keystore path required. Use --root-keystore or set ARROWHEAD_ROOT_KEYSTORE.[/red]")
            sys.exit(1)

        if not root_alias:
            rprint(f"[red]Error: Root keystore alias required. Use --root-alias or set ARROWHEAD_ROOT_KEYSTORE_ALIAS.[/red]")
            sys.exit(1)

        if not cloud_keystore:
            rprint(f"[red]Error: Cloud keystore path required. Use --cloud-keystore or set ARROWHEAD_CLOUD_KEYSTORE.[/red]")
            sys.exit(1)

        if not cloud_alias:
            rprint(f"[red]Error: Cloud keystore alias required. Use --cloud-alias or set ARROWHEAD_CLOUD_KEYSTORE_ALIAS.[/red]")
            sys.exit(1)

        if not password:
            rprint(f"[red]Error: Keystore password required. Use --password or set ARROWHEAD_KEYSTORE_PASSWORD.[/red]")
            sys.exit(1)

        if not os.path.exists(root_keystore):
            rprint(f"[red]Error: Root keystore file '{root_keystore}' not found.[/red]")
            sys.exit(1)

        if not os.path.exists(cloud_keystore):
            rprint(f"[red]Error: Cloud keystore file '{cloud_keystore}' not found.[/red]")
            sys.exit(1)

        system_keystore = f"{name}.p12"
        system_dname = f"{name}.{cloud_alias}"
        san = generate_subject_alternative_name(name)

        # Check if system keystore already exists
        if os.path.exists(system_keystore):
            rprint(f"[red]Error: System keystore '{system_keystore}' already exists[/red]")
            sys.exit(1)

        # Load certificate manager and create keystore
        cert_manager = load_cert_manager()

        with console.status(f"Generating certificate for system '{name}'..."):
            cert_manager.create_system_keystore(
                root_keystore=root_keystore,
                root_alias=root_alias,
                cloud_keystore=cloud_keystore,
                cloud_alias=cloud_alias,
                system_keystore=system_keystore,
                system_dname=system_dname,
                system_alias=name,
                san=san,
                password=password,
            )

        # Get public key for authentication info
        public_key = cert_manager.get_public_key(system_keystore, password)

        rprint(f"[green]✓ Certificate generated successfully: {system_keystore}[/green]")
        rprint(f"[blue]✓ Public key file created: {name}.pub[/blue]")

        # Create environment file
        env_filename = f"{name}.env"
        env_content = f"""# Arrowhead system configuration for {name}
export ARROWHEAD_TLS=true
export ARROWHEAD_VERBOSE=false
export ARROWHEAD_AUTHORIZATION_HOST={config.authorization_host}
export ARROWHEAD_AUTHORIZATION_PORT={config.authorization_port}
export ARROWHEAD_SERVICEREGISTRY_HOST={config.service_registry_host}
export ARROWHEAD_SERVICEREGISTRY_PORT={config.service_registry_port}
export ARROWHEAD_ORCHESTRATOR_HOST={config.orchestrator_host}
export ARROWHEAD_ORCHESTRATOR_PORT={config.orchestrator_port}
export ARROWHEAD_KEYSTORE_PATH={system_keystore}
export ARROWHEAD_KEYSTORE_PASSWORD={password}
export ARROWHEAD_TRUSTSTORE={config.truststore_path or "truststore.pem"}
export ARROWHEAD_SYSTEM_NAME={name}
export ARROWHEAD_SYSTEM_ADDRESS=localhost
export ARROWHEAD_SYSTEM_PORT=8080
"""

        with open(env_filename, "w") as f:
            f.write(env_content)

        rprint(f"[cyan]✓ Environment file created: {env_filename}[/cyan]")

        # Show authentication info
        table = Table(title=f"Certificate Details for '{name}'")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("System Name", name)
        table.add_row("Keystore File", system_keystore)
        table.add_row("Public Key File", f"{name}.pub")
        table.add_row("Environment File", env_filename)
        table.add_row("Authentication Info", public_key[:50] + "..." if len(public_key) > 50 else public_key)
        console.print(table)

    except Exception as e:
        rprint(f"[red]Error generating certificate: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Certificate generation failed")
        sys.exit(1)


@certs.command("convert")
@click.option("--p12-file", required=True, help="Input PKCS#12 file")
@click.option("--password", help="Keystore password (default: from env)")
@click.option("--cert-output", help="Output certificate file (default: <p12-file>.crt)")
@click.option("--key-output", help="Output private key file (default: <p12-file>.key)")
def convert_p12_to_pem(
    p12_file: str,
    password: Optional[str],
    cert_output: Optional[str],
    key_output: Optional[str],
) -> None:
    """Convert PKCS#12 file to PEM format. This is a local operation and does not require async."""
    if not os.path.exists(p12_file):
        rprint(f"[red]Error: PKCS#12 file '{p12_file}' not found[/red]")
        sys.exit(1)
    try:
        config = load_sysops_config()
        password = password or config.password or "changeit"
        base_name = os.path.splitext(p12_file)[0]
        cert_output = cert_output or f"{base_name}.crt"
        key_output = key_output or f"{base_name}.key"
        cert_manager = load_cert_manager()
        with console.status(f"Converting {p12_file} to PEM format..."):
            cert_manager.convert_p12_to_pem(p12_file, password, cert_output, key_output)
        rprint(f"[green]✓ Certificate extracted to: {cert_output}[/green]")
        rprint(f"[green]✓ Private key extracted to: {key_output}[/green]")
    except Exception as e:
        rprint(f"[red]Error converting certificate: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Certificate conversion failed")
        sys.exit(1)


@cli.command()
@click.option("--service", required=True, help="Service definition to orchestrate")
@click.option("--system", help="Requester system name (overrides env)")
@click.option("--address", help="Requester system address (overrides env)")
@click.option("--port", type=int, help="Requester system port (overrides env)")
@click.option("--keystore", help="Requester keystore path (overrides env)")
@click.option("--password", help="Requester keystore password (overrides env)")
@click.option("--compact", is_flag=True, help="Compact output format")
def orchestrate(
    service: str,
    system: Optional[str],
    address: Optional[str],
    port: Optional[int],
    keystore: Optional[str],
    password: Optional[str],
    compact: bool,
) -> None:
    """Request service orchestration."""
    async def _main() -> None:
        config = load_sysops_config()
        requester_system_name = system or os.getenv("ARROWHEAD_SYSTEM_NAME", "cli-consumer")
        requester_address = address or os.getenv("ARROWHEAD_SYSTEM_ADDRESS", "localhost")
        requester_port = port or int(os.getenv("ARROWHEAD_SYSTEM_PORT", "8080"))
        
        if keystore:
            config.keystore_path = keystore
        if password:
            config.password = password

        from ..rpc.utils import build_orchestration_request
        orchestration_request = build_orchestration_request(
            requester_system_name, requester_address, requester_port, service
        )

        async with ArrowheadClient(config) as client:
            response = await client.orchestrate(orchestration_request)

        if not response.response:
            rprint(f"[yellow]No providers found for service: {service}[/yellow]")
            return

        if compact:
            table = Table(title=f"Orchestration: {service}")
            table.add_column("Provider", style="green")
            table.add_column("Address", style="blue")
            table.add_column("URI", style="magenta")

            for matched_service in response.response:
                table.add_row(
                    matched_service.provider.system_name,
                    f"{matched_service.provider.address}:{matched_service.provider.port}",
                    matched_service.service_uri,
                )
        else:
            table = Table(title=f"Orchestration Results for '{service}'")
            table.add_column("Provider", style="green")
            table.add_column("Address", style="blue")
            table.add_column("URI", style="magenta")
            table.add_column("Secure", style="cyan")
            table.add_column("Interfaces", style="yellow")

            for matched_service in response.response:
                interfaces = ", ".join([iface.interface_name for iface in matched_service.interfaces])
                table.add_row(
                    matched_service.provider.system_name,
                    f"{matched_service.provider.address}:{matched_service.provider.port}",
                    matched_service.service_uri,
                    matched_service.secure,
                    interfaces,
                )

        console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    cli()
