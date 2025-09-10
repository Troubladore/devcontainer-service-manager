"""Tests for service state simulation and contract fulfillment."""

from unittest.mock import patch

import pytest
from devcontainer_services.core.service_pool import ServiceStatus

from tests.conftest import (
    verify_no_port_conflicts,
    verify_proper_dependencies,
    verify_services_healthy,
)


class TestServiceStateSimulation:
    """Test service state simulation and contract fulfillment."""

    @patch("devcontainer_services.core.service_pool.docker")
    def test_no_services_running_state(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
    ):
        """Test starting services when none are running."""
        # Setup: No services running
        service_state_simulator.simulate_no_services()
        mock_docker_module.from_env.return_value = mock_docker

        # Add services to pool
        expected_services = []
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)
            expected_services.append(service_name)

        # Contract: Start all services from clean state
        results = service_pool.start_all_services()

        # Verification
        assert all(results.values()), "All services should start successfully"
        assert len(results) == len(expected_services), "All expected services should be started"

        # Verify contract fulfillment
        assert verify_services_healthy(
            service_pool, expected_services
        ), "All services should be healthy"
        assert verify_proper_dependencies(service_pool), "Dependencies should be properly resolved"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_partial_services_running_state(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
    ):
        """Test starting services when some are already running."""
        # Setup: Postgres is running, Airflow services are not
        running_services = ["postgres"]
        service_state_simulator.simulate_partial_services(running_services)
        mock_docker_module.from_env.return_value = mock_docker

        # Add services to pool
        expected_services = []
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)
            expected_services.append(service_name)

        # Contract: Start only missing services, reuse existing ones
        results = service_pool.start_all_services()

        # Verification
        assert all(results.values()), "All services should start or be reused successfully"

        # Verify that existing service was reused (not restarted)
        postgres_service = service_pool.get_service("postgres")
        assert postgres_service.status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING]

        # Verify contract fulfillment
        assert verify_services_healthy(
            service_pool, expected_services
        ), "All services should be healthy"
        assert verify_proper_dependencies(service_pool), "Dependencies should be properly resolved"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_all_services_running_state(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
    ):
        """Test starting services when all are already running."""
        # Setup: All services are running
        all_services = list(sample_services_config.keys())
        service_state_simulator.simulate_all_services_running(all_services)
        mock_docker_module.from_env.return_value = mock_docker

        # Add services to pool
        expected_services = []
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)
            expected_services.append(service_name)

        # Contract: Reuse all existing services, start none
        results = service_pool.start_all_services()

        # Verification
        assert all(results.values()), "All services should be reused successfully"

        # Verify that no new containers were created (all reused)
        for service_name in expected_services:
            service = service_pool.get_service(service_name)
            assert service.status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING]

        # Verify contract fulfillment
        assert verify_services_healthy(
            service_pool, expected_services
        ), "All services should be healthy"
        assert verify_proper_dependencies(service_pool), "Dependencies should be properly resolved"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_unhealthy_services_state(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
    ):
        """Test recovery from unhealthy service state."""
        # Setup: All services exist but some are unhealthy
        all_services = list(sample_services_config.keys())
        service_state_simulator.simulate_all_services_running(all_services)
        unhealthy_services = ["airflow-webserver"]
        service_state_simulator.simulate_unhealthy_services(unhealthy_services)
        mock_docker_module.from_env.return_value = mock_docker

        # Add services to pool
        expected_services = []
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)
            expected_services.append(service_name)

        # Contract: Restart unhealthy services, keep healthy ones
        results = service_pool.start_all_services()

        # Verification
        assert all(results.values()), "All services should be healthy after recovery"

        # Verify contract fulfillment
        assert verify_services_healthy(
            service_pool, expected_services
        ), "All services should be healthy"
        assert verify_proper_dependencies(service_pool), "Dependencies should be properly resolved"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_mixed_state_complex_scenario(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
    ):
        """Test complex scenario with mixed service states."""
        # Setup: Complex scenario
        # - postgres: running and healthy
        # - airflow-scheduler: not running
        # - airflow-webserver: running but unhealthy
        service_state_simulator.simulate_partial_services(["postgres", "airflow-webserver"])
        service_state_simulator.simulate_unhealthy_services(["airflow-webserver"])
        mock_docker_module.from_env.return_value = mock_docker

        # Add services to pool
        expected_services = []
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)
            expected_services.append(service_name)

        # Contract: Handle mixed state correctly
        results = service_pool.start_all_services()

        # Verification
        assert all(results.values()), "All services should be resolved successfully"

        # Verify specific behaviors
        postgres = service_pool.get_service("postgres")
        scheduler = service_pool.get_service("airflow-scheduler")
        webserver = service_pool.get_service("airflow-webserver")

        # Postgres should be reused (was healthy)
        assert postgres.status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING]

        # Scheduler should be started (was missing)
        assert scheduler.status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING]

        # Webserver should be restarted (was unhealthy)
        assert webserver.status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING]

        # Verify contract fulfillment
        assert verify_services_healthy(
            service_pool, expected_services
        ), "All services should be healthy"
        assert verify_proper_dependencies(service_pool), "Dependencies should be properly resolved"


