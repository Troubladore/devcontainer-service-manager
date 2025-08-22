"""Command-line interface for DevContainer Service Manager."""

import click
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rich_print

from .core.namespace_manager import NamespaceManager
from .core.service_pool import ServicePool, ServiceStatus
from .core.port_allocator import PortAllocator
from .core.health_monitor import HealthMonitor


console = Console()


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def main(ctx, version):
    """DevContainer Service Manager - Intelligent service management for DevContainers."""
    if version:
        from . import __version__
        click.echo(f"DevContainer Service Manager v{__version__}")
        return
    
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path), 
              default='.devcontainer/services.yaml',
              help='Path to services configuration file')
@click.option('--namespace', '-n', help='Override namespace (default: auto-detect)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
def up(config: Path, namespace: Optional[str], dry_run: bool):
    """Start services for the current project."""
    try:
        # Initialize managers
        ns_manager = NamespaceManager()
        port_allocator = PortAllocator()
        
        # Determine namespace
        if not namespace:
            namespace = ns_manager.get_current_namespace()
        
        console.print(f"[bold blue]Starting services for namespace: {namespace}[/bold blue]")
        
        # Load configuration
        if not config.exists():
            console.print(f"[bold red]Configuration file not found: {config}[/bold red]")
            sys.exit(1)
        
        service_pool = ServicePool(namespace)
        services_config = service_pool.load_services_config(config)
        
        if dry_run:
            console.print("[bold yellow]DRY RUN - No services will be started[/bold yellow]")
        
        # Check for port conflicts
        conflicts = port_allocator.check_port_conflicts(services_config)
        if conflicts:
            console.print("[bold red]Port conflicts detected:[/bold red]")
            for conflict in conflicts:
                console.print(f"  • {conflict}")
            if not dry_run:
                sys.exit(1)
        
        # Add services to pool
        for service_name, service_config in services_config.items():
            service_pool.add_service(service_name, service_config)
        
        if dry_run:
            _show_services_table(service_pool.list_services(), "Services to be started")
            return
        
        # Start services
        with console.status("[bold green]Starting services...") as status:
            results = service_pool.start_all_services()
        
        # Show results
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        if success_count == total_count:
            console.print(f"[bold green]✓ Successfully started {success_count}/{total_count} services[/bold green]")
        else:
            console.print(f"[bold yellow]⚠ Started {success_count}/{total_count} services[/bold yellow]")
            for service_name, success in results.items():
                if not success:
                    console.print(f"  [red]✗ {service_name}[/red]")
        
        # Show service status
        status(namespace=namespace, all=False)
        
    except Exception as e:
        console.print(f"[bold red]Error starting services: {e}[/bold red]")
        sys.exit(1)


@main.command()
@click.option('--namespace', '-n', help='Namespace to stop (default: current)')
@click.option('--all', is_flag=True, help='Stop all namespaces')
def down(namespace: Optional[str], all: bool):
    """Stop services for a namespace."""
    try:
        ns_manager = NamespaceManager()
        
        if all:
            # Stop all namespaces
            active_namespaces = ns_manager.list_active_namespaces()
            for ns_info in active_namespaces:
                _stop_namespace_services(ns_info.name)
        else:
            # Stop specific or current namespace
            if not namespace:
                namespace = ns_manager.get_current_namespace()
            
            _stop_namespace_services(namespace)
        
    except Exception as e:
        console.print(f"[bold red]Error stopping services: {e}[/bold red]")
        sys.exit(1)


def _stop_namespace_services(namespace: str):
    """Stop services for a specific namespace."""
    console.print(f"[bold blue]Stopping services for namespace: {namespace}[/bold blue]")
    
    service_pool = ServicePool(namespace)
    
    with console.status("[bold yellow]Stopping services...") as status:
        # Find existing services by scanning Docker containers
        try:
            import docker
            client = docker.from_env()
            containers = client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={namespace}'
            })
            
            for container in containers:
                service_name = container.labels.get('devcontainer-service-manager.service', 'unknown')
                service_pool.services[service_name] = service_pool.ServiceInfo(
                    name=service_name,
                    namespace=namespace,
                    template='',
                    container_id=container.id
                )
        
        except ImportError:
            console.print("[yellow]Docker not available, cannot stop services[/yellow]")
            return
        
        results = service_pool.stop_all_services()
    
    # Show results
    stopped_count = sum(1 for success in results.values() if success)
    console.print(f"[bold green]✓ Stopped {stopped_count} services in namespace {namespace}[/bold green]")


