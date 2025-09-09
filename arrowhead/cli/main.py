"""Main CLI entry point for Arrowhead Framework."""

import asyncio
import logging
import os
import re
import sys
from typing import Optional, Tuple
import textwrap

import click
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from arrowhead.security.cert_manager import CertManager

from ..rpc.model import AddAuthorizationRequest, ProviderSystem, ServiceRegistrationRequest, SystemRegistration, OrchestrationRequest
from ..rpc.client import Client
from ..rpc.config import Config

console = Console()
logger = logging.getLogger(__name__)


def is_valid_system_name(system_name: str) -> bool:
    return len(system_name) > 0 and re.match(r"^[a-zA-Z0-9]+$", system_name) is not None

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Python CLI to interact with Arrowhead Core Systems."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARN,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


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
    try:
        config = Config.load_from_env(privileged=True)
    except ValueError as e:
        rprint(f"[red]Error loading configuration:\n  {e}[/red]")
        sys.exit(1)

    table = Table(title="Environment Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Authorization Host", config.authorization_host)
    table.add_row("Authorization Port", str(config.authorization_port))
    table.add_row("Service Registry Host", config.service_registry_host)
    table.add_row("Service Registry Port", str(config.service_registry_port))
    table.add_row("Orchestrator Host", config.orchestrator_host)
    table.add_row("Orchestrator Port", str(config.orchestrator_port))
    table.add_row("Keystore Path", config.keystore_path)
    table.add_row("Truststore Path", config.truststore_path)
    table.add_row("Root Keystore Path", config.root_keystore_path or "Not set")
    table.add_row("Root Keystore Alias", config.root_keystore_alias or "Not set")
    table.add_row("cloud_keystore_path", config.cloud_keystore_path or "Not set")
    table.add_row("cloud_keystore_alias", config.cloud_keystore_alias or "Not set")

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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            systems_list = await client.get_systems()

            if not systems_list:
                rprint("[yellow]No systems found[/yellow]")
                return

            if filter:
                systems_list = [
                    s for s in systems_list if filter.lower() in s.name.lower()
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
                    system.name,
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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            system = await client.get_system_by_id(id)

            table = Table(title=f"System Details - {system.name}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("ID", str(system.id))
            table.add_row("System Name", system.name)
            table.add_row("Address", system.address)
            table.add_row("Port", str(system.port))
            table.add_row("Authentication Info",
                          system.authentication_info or "N/A")
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
@click.option('--name', 'names', multiple=True, required=True, help='Name of a system. Can be used multiple times for batch registration.')
@click.option('--address', 'addresses', multiple=True, required=True, help='Address of a system.')
@click.option('--port', 'ports', multiple=True, required=True, type=int, help='Port of a system.')
def register(names: Tuple[str], addresses: Tuple[str], ports: Tuple[int]) -> None:
    r"""
    Register one or more systems concurrently.

    To register multiple systems, provide a set of --name, --address, and --port
    options for each system. The options are grouped by order.

    Example:
    arrowhead systems register --name sys1 --address host1 --port 8080 ...
    """
    async def _main() -> None:
        if not (len(names) == len(addresses) == len(ports)):
            rprint(f"[bold red]Error: Mismatched number of options.[/bold red]")
            rprint(
                f"You provided {len(names)} names, {len(addresses)} addresses, and {len(ports)} ports.")
            rprint("Please provide one of each for every system.")
            sys.exit(1)

        parsed_systems = []
        for i in range(len(names)):
            name, address, port = names[i], addresses[i], ports[i]
            if not is_valid_system_name(name):
                rprint(
                    f"[red]Error: Invalid system name '{name}'. Skipping.[/red]")
                continue
            parsed_systems.append((name, address, port))

        if not parsed_systems:
            rprint("[yellow]No valid systems to register.[/yellow]")
            return

        config = Config.load_from_env(privileged=True)

        # First, generate certificates for all systems
        cert_results = []
        for name, address, port in parsed_systems:
            try:

                root_keystore = config.root_keystore_path
                root_alias = config.root_keystore_alias
                cloud_keystore = config.cloud_keystore_path
                cloud_alias = config.cloud_keystore_alias
                password = config.keystore_password

                if not root_keystore or not root_alias or not cloud_keystore or not cloud_alias or not password:
                    cert_results.append(
                        (name, None, "Missing certificate configuration"))
                    continue

                system_keystore = f"{name}.p12"
                if os.path.exists(system_keystore):
                    logger.warning(
                        f"Keystore {system_keystore} already exists, skipping certificate generation.")
                    cert_results.append((name, "existing", None))
                    continue

                cert_manager = CertManager()
                cert_manager.create_system_keystore(
                    root_keystore=root_keystore,
                    root_alias=root_alias,
                    cloud_keystore=cloud_keystore,
                    cloud_alias=cloud_alias,
                    system_keystore=system_keystore,
                    system_dname=f"CN={name}",
                    system_alias=name,
                    san=CertManager.generate_subject_alternative_name(name),
                    password=password,
                )
                auth_info = cert_manager.get_public_key(
                    system_keystore, password)
                cert_results.append((name, auth_info, None))

                # Create env file
                env_content = textwrap.dedent(f"""\
                    export ARROWHEAD_KEYSTORE_PATH=./{name}.p12
                    export ARROWHEAD_SYSTEM_NAME={name}
                    export ARROWHEAD_SYSTEM_ADDRESS={address}
                    export ARROWHEAD_SYSTEM_PORT={port}""")
                with open(f"{name}.env", "w") as f:
                    f.write(env_content)

            except Exception as e:
                cert_results.append((name, None, str(e)))

        # Create system registration requests for successful cert generations
        system_regs = []
        for i, (name, auth_info, error) in enumerate(cert_results):
            if auth_info and not error:
                address, port = parsed_systems[i][1], parsed_systems[i][2]
                if auth_info == "existing":
                    # Load auth info from existing certificate
                    cert_manager = CertManager()
                    assert config.keystore_password, "Password must be set for existing keystore"
                    auth_info = cert_manager.get_public_key(
                        f"{name}.p12", config.keystore_password)

                system_reg = SystemRegistration(
                    address=address,
                    authenticationInfo=auth_info,
                    port=port,
                    systemName=name,
                )
                system_regs.append((system_reg, name))

        # Batch register systems if any are ready
        results = []
        if system_regs:
            async with Client(config) as client:
                reg_list = [reg for reg, _ in system_regs]
                status_message = f"Batch registering {len(reg_list)} system(s)..."
                with console.status(status_message):
                    try:
                        batch_results = await client.register_systems_batch(reg_list)
                        for i, system in enumerate(batch_results):
                            results.append((parsed_systems[i], system, None))
                    except Exception as e:
                        # If batch fails, mark all as failed
                        for i, (_, name) in enumerate(system_regs):
                            results.append((parsed_systems[i], None, str(e)))

        # Add certificate generation failures to results
        for i, (name, auth_info, error) in enumerate(cert_results):
            if error:
                results.append((parsed_systems[i], None, error))

        table = Table(title="Registration Summary")
        table.add_column("System Name", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="green")

        success_count = 0
        for (name, _, _), system, error in results:
            if error:
                table.add_row(name, "[red]Failed[/red]", error)
            else:
                table.add_row(name, "[green]Success[/green]",
                              f"Registered with ID: {system.id}. Files '{name}.p12' and '{name}.env' created.")
                success_count += 1

        console.print(table)
        rprint(
            f"\n[bold green]Finished: {success_count}/{len(results)} systems registered successfully.[/bold green]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(
            f"[red]An unexpected error occurred during registration: {e}[/red]")
        sys.exit(1)


@systems.command("unregister")
@click.option("--id", "-i", type=int, required=True, help="System ID")
def unregister_system(id: int) -> None:
    """Unregister a system."""

    async def _main() -> None:
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            await client.unregister_system_by_id(id)
            rprint(
                f"[green]Successfully unregistered system with ID {id}[/green]")

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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            services_list = await client.get_services()

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
                method = service.metadata.get(
                    "http-method", "N/A") if service.metadata else "N/A"
                table.add_row(
                    str(service.id),
                    service.service_definition.service_definition,
                    service.provider.name,
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
@click.option('--system', 'systems', multiple=True, required=True, help='Provider system name. Can be used multiple times for batch registration.')
@click.option('--definition', 'definitions', multiple=True, required=True, help='Service definition name.')
@click.option('--uri', 'uris', multiple=True, required=True, help='Service URI path.')
@click.option('--method', 'methods', multiple=True, required=True, type=click.Choice(["GET", "POST", "PUT", "DELETE"]), help='HTTP method.')
def register_service(systems: Tuple[str], definitions: Tuple[str], uris: Tuple[str], methods: Tuple[str]) -> None:
    """Register one or more services concurrently."""
    async def _main() -> None:
        if not (len(systems) == len(definitions) == len(uris) == len(methods)):
            rprint(
                "[bold red]Error: Mismatched number of service options.[/bold red]")
            rprint(
                f"You provided {len(systems)} systems, {len(definitions)} definitions, {len(uris)} URIs, and {len(methods)} methods.")
            rprint("Please provide one of each for every service.")
            sys.exit(1)

        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            all_systems = {s.name: s for s in await client.get_systems()}

            service_regs = []
            for i in range(len(systems)):
                sys_name = systems[i]
                if sys_name not in all_systems:
                    rprint(
                        f"[red]Error: Provider system '{sys_name}' not found. Skipping service '{definitions[i]}'.[/red]")
                    continue

                system = all_systems[sys_name]
                provider_system = ProviderSystem(
                    systemName=system.name,
                    address=system.address,
                    port=system.port,
                    authenticationInfo=system.authentication_info or ""
                )
                service_reg = ServiceRegistrationRequest(
                    endOfValidity="",
                    interfaces=["HTTP-SECURE-JSON"],
                    metadata={"http-method": methods[i]},
                    providerSystem=provider_system,
                    secure="TOKEN",
                    serviceDefinition=definitions[i],
                    serviceUri=uris[i],
                    version="1"
                )
                service_regs.append(service_reg)

            if not service_regs:
                rprint("[yellow]No valid services to register.[/yellow]")
                return

            with console.status(f"Registering {len(service_regs)} services concurrently..."):
                results = await client.register_services_batch(service_regs)

            table = Table(title="Service Registration Summary")
            table.add_column("Service Definition", style="cyan")
            table.add_column("Provider System", style="yellow")
            table.add_column("URI", style="green")
            table.add_column("Method", style="blue")
            table.add_column("ID", style="magenta")

            for service in results:
                method = service.metadata.get(
                    "http-method", "N/A") if service.metadata else "N/A"
                table.add_row(
                    service.service_definition.service_definition,
                    service.provider.name,
                    service.service_uri,
                    method,
                    str(service.id)
                )

            console.print(table)
            rprint(
                f"\n[bold green]Successfully registered {len(results)} services.[/bold green]")

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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            try:
                service = await client.get_service_by_id(id)
                service_name = service.service_definition.service_definition
                provider_name = service.provider.name
            except Exception:
                rprint(f"[red]Error: Service with ID {id} not found[/red]")
                sys.exit(1)

            with console.status(f"Unregistering service '{service_name}' (ID: {id})..."):
                await client.unregister_service(id)

            rprint(
                f"[green]✓ Service '{service_name}' from system '{provider_name}' unregistered successfully[/green]")

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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            service = await client.get_service_by_id(id)

            table = Table(
                title=f"Service Details - {service.service_definition.service_definition}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Service ID", str(service.id))
            table.add_row("Service Definition", service.service_definition.service_definition)
            table.add_row("Service URI", service.service_uri)
            table.add_row("Provider System", service.provider.name)
            table.add_row("Provider Address", f"{service.provider.address}:{service.provider.port}")
            table.add_row("Security", service.secure)
            table.add_row("Version", str(service.version))
            table.add_row("Created", (service.created_at.strftime("%Y-%m-%d %H:%M:%S") if service.created_at else "N/A"))
            table.add_row("Updated", (service.updated_at.strftime("%Y-%m-%d %H:%M:%S") if service.updated_at else "N/A"))
            table.add_row("End of Validity", (service.end_of_validity.strftime("%Y-%m-%d %H:%M:%S") if service.end_of_validity else "N/A"))

            if service.interfaces:
                interfaces_str = ", ".join(
                    [intf.interface_name for intf in service.interfaces])
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
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            auth_list = await client.get_authorizations()

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
                    auth.consumer_system.name,
                    auth.provider_system.name,
                    auth.service_definition.service_definition,
                )

            console.print(table)

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        sys.exit(1)


@auths.command("add")
@click.option('--consumer', 'consumers', multiple=True, required=True, help='Consumer system name. Can be used multiple times for batch authorization.')
@click.option('--provider', 'providers', multiple=True, required=True, help='Provider system name.')
@click.option('--service', 'services', multiple=True, required=True, help='Service definition.')
def add_authorization(consumers: Tuple[str], providers: Tuple[str], services: Tuple[str]) -> None:
    """Add one or more authorization rules."""
    async def _main() -> None:
        if not (len(consumers) == len(providers) == len(services)):
            rprint(
                "[bold red]Error: Mismatched number of authorization options.[/bold red]")
            rprint(
                f"You provided {len(consumers)} consumers, {len(providers)} providers, and {len(services)} services.")
            rprint("Please provide one of each for every authorization rule.")
            sys.exit(1)

        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            # Get all systems to resolve names to IDs
            all_systems = {s.name: s for s in await client.get_systems()}

            auth_reqs = []
            for consumer_name, provider_name, service_def in zip(consumers, providers, services):
                try:
                    consumer = all_systems[consumer_name]
                    provider = all_systems[provider_name]

                    # Get service definition IDs for this provider and service
                    service_def_ids = await client.get_service_definition_ids_for_provider(provider.id, service_def)
                    if not service_def_ids:
                        rprint(
                            f"[red]Warning: No service definition '{service_def}' found for provider '{provider_name}'. Skipping.[/red]")
                        continue

                    # Get interface IDs for this provider
                    interface_ids = await client.get_interface_ids_for_provider(provider.id)
                    if not interface_ids:
                        rprint(
                            f"[red]Warning: No interfaces found for provider '{provider_name}'. Skipping.[/red]")
                        continue

                    auth_req = AddAuthorizationRequest(
                        consumerId=consumer.id,
                        providerIds=[provider.id],
                        serviceDefinitionIds=service_def_ids,
                        interfaceIds=interface_ids,
                    )
                    auth_reqs.append(auth_req)

                except KeyError as e:
                    rprint(
                        f"[red]Error: System '{e.args[0]}' not found. Skipping authorization rule.[/red]")
                    continue

            if not auth_reqs:
                rprint("[yellow]No valid authorization rules to add.[/yellow]")
                return

            with console.status(f"Adding {len(auth_reqs)} authorization rules in batch..."):
                results = await client.add_authorizations_batch(auth_reqs)

            table = Table(title="Authorization Rules Summary")
            table.add_column("Consumer", style="cyan")
            table.add_column("Provider", style="yellow")
            table.add_column("Service", style="green")
            table.add_column("ID", style="magenta")

            for auth in results:
                table.add_row(
                    auth.consumer_system.name,
                    auth.provider_system.name,
                    auth.service_definition.service_definition,
                    str(auth.id)
                )

            console.print(table)
            rprint(
                f"\n[bold green]Successfully added {len(results)} authorization rules.[/bold green]")

    try:
        asyncio.run(_main())
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Authorization addition failed")
        sys.exit(1)


@auths.command("remove")
@click.option(
    "--id", "-i", type=int, required=True, help="Authorization rule ID to remove"
)
def remove_authorization(id: int) -> None:
    """Remove an authorization rule by ID."""
    async def _main() -> None:
        config = Config.load_from_env(privileged=True)
        async with Client(config) as client:
            try:
                auth_list = await client.get_authorizations()
                auth_to_remove = next(
                    (auth for auth in auth_list if auth.id == id), None)
                if not auth_to_remove:
                    rprint(
                        f"[red]Error: Authorization rule with ID {id} not found[/red]")
                    sys.exit(1)

                consumer_name = auth_to_remove.consumer_system.name
                provider_name = auth_to_remove.provider_system.name
                service_name = auth_to_remove.service_definition.service_definition

            except Exception:
                rprint(
                    f"[red]Error: Authorization rule with ID {id} not found[/red]")
                sys.exit(1)

            with console.status(f"Removing authorization rule (ID: {id})..."):
                await client.remove_authorization(id)

            rprint("[green]✓ Authorization rule removed successfully[/green]")
            rprint(
                f"[blue]Removed: {consumer_name} → {provider_name} → {service_name}[/blue]")

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
    """Generate a system certificate."""
    if not is_valid_system_name(name):
        rprint(
            "[red]Error: System name is invalid. Only letters and numbers are allowed.[/red]")
        sys.exit(1)

    try:
        config = Config.load_from_env(privileged=True)
        root_keystore = root_keystore or config.root_keystore_path
        root_alias = root_alias or config.root_keystore_alias
        cloud_keystore = cloud_keystore or config.cloud_keystore_path
        cloud_alias = cloud_alias or config.cloud_keystore_alias
        password = password or config.keystore_password or click.prompt(
            "Keystore password", hide_input=True, confirmation_prompt=True)

        if not root_keystore:
            rprint(
                f"[red]Error: Root keystore path required. Use --root-keystore or set ARROWHEAD_ROOT_KEYSTORE.[/red]")
            sys.exit(1)

        if not root_alias:
            rprint(
                f"[red]Error: Root keystore alias required. Use --root-alias or set ARROWHEAD_ROOT_KEYSTORE_ALIAS.[/red]")
            sys.exit(1)

        if not cloud_keystore:
            rprint(
                f"[red]Error: Cloud keystore path required. Use --cloud-keystore or set ARROWHEAD_CLOUD_KEYSTORE.[/red]")
            sys.exit(1)

        if not cloud_alias:
            rprint(
                f"[red]Error: Cloud keystore alias required. Use --cloud-alias or set ARROWHEAD_CLOUD_KEYSTORE_ALIAS.[/red]")
            sys.exit(1)

        if not password:
            rprint(
                f"[red]Error: Keystore password required. Use --password or set ARROWHEAD_KEYSTORE_PASSWORD.[/red]")
            sys.exit(1)

        if not os.path.exists(root_keystore):
            rprint(
                f"[red]Error: Root keystore file '{root_keystore}' not found.[/red]")
            sys.exit(1)

        if not os.path.exists(cloud_keystore):
            rprint(
                f"[red]Error: Cloud keystore file '{cloud_keystore}' not found.[/red]")
            sys.exit(1)

        system_keystore = f"{name}.p12"
        # FIX: The Distinguished Name (DN) for the certificate's subject
        # should match the system name exactly for mTLS authentication.
        # We will use the simple system name for the Common Name (CN).
        system_dname = f"CN={name}"
        san = CertManager.generate_subject_alternative_name(name)

        # Check if system keystore already exists
        if os.path.exists(system_keystore):
            rprint(
                f"[red]Error: System keystore '{system_keystore}' already exists[/red]")
            sys.exit(1)

        # Load certificate manager and create keystore
        cert_manager = CertManager()

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

        rprint(
            f"[green]✓ Certificate generated successfully: {system_keystore}[/green]")
        rprint(f"[blue]✓ Public key file created: {name}.pub[/blue]")

        # Create environment file
        env_filename = f"{name}.env"
        env_content = textwrap.dedent(f"""\
            # Arrowhead system configuration for {name}
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
            export ARROWHEAD_SYSTEM_PORT=8080""")

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
        table.add_row("Authentication Info",
                      public_key[:50] + "..." if len(public_key) > 50 else public_key)
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
    """Convert PKCS#12 file to PEM format."""
    if not os.path.exists(p12_file):
        rprint(f"[red]Error: PKCS#12 file '{p12_file}' not found[/red]")
        sys.exit(1)
    try:
        config = Config.load_from_env(privileged=True)
        password = password or config.keystore_password or "changeit"
        base_name = os.path.splitext(p12_file)[0]
        cert_output = cert_output or f"{base_name}.crt"
        key_output = key_output or f"{base_name}.key"
        cert_manager = CertManager()
        with console.status(f"Converting {p12_file} to PEM format..."):
            cert_manager.convert_p12_to_pem(
                p12_file, password, cert_output, key_output)
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
        # Orchestration is done by a regular system, not sysop.
        privileged = system is None and address is None and port is None
        config = Config.load_from_env(privileged)

        requester_system_name = system or os.getenv("ARROWHEAD_SYSTEM_NAME", "cli-consumer")
        requester_address = address or os.getenv("ARROWHEAD_SYSTEM_ADDRESS", "localhost")
        requester_port = port or int(os.getenv("ARROWHEAD_SYSTEM_PORT", "8080"))

        config.keystore_path = keystore or config.keystore_path
        config.keystore_password = password or config.keystore_password

        orchestration_request = OrchestrationRequest(requester_system_name, requester_address, requester_port, service)

        async with Client(config) as client:
            response = await client.orchestrate(orchestration_request)

        if not response.matches:
            rprint(
                f"[yellow]No providers found for service: {service}[/yellow]")
            return

        if compact:
            table = Table(title=f"Orchestration: {service}")
            table.add_column("Provider", style="green")
            table.add_column("Address", style="blue")
            table.add_column("URI", style="magenta")

            for matched_service in response.matches:
                table.add_row(
                    matched_service.provider.name,
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

            for matched_service in response.matches:
                interfaces = ", ".join([intf.interface_name for intf in matched_service.interfaces])
                table.add_row(
                    matched_service.provider.name,
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


if __name__ == "__main__":
    main()
