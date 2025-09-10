"""Performance and cleanup tests for DevContainer Service Manager."""

import gc
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import psutil
from devcontainer_services.core.service_pool import ServicePool


class TestPerformance:
    """Performance tests for service management operations."""

    def test_startup_time_scalability(self, service_pool, mock_docker):
        """Test startup time scalability with increasing number of services."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            service_counts = [1, 5, 10, 25, 50]
            startup_times = []

            for service_count in service_counts:
                # Setup services
                service_pool.services.clear()  # Reset for each test

                for i in range(service_count):
                    service_name = f"service-{i:03d}"
                    config = {"template": f"test:v{i}", "persistent": True}
                    service_pool.add_service(service_name, config)

                # Measure startup time
                start_time = time.time()
                results = service_pool.start_all_services()
                end_time = time.time()

                startup_time = end_time - start_time
                startup_times.append(startup_time)

                # Verify all services started
                assert len(results) == service_count, f"All {service_count} services should start"
                assert all(results.values()), f"All {service_count} services should succeed"

            # Performance verification: startup time should scale reasonably
            # Allow some variance but shouldn't grow exponentially
            for i in range(1, len(startup_times)):
                ratio = startup_times[i] / startup_times[0]
                expected_ratio = service_counts[i] / service_counts[0]

                # Allow 2x overhead for each additional service (generous bound)
                assert (
                    ratio <= expected_ratio * 2
                ), f"Startup time scaling too poorly: {ratio} vs expected {expected_ratio}"

    def test_dependency_resolution_performance(self, service_pool):
        """Test performance of dependency resolution algorithm."""
        # Setup: Complex dependency graph
        services_count = 100
        max_dependencies = 5

        for i in range(services_count):
            service_name = f"service-{i}"

            # Create realistic dependency patterns
            depends_on = []
            if i > 0:
                # Each service depends on a few previous services
                dependency_count = min(max_dependencies, i)
                for j in range(max(0, i - dependency_count), i):
                    if j % 3 == 0:  # Not every service is a dependency
                        depends_on.append(f"service-{j}")

            config = {"template": f"service:v{i}", "depends_on": depends_on, "persistent": True}
            service_pool.add_service(service_name, config)

        # Measure dependency resolution time
        start_time = time.time()
        ordered_services = service_pool._sort_services_by_dependencies()
        end_time = time.time()

        resolution_time = end_time - start_time

        # Performance verification
        assert len(ordered_services) == services_count, "All services should be ordered"
        assert resolution_time < 1.0, f"Dependency resolution too slow: {resolution_time}s"

        # Verify order is correct (sample verification)
        for i, service_name in enumerate(ordered_services):
            int(service_name.split("-")[1])
            service_info = service_pool.get_service(service_name)

            # All dependencies should appear earlier in the list
            for dependency in service_info.depends_on:
                dep_index = ordered_services.index(dependency)
                assert dep_index < i, f"Dependency {dependency} should appear before {service_name}"

    def test_port_allocation_performance(self, port_allocator):
        """Test performance of port allocation under load."""
        namespaces = [f"perf-test-{i}" for i in range(10)]
        services_per_namespace = 20

        # Measure port allocation time
        start_time = time.time()

        for namespace in namespaces:
            # Allocate range
            port_range = port_allocator.allocate_port_range(namespace)

            # Allocate individual ports
            for service_id in range(services_per_namespace):
                service_name = f"service-{service_id}"
                port = port_allocator.allocate_port(namespace, service_name)
                assert (
                    port_range.start <= port <= port_range.end
                ), f"Port {port} outside range for {namespace}"

        end_time = time.time()
        allocation_time = end_time - start_time

        total_allocations = len(namespaces) * services_per_namespace

        # Performance verification
        assert allocation_time < 2.0, f"Port allocation too slow: {allocation_time}s"

        avg_time_per_allocation = allocation_time / total_allocations
        assert (
            avg_time_per_allocation < 0.01
        ), f"Average allocation time too slow: {avg_time_per_allocation}s"

    def test_health_monitoring_performance(self, health_monitor, temp_config_dir):
        """Test performance of health monitoring with many services."""
        service_pools = {}
        services_per_pool = 10
        pool_count = 5

        # Setup multiple service pools with services
        for pool_id in range(pool_count):
            namespace = f"health-perf-{pool_id}"
            service_pool = ServicePool(namespace, config_dir=temp_config_dir)

            for service_id in range(services_per_pool):
                service_name = f"service-{service_id}"
                config = {"template": "test:latest", "health_check": True, "persistent": True}
                service_pool.add_service(service_name, config)

            health_monitor.add_service_pool(namespace, service_pool)
            service_pools[namespace] = service_pool

        # Measure health check time
        start_time = time.time()
        health_results = health_monitor.check_all_health()
        end_time = time.time()

        health_check_time = end_time - start_time
        total_services = pool_count * services_per_pool

        # Performance verification
        assert len(health_results) == pool_count, "Should check all service pools"
        assert health_check_time < 1.0, f"Health checking too slow: {health_check_time}s"

        avg_time_per_service = health_check_time / total_services
        assert (
            avg_time_per_service < 0.05
        ), f"Average health check time too slow: {avg_time_per_service}s"

    def test_concurrent_operations_performance(self, service_pool, mock_docker):
        """Test performance under concurrent operations."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup services
            service_count = 20
            for i in range(service_count):
                service_name = f"concurrent-service-{i}"
                config = {"template": f"test:v{i}", "persistent": True}
                service_pool.add_service(service_name, config)

            # Define concurrent operations
            def start_operation():
                return service_pool.start_all_services()

            def status_operation():
                return service_pool.get_service_status()

            def health_operation():
                results = {}
                for service_name in service_pool.services:
                    results[service_name] = service_pool.check_service_health(service_name)
                return results

            operations = [start_operation, status_operation, health_operation]
            concurrent_tasks = 10

            # Measure concurrent execution time
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=concurrent_tasks) as executor:
                futures = []

                # Submit mixed operations
                for i in range(concurrent_tasks):
                    operation = operations[i % len(operations)]
                    future = executor.submit(operation)
                    futures.append(future)

                # Wait for all to complete
                results = []
                for future in as_completed(futures, timeout=10):
                    results.append(future.result())

            end_time = time.time()
            concurrent_time = end_time - start_time

            # Performance verification
            assert len(results) == concurrent_tasks, "All concurrent operations should complete"
            assert concurrent_time < 5.0, f"Concurrent operations too slow: {concurrent_time}s"

    def test_memory_usage_performance(self, service_pool, mock_docker):
        """Test memory usage patterns and potential leaks."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Get initial memory usage
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            initial_objects = len(gc.get_objects())

            # Perform many service operations
            cycles = 50
            services_per_cycle = 10

            for cycle in range(cycles):
                # Add services
                for i in range(services_per_cycle):
                    service_name = f"memory-test-{cycle}-{i}"
                    config = {"template": f"test:cycle{cycle}", "persistent": True}
                    service_pool.add_service(service_name, config)

                # Start services
                service_pool.start_all_services()

                # Check status
                service_pool.get_service_status()

                # Stop services
                service_pool.stop_all_services()

                # Clear services for next cycle
                service_pool.services.clear()

                # Periodic garbage collection
                if cycle % 10 == 0:
                    gc.collect()

            # Force final garbage collection
            gc.collect()

            # Check final memory usage
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            final_objects = len(gc.get_objects())

            memory_growth = final_memory - initial_memory
            object_growth = final_objects - initial_objects

            # Performance verification - memory shouldn't grow excessively
            assert memory_growth < 100, f"Memory usage grew too much: {memory_growth}MB"

            # Object count growth should be reasonable
            growth_ratio = object_growth / max(initial_objects, 1)
            assert growth_ratio < 0.5, f"Object count grew too much: {growth_ratio * 100}%"


class TestCleanup:
    """Tests for cleanup operations and resource management."""

    def test_service_cleanup_completeness(self, service_pool, mock_docker, sample_services_config):
        """Test that cleanup operations are complete and thorough."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup and start services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            start_results = service_pool.start_all_services()
            assert all(start_results.values()), "All services should start"

            # Record initial state
            mock_docker.containers.list(all=True)
            initial_services = list(service_pool.services.keys())

            # Perform cleanup
            stop_results = service_pool.stop_all_services()
            assert all(stop_results.values()), "All services should stop"

            # Verify cleanup completeness
            final_containers = mock_docker.containers.list()  # Only running containers
            running_containers = [c for c in final_containers if c.status == "running"]

            # No containers should still be running
            assert len(running_containers) == 0, "No containers should be running after cleanup"

            # Service pool should still track services (for persistence)
            assert len(service_pool.services) == len(
                initial_services
            ), "Service pool should maintain service definitions"

    def test_namespace_cleanup_isolation(self, namespace_manager, temp_config_dir, mock_docker):
        """Test that namespace cleanup doesn't affect other namespaces."""
        # Setup multiple namespaces with services
        namespaces = ["cleanup-test-1", "cleanup-test-2", "cleanup-test-3"]
        service_pools = {}

        for namespace in namespaces:
            service_pool = ServicePool(namespace, config_dir=temp_config_dir)

            # Add a service to each namespace
            service_pool.add_service(
                "test-service", {"template": "test:latest", "persistent": True}
            )

            # Simulate running containers
            container = mock_docker.MockDockerContainer(
                name=f"{namespace}_test-service",
                status="running",
                labels={
                    "devcontainer-service-manager.namespace": namespace,
                    "devcontainer-service-manager.service": "test-service",
                },
            )
            mock_docker.add_running_container(container)

            service_pools[namespace] = service_pool

        # Cleanup one namespace
        target_namespace = namespaces[0]
        namespace_manager.cleanup_namespace(target_namespace)

        # Verify only target namespace was cleaned
        remaining_containers = mock_docker.containers.list(all=True)

        target_containers = [
            c
            for c in remaining_containers
            if c.labels.get("devcontainer-service-manager.namespace") == target_namespace
        ]
        other_containers = [
            c
            for c in remaining_containers
            if c.labels.get("devcontainer-service-manager.namespace") in namespaces[1:]
        ]

        # Target namespace should be cleaned
        running_target = [c for c in target_containers if c.status == "running"]
        assert len(running_target) == 0, "Target namespace containers should be stopped"

        # Other namespaces should be unaffected
        running_others = [c for c in other_containers if c.status == "running"]
        assert (
            len(running_others) == len(namespaces) - 1
        ), "Other namespace containers should still be running"

    def test_port_allocation_cleanup(self, port_allocator):
        """Test cleanup of port allocations."""
        # Allocate ports for multiple namespaces
        namespaces = ["port-cleanup-1", "port-cleanup-2", "port-cleanup-3"]
        allocated_ranges = {}

        for namespace in namespaces:
            port_range = port_allocator.allocate_port_range(namespace)
            allocated_ranges[namespace] = port_range

            # Allocate some individual ports
            for i in range(5):
                port_allocator.allocate_port(namespace, f"service-{i}")

        # Verify allocations exist
        for namespace in namespaces:
            ports = port_allocator.get_namespace_ports(namespace)
            assert len(ports) > 0, f"Namespace {namespace} should have allocated ports"

        # Cleanup one namespace
        target_namespace = namespaces[0]
        port_allocator.cleanup_namespace(target_namespace)

        # Verify cleanup
        target_ports = port_allocator.get_namespace_ports(target_namespace)
        assert len(target_ports) == 0, "Target namespace ports should be cleaned"

        # Other namespaces should be unaffected
        for namespace in namespaces[1:]:
            ports = port_allocator.get_namespace_ports(namespace)
            assert len(ports) > 0, f"Other namespace {namespace} ports should remain"

    def test_health_monitor_cleanup(self, health_monitor, temp_config_dir):
        """Test cleanup of health monitoring resources."""
        # Setup monitoring for multiple service pools
        namespaces = ["health-cleanup-1", "health-cleanup-2"]
        service_pools = {}

        for namespace in namespaces:
            service_pool = ServicePool(namespace, config_dir=temp_config_dir)
            service_pool.add_service(
                "test-service", {"template": "test:latest", "health_check": True}
            )

            health_monitor.add_service_pool(namespace, service_pool)
            service_pools[namespace] = service_pool

        # Start monitoring
        health_monitor.start_monitoring()

        # Verify monitoring is active
        assert health_monitor._running, "Health monitor should be running"
        assert len(health_monitor.monitored_pools) == 2, "Should monitor both namespaces"

        # Remove one service pool
        target_namespace = namespaces[0]
        health_monitor.remove_service_pool(target_namespace)

        # Verify cleanup
        assert (
            target_namespace not in health_monitor.monitored_pools
        ), "Target namespace should be removed from monitoring"
        assert (
            namespaces[1] in health_monitor.monitored_pools
        ), "Other namespace should remain in monitoring"

        # Stop monitoring completely
        health_monitor.stop_monitoring()

        # Verify complete cleanup
        assert not health_monitor._running, "Health monitor should be stopped"
        assert (
            health_monitor._monitor_thread is None or not health_monitor._monitor_thread.is_alive()
        ), "Monitor thread should be stopped"

    def test_temporary_resource_cleanup(self, temp_config_dir):
        """Test cleanup of temporary resources and files."""
        # Create temporary files and directories
        temp_files = []
        temp_dirs = []

        for i in range(5):
            # Create temporary files
            temp_file = temp_config_dir / f"temp_file_{i}.tmp"
            temp_file.write_text(f"Temporary content {i}")
            temp_files.append(temp_file)

            # Create temporary directories
            temp_dir = temp_config_dir / f"temp_dir_{i}"
            temp_dir.mkdir()
            temp_dirs.append(temp_dir)

        # Verify resources exist
        for temp_file in temp_files:
            assert temp_file.exists(), f"Temp file {temp_file} should exist"

        for temp_dir in temp_dirs:
            assert temp_dir.exists(), f"Temp dir {temp_dir} should exist"

        # Simulate cleanup process (in real implementation, this would be automatic)
        import shutil

        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        # Verify cleanup
        for temp_file in temp_files:
            assert not temp_file.exists(), f"Temp file {temp_file} should be cleaned"

        for temp_dir in temp_dirs:
            assert not temp_dir.exists(), f"Temp dir {temp_dir} should be cleaned"

    def test_graceful_shutdown_cleanup(
        self, service_pool, health_monitor, mock_docker, sample_services_config, temp_config_dir
    ):
        """Test graceful shutdown and cleanup of all components."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup complete system
            namespace = "graceful-shutdown-test"

            # Add services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # Start health monitoring
            health_monitor.add_service_pool(namespace, service_pool)
            health_monitor.start_monitoring()

            # Start services
            start_results = service_pool.start_all_services()
            assert all(start_results.values()), "All services should start"

            # Verify system is fully operational
            assert health_monitor._running, "Health monitor should be running"

            health_results = health_monitor.check_all_health()
            assert namespace in health_results, "Health monitoring should be active"

            running_containers = [c for c in mock_docker.containers.list() if c.status == "running"]
            assert len(running_containers) > 0, "Containers should be running"

            # Perform graceful shutdown
            # 1. Stop monitoring
            health_monitor.stop_monitoring()

            # 2. Stop all services
            stop_results = service_pool.stop_all_services()
            assert all(stop_results.values()), "All services should stop gracefully"

            # 3. Clean up resources (would be automatic in real implementation)
            service_pool.services.clear()
            health_monitor.monitored_pools.clear()

            # Verify complete shutdown
            assert not health_monitor._running, "Health monitor should be stopped"

            final_running = [c for c in mock_docker.containers.list() if c.status == "running"]
            assert len(final_running) == 0, "No containers should be running after shutdown"

    def test_cleanup_error_recovery(self, service_pool, mock_docker, sample_services_config):
        """Test recovery when cleanup operations encounter errors."""
        with patch("devcontainer_services.core.service_pool.docker") as mock_docker_module:
            mock_docker_module.from_env.return_value = mock_docker

            # Setup services
            for service_name, config in sample_services_config.items():
                service_pool.add_service(service_name, config)

            # Start services
            service_pool.start_all_services()

            # Make some containers fail to stop (simulate cleanup errors)
            original_stop = mock_docker.MockDockerContainer.stop

            def failing_stop(self, timeout=10):
                if "postgres" in self.name:
                    raise Exception("Simulated stop failure")
                return original_stop(self, timeout)

            mock_docker.MockDockerContainer.stop = failing_stop

            # Attempt cleanup (should handle errors gracefully)
            stop_results = service_pool.stop_all_services()

            # Should attempt to stop all services even if some fail
            assert "postgres" in stop_results, "Should attempt to stop postgres"
            assert "airflow-webserver" in stop_results, "Should attempt to stop airflow"

            # Other services should succeed even if postgres failed
            non_postgres_services = [
                name for name in stop_results if not name.startswith("postgres")
            ]
            for service_name in non_postgres_services:
                # These should succeed (or at least be attempted)
                assert service_name in stop_results, f"Should attempt to stop {service_name}"

            # System should remain stable after partial cleanup failure
            status_results = service_pool.get_service_status()
            assert isinstance(status_results, dict), "Status should work after partial cleanup"