@main.command()
@click.option('--namespace', '-n', help='Show specific namespace (default: current)')
@click.option('--all', is_flag=True, help='Show all namespaces')
def status(namespace: Optional[str], all: bool):
    """Show service status."""
    try:
        ns_manager = NamespaceManager()
        
        if all:
            # Show all namespaces
            active_namespaces = ns_manager.list_active_namespaces()
            if not active_namespaces:
                console.print("[yellow]No active namespaces found[/yellow]")
                return
            
            for ns_info in active_namespaces:
                _show_namespace_status(ns_info.name)
                console.print()  # Add spacing between namespaces
        else:
            # Show specific or current namespace
            if not namespace:
                namespace = ns_manager.get_current_namespace()
            
            _show_namespace_status(namespace)
        
    except Exception as e:
        console.print(f"[bold red]Error getting status: {e}[/bold red]")
        sys.exit(1)


def _show_namespace_status(namespace: str):
    """Show status for a specific namespace."""
    service_pool = ServicePool(namespace)
    
    # Try to discover existing services
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={
            'label': f'devcontainer-service-manager.namespace={namespace}'
        })
        
        if not containers:
            console.print(f"[yellow]No services found for namespace: {namespace}[/yellow]")
            return
        
        services = []
        for container in containers:
            service_name = container.labels.get('devcontainer-service-manager.service', container.name)
            template = container.labels.get('devcontainer-service-manager.template', 'unknown')
            
            # Determine status
            if container.status == 'running':
                status = ServiceStatus.HEALTHY
            elif container.status in ['exited', 'dead']:
                status = ServiceStatus.STOPPED
            else:
                status = ServiceStatus.UNHEALTHY
            
            service_info = service_pool.ServiceInfo(
                name=service_name,
                namespace=namespace,
                template=template,
                container_id=container.id,
                status=status
            )
            services.append(service_info)
        
        _show_services_table(services, f"Services in namespace: {namespace}")
        
    except ImportError:
        console.print("[yellow]Docker not available, cannot show service status[/yellow]")


