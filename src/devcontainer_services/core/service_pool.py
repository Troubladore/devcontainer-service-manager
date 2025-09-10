"""Service pool management with health monitoring and lifecycle control."""

import hashlib
import time
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

# Import docker at module level for mocking in tests
try:
    import docker
except ImportError:
    docker = None


class ServiceStatus(str, Enum):
    """Service status enumeration."""

    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    MISSING = "missing"


class BuildConfig(BaseModel):
    """Configuration for custom Docker builds."""

    dockerfile: str  # Path to Dockerfile
    context: str = "."  # Build context directory
    target: str | None = None  # Multi-stage build target
    args: dict[str, str] = {}  # Build arguments
    cache_from: list[str] = []  # Cache sources


class ServiceInfo(BaseModel):
    """Information about a managed service."""

    name: str
    namespace: str
    template: str
    container_id: str | None = None
    status: ServiceStatus = ServiceStatus.MISSING
    ports: dict[str, int] = {}
    depends_on: list[str] = []
    persistent: bool = True
    health_check: bool = False
    last_health_check: float | None = None


class ServicePool:
    """Manages a pool of services for a namespace."""

    def __init__(self, namespace: str, config_dir: Path | None = None):
        self.namespace = namespace
        self.config_dir = config_dir or Path.home() / ".devcontainer-services"
        self.services: dict[str, ServiceInfo] = {}
        self.templates_dir = self.config_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def load_services_config(self, config_path: Path) -> dict[str, Any]:
        """Load services configuration from YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Services config not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        return config.get("services", {})

    def add_service(self, name: str, config: dict[str, Any]) -> ServiceInfo:
        """Add a service to the pool."""
        service_info = ServiceInfo(
            name=name,
            namespace=self.namespace,
            template=config.get("template", ""),
            depends_on=config.get("depends_on", []),
            persistent=config.get("persistent", True),
            health_check=config.get("health_check", False),
        )

        self.services[name] = service_info
        return service_info

    def get_service(self, name: str) -> ServiceInfo | None:
        """Get service information."""
        return self.services.get(name)

    def list_services(self) -> list[ServiceInfo]:
        """List all services in the pool."""
        return list(self.services.values())

    def start_service(self, name: str) -> bool:
        """Start a specific service."""
        service = self.services.get(name)
        if not service:
            return False

        # Check if service is already running
        if self._is_service_running(service):
            service.status = ServiceStatus.HEALTHY
            return True

        # Start dependencies first
        for dep in service.depends_on:
            if not self.start_service(dep):
                return False

        # Load template and start service
        template_config = self._load_template(service.template)
        if not template_config:
            return False

        success = self._start_service_container(service, template_config)
        if success:
            service.status = ServiceStatus.STARTING
            # Wait a moment for container to initialize
            time.sleep(2)
            service.status = (
                ServiceStatus.HEALTHY
                if self._is_service_running(service)
                else ServiceStatus.UNHEALTHY
            )

        return success

    def stop_service(self, name: str) -> bool:
        """Stop a specific service."""
        service = self.services.get(name)
        if not service:
            return False

        success = self._stop_service_container(service)
        if success:
            service.status = ServiceStatus.STOPPED
            service.container_id = None

        return success

    def restart_service(self, name: str) -> bool:
        """Restart a specific service."""
        self.stop_service(name)
        time.sleep(1)
        return self.start_service(name)

    def start_all_services(self) -> dict[str, bool]:
        """Start all services in dependency order."""
        results = {}

        # Sort services by dependencies
        ordered_services = self._sort_services_by_dependencies()

        for service_name in ordered_services:
            results[service_name] = self.start_service(service_name)

        return results

    def stop_all_services(self) -> dict[str, bool]:
        """Stop all services."""
        results = {}

        # Stop in reverse dependency order
        ordered_services = self._sort_services_by_dependencies()
        for service_name in reversed(ordered_services):
            results[service_name] = self.stop_service(service_name)

        return results

    def check_service_health(self, name: str) -> ServiceStatus:
        """Check health of a specific service."""
        service = self.services.get(name)
        if not service:
            return ServiceStatus.MISSING

        if not service.health_check:
            # If no health check configured, just check if running
            return (
                ServiceStatus.HEALTHY
                if self._is_service_running(service)
                else ServiceStatus.STOPPED
            )

        # Perform health check
        is_healthy = self._perform_health_check(service)
        service.status = ServiceStatus.HEALTHY if is_healthy else ServiceStatus.UNHEALTHY
        service.last_health_check = time.time()

        return service.status

    def get_service_status(self) -> dict[str, ServiceStatus]:
        """Get status of all services."""
        status = {}
        for name, _service in self.services.items():
            status[name] = self.check_service_health(name)
        return status

    def _load_template(self, template: str) -> dict[str, Any] | None:
        """Load service template configuration."""
        # Handle template format like "postgres:16" or "airflow:2.9.3"
        if ":" in template:
            template_name, version = template.split(":", 1)
        else:
            template_name, version = template, "latest"

        template_file = self.templates_dir / f"{template_name}.yaml"
        if not template_file.exists():
            # Return basic template for unknown services
            return self._create_basic_template(template_name, version)

        with open(template_file) as f:
            template_config = yaml.safe_load(f)

        # Substitute version
        if "image" in template_config:
            template_config["image"] = template_config["image"].replace("{{version}}", version)

        return template_config

    def _create_basic_template(self, name: str, version: str) -> dict[str, Any]:
        """Create a basic template for unknown services."""
        return {
            "image": f"{name}:{version}",
            "container_name": f"{self.namespace}_{name}",
            "labels": {
                "devcontainer-service-manager.namespace": self.namespace,
                "devcontainer-service-manager.service": name,
            },
        }

    def _sort_services_by_dependencies(self) -> list[str]:
        """Sort services in dependency order using topological sort."""
        # Simple topological sort implementation
        visited = set()
        temp_visited = set()
        result = []

        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            if service_name in visited:
                return

            temp_visited.add(service_name)

            service = self.services.get(service_name)
            if service:
                for dep in service.depends_on:
                    if dep in self.services:
                        visit(dep)

            temp_visited.remove(service_name)
            visited.add(service_name)
            result.append(service_name)

        for service_name in self.services:
            if service_name not in visited:
                visit(service_name)

        return result

    def _is_service_running(self, service: ServiceInfo) -> bool:
        """Check if service container is running."""
        try:
            if docker is None:
                return False
            client = docker.from_env()

            # Look for container by name or labels
            containers = client.containers.list(
                filters={
                    "label": [
                        f"devcontainer-service-manager.namespace={self.namespace}",
                        f"devcontainer-service-manager.service={service.name}",
                    ]
                }
            )

            if containers:
                container = containers[0]
                service.container_id = container.id
                return container.status == "running"

        except Exception:
            pass

        return False

    def _start_service_container(
        self, service: ServiceInfo, template_config: dict[str, Any]
    ) -> bool:
        """Start service container using Docker."""
        try:
            if docker is None:
                return False
            client = docker.from_env()

            # Handle custom builds or use pre-built image
            if "build" in template_config:
                image_name = self._build_custom_image(service, template_config["build"])
                if not image_name:
                    return False
            else:
                image_name = template_config.get("image")

            if not image_name:
                print(f"No image or build configuration found for service {service.name}")
                return False

            container_config = {
                "image": image_name,
                "name": f"{self.namespace}_{service.name}",
                "labels": {
                    "devcontainer-service-manager.namespace": self.namespace,
                    "devcontainer-service-manager.service": service.name,
                    "devcontainer-service-manager.template": service.template,
                },
                "detach": True,
                "remove": False,
            }

            # Add template-specific configuration
            if "environment" in template_config:
                container_config["environment"] = template_config["environment"]

            if "ports" in template_config:
                container_config["ports"] = template_config["ports"]

            if "volumes" in template_config:
                container_config["volumes"] = template_config["volumes"]

            if "command" in template_config:
                container_config["command"] = template_config["command"]

            # Handle existing container with same name
            container_name = container_config["name"]
            try:
                existing_container = client.containers.get(container_name)
                # Check if it's our container by labels
                labels = existing_container.labels or {}
                if (
                    labels.get("devcontainer-service-manager.namespace") == self.namespace
                    and labels.get("devcontainer-service-manager.service") == service.name
                ):
                    # It's our container - try to start it if stopped
                    if existing_container.status != "running":
                        existing_container.start()
                    service.container_id = existing_container.id
                    return True
                else:
                    # It's a different container with same name - remove it
                    if existing_container.status == "running":
                        existing_container.stop(timeout=5)
                    existing_container.remove(force=True)
            except docker.errors.NotFound:
                # No existing container, proceed with creation
                pass

            # Create and start container
            container = client.containers.run(**container_config)
            service.container_id = container.id

            return True
        except Exception as e:
            print(f"Failed to start service {service.name}: {e}")
            return False

    def _stop_service_container(self, service: ServiceInfo) -> bool:
        """Stop service container."""
        try:
            if docker is None:
                return False
            client = docker.from_env()

            if service.container_id:
                container = client.containers.get(service.container_id)
                container.stop(timeout=10)
                if not service.persistent:
                    container.remove()
                return True
            else:
                # Find container by labels
                containers = client.containers.list(
                    all=True,
                    filters={
                        "label": [
                            f"devcontainer-service-manager.namespace={self.namespace}",
                            f"devcontainer-service-manager.service={service.name}",
                        ]
                    },
                )

                for container in containers:
                    container.stop(timeout=10)
                    if not service.persistent:
                        container.remove()

                return True
        except Exception as e:
            print(f"Failed to stop service {service.name}: {e}")
            return False

    def _perform_health_check(self, service: ServiceInfo) -> bool:
        """Perform health check on service."""
        if not service.container_id:
            return False

        try:
            if docker is None:
                return False
            client = docker.from_env()
            container = client.containers.get(service.container_id)

            # Check if container is running
            if container.status != "running":
                return False

            # TODO: Implement service-specific health checks
            # For now, just check if container is running
            return True
        except Exception:
            return False

    def _build_custom_image(self, service: ServiceInfo, build_config: dict[str, Any]) -> str | None:
        """Build custom Docker image with fingerprint caching."""
        try:
            if docker is None:
                return None

            # Import fingerprint system
            try:
                from devcontainer_services.caching.fingerprint import DockerBuildFingerprint
            except ImportError:
                print(
                    "Warning: Caching system not available, "
                    "building without fingerprint optimization"
                )
                return self._docker_build_simple(service, build_config)

            # Calculate build context paths
            dockerfile_path = Path(build_config["dockerfile"])
            context_path = Path(build_config.get("context", "."))

            # Make paths absolute if they're relative
            if not dockerfile_path.is_absolute():
                dockerfile_path = context_path / dockerfile_path
            if not context_path.is_absolute():
                context_path = Path.cwd() / context_path

            # Generate fingerprint for build caching
            try:
                fingerprint = DockerBuildFingerprint.compute_fingerprint(
                    context_path, dockerfile_path
                )
                fingerprint_short = fingerprint[:12]
            except Exception as e:
                print(f"Warning: Could not compute fingerprint: {e}")
                fingerprint_short = hashlib.md5(
                    f"{service.name}-{time.time()}".encode()
                ).hexdigest()[:12]

            # Generate image name with fingerprint
            image_name = f"dcsm-{self.namespace}-{service.name}:{fingerprint_short}"

            # Check if cached image exists
            client = docker.from_env()
            try:
                client.images.get(image_name)
                print(f"Using cached image: {image_name}")
                return image_name
            except docker.errors.ImageNotFound:
                pass

            # Build new image
            print(f"Building custom image: {image_name}")
            return self._docker_build(service, build_config, image_name, context_path)

        except Exception as e:
            print(f"Failed to build custom image for service {service.name}: {e}")
            return None

    def _docker_build_simple(
        self, service: ServiceInfo, build_config: dict[str, Any]
    ) -> str | None:
        """Simple Docker build without fingerprint caching."""
        image_name = f"dcsm-{self.namespace}-{service.name}:latest"
        context_path = Path(build_config.get("context", "."))
        if not context_path.is_absolute():
            context_path = Path.cwd() / context_path
        return self._docker_build(service, build_config, image_name, context_path)

    def _docker_build(
        self,
        service: ServiceInfo,
        build_config: dict[str, Any],
        image_name: str,
        context_path: Path,
    ) -> str | None:
        """Perform the actual Docker build."""
        try:
            client = docker.from_env()

            # Prepare build arguments
            build_args = {
                "dockerfile": build_config["dockerfile"],
                "tag": image_name,
                "path": str(context_path),
                "rm": True,  # Remove intermediate containers
                "forcerm": True,  # Always remove intermediate containers
            }

            # Add build target if specified
            if build_config.get("target"):
                build_args["target"] = build_config["target"]

            # Add build arguments
            if build_config.get("args"):
                build_args["buildargs"] = build_config["args"]

            # Add cache_from if specified
            if build_config.get("cache_from"):
                build_args["cache_from"] = build_config["cache_from"]

            # Perform build
            image, build_logs = client.images.build(**build_args)

            # Print build logs for debugging
            for log in build_logs:
                if "stream" in log:
                    print(log["stream"].strip())

            # Label the image for lifecycle management
            image.tag(image_name)
            client.api.tag(image.id, image_name)

            return image_name

        except Exception as e:
            print(f"Docker build failed: {e}")
            return None

    def _image_exists(self, image_name: str) -> bool:
        """Check if Docker image exists locally."""
        try:
            if docker is None:
                return False
            client = docker.from_env()
            client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            return False
        except Exception:
            return False
