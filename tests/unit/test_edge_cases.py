"""Tests for edge cases and error handling scenarios."""

import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from devcontainer_services.core.health_monitor import HealthMonitor
from devcontainer_services.core.service_pool import ServicePool


class TestErrorHandling:
    """Test error handling in various failure scenarios."""

    @patch("devcontainer_services.core.service_pool.docker")
    def test_docker_unavailable(self, mock_docker_module, service_pool, sample_services_config):
        """Test behavior when Docker is not available."""
        # Simulate Docker import failure
        mock_docker_module.from_env.side_effect = ImportError("Docker not available")

        # Add services to pool
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)

        # Contract: Should handle Docker unavailability gracefully
        results = service_pool.start_all_services()

        # Verification: Should not crash, but services won't start
        assert isinstance(results, dict), "Should return results dict even when Docker unavailable"
        # Results may be False but should not raise exception

    @patch("devcontainer_services.core.service_pool.docker")
    def test_docker_connection_failure(
        self, mock_docker_module, service_pool, mock_docker, sample_services_config
    ):
        """Test behavior when Docker connection fails."""
        # Setup Docker to fail on connection
        mock_docker_module.from_env.side_effect = Exception("Docker daemon not running")

        # Add services to pool
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)

        # Contract: Should handle connection failures gracefully
        results = service_pool.start_all_services()

        # Verification: Should not crash
        assert isinstance(results, dict), "Should handle Docker connection failure gracefully"

    def test_invalid_template_handling(self, service_pool, temp_config_dir):
        """Test handling of invalid service templates."""
        # Setup: Add service with non-existent template
        invalid_config = {"template": "nonexistent-service:latest", "persistent": True}

        service_pool.add_service("invalid-service", invalid_config)

        # Contract: Should handle invalid templates gracefully
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker = MagicMock()
            mock_docker_module.from_env.return_value = mock_docker

            results = service_pool.start_all_services()

            # Should not crash, even with invalid template
            assert "invalid-service" in results

    def test_corrupted_config_handling(self, service_pool):
        """Test handling of corrupted service configuration."""
        # Setup: Add service with malformed configuration
        corrupted_configs = [
            {"template": None},  # Missing template
            {"template": ""},  # Empty template
            {"template": "valid:tag", "depends_on": "not-a-list"},  # Wrong type
            {"template": "valid:tag", "ports": {"not": "valid"}},  # Wrong port format
        ]

        for i, config in enumerate(corrupted_configs):
            service_name = f"corrupted-{i}"
            service_pool.add_service(service_name, config)

        # Contract: Should handle corrupted configs gracefully
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker = MagicMock()
            mock_docker_module.from_env.return_value = mock_docker

            # Should not crash even with corrupted configs
            results = service_pool.start_all_services()
            assert isinstance(results, dict)

    def test_resource_exhaustion_handling(self, port_allocator):
        """Test handling when system resources are exhausted."""
        # Simulate port exhaustion by allocating many ranges
        allocated_namespaces = []

        # Try to exhaust port ranges (this should eventually fail gracefully)
        try:
            for i in range(1000):  # Try to allocate way too many ranges
                namespace = f"namespace-{i}"
                port_allocator.allocate_port_range(namespace, required_ports=100)
                allocated_namespaces.append(namespace)
        except RuntimeError as e:
            # Expected: Should eventually hit resource limits gracefully
            assert "Unable to find available port range" in str(e)

        # System should still be functional for cleanup
        for namespace in allocated_namespaces[:10]:  # Clean up a few
            port_allocator.cleanup_namespace(namespace)

    def test_concurrent_access_safety(self, service_pool, sample_services_config):
        """Test thread safety under concurrent access."""
        # Setup services
        for service_name, config in sample_services_config.items():
            service_pool.add_service(service_name, config)

        results = []
        exceptions = []

        def concurrent_start():
            try:
                with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
                    mock_docker = MagicMock()
                    mock_docker_module.from_env.return_value = mock_docker
                    result = service_pool.start_all_services()
                    results.append(result)
            except Exception as e:
                exceptions.append(e)

        # Start multiple concurrent operations
        threads = []
        for _i in range(5):
            thread = threading.Thread(target=concurrent_start)
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=5)

        # Verification: Should not have unhandled exceptions
        assert len(exceptions) == 0, f"Concurrent access caused exceptions: {exceptions}"
        assert len(results) == 5, "All concurrent operations should complete"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_service_configuration(self, service_pool):
        """Test handling empty service configurations."""
        # Setup: Empty services config

        # Contract: Should handle empty config gracefully
        results = service_pool.start_all_services()

        assert results == {}, "Empty configuration should return empty results"

    def test_single_service_configuration(self, service_pool):
        """Test configuration with only one service."""
        # Setup: Single service
        single_config = {"template": "postgres:16", "persistent": True}

        service_pool.add_service("single-service", single_config)

        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker = MagicMock()
            mock_docker_module.from_env.return_value = mock_docker

            results = service_pool.start_all_services()

            assert "single-service" in results
            assert len(results) == 1

    def test_deep_dependency_chain(self, service_pool):
        """Test handling of deep dependency chains."""
        # Setup: Create a deep dependency chain
        chain_length = 10
        chain_services = {}

        for i in range(chain_length):
            service_name = f"service-{i}"
            depends_on = [f"service-{i-1}"] if i > 0 else []

            chain_services[service_name] = {
                "template": f"service:v{i}",
                "depends_on": depends_on,
                "persistent": True,
            }
            service_pool.add_service(service_name, chain_services[service_name])

        # Contract: Should handle deep dependency chains
        ordered_services = service_pool._sort_services_by_dependencies()

        # Verification: Services should be in correct order
        assert len(ordered_services) == chain_length
        for i in range(chain_length):
            expected_service = f"service-{i}"
            assert expected_service in ordered_services
            # Each service should come after its dependency
            if i > 0:
                dependency = f"service-{i-1}"
                dep_index = ordered_services.index(dependency)
                service_index = ordered_services.index(expected_service)
                assert (
                    dep_index < service_index
                ), f"Dependency order violated for {expected_service}"

    def test_self_dependency(self, service_pool):
        """Test handling of self-referential dependencies."""
        # Setup: Service that depends on itself
        self_dependent_config = {
            "template": "circular:latest",
            "depends_on": ["self-service"],  # Depends on itself
        }

        service_pool.add_service("self-service", self_dependent_config)

        # Contract: Should detect and handle self-dependency
        with pytest.raises(ValueError, match="Circular dependency"):
            service_pool._sort_services_by_dependencies()

    def test_multiple_circular_dependencies(self, service_pool):
        """Test detection of complex circular dependencies."""
        # Setup: Multiple circular dependency scenarios
        circular_configs = {
            # Simple cycle: A -> B -> A
            "service-a": {"template": "test:latest", "depends_on": ["service-b"]},
            "service-b": {"template": "test:latest", "depends_on": ["service-a"]},
            # Longer cycle: C -> D -> E -> C
            "service-c": {"template": "test:latest", "depends_on": ["service-d"]},
            "service-d": {"template": "test:latest", "depends_on": ["service-e"]},
            "service-e": {"template": "test:latest", "depends_on": ["service-c"]},
        }

        for service_name, config in circular_configs.items():
            service_pool.add_service(service_name, config)

        # Contract: Should detect circular dependencies
        with pytest.raises(ValueError, match="Circular dependency"):
            service_pool._sort_services_by_dependencies()

    def test_very_long_service_names(self, namespace_manager):
        """Test handling of very long service and namespace names."""
        # Setup: Very long names
        long_project = "a" * 100
        long_branch = "b" * 100

        # Test namespace creation with long names
        with patch.object(namespace_manager, "_detect_project_name", return_value=long_project):
            with patch.object(namespace_manager, "_get_current_branch", return_value=long_branch):
                namespace = namespace_manager.get_current_namespace()

                # Should handle long names gracefully (possibly truncating)
                assert len(namespace) <= 150, "Namespace should be reasonably bounded"
                assert namespace is not None
                assert len(namespace) > 0

    def test_special_characters_in_names(self, namespace_manager):
        """Test handling of special characters in names."""
        # Setup: Names with special characters
        special_project = "my-project@#$%^&*()"
        special_branch = "feature/fix-bug#123"

        with patch.object(namespace_manager, "_detect_project_name", return_value=special_project):
            with patch.object(
                namespace_manager, "_get_current_branch", return_value=special_branch
            ):
                namespace = namespace_manager.get_current_namespace()

                # Should sanitize special characters
                assert "@" not in namespace, "Special characters should be sanitized"
                assert "#" not in namespace, "Special characters should be sanitized"
                assert "/" not in namespace, "Special characters should be sanitized"
                assert len(namespace) > 0, "Should not result in empty namespace"

    def test_port_allocation_boundary_conditions(self, port_allocator):
        """Test port allocation at boundary conditions."""
        # Test allocation at port limits
        namespace = "boundary-test"

        # Allocate a range
        port_range = port_allocator.allocate_port_range(namespace)

        # Try to allocate all ports in the range
        allocated_ports = []
        for i in range(port_range.end - port_range.start + 1):
            try:
                port = port_allocator.allocate_port(namespace, f"service-{i}")
                allocated_ports.append(port)
            except RuntimeError:
                # Expected when range is exhausted
                break

        # Should have allocated some ports
        assert len(allocated_ports) > 0, "Should allocate at least some ports"

        # All allocated ports should be in range
        for port in allocated_ports:
            assert (
                port_range.start <= port <= port_range.end
            ), f"Port {port} outside allocated range {port_range.start}-{port_range.end}"

    def test_health_monitor_edge_cases(self, health_monitor, service_pool):
        """Test health monitor edge cases."""
        # Setup: Empty service pool
        health_monitor.add_service_pool("empty-namespace", service_pool)

        # Should handle empty service pools
        results = health_monitor.check_all_health()
        assert "empty-namespace" in results
        assert results["empty-namespace"] == {}

        # Test monitoring non-existent service
        result = health_monitor.check_service_health("empty-namespace", "non-existent")
        assert result is None, "Should handle non-existent service gracefully"

    def test_rapid_state_changes(self, service_pool, sample_services_config):
        """Test handling of rapid state changes."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker = MagicMock()
            mock_docker_module.from_env.return_value = mock_docker

            # Setup services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # Perform rapid start/stop operations
            for _i in range(10):
                service_pool.start_all_services()
                service_pool.stop_all_services()

            # Final state should be consistent
            final_results = service_pool.start_all_services()
            assert isinstance(final_results, dict)
            assert len(final_results) == len(sample_services_config)


class TestBoundaryConditions:
    """Test system behavior at boundary conditions."""

    def test_maximum_services_limit(self, service_pool):
        """Test behavior with maximum number of services."""
        # Setup: Large number of services
        max_services = 100

        for i in range(max_services):
            service_name = f"service-{i:03d}"
            config = {"template": f"service:v{i}", "persistent": True}
            service_pool.add_service(service_name, config)

        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker = MagicMock()
            mock_docker_module.from_env.return_value = mock_docker

            # Should handle large number of services
            results = service_pool.start_all_services()

            assert len(results) == max_services, "Should handle maximum number of services"

    def test_zero_timeout_conditions(self, health_monitor):
        """Test behavior with zero or very small timeouts."""
        # Setup health monitor with minimal timeout
        fast_monitor = HealthMonitor(check_interval=0.1)

        # Should handle fast checking gracefully
        fast_monitor.start_monitoring()
        time.sleep(0.2)  # Let it run briefly
        fast_monitor.stop_monitoring()

        # Should not crash with fast intervals
        assert not fast_monitor._running, "Monitor should stop cleanly"

    def test_system_resource_limits(self, port_allocator):
        """Test behavior near system resource limits."""
        # Test with system port limits
        try:
            # Try to bind to port 0 (should get any available port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", 0))
            sock.getsockname()[1]
            sock.close()

            # Port allocator should respect actually available ports
            namespace = "resource-test"
            port_range = port_allocator.allocate_port_range(namespace)

            # Should not allocate ports outside reasonable ranges
            assert 1024 <= port_range.start <= 65535, "Should allocate reasonable port range"
            assert port_range.start < port_range.end, "Range should be valid"

        except Exception:
            # If we can't test with real sockets, at least verify range logic
            namespace = "resource-test"
            port_range = port_allocator.allocate_port_range(namespace)
            assert port_range.start > 0
            assert port_range.end > port_range.start

    def test_configuration_size_limits(self, temp_config_dir):
        """Test handling of very large configurations."""
        # Create a very large service configuration
        large_config = {}

        # Add many services with complex configurations
        for i in range(50):
            large_config[f"service-{i}"] = {
                "template": f"large-service:v{i}",
                "environment": {f"VAR_{j}": f"value_{j}" for j in range(20)},
                "depends_on": [f"service-{j}" for j in range(max(0, i - 3), i)],
                "persistent": True,
                "health_check": True,
            }

        # Write large config to file
        import yaml

        config_file = temp_config_dir / "large-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"services": large_config}, f)

        # Should handle large configurations
        service_pool = ServicePool("large-test", config_dir=temp_config_dir)
        loaded_config = service_pool.load_services_config(config_file)

        assert len(loaded_config) == 50, "Should load large configuration"

    def test_memory_usage_patterns(self, service_pool, sample_services_config):
        """Test memory usage patterns under various conditions."""
        import gc

        # Get initial memory usage
        initial_objects = len(gc.get_objects())

        # Perform many operations
        for cycle in range(10):
            # Add services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(f"{service_name}-{cycle}", config)

            with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
                mock_docker = MagicMock()
                mock_docker_module.from_env.return_value = mock_docker

                # Start and stop services
                service_pool.start_all_services()
                service_pool.stop_all_services()

            # Clear services for next cycle
            service_pool.services.clear()

            # Force garbage collection
            gc.collect()

        # Check final memory usage
        final_objects = len(gc.get_objects())

        # Memory usage should not grow excessively
        # (This is a rough check, exact numbers vary by Python implementation)
        growth_ratio = final_objects / initial_objects
        assert growth_ratio < 2.0, f"Memory usage grew too much: {growth_ratio}x"


class TestRecoveryScenarios:
    """Test recovery from various failure scenarios."""

    def test_recovery_from_partial_corruption(
        self, service_pool, mock_docker, sample_services_config, service_state_simulator
    ):
        """Test recovery when some services are corrupted."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup: Some services in corrupted state
            service_state_simulator.simulate_partial_services(["postgres"])

            # Corrupt one container (simulate corruption)
            postgres_container = None
            for container in mock_docker.containers._containers.values():
                if "postgres" in container.name:
                    postgres_container = container
                    break

            if postgres_container:
                # Simulate container corruption
                postgres_container.status = "dead"
                postgres_container.labels = {}  # Lost labels

            # Setup services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # Should recover from corruption
            results = service_pool.start_all_services()

            # Should handle corrupted services
            assert isinstance(results, dict)
            assert "postgres" in results

    def test_recovery_from_network_isolation(self, service_pool, sample_services_config):
        """Test recovery when services are network-isolated."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            # Simulate network connectivity issues
            mock_docker = MagicMock()
            mock_docker.from_env.side_effect = [
                Exception("Network timeout"),  # First call fails
                MagicMock(),  # Second call succeeds
            ]
            mock_docker_module.from_env = mock_docker.from_env

            # Setup services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # First attempt should handle network issues
            results1 = service_pool.start_all_services()

            # Second attempt should succeed
            results2 = service_pool.start_all_services()

            # Should handle network recovery
            assert isinstance(results1, dict)
            assert isinstance(results2, dict)

    def test_recovery_from_resource_exhaustion(self, port_allocator):
        """Test recovery after resource exhaustion."""
        # Setup: Exhaust resources
        allocated_namespaces = []

        # Allocate many ranges to approach exhaustion
        for i in range(10):
            try:
                namespace = f"exhaust-{i}"
                port_allocator.allocate_port_range(namespace)
                allocated_namespaces.append(namespace)
            except RuntimeError:
                break

        # Clean up some resources
        for namespace in allocated_namespaces[:5]:
            port_allocator.cleanup_namespace(namespace)

        # Should be able to allocate again after cleanup
        recovery_namespace = "recovery-test"
        recovery_range = port_allocator.allocate_port_range(recovery_namespace)

        assert recovery_range is not None, "Should recover after resource cleanup"
        assert recovery_range.namespace == recovery_namespace
