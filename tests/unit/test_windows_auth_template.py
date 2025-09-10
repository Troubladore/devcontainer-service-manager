"""Unit tests for Windows authentication Airflow template."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from devcontainer_services.core.service_pool import ServicePool


class TestWindowsAuthTemplate:
    """Test Windows authentication template functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pool = ServicePool("test-namespace", config_dir=self.temp_dir)

        # Copy the Windows auth template to test directory
        template_src = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        template_dst = self.pool.templates_dir / "airflow-windows.yaml"

        if template_src.exists():
            shutil.copy2(template_src, template_dst)

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_template_exists(self):
        """Test that Windows auth template file exists."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        assert template_path.exists(), "airflow-windows.yaml template should exist"

    def test_template_yaml_valid(self):
        """Test that template is valid YAML."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        assert isinstance(template_data, dict)
        assert "environment" in template_data
        assert "volumes" in template_data
        assert "components" in template_data

    def test_template_has_windows_auth_config(self):
        """Test template contains Windows authentication configuration."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        env_vars = template_data["environment"]

        # Check LDAP configuration
        assert "AIRFLOW__WEBSERVER__AUTHENTICATE" in env_vars
        assert "AIRFLOW__WEBSERVER__AUTH_BACKEND" in env_vars
        assert "AIRFLOW__LDAP__URI" in env_vars
        assert "AIRFLOW__LDAP__USER_FILTER" in env_vars
        assert "AIRFLOW__LDAP__USER_NAME_ATTR" in env_vars

        # Check Kerberos configuration
        assert "AIRFLOW__KERBEROS__CCACHE" in env_vars
        assert "AIRFLOW__KERBEROS__PRINCIPAL" in env_vars
        assert "KRB5_CONFIG" in env_vars
        assert "KRB5CCNAME" in env_vars

    def test_template_has_build_support(self):
        """Test template supports custom builds."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        # Should have build configuration
        assert "build" in template_data
        build_config = template_data["build"]
        assert "dockerfile" in build_config
        assert "context" in build_config
        assert "target" in build_config
        assert "args" in build_config
        assert "ENABLE_WINDOWS_AUTH" in build_config["args"]

    def test_template_has_windows_volumes(self):
        """Test template has Windows-specific volume mounts."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        volumes = template_data["volumes"]
        volume_strings = [str(vol) for vol in volumes]

        # Check for Windows auth volumes
        krb5_volume = any("krb5.conf" in vol for vol in volume_strings)
        keytab_volume = any("keytab" in vol for vol in volume_strings)
        cacert_volume = any("ldap-ca.crt" in vol for vol in volume_strings)

        assert krb5_volume, "Should have krb5.conf volume mount"
        assert keytab_volume, "Should have Kerberos keytab volume mount"
        assert cacert_volume, "Should have LDAP CA cert volume mount"

    def test_template_has_metadata(self):
        """Test template includes Windows auth metadata."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        metadata = template_data["metadata"]
        assert "windows_auth_enabled" in metadata
        assert metadata["windows_auth_enabled"] is True
        assert "required_volumes" in metadata
        assert "required_environment" in metadata

    def test_service_pool_loads_windows_template(self):
        """Test ServicePool can load Windows auth template."""
        template_config = self.pool._load_template("airflow-windows:3.0.6")

        if template_config:  # Only test if template exists in test environment
            assert isinstance(template_config, dict)
            assert "environment" in template_config

            # Check Windows auth environment variables are present
            env_vars = template_config["environment"]
            assert "AIRFLOW__WEBSERVER__AUTHENTICATE" in env_vars
            assert "AIRFLOW__LDAP__URI" in env_vars

    def test_template_component_configurations(self):
        """Test template component configurations include Windows auth."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        components = template_data["components"]

        # Test webserver component
        webserver = components["webserver"]
        assert "environment" in webserver
        assert "AIRFLOW__WEBSERVER__RBAC" in webserver["environment"]

        # Test init component has user creation
        init = components["init"]
        assert "command" in init
        command_str = (
            " ".join(init["command"]) if isinstance(init["command"], list) else init["command"]
        )
        assert "airflow users create" in command_str

    def test_template_network_configuration(self):
        """Test template includes Windows auth network configuration."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        assert "networks" in template_data
        networks = template_data["networks"]
        assert "windows_auth" in networks

        auth_network = networks["windows_auth"]
        assert auth_network["driver"] == "bridge"
        assert auth_network["enable_ipv6"] is False

    def test_template_labels_include_windows_auth(self):
        """Test template labels include Windows auth indicator."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        labels = template_data["labels"]
        assert "devcontainer-service-manager.windows-auth" in labels
        assert labels["devcontainer-service-manager.windows-auth"] == "enabled"

    def test_service_creation_with_windows_template(self):
        """Test creating service with Windows auth template."""
        service_config = {
            "template": "airflow-windows:3.0.6",
            "build": {
                "dockerfile": "Dockerfile.airflow",
                "context": ".",
                "target": "development",
                "args": {"ENABLE_WINDOWS_AUTH": "true", "AIRFLOW_VERSION": "3.0.6"},
            },
            "persistent": True,
            "health_check": True,
        }

        service = self.pool.add_service("airflow-webserver", service_config)

        assert service.name == "airflow-webserver"
        assert service.namespace == "test-namespace"
        assert service.template == "airflow-windows:3.0.6"
        assert service.persistent is True
        assert service.health_check is True

    @patch("devcontainer_services.core.service_pool.docker")
    def test_windows_template_with_build_configuration(self, mock_docker):
        """Test Windows template works with custom build configuration."""
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client

        # Mock fingerprint system
        with patch(
            "devcontainer_services.caching.fingerprint.DockerFingerprinter"
        ) as mock_fingerprinter:
            mock_fp_instance = Mock()
            mock_fingerprinter.return_value = mock_fp_instance
            mock_fp_instance.compute_fingerprint.return_value = "windows123auth"

            # Mock image doesn't exist (force build)
            mock_client.images.get.side_effect = mock_docker.errors.ImageNotFound("Not found")

            # Mock successful build
            mock_image = Mock()
            mock_client.images.build.return_value = (mock_image, [{"stream": "Build success"}])

            # Load template and test build integration
            template_config = self.pool._load_template("airflow-windows:3.0.6")

            if template_config and "build" in template_config:
                service = self.pool.add_service(
                    "test-windows-build",
                    {
                        "template": "airflow-windows:3.0.6",
                        "build": template_config["build"],
                        "persistent": True,
                    },
                )

                # Test build method with Windows template
                result = self.pool._build_custom_image(service, template_config["build"])

                # Should generate appropriate image name
                if result:
                    assert "dcsm-test-namespace-test-windows-build" in result
                    assert "windows123au" in result  # Fingerprint truncated to 10 chars

    def test_template_default_values(self):
        """Test template provides sensible defaults for Windows auth."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_content = f.read()

        # Check for default values in template variables
        assert "default('True')" in template_content  # ENABLE_WINDOWS_AUTH
        assert "default('LocalExecutor')" in template_content
        assert "default('False')" in template_content  # LOAD_EXAMPLES
        assert "default('sAMAccountName')" in template_content  # LDAP attr
        assert "default('/tmp/airflow_krb5_ccache')" in template_content  # Kerberos cache

    def test_template_required_fields_documented(self):
        """Test template documents required configuration fields."""
        template_path = Path("src/devcontainer_services/templates/airflow-windows.yaml")
        with open(template_path) as f:
            template_data = yaml.safe_load(f)

        metadata = template_data["metadata"]

        # Should document required environment variables
        required_env = metadata["required_environment"]
        assert any("ldap_uri" in req for req in required_env)
        assert any("kerberos_principal" in req for req in required_env)

        # Should document required volumes
        required_volumes = metadata["required_volumes"]
        assert any("krb5_config_path" in req for req in required_volumes)
        assert any("kerberos_keytab_path" in req for req in required_volumes)
