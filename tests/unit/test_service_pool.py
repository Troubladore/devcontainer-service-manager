"""Unit tests for service pool with custom build support."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devcontainer_services.core.service_pool import (
    BuildConfig,
    ServiceInfo,
    ServicePool,
)


class TestBuildConfig:
    """Test BuildConfig model."""

    def test_build_config_minimal(self):
        """Test BuildConfig with minimal parameters."""
        config = BuildConfig(dockerfile="Dockerfile")
        assert config.dockerfile == "Dockerfile"
        assert config.context == "."
        assert config.target is None
        assert config.args == {}
        assert config.cache_from == []

    def test_build_config_full(self):
        """Test BuildConfig with all parameters."""
        config = BuildConfig(
            dockerfile="Dockerfile.airflow",
            context="./build",
            target="development",
            args={"AIRFLOW_VERSION": "3.0.6", "ENABLE_AUTH": "true"},
            cache_from=["airflow:latest", "python:3.12"],
        )
        assert config.dockerfile == "Dockerfile.airflow"
        assert config.context == "./build"
        assert config.target == "development"
        assert config.args == {"AIRFLOW_VERSION": "3.0.6", "ENABLE_AUTH": "true"}
        assert config.cache_from == ["airflow:latest", "python:3.12"]

    def test_build_config_serialization(self):
        """Test BuildConfig serialization."""
        config = BuildConfig(
            dockerfile="Dockerfile.test", target="production", args={"TEST": "value"}
        )
        data = config.model_dump()
        assert data["dockerfile"] == "Dockerfile.test"
        assert data["context"] == "."
        assert data["target"] == "production"
        assert data["args"] == {"TEST": "value"}


class TestServicePool:
    """Test ServicePool functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pool = ServicePool("test-namespace", config_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_service_pool_init(self):
        """Test ServicePool initialization."""
        assert self.pool.namespace == "test-namespace"
        assert self.pool.config_dir == self.temp_dir
        assert self.pool.services == {}
        assert self.pool.templates_dir.exists()

    def test_add_service_with_build_config(self):
        """Test adding service with build configuration."""
        service_config = {
            "template": "airflow:3.0.6",
            "build": {
                "dockerfile": "Dockerfile.airflow",
                "context": ".",
                "target": "development",
                "args": {"AIRFLOW_VERSION": "3.0.6"},
            },
            "persistent": True,
            "health_check": True,
        }

        service = self.pool.add_service("airflow-webserver", service_config)

        assert service.name == "airflow-webserver"
        assert service.namespace == "test-namespace"
        assert service.template == "airflow:3.0.6"
        assert service.persistent is True
        assert service.health_check is True

    def test_add_service_with_image_config(self):
        """Test adding service with traditional image configuration."""
        service_config = {"template": "postgres:16", "image": "postgres:16", "persistent": True}

        service = self.pool.add_service("postgres", service_config)

        assert service.name == "postgres"
        assert service.template == "postgres:16"
        assert service.persistent is True

    def test_get_service(self):
        """Test getting service information."""
        service_config = {"template": "test:latest"}
        self.pool.add_service("test-service", service_config)

        service = self.pool.get_service("test-service")
        assert service is not None
        assert service.name == "test-service"

        missing_service = self.pool.get_service("nonexistent")
        assert missing_service is None

    def test_list_services(self):
        """Test listing all services."""
        assert self.pool.list_services() == []

        self.pool.add_service("service1", {"template": "test:1"})
        self.pool.add_service("service2", {"template": "test:2"})

        services = self.pool.list_services()
        assert len(services) == 2
        assert services[0].name in ["service1", "service2"]
        assert services[1].name in ["service1", "service2"]

    def test_build_custom_image_no_docker(self):
        """Test build custom image when Docker is not available."""
        with patch("devcontainer_services.core.service_pool.docker", None):
            result = self.pool._build_custom_image(
                ServiceInfo(name="test", namespace="test", template="test"),
                {"dockerfile": "Dockerfile", "context": "."},
            )
            assert result is None

    @patch("devcontainer_services.core.service_pool.docker")
    def test_build_custom_image_no_fingerprint_system(self, mock_docker):
        """Test build custom image without fingerprint system."""
        mock_docker.from_env.return_value = Mock()

        with patch.object(self.pool, "_docker_build_simple") as mock_build:
            mock_build.return_value = "test-image:latest"

            result = self.pool._build_custom_image(
                ServiceInfo(name="test", namespace="test", template="test"),
                {"dockerfile": "Dockerfile", "context": "."},
            )

            mock_build.assert_called_once()
            assert result == "test-image:latest"

    @patch("devcontainer_services.core.service_pool.docker")
    @patch("devcontainer_services.caching.fingerprint.DockerFingerprinter")
    def test_build_custom_image_with_caching(self, mock_fingerprint, mock_docker):
        """Test build custom image with fingerprint caching."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_fingerprint_instance = Mock()
        mock_fingerprint.return_value = mock_fingerprint_instance
        mock_fingerprint_instance.compute_fingerprint.return_value = "abc123def456"

        # Mock cached image exists
        mock_client.images.get.return_value = Mock()

        result = self.pool._build_custom_image(
            ServiceInfo(name="test", namespace="test", template="test"),
            {"dockerfile": "Dockerfile", "context": "."},
        )

        expected_image = "dcsm-test-test:abc123def456"
        assert result == expected_image
        mock_client.images.get.assert_called_once_with(expected_image)

    @patch("devcontainer_services.core.service_pool.docker")
    def test_docker_build_simple(self, mock_docker):
        """Test simple Docker build without caching."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client

        with patch.object(self.pool, "_docker_build") as mock_build:
            mock_build.return_value = "test-image:latest"

            service = ServiceInfo(name="test", namespace="test", template="test")
            build_config = {"dockerfile": "Dockerfile", "context": "."}

            result = self.pool._docker_build_simple(service, build_config)

            mock_build.assert_called_once()
            assert result == "test-image:latest"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_docker_build_success(self, mock_docker):
        """Test successful Docker build."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client

        # Mock successful build
        mock_image = Mock()
        mock_client.images.build.return_value = (mock_image, [{"stream": "Build log"}])

        service = ServiceInfo(name="test", namespace="test", template="test")
        build_config = {
            "dockerfile": "Dockerfile",
            "context": ".",
            "target": "development",
            "args": {"TEST": "value"},
            "cache_from": ["test:latest"],
        }

        result = self.pool._docker_build(service, build_config, "test-image:tag", Path("."))

        assert result == "test-image:tag"
        mock_client.images.build.assert_called_once()

        # Verify build arguments
        build_call = mock_client.images.build.call_args
        assert build_call[1]["dockerfile"] == "Dockerfile"
        assert build_call[1]["target"] == "development"
        assert build_call[1]["buildargs"] == {"TEST": "value"}
        assert build_call[1]["cache_from"] == ["test:latest"]

    @patch("devcontainer_services.core.service_pool.docker")
    def test_docker_build_failure(self, mock_docker):
        """Test Docker build failure."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.build.side_effect = Exception("Build failed")

        service = ServiceInfo(name="test", namespace="test", template="test")
        build_config = {"dockerfile": "Dockerfile", "context": "."}

        result = self.pool._docker_build(service, build_config, "test-image:tag", Path("."))

        assert result is None

    @patch("devcontainer_services.core.service_pool.docker")
    def test_image_exists_true(self, mock_docker):
        """Test image exists check when image is found."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = Mock()  # Image found

        result = self.pool._image_exists("test-image:latest")
        assert result is True

    @patch("devcontainer_services.core.service_pool.docker")
    def test_image_exists_false(self, mock_docker):
        """Test image exists check when image is not found."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.side_effect = mock_docker.errors.ImageNotFound("Not found")

        result = self.pool._image_exists("test-image:latest")
        assert result is False

    def test_image_exists_no_docker(self):
        """Test image exists check when Docker is not available."""
        with patch("devcontainer_services.core.service_pool.docker", None):
            result = self.pool._image_exists("test-image:latest")
            assert result is False

    @patch("devcontainer_services.core.service_pool.docker")
    def test_start_service_container_with_build(self, mock_docker):
        """Test starting container with build configuration."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client

        with patch.object(self.pool, "_build_custom_image") as mock_build:
            mock_build.return_value = "custom-image:abc123"
            mock_client.containers.get.side_effect = mock_docker.errors.NotFound("Not found")
            mock_client.containers.run.return_value = Mock(id="container123")

            service = ServiceInfo(name="test", namespace="test", template="test")
            template_config = {"build": {"dockerfile": "Dockerfile", "context": "."}}

            result = self.pool._start_service_container(service, template_config)

            assert result is True
            mock_build.assert_called_once()
            mock_client.containers.run.assert_called_once()

    @patch("devcontainer_services.core.service_pool.docker")
    def test_start_service_container_with_image(self, mock_docker):
        """Test starting container with image configuration."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.get.side_effect = mock_docker.errors.NotFound("Not found")
        mock_client.containers.run.return_value = Mock(id="container123")

        service = ServiceInfo(name="test", namespace="test", template="test")
        template_config = {"image": "postgres:16"}

        result = self.pool._start_service_container(service, template_config)

        assert result is True
        mock_client.containers.run.assert_called_once()

        # Verify image was used
        run_call = mock_client.containers.run.call_args
        assert run_call[1]["image"] == "postgres:16"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_start_service_container_no_config(self, mock_docker):
        """Test starting container with neither build nor image configuration."""
        service = ServiceInfo(name="test", namespace="test", template="test")
        template_config = {}  # No image or build config

        result = self.pool._start_service_container(service, template_config)

        assert result is False

    def test_sort_services_by_dependencies(self):
        """Test dependency sorting."""
        # Add services with dependencies
        self.pool.add_service("postgres", {"template": "postgres:16", "depends_on": []})
        self.pool.add_service(
            "airflow-init", {"template": "airflow:3.0.6", "depends_on": ["postgres"]}
        )
        self.pool.add_service(
            "airflow-webserver", {"template": "airflow:3.0.6", "depends_on": ["airflow-init"]}
        )

        sorted_services = self.pool._sort_services_by_dependencies()

        # postgres should come first, then airflow-init, then airflow-webserver
        postgres_idx = sorted_services.index("postgres")
        init_idx = sorted_services.index("airflow-init")
        webserver_idx = sorted_services.index("airflow-webserver")

        assert postgres_idx < init_idx < webserver_idx

    def test_sort_services_circular_dependency(self):
        """Test handling of circular dependencies."""
        # Add services with circular dependencies
        self.pool.add_service("service-a", {"template": "test:1", "depends_on": ["service-b"]})
        self.pool.add_service("service-b", {"template": "test:2", "depends_on": ["service-a"]})

        with pytest.raises(ValueError, match="Circular dependency detected"):
            self.pool._sort_services_by_dependencies()