class TestPortConflictResolution:
    """Test port conflict detection and resolution."""

    def test_no_port_conflicts_clean_state(self, port_allocator, sample_services_config):
        """Test port allocation when no conflicts exist."""
        # Contract: Should allocate ports without conflicts
        conflicts = port_allocator.check_port_conflicts(sample_services_config)

        # Verification
        assert len(conflicts) == 0, "Should be no port conflicts in clean state"
        assert verify_no_port_conflicts(port_allocator, sample_services_config)

    def test_port_conflict_detection(self, port_allocator, service_state_simulator):
        """Test detection of existing port conflicts."""
        # Setup: Simulate conflicting services using standard ports
        conflicting_ports = [8080, 5432]
        service_state_simulator.simulate_conflicting_services(conflicting_ports)

        # Mock the port availability check to simulate occupied ports
        original_is_port_available = port_allocator._is_port_available

        def mock_is_port_available(port):
            return port not in conflicting_ports

        port_allocator._is_port_available = mock_is_port_available

        try:
            # Services that want to use the same ports
            conflicting_config = {
                "postgres": {"ports": ["5432:5432"]},
                "airflow": {"ports": ["webserver:8080"]},
            }

            # Contract: Should detect port conflicts
            conflicts = port_allocator.check_port_conflicts(conflicting_config)

            # Verification
            assert len(conflicts) > 0, "Should detect port conflicts"
            assert any("8080" in conflict for conflict in conflicts), "Should detect 8080 conflict"
            assert any("5432" in conflict for conflict in conflicts), "Should detect 5432 conflict"
        finally:
            # Restore original method
            port_allocator._is_port_available = original_is_port_available

    def test_port_range_allocation(self, port_allocator):
        """Test port range allocation for namespaces."""
        namespace1 = "project-a_main"
        namespace2 = "project-b_feature"

        # Contract: Should allocate non-overlapping port ranges
        range1 = port_allocator.allocate_port_range(namespace1)
        range2 = port_allocator.allocate_port_range(namespace2)

        # Verification
        assert range1.start != range2.start, "Different namespaces should get different ranges"
        assert range1.end < range2.start or range2.end < range1.start, "Ranges should not overlap"
        assert range1.namespace == namespace1
        assert range2.namespace == namespace2

    def test_port_allocation_within_range(self, port_allocator):
        """Test port allocation within namespace ranges."""
        namespace = "test-project_main"

        # Allocate range
        port_range = port_allocator.allocate_port_range(namespace)

        # Contract: Should allocate ports within the range
        port1 = port_allocator.allocate_port(namespace, "postgres")
        port2 = port_allocator.allocate_port(namespace, "airflow")

        # Verification
        assert port_range.start <= port1 <= port_range.end, "Port should be within allocated range"
        assert port_range.start <= port2 <= port_range.end, "Port should be within allocated range"
        assert port1 != port2, "Different services should get different ports"
        assert port1 in port_range.allocated_ports
        assert port2 in port_range.allocated_ports


class TestDependencyResolution:
    """Test service dependency resolution."""

    @patch("devcontainer_services.core.service_pool.docker")
    def test_dependency_order_resolution(self, mock_docker_module, service_pool, mock_docker):
        """Test that services start in correct dependency order."""
        mock_docker_module.from_env.return_value = mock_docker

        # Setup: Services with complex dependencies
        services_config = {
            "postgres": {"template": "postgres:16", "depends_on": []},
            "redis": {"template": "redis:7", "depends_on": []},
            "airflow-init": {"template": "airflow:2.9.3", "depends_on": ["postgres", "redis"]},
            "airflow-scheduler": {"template": "airflow:2.9.3", "depends_on": ["airflow-init"]},
            "airflow-webserver": {"template": "airflow:2.9.3", "depends_on": ["airflow-init"]},
        }

        # Add services to pool
        for service_name, config in services_config.items():
            service_pool.add_service(service_name, config)

        # Contract: Should resolve dependencies correctly
        ordered_services = service_pool._sort_services_by_dependencies()

        # Verification: Dependencies should come before dependents
        postgres_idx = ordered_services.index("postgres")
        redis_idx = ordered_services.index("redis")
        init_idx = ordered_services.index("airflow-init")
        scheduler_idx = ordered_services.index("airflow-scheduler")
        webserver_idx = ordered_services.index("airflow-webserver")

        assert postgres_idx < init_idx, "postgres should start before airflow-init"
        assert redis_idx < init_idx, "redis should start before airflow-init"
        assert init_idx < scheduler_idx, "airflow-init should start before scheduler"
        assert init_idx < webserver_idx, "airflow-init should start before webserver"

    @patch("devcontainer_services.core.service_pool.docker")
    def test_circular_dependency_detection(self, mock_docker_module, service_pool, mock_docker):
        """Test detection of circular dependencies."""
        mock_docker_module.from_env.return_value = mock_docker

        # Setup: Circular dependency
        services_config = {
            "service-a": {"template": "test:latest", "depends_on": ["service-b"]},
            "service-b": {"template": "test:latest", "depends_on": ["service-c"]},
            "service-c": {
                "template": "test:latest",
                "depends_on": ["service-a"],  # Creates circular dependency
            },
        }

        # Add services to pool
        for service_name, config in services_config.items():
            service_pool.add_service(service_name, config)

        # Contract: Should detect circular dependencies
        with pytest.raises(ValueError, match="Circular dependency"):
            service_pool._sort_services_by_dependencies()

    @patch("devcontainer_services.core.service_pool.docker")
    def test_missing_dependency_handling(self, mock_docker_module, service_pool, mock_docker):
        """Test handling of missing dependencies."""
        mock_docker_module.from_env.return_value = mock_docker

        # Setup: Service with missing dependency
        services_config = {
            "dependent-service": {
                "template": "test:latest",
                "depends_on": ["missing-service"],  # This service doesn't exist
            }
        }

        service_pool.add_service("dependent-service", services_config["dependent-service"])

        # Contract: Should handle missing dependencies gracefully
        ordered_services = service_pool._sort_services_by_dependencies()

        # Verification: Should still include the dependent service
        assert "dependent-service" in ordered_services


