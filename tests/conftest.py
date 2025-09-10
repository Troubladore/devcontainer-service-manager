"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from devcontainer_services.core.health_monitor import HealthMonitor
from devcontainer_services.core.namespace_manager import NamespaceManager
from devcontainer_services.core.port_allocator import PortAllocator
from devcontainer_services.core.service_pool import ServicePool, ServiceStatus


class MockDockerContainer:
    """Mock Docker container for testing."""

    def __init__(self, name: str, status: str = "running", labels: dict[str, str] | None = None):
        self.name = name
        self.id = f"mock-{name}-{int(time.time())}"
        self.status = status
        self.labels = labels or {}
        self.ports = {}

    def stop(self, timeout: int = 10):
        self.status = "exited"

    def remove(self):
        self.status = "removed"

    def restart(self):
        self.status = "running"


class MockDockerClient:
    """Mock Docker client for testing."""

    def __init__(self):
        self.containers = MockContainerManager()
        self.networks = MockNetworkManager()
        self._running_containers: dict[str, MockDockerContainer] = {}

    def from_env(self):
        return self

    def add_running_container(self, container: MockDockerContainer):
        """Add a container to the mock environment."""
        self._running_containers[container.name] = container
        self.containers._containers[container.name] = container

    def remove_container(self, name: str):
        """Remove a container from the mock environment."""
        if name in self._running_containers:
            del self._running_containers[name]
        if name in self.containers._containers:
            del self.containers._containers[name]


class MockContainerManager:
    """Mock container manager."""

    def __init__(self):
        self._containers: dict[str, MockDockerContainer] = {}

    def list(self, all: bool = False, filters: dict | None = None) -> list[MockDockerContainer]:
        containers = []

        for container in self._containers.values():
            # Apply status filter
            if not all and container.status != "running":
                continue

            # Apply label filters
            if filters and "label" in filters:
                label_filters = filters["label"]
                if isinstance(label_filters, str):
                    label_filters = [label_filters]

                matches = True
                for label_filter in label_filters:
                    if "=" in label_filter:
                        key, value = label_filter.split("=", 1)
                        if container.labels.get(key) != value:
                            matches = False
                            break
                    else:
                        if label_filter not in container.labels:
                            matches = False
                            break

                if not matches:
                    continue

            containers.append(container)

        return containers

    def get(self, container_id: str) -> MockDockerContainer:
        for container in self._containers.values():
            if container.id == container_id:
                return container
        raise Exception(f"Container {container_id} not found")

    def run(self, **kwargs) -> MockDockerContainer:
        name = kwargs.get("name", f"container-{len(self._containers)}")
        labels = kwargs.get("labels", {})

        container = MockDockerContainer(name=name, labels=labels)
        self._containers[name] = container
        return container


class MockNetworkManager:
    """Mock network manager."""

    def __init__(self):
        self._networks = []

    def list(self) -> list:
        return self._networks

    def create(self, name: str):
        network = Mock()
        network.name = name
        self._networks.append(network)
        return network


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    temp_dir = tempfile.mkdtemp()
    config_dir = Path(temp_dir) / ".devcontainer-services"
    config_dir.mkdir(parents=True)

    # Create templates directory with basic templates
    templates_dir = config_dir / "templates"
    templates_dir.mkdir()

    # Create basic postgres template
    postgres_template = templates_dir / "postgres.yaml"
    postgres_template.write_text(
        """
image: "postgres:{{version}}"
container_name: "{{namespace}}_postgres"
environment:
  POSTGRES_DB: "test"
  POSTGRES_USER: "test"
  POSTGRES_PASSWORD: "test"
labels:
  devcontainer-service-manager.namespace: "{{namespace}}"
  devcontainer-service-manager.service: "postgres"
"""
    )

    # Create basic airflow template
    airflow_template = templates_dir / "airflow.yaml"
    airflow_template.write_text(
        """
image: "apache/airflow:{{version}}"
container_name: "{{namespace}}_airflow_{{component}}"
environment:
  AIRFLOW__CORE__EXECUTOR: "LocalExecutor"
labels:
  devcontainer-service-manager.namespace: "{{namespace}}"
  devcontainer-service-manager.service: "airflow-{{component}}"
"""
    )

    yield config_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_docker():
    """Mock Docker client."""
    return MockDockerClient()


@pytest.fixture
def namespace_manager(temp_config_dir):
    """Create a namespace manager with temporary config."""
    return NamespaceManager(config_dir=temp_config_dir)


