"""
Robust cleanup utilities for Docker resources.

Ensures all containers, networks, and volumes are properly cleaned up
to prevent resource leaks and conflicts between operations.

This module prevents the resource accumulation issues that can occur
during repeated Docker operations and testing.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class TestCleanupManager:
    """Manages cleanup of Docker resources created during operations."""

    def __init__(self):
        self.tracked_containers: set[str] = set()
        self.tracked_networks: set[str] = set()
        self.tracked_volumes: set[str] = set()

    def track_container(self, container_name_or_id: str):
        """Track a container for cleanup."""
        self.tracked_containers.add(container_name_or_id)

    def track_network(self, network_name: str):
        """Track a network for cleanup."""
        self.tracked_networks.add(network_name)

    def track_volume(self, volume_name: str):
        """Track a volume for cleanup."""
        self.tracked_volumes.add(volume_name)

    def cleanup_project(self, project_dir: Path, timeout: int = 60) -> bool:
        """Clean up all resources for a specific project directory.

        Args:
            project_dir: Path to project directory
            timeout: Timeout for cleanup operations

        Returns:
            True if cleanup successful, False otherwise
        """
        success = True

        compose_file = project_dir / ".devcontainer" / "compose.yaml"
        if not compose_file.exists():
            logger.warning(f"No compose file found at {compose_file}")
            return True

        try:
            # Get project name from compose file to identify resources
            project_name = self._get_compose_project_name(compose_file)

            # Stop and remove containers with volumes
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    "--timeout",
                    str(timeout // 2),
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                logger.info(f"✅ Cleaned up project: {project_dir.name}")
            else:
                logger.warning(f"⚠️ Cleanup issues for {project_dir.name}: {result.stderr}")
                success = False

            # Additional cleanup for any orphaned resources
            if project_name:
                self._cleanup_orphaned_resources(project_name)

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Cleanup timeout for {project_dir.name}")
            success = False
        except Exception as e:
            logger.error(f"❌ Cleanup error for {project_dir.name}: {e}")
            success = False

        return success

    def cleanup_by_project_name(self, project_name: str, timeout: int = 60) -> bool:
        """Clean up resources by project name pattern.

        Args:
            project_name: Project name to match containers/networks/volumes
            timeout: Timeout for cleanup operations

        Returns:
            True if cleanup successful, False otherwise
        """
        success = True

        try:
            logger.info(f"🧹 Cleaning up Docker resources for project: {project_name}")

            # Stop and remove containers matching project name
            containers = self._get_containers_by_name_pattern(project_name)
            for container in containers:
                if not self._stop_and_remove_container(container, timeout):
                    success = False

            # Remove networks matching project name
            networks = self._get_networks_by_name_pattern(project_name)
            for network in networks:
                if not self._remove_network(network):
                    success = False

            # Remove volumes matching project name
            volumes = self._get_volumes_by_name_pattern(project_name)
            for volume in volumes:
                if not self._remove_volume(volume):
                    success = False

            if success:
                logger.info(f"✅ Successfully cleaned up all resources for: {project_name}")
            else:
                logger.warning(f"⚠️ Some cleanup operations failed for: {project_name}")

        except Exception as e:
            logger.error(f"❌ Error during cleanup for {project_name}: {e}")
            success = False

        return success

    def _get_compose_project_name(self, compose_file: Path) -> str | None:
        """Extract project name from compose file."""
        try:
            content = compose_file.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    def _get_containers_by_name_pattern(self, pattern: str) -> list[str]:
        """Get container names matching a pattern."""
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={pattern}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")
        except Exception as e:
            logger.warning(f"Error getting containers for pattern {pattern}: {e}")

        return []

    def _get_networks_by_name_pattern(self, pattern: str) -> list[str]:
        """Get network names matching a pattern."""
        try:
            result = subprocess.run(
                ["docker", "network", "ls", "--filter", f"name={pattern}", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Filter out 'bridge', 'host', 'none' default networks
                networks = result.stdout.strip().split("\n")
                return [n for n in networks if n not in ["bridge", "host", "none"]]
        except Exception as e:
            logger.warning(f"Error getting networks for pattern {pattern}: {e}")

        return []

    def _get_volumes_by_name_pattern(self, pattern: str) -> list[str]:
        """Get volume names matching a pattern."""
        try:
            result = subprocess.run(
                ["docker", "volume", "ls", "--filter", f"name={pattern}", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")
        except Exception as e:
            logger.warning(f"Error getting volumes for pattern {pattern}: {e}")

        return []

    def _stop_and_remove_container(self, container: str, timeout: int = 30) -> bool:
        """Stop and remove a container."""
        try:
            # Try graceful stop first
            subprocess.run(
                ["docker", "stop", container], capture_output=True, timeout=timeout, check=False
            )

            # Force remove
            result = subprocess.run(
                ["docker", "rm", "-f", container], capture_output=True, timeout=30
            )

            if result.returncode == 0:
                logger.debug(f"Removed container: {container}")
                return True
            else:
                logger.warning(f"Failed to remove container {container}: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"Error removing container {container}: {e}")
            return False

    def _remove_network(self, network: str) -> bool:
        """Remove a network."""
        try:
            result = subprocess.run(
                ["docker", "network", "rm", network], capture_output=True, timeout=30
            )

            if result.returncode == 0:
                logger.debug(f"Removed network: {network}")
                return True
            else:
                logger.warning(f"Failed to remove network {network}: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"Error removing network {network}: {e}")
            return False

    def _remove_volume(self, volume: str) -> bool:
        """Remove a volume."""
        try:
            result = subprocess.run(
                ["docker", "volume", "rm", "-f", volume], capture_output=True, timeout=30
            )

            if result.returncode == 0:
                logger.debug(f"Removed volume: {volume}")
                return True
            else:
                logger.warning(f"Failed to remove volume {volume}: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"Error removing volume {volume}: {e}")
            return False

    def _cleanup_orphaned_resources(self, project_name: str):
        """Clean up any orphaned resources for a project."""
        try:
            # Find and remove containers with project name
            containers = self._get_containers_by_name_pattern(project_name)
            for container in containers:
                self._stop_and_remove_container(container)

            # Find and remove networks with project name
            networks = self._get_networks_by_name_pattern(project_name)
            for network in networks:
                self._remove_network(network)

            # Find and remove volumes with project name
            volumes = self._get_volumes_by_name_pattern(project_name)
            for volume in volumes:
                self._remove_volume(volume)

        except Exception as e:
            logger.warning(f"Error cleaning orphaned resources: {e}")

    def cleanup_all_tracked(self) -> bool:
        """Clean up all tracked resources."""
        success = True

        # Clean up tracked containers
        for container in self.tracked_containers:
            if not self._stop_and_remove_container(container):
                success = False

        # Clean up tracked networks
        for network in self.tracked_networks:
            if not self._remove_network(network):
                success = False

        # Clean up tracked volumes
        for volume in self.tracked_volumes:
            if not self._remove_volume(volume):
                success = False

        # Clear tracking
        self.tracked_containers.clear()
        self.tracked_networks.clear()
        self.tracked_volumes.clear()

        return success

    def emergency_cleanup(self):
        """Emergency cleanup of all test-related Docker resources."""
        logger.warning("🚨 Running emergency cleanup of all test resources")

        try:
            # Stop all containers with test-related names
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", "name=test"], capture_output=True, text=True
            )

            if result.stdout.strip():
                container_ids = result.stdout.strip().split("\n")
                subprocess.run(["docker", "stop", *container_ids], capture_output=True, timeout=60)
                subprocess.run(
                    ["docker", "rm", "-f", *container_ids], capture_output=True, timeout=60
                )

            # Clean up test networks
            result = subprocess.run(
                ["docker", "network", "ls", "-q", "--filter", "name=test"],
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                network_ids = result.stdout.strip().split("\n")
                for network_id in network_ids:
                    subprocess.run(
                        ["docker", "network", "rm", network_id], capture_output=True, timeout=30
                    )

            # Prune system
            subprocess.run(["docker", "system", "prune", "-f"], capture_output=True, timeout=120)

            logger.info("✅ Emergency cleanup completed")

        except Exception as e:
            logger.error(f"❌ Emergency cleanup failed: {e}")

    def get_resource_usage(self) -> dict:
        """Get current Docker resource usage statistics."""
        try:
            # Get container count
            result = subprocess.run(["docker", "ps", "-a", "-q"], capture_output=True, text=True)
            container_count = len([line for line in result.stdout.strip().split("\n") if line])

            # Get network count (exclude defaults)
            result = subprocess.run(
                ["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True
            )
            networks = result.stdout.strip().split("\n")
            network_count = len([n for n in networks if n not in ["bridge", "host", "none"]])

            # Get volume count
            result = subprocess.run(
                ["docker", "volume", "ls", "-q"], capture_output=True, text=True
            )
            volume_count = len([line for line in result.stdout.strip().split("\n") if line])

            # Get system disk usage
            result = subprocess.run(
                ["docker", "system", "df", "--format", "json"], capture_output=True, text=True
            )

            system_info = {}
            if result.returncode == 0 and result.stdout.strip():
                import json

                system_info = json.loads(result.stdout)

            return {
                "containers": container_count,
                "networks": network_count,
                "volumes": volume_count,
                "system_df": system_info,
            }

        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {}


# Global cleanup manager instance
_cleanup_manager = TestCleanupManager()


def register_cleanup_project(project_dir: Path):
    """Register a project for cleanup."""
    _cleanup_manager.track_container(f"{project_dir.name}-*")


def cleanup_project(project_dir: Path, timeout: int = 60) -> bool:
    """Clean up a specific project."""
    return _cleanup_manager.cleanup_project(project_dir, timeout)


def cleanup_by_project_name(project_name: str, timeout: int = 60) -> bool:
    """Clean up resources by project name."""
    return _cleanup_manager.cleanup_by_project_name(project_name, timeout)


def emergency_cleanup():
    """Run emergency cleanup of all test resources."""
    _cleanup_manager.emergency_cleanup()


def cleanup_all_tracked():
    """Clean up all tracked resources."""
    return _cleanup_manager.cleanup_all_tracked()


def get_resource_usage():
    """Get current Docker resource usage."""
    return _cleanup_manager.get_resource_usage()
