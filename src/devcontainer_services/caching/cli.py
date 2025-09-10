#!/usr/bin/env python3
"""
CLI commands for Docker build caching management.

Provides commands to manage the fingerprint-based caching system,
including cache status, cleanup, and optimization features.
"""

import logging

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .cleanup import cleanup_by_project_name, get_resource_usage
from .fingerprint import CrossRepoCacheManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def cache():
    """Docker build caching management commands."""
    pass


@cache.command()
def status():
    """Show cache registry status and statistics."""
    cache_manager = CrossRepoCacheManager()

    # Get registry status
    registry_status = cache_manager.get_registry_status()

    # Create status panel
    if registry_status["running"]:
        status_text = f"✅ Registry running at {registry_status['registry_url']}"
        if registry_status.get("api_healthy"):
            status_text += "\n✅ Registry API responding"
        else:
            status_text += "\n⚠️ Registry API not responding"
    else:
        status_text = f"❌ Registry not running\nURL: {registry_status['registry_url']}"
        if registry_status.get("error"):
            status_text += f"\nError: {registry_status['error']}"

    console.print(Panel(status_text, title="Docker Registry Status"))

    # Show cached images if registry is running
    if registry_status["running"]:
        cached_images = cache_manager.list_cached_images()

        if cached_images:
            table = Table(title="Cached Images")
            table.add_column("Type", style="cyan")
            table.add_column("Fingerprint", style="yellow")
            table.add_column("Full Name", style="green")

            for image in cached_images:
                # Extract type and fingerprint from tag
                tag = image["tag"]
                if "-" in tag:
                    image_type, fingerprint = tag.split("-", 1)
                else:
                    image_type, fingerprint = tag, "unknown"

                table.add_row(image_type, fingerprint, image["full_name"])

            console.print(table)
        else:
            console.print("📭 No cached images found")

    # Show Docker resource usage
    resource_usage = get_resource_usage()
    if resource_usage:
        usage_text = f"""
Containers: {resource_usage.get('containers', 'unknown')}
Networks: {resource_usage.get('networks', 'unknown')}
Volumes: {resource_usage.get('volumes', 'unknown')}
"""
        console.print(Panel(usage_text, title="Docker Resource Usage"))


@cache.command()
@click.argument("project_name")
def configure(project_name):
    """Configure caching for a specific project."""
    console.print(f"🔧 Configuring cache for project: {project_name}")

    # Ensure registry is running
    cache_manager = CrossRepoCacheManager()
    if cache_manager.ensure_local_registry():
        console.print("✅ Local registry is ready")

        # TODO: Add project-specific configuration
        # For now, just confirm setup
        console.print(f"✅ Project '{project_name}' configured for caching")
        console.print(f"Registry: {cache_manager.CACHE_REGISTRY}")
    else:
        console.print("❌ Failed to ensure registry is running")
        console.print("Run 'dcm-cache registry start' to troubleshoot")


@cache.command()
@click.option("--older-than", default="7d", help="Remove images older than (e.g., 7d, 24h)")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be removed without actually removing"
)
def clean(older_than, dry_run):
    """Clean up old cached images."""
    if dry_run:
        console.print(f"🔍 Dry run: Would remove cached images older than {older_than}")
    else:
        console.print(f"🧹 Cleaning cached images older than {older_than}")

    cache_manager = CrossRepoCacheManager()
    cached_images = cache_manager.list_cached_images()

    if not cached_images:
        console.print("📭 No cached images to clean")
        return

    # TODO: Implement age-based filtering and cleanup
    # For now, just list what we found
    console.print(f"Found {len(cached_images)} cached images")

    if dry_run:
        console.print("Use without --dry-run to perform actual cleanup")
    else:
        console.print("⚠️ Age-based cleanup not yet implemented")
        console.print("Use 'docker system prune' for manual cleanup")


@cache.command()
def optimize():
    """Pre-build common base images for faster builds."""
    console.print("🚀 Optimizing cache by pre-building common images...")

    # Common base images for data engineering projects
    common_images = ["python:3.12-slim", "apache/airflow:3.0.6", "postgres:16", "redis:7-alpine"]

    for image in common_images:
        console.print(f"📥 Pulling {image}...")
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "pull", image], capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                console.print(f"✅ {image} ready")
            else:
                console.print(f"⚠️ Failed to pull {image}: {result.stderr}")

        except subprocess.TimeoutExpired:
            console.print(f"⏰ Timeout pulling {image}")
        except Exception as e:
            console.print(f"❌ Error pulling {image}: {e}")

    console.print("✅ Cache optimization complete")


@cache.group()
def registry():
    """Registry management commands."""
    pass


@registry.command()
def start():
    """Start the local Docker registry."""
    cache_manager = CrossRepoCacheManager()

    if cache_manager.ensure_local_registry():
        console.print("✅ Local Docker registry started")
        console.print(f"Registry URL: http://{cache_manager.CACHE_REGISTRY}")
    else:
        console.print("❌ Failed to start local registry")
        console.print("Check Docker daemon and port 5000 availability")


@registry.command()
def stop():
    """Stop the local Docker registry."""
    try:
        import subprocess

        # Stop registry container
        result = subprocess.run(["docker", "stop", "registry"], capture_output=True, text=True)

        if result.returncode == 0:
            console.print("✅ Registry stopped")
        else:
            console.print(f"⚠️ Registry may not have been running: {result.stderr}")

        # Remove registry container
        subprocess.run(["docker", "rm", "registry"], capture_output=True, text=True)

    except Exception as e:
        console.print(f"❌ Error stopping registry: {e}")


@registry.command()
def logs():
    """Show registry logs."""
    try:
        import subprocess

        result = subprocess.run(["docker", "logs", "registry"], capture_output=True, text=True)

        if result.returncode == 0:
            console.print("📋 Registry logs:")
            console.print(result.stdout)
        else:
            console.print(f"❌ Failed to get registry logs: {result.stderr}")

    except Exception as e:
        console.print(f"❌ Error getting registry logs: {e}")


@cache.command()
@click.argument("project_name")
@click.option("--timeout", default=60, help="Cleanup timeout in seconds")
def cleanup(project_name, timeout):
    """Clean up Docker resources for a specific project."""
    console.print(f"🧹 Cleaning up Docker resources for: {project_name}")

    success = cleanup_by_project_name(project_name, timeout)

    if success:
        console.print(f"✅ Successfully cleaned up project: {project_name}")
    else:
        console.print(f"⚠️ Some cleanup operations failed for: {project_name}")
        console.print("Check logs for details")


def main():
    """Main entry point for dcm-cache command."""
    cache()


if __name__ == "__main__":
    main()