@pytest.fixture
def port_allocator():
    """Create a port allocator."""
    return PortAllocator()


@pytest.fixture
def service_pool(temp_config_dir):
    """Create a service pool."""
    return ServicePool("test-namespace", config_dir=temp_config_dir)


@pytest.fixture
def health_monitor():
    """Create a health monitor."""
    return HealthMonitor(check_interval=1)  # Fast checking for tests


@pytest.fixture
def sample_services_config():
    """Sample services configuration for testing."""
    return {
        "postgres": {"template": "postgres:16", "persistent": True, "health_check": True},
        "airflow-scheduler": {
            "template": "airflow:2.9.3",
            "component": "scheduler",
            "depends_on": ["postgres"],
            "persistent": True,
            "health_check": True,
        },
        "airflow-webserver": {
            "template": "airflow:2.9.3",
            "component": "webserver",
            "depends_on": ["postgres"],
            "persistent": True,
            "health_check": True,
            "ports": ["webserver:8080"],
        },
    }


@pytest.fixture
def services_config_file(temp_config_dir, sample_services_config):
    """Create a services configuration file."""
    import yaml

    config_file = temp_config_dir / "test-services.yaml"
    config_content = {"namespace": "test-project", "services": sample_services_config}

    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    return config_file


class ServiceStateSimulator:
    """Helper class to simulate various service states."""

    def __init__(self, mock_docker: MockDockerClient, namespace: str = "test-project"):
        self.mock_docker = mock_docker
        self.namespace = namespace

    def simulate_no_services(self):
        """Simulate state where no services are running."""
        # Clear all containers
        self.mock_docker.containers._containers.clear()
        self.mock_docker._running_containers.clear()

    def simulate_partial_services(self, running_services: list[str]):
        """Simulate state where only some services are running."""
        self.simulate_no_services()

        for service_name in running_services:
            container = MockDockerContainer(
                name=f"{self.namespace}_{service_name}",
                status="running",
                labels={
                    "devcontainer-service-manager.namespace": self.namespace,
                    "devcontainer-service-manager.service": service_name,
                },
            )
            self.mock_docker.add_running_container(container)

    def simulate_all_services_running(self, service_names: list[str]):
        """Simulate state where all services are running."""
        self.simulate_partial_services(service_names)

    def simulate_unhealthy_services(self, unhealthy_services: list[str]):
        """Simulate state where some services are unhealthy."""
        for service_name in unhealthy_services:
            container_name = f"{self.namespace}_{service_name}"
            if container_name in self.mock_docker.containers._containers:
                container = self.mock_docker.containers._containers[container_name]
                container.status = "exited"

    def simulate_conflicting_services(self, conflicting_ports: list[int]):
        """Simulate state where services are using conflicting ports."""
        for i, port in enumerate(conflicting_ports):
            container = MockDockerContainer(name=f"conflicting-service-{i}", status="running")
            container.ports = {f"{port}/tcp": [{"HostPort": str(port)}]}
            self.mock_docker.add_running_container(container)


@pytest.fixture
def service_state_simulator(mock_docker):
    """Create a service state simulator."""
    return ServiceStateSimulator(mock_docker)


# Contract verification helpers
def verify_services_healthy(service_pool: ServicePool, expected_services: list[str]) -> bool:
    """Verify that all expected services are healthy."""
    status = service_pool.get_service_status()

    for service_name in expected_services:
        if service_name not in status:
            return False
        if status[service_name] != ServiceStatus.HEALTHY:
            return False

    return True


def verify_no_port_conflicts(
    port_allocator: PortAllocator, services_config: dict[str, Any]
) -> bool:
    """Verify that no port conflicts exist."""
    conflicts = port_allocator.check_port_conflicts(services_config)
    return len(conflicts) == 0


def verify_proper_dependencies(service_pool: ServicePool) -> bool:
    """Verify that service dependencies are properly resolved."""
    # Check that services are started in dependency order
    # This is a simplified check - in a real scenario we'd verify timing
    for _service_name, service_info in service_pool.services.items():
        for dependency in service_info.depends_on:
            if dependency not in service_pool.services:
                return False

            dep_service = service_pool.services[dependency]
            if (
                dep_service.status == ServiceStatus.MISSING
                and service_info.status == ServiceStatus.HEALTHY
            ):
                return False

    return True