def _show_services_table(services, title: str):
    """Show services in a formatted table."""
    table = Table(title=title)
    table.add_column("Service", style="cyan")
    table.add_column("Template", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Container ID", style="dim")
    
    for service in services:
        status_color = {
            ServiceStatus.HEALTHY: "green",
            ServiceStatus.UNHEALTHY: "red", 
            ServiceStatus.STOPPED: "yellow",
            ServiceStatus.STARTING: "blue",
            ServiceStatus.MISSING: "dim"
        }.get(service.status, "white")
        
        container_id = service.container_id[:12] if service.container_id else "N/A"
        
        table.add_row(
            service.name,
            service.template,
            f"[{status_color}]{service.status.value}[/{status_color}]",
            container_id
        )
    
    console.print(table)


@main.command()
@click.option('--unused', is_flag=True, help='Clean up only unused services')
@click.option('--force', is_flag=True, help='Force cleanup without confirmation')
@click.option('--namespace', '-n', help='Clean specific namespace')
def clean(unused: bool, force: bool, namespace: Optional[str]):
    """Clean up services and resources."""
    try:
        ns_manager = NamespaceManager()
        
        if namespace:
            namespaces_to_clean = [namespace]
        else:
            # Get all active namespaces
            active_namespaces = ns_manager.list_active_namespaces()
            namespaces_to_clean = [ns.name for ns in active_namespaces]
        
        if not namespaces_to_clean:
            console.print("[yellow]No namespaces to clean[/yellow]")
            return
        
        # Show what will be cleaned
        console.print("[bold yellow]The following namespaces will be cleaned:[/bold yellow]")
        for ns in namespaces_to_clean:
            console.print(f"  • {ns}")
        
        if not force:
            if not click.confirm("Are you sure you want to continue?"):
                console.print("Cleanup cancelled")
                return
        
        # Clean namespaces
        for ns in namespaces_to_clean:
            console.print(f"[blue]Cleaning namespace: {ns}[/blue]")
            ns_manager.cleanup_namespace(ns)
        
        console.print("[bold green]✓ Cleanup completed[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]Error during cleanup: {e}[/bold red]")
        sys.exit(1)


@main.command()
@click.option('--namespace', '-n', help='Check specific namespace (default: current)')
def health(namespace: Optional[str]):
    """Check service health."""
    try:
        ns_manager = NamespaceManager()
        
        if not namespace:
            namespace = ns_manager.get_current_namespace()
        
        console.print(f"[bold blue]Checking health for namespace: {namespace}[/bold blue]")
        
        health_monitor = HealthMonitor()
        service_pool = ServicePool(namespace)
        health_monitor.add_service_pool(namespace, service_pool)
        
        results = health_monitor.check_all_health()
        namespace_results = results.get(namespace, {})
        
        if not namespace_results:
            console.print("[yellow]No services found for health check[/yellow]")
            return
        
        # Show health results
        table = Table(title=f"Health Check Results: {namespace}")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green") 
        table.add_column("Last Check", style="dim")
        
        for service_name, result in namespace_results.items():
            status_color = {
                ServiceStatus.HEALTHY: "green",
                ServiceStatus.UNHEALTHY: "red",
                ServiceStatus.STOPPED: "yellow",
                ServiceStatus.MISSING: "dim"
            }.get(result.status, "white")
            
            import datetime
            check_time = datetime.datetime.fromtimestamp(result.timestamp).strftime("%H:%M:%S")
            
            table.add_row(
                service_name,
                f"[{status_color}]{result.status.value}[/{status_color}]",
                check_time
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error checking health: {e}[/bold red]")
        sys.exit(1)


@main.command()
@click.option('--service', '-s', required=True, help='Service to repair')
@click.option('--namespace', '-n', help='Namespace (default: current)')
def repair(service: str, namespace: Optional[str]):
    """Repair an unhealthy service."""
    try:
        ns_manager = NamespaceManager()
        
        if not namespace:
            namespace = ns_manager.get_current_namespace()
        
        console.print(f"[bold blue]Repairing service '{service}' in namespace: {namespace}[/bold blue]")
        
        health_monitor = HealthMonitor()
        service_pool = ServicePool(namespace)
        health_monitor.add_service_pool(namespace, service_pool)
        
        with console.status("[bold yellow]Repairing service...") as status:
            success = health_monitor.repair_service(namespace, service)
        
        if success:
            console.print(f"[bold green]✓ Successfully repaired service '{service}'[/bold green]")
        else:
            console.print(f"[bold red]✗ Failed to repair service '{service}'[/bold red]")
            sys.exit(1)
        
    except Exception as e:
        console.print(f"[bold red]Error repairing service: {e}[/bold red]")
        sys.exit(1)


@main.command('template')
@click.argument('action', type=click.Choice(['list', 'show']))
@click.argument('template_name', required=False)
def template_cmd(action: str, template_name: Optional[str]):
    """Manage service templates."""
    try:
        config_dir = Path.home() / ".devcontainer-services"
        templates_dir = config_dir / "templates"
        
        if action == 'list':
            template_files = list(templates_dir.glob("*.yaml"))
            
            if not template_files:
                console.print("[yellow]No templates found[/yellow]")
                return
            
            table = Table(title="Available Service Templates")
            table.add_column("Template", style="cyan")
            table.add_column("File", style="dim")
            
            for template_file in template_files:
                template_name = template_file.stem
                table.add_row(template_name, str(template_file))
            
            console.print(table)
        
        elif action == 'show':
            if not template_name:
                console.print("[red]Template name required for 'show' action[/red]")
                sys.exit(1)
            
            template_file = templates_dir / f"{template_name}.yaml"
            if not template_file.exists():
                console.print(f"[red]Template not found: {template_name}[/red]")
                sys.exit(1)
            
            content = template_file.read_text()
            console.print(Panel(content, title=f"Template: {template_name}"))
        
    except Exception as e:
        console.print(f"[bold red]Error managing templates: {e}[/bold red]")
        sys.exit(1)


@main.command('namespace')
@click.argument('action', type=click.Choice(['list']))
def namespace_cmd(action: str):
    """Manage namespaces."""
    try:
        if action == 'list':
            ns_manager = NamespaceManager()
            active_namespaces = ns_manager.list_active_namespaces()
            
            if not active_namespaces:
                console.print("[yellow]No active namespaces found[/yellow]")
                return
            
            table = Table(title="Active Namespaces")
            table.add_column("Namespace", style="cyan")
            table.add_column("Project", style="blue")
            table.add_column("Branch", style="green")
            table.add_column("Services", style="yellow")
            
            for ns_info in active_namespaces:
                services_count = len(ns_info.active_services)
                table.add_row(
                    ns_info.name,
                    ns_info.project,
                    ns_info.branch,
                    str(services_count)
                )
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error managing namespaces: {e}[/bold red]")
        sys.exit(1)


if __name__ == '__main__':
    main()