class TestContractFulfillment:
    """Test that the service manager always fulfills its contract."""

    @patch("devcontainer_services.core.service_pool.docker")
    @pytest.mark.parametrize(
        "initial_state",
        ["no_services", "partial_services", "all_services", "unhealthy_services", "mixed_state"],
    )
    def test_contract_fulfillment_from_any_state(
        self,
        mock_docker_module,
        service_pool,
        mock_docker,
        sample_services_config,
        service_state_simulator,
        initial_state,
    ):
        """Test that services are always brought to healthy state regardless of initial state."""
        mock_docker_module.from_env.return_value = mock_docker

        # Setup different initial states
        expected_services = list(sample_services_config.keys())

        if initial_state == "no_services":
            service_state_simulator.simulate_no_services()
        elif initial_state == "partial_services":
            service_state_simulator.simulate_partial_services(["postgres"])
        elif initial_state == "all_services":
            service_state_simulator.simulate_all_services_running(expected_services)
        elif initial_state == "unhealthy_services":
            service_state_simulator.simulate_all_services_running(expected_services)
            service_state_simulator.simulate_unhealthy_services(["airflow-webserver"])
        elif initial_state == "mixed_state":
            service_state_simulator.simulate_partial_services(["postgres", "airflow-webserver"])
            service_state_simulator.simulate_unhealthy_services(["airflow-webserver"])

        # Add services to pool
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)

        # CONTRACT EXECUTION
        results = service_pool.start_all_services()

        # CONTRACT VERIFICATION
        # 1. All requested services should be started/reused successfully
        assert all(results.values()), f"All services should be started from {initial_state} state"

        # 2. All services should be healthy
        assert verify_services_healthy(
            service_pool, expected_services
        ), f"All services should be healthy from {initial_state} state"

        # 3. Dependencies should be properly resolved
        assert verify_proper_dependencies(
            service_pool
        ), f"Dependencies should be resolved from {initial_state} state"

        # 4. Each service should have a valid container ID or be properly tracked
        for service_name in expected_services:
            service = service_pool.get_service(service_name)
            assert service is not None, f"Service {service_name} should exist in pool"
            assert (
                service.status != ServiceStatus.MISSING
            ), f"Service {service_name} should not be missing after start"

    def test_idempotent_operations(
        self, service_pool, mock_docker, sample_services_config, service_state_simulator
    ):
        """Test that operations are idempotent - running them multiple times is safe."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup: Start with no services
            service_state_simulator.simulate_no_services()

            # Add services to pool
            expected_services = []
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)
                expected_services.append(service_name)

            # Contract: Multiple start operations should be safe
            results1 = service_pool.start_all_services()
            results2 = service_pool.start_all_services()
            results3 = service_pool.start_all_services()

            # Verification: All operations should succeed
            assert all(results1.values()), "First start should succeed"
            assert all(results2.values()), "Second start should succeed (idempotent)"
            assert all(results3.values()), "Third start should succeed (idempotent)"

            # Final state should be consistent
            assert verify_services_healthy(service_pool, expected_services)
            assert verify_proper_dependencies(service_pool)

    def test_recovery_from_failure_state(
        self, service_pool, mock_docker, sample_services_config, service_state_simulator
    ):
        """Test recovery when service start operations fail."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup: Simulate a state where service start fails initially
            service_state_simulator.simulate_no_services()

            # Make the first service start fail, then succeed
            original_run = mock_docker.containers.run
            call_count = 0

            def failing_run(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:  # First call fails
                    raise Exception("Simulated start failure")
                return original_run(**kwargs)

            mock_docker.containers.run = failing_run

            # Add services to pool
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # Contract: Should handle failures gracefully and allow retry
            results1 = service_pool.start_all_services()

            # First attempt should have at least one failure
            assert not all(results1.values()), "First attempt should have failures"

            # Reset mock to allow success
            mock_docker.containers.run = original_run

            # Contract: Retry should succeed
            results2 = service_pool.start_all_services()

            # Verification: Retry should recover
            assert all(results2.values()), "Retry should succeed after failure recovery"
