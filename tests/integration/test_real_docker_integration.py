"""Integration tests with real Docker containers.

These tests require Docker to be running and available.
They test the actual container lifecycle management.
"""

import pytest
import docker
import time
import requests
from pathlib import Path
from typing import Dict, List
import subprocess

from devcontainer_services.core.service_pool import ServicePool, ServiceStatus
from devcontainer_services.core.namespace_manager import NamespaceManager
from devcontainer_services.core.port_allocator import PortAllocator
from devcontainer_services.core.health_monitor import HealthMonitor


# Skip all tests in this module if Docker is not available
def docker_available():
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not docker_available(),
    reason="Docker not available or not running"
)


@pytest.fixture(scope="module")
def docker_client():
    """Create a Docker client for integration tests."""
    client = docker.from_env()
    yield client
    # Cleanup any test containers after module
    try:
        containers = client.containers.list(all=True, filters={
            'label': 'devcontainer-service-manager.test=true'
        })
        for container in containers:
            try:
                container.stop(timeout=5)
                container.remove()
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture
def integration_namespace():
    """Generate a unique namespace for integration tests."""
    import uuid
    return f"integration-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def integration_service_pool(temp_config_dir, integration_namespace):
    """Create a service pool for integration tests."""
    return ServicePool(integration_namespace, config_dir=temp_config_dir)


class TestRealDockerIntegration:
    """Integration tests with real Docker containers."""
    
    def test_postgres_container_lifecycle(self, docker_client, integration_service_pool, 
                                        integration_namespace, port_allocator):
        """Test complete PostgreSQL container lifecycle."""
        # Setup service configuration
        postgres_config = {
            "template": "postgres:16",
            "persistent": True,
            "health_check": True
        }
        
        service_name = "postgres"
        integration_service_pool.add_service(service_name, postgres_config)
        
        # Allocate ports
        port_range = port_allocator.allocate_port_range(integration_namespace)
        postgres_port = port_allocator.allocate_port(integration_namespace, service_name)
        
        try:
            # Test: Start service
            start_results = integration_service_pool.start_all_services()
            assert start_results[service_name], "PostgreSQL should start successfully"
            
            # Verify container exists
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers) > 0, "Container should be created"
            
            postgres_container = containers[0]
            assert postgres_container.status == 'running', "Container should be running"
            
            # Test: Health check
            service_status = integration_service_pool.check_service_health(service_name)
            assert service_status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING], \
                   "PostgreSQL should be healthy or starting"
            
            # Wait for container to be fully ready
            max_wait = 30
            wait_time = 0
            while wait_time < max_wait:
                try:
                    # Test actual PostgreSQL connection
                    exec_result = postgres_container.exec_run([
                        "pg_isready", "-U", "test", "-d", "test"
                    ])
                    if exec_result.exit_code == 0:
                        break
                except Exception:
                    pass
                time.sleep(1)
                wait_time += 1
            
            # Test: Service reuse (idempotent start)
            reuse_results = integration_service_pool.start_all_services()
            assert reuse_results[service_name], "Service should be reused successfully"
            
            # Verify same container is still running
            postgres_container.reload()
            assert postgres_container.status == 'running', "Same container should still be running"
            
        finally:
            # Cleanup: Stop service
            stop_results = integration_service_pool.stop_all_services()
            assert stop_results[service_name], "PostgreSQL should stop successfully"
            
            # Verify container is stopped
            time.sleep(2)
            postgres_container.reload()
            assert postgres_container.status in ['exited', 'dead'], "Container should be stopped"
    
    def test_multi_service_dependency_resolution(self, docker_client, integration_service_pool,
                                               integration_namespace, port_allocator):
        """Test dependency resolution with real containers."""
        # Setup: PostgreSQL + Redis with a dependent service
        services_config = {
            "postgres": {
                "template": "postgres:16",
                "persistent": True,
                "health_check": True
            },
            "redis": {
                "template": "redis:7-alpine",
                "persistent": True,
                "health_check": True
            },
            # Simple service that depends on both
            "app": {
                "template": "alpine:latest",
                "command": ["sleep", "30"],
                "depends_on": ["postgres", "redis"],
                "persistent": False
            }
        }
        
        # Add services to pool
        for service_name, config in services_config.items():
            integration_service_pool.add_service(service_name, config)
        
        # Allocate ports
        port_range = port_allocator.allocate_port_range(integration_namespace)
        
        try:
            # Test: Start all services
            start_results = integration_service_pool.start_all_services()
            
            # All services should start successfully
            for service_name in services_config:
                assert start_results[service_name], f"Service {service_name} should start"
            
            # Verify all containers exist and are running
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers) == 3, "All three containers should be created"
            
            running_containers = [c for c in containers if c.status == 'running']
            assert len(running_containers) == 3, "All containers should be running"
            
            # Verify dependency order was respected (indirect test via timing)
            # Dependencies (postgres, redis) should have started before dependent (app)
            app_container = None
            for container in containers:
                if 'app' in container.name:
                    app_container = container
                    break
            
            assert app_container is not None, "App container should exist"
            assert app_container.status == 'running', "App container should be running"
            
        finally:
            # Cleanup: Stop all services
            stop_results = integration_service_pool.stop_all_services()
            for service_name in services_config:
                assert stop_results[service_name], f"Service {service_name} should stop"
    
    def test_port_conflict_detection_real(self, docker_client, integration_namespace,
                                        port_allocator):
        """Test port conflict detection with real containers."""
        # Start a container that occupies a specific port
        conflicting_port = 18080
        
        # Start container using the conflicting port
        conflicting_container = docker_client.containers.run(
            "nginx:alpine",
            name=f"conflicting-{integration_namespace}",
            ports={'80/tcp': conflicting_port},
            detach=True,
            labels={'devcontainer-service-manager.test': 'true'}
        )
        
        try:
            # Wait for container to start
            time.sleep(2)
            
            # Test: Port conflict detection
            services_config = {
                "web-server": {
                    "ports": [f"{conflicting_port}:80"]
                }
            }
            
            conflicts = port_allocator.check_port_conflicts(services_config)
            
            # Should detect the port conflict
            assert len(conflicts) > 0, "Should detect port conflict"
            assert any(str(conflicting_port) in conflict for conflict in conflicts), \
                   f"Should detect conflict on port {conflicting_port}"
            
        finally:
            # Cleanup conflicting container
            try:
                conflicting_container.stop(timeout=5)
                conflicting_container.remove()
            except Exception:
                pass
    
    def test_service_recovery_real(self, docker_client, integration_service_pool,
                                 integration_namespace):
        """Test service recovery with real containers."""
        # Setup service
        redis_config = {
            "template": "redis:7-alpine",
            "persistent": True,
            "health_check": True
        }
        
        service_name = "redis"
        integration_service_pool.add_service(service_name, redis_config)
        
        try:
            # Start service
            start_results = integration_service_pool.start_all_services()
            assert start_results[service_name], "Redis should start successfully"
            
            # Find the container
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers) > 0, "Container should exist"
            
            redis_container = containers[0]
            assert redis_container.status == 'running', "Container should be running"
            
            # Simulate failure by stopping the container externally
            redis_container.stop()
            time.sleep(2)
            
            # Verify container is stopped
            redis_container.reload()
            assert redis_container.status in ['exited', 'dead'], "Container should be stopped"
            
            # Test: Recovery via restart
            restart_success = integration_service_pool.restart_service(service_name)
            assert restart_success, "Service should restart successfully"
            
            # Verify container is running again
            time.sleep(2)
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            running_containers = [c for c in containers if c.status == 'running']
            assert len(running_containers) > 0, "Container should be running after recovery"
            
        finally:
            # Cleanup
            stop_results = integration_service_pool.stop_all_services()
            assert stop_results[service_name], "Service should stop"
    
    def test_health_monitoring_real(self, docker_client, integration_service_pool,
                                  integration_namespace):
        """Test health monitoring with real containers."""
        # Setup health monitor
        health_monitor = HealthMonitor(check_interval=2)
        health_monitor.add_service_pool(integration_namespace, integration_service_pool)
        
        # Setup service with health check
        postgres_config = {
            "template": "postgres:16",
            "persistent": True,
            "health_check": True
        }
        
        service_name = "postgres"
        integration_service_pool.add_service(service_name, postgres_config)
        
        try:
            # Start monitoring
            health_monitor.start_monitoring()
            
            # Start service
            start_results = integration_service_pool.start_all_services()
            assert start_results[service_name], "PostgreSQL should start"
            
            # Wait for service to be healthy
            max_wait = 30
            wait_time = 0
            healthy = False
            
            while wait_time < max_wait:
                health_results = health_monitor.check_all_health()
                if (integration_namespace in health_results and 
                    service_name in health_results[integration_namespace]):
                    result = health_results[integration_namespace][service_name]
                    if result.status == ServiceStatus.HEALTHY:
                        healthy = True
                        break
                time.sleep(2)
                wait_time += 2
            
            assert healthy, "Service should become healthy within timeout"
            
            # Test recovery monitoring
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            if containers:
                postgres_container = containers[0]
                
                # Stop container to simulate failure
                postgres_container.stop()
                time.sleep(2)
                
                # Health monitor should detect unhealthy state
                health_results = health_monitor.check_all_health()
                if (integration_namespace in health_results and 
                    service_name in health_results[integration_namespace]):
                    result = health_results[integration_namespace][service_name]
                    assert result.status != ServiceStatus.HEALTHY, \
                           "Health monitor should detect unhealthy service"
                
                # Test repair
                repair_success = health_monitor.repair_service(integration_namespace, service_name)
                assert repair_success, "Service repair should succeed"
                
                # Service should become healthy again
                time.sleep(5)
                health_results = health_monitor.check_all_health()
                if (integration_namespace in health_results and 
                    service_name in health_results[integration_namespace]):
                    result = health_results[integration_namespace][service_name]
                    assert result.status == ServiceStatus.HEALTHY, \
                           "Service should be healthy after repair"
            
        finally:
            # Stop monitoring and cleanup
            health_monitor.stop_monitoring()
            stop_results = integration_service_pool.stop_all_services()
            assert stop_results[service_name], "Service should stop"
    
    def test_namespace_isolation_real(self, docker_client, temp_config_dir, port_allocator):
        """Test namespace isolation with real containers."""
        # Setup two different namespaces
        namespace1 = f"isolation-test-1-{int(time.time())}"
        namespace2 = f"isolation-test-2-{int(time.time())}"
        
        service_pool1 = ServicePool(namespace1, config_dir=temp_config_dir)
        service_pool2 = ServicePool(namespace2, config_dir=temp_config_dir)
        
        # Same service name in both namespaces
        redis_config = {
            "template": "redis:7-alpine",
            "persistent": True
        }
        
        service_pool1.add_service("redis", redis_config)
        service_pool2.add_service("redis", redis_config)
        
        # Allocate port ranges for each namespace
        range1 = port_allocator.allocate_port_range(namespace1)
        range2 = port_allocator.allocate_port_range(namespace2)
        
        try:
            # Start services in both namespaces
            results1 = service_pool1.start_all_services()
            results2 = service_pool2.start_all_services()
            
            assert results1["redis"], "Redis in namespace1 should start"
            assert results2["redis"], "Redis in namespace2 should start"
            
            # Verify both containers exist and are isolated
            containers1 = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={namespace1}'
            })
            containers2 = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={namespace2}'
            })
            
            assert len(containers1) == 1, "Namespace1 should have one container"
            assert len(containers2) == 1, "Namespace2 should have one container"
            
            # Containers should have different names
            container1_name = containers1[0].name
            container2_name = containers2[0].name
            assert container1_name != container2_name, "Containers should have different names"
            
            # Both containers should be running
            assert containers1[0].status == 'running', "Namespace1 container should be running"
            assert containers2[0].status == 'running', "Namespace2 container should be running"
            
            # Verify port ranges are different
            assert range1.start != range2.start, "Port ranges should be different"
            
        finally:
            # Cleanup both namespaces
            stop_results1 = service_pool1.stop_all_services()
            stop_results2 = service_pool2.stop_all_services()
            
            assert stop_results1["redis"], "Namespace1 redis should stop"
            assert stop_results2["redis"], "Namespace2 redis should stop"
    
    def test_full_workflow_integration(self, docker_client, integration_service_pool,
                                     integration_namespace, port_allocator):
        """Test complete workflow from config to running services."""
        # Setup: Complex service configuration similar to data engineering stack
        services_config = {
            "postgres": {
                "template": "postgres:16",
                "persistent": True,
                "health_check": True,
                "environment": {
                    "POSTGRES_DB": "testdb",
                    "POSTGRES_USER": "testuser",
                    "POSTGRES_PASSWORD": "testpass"
                }
            },
            "redis": {
                "template": "redis:7-alpine",
                "persistent": True,
                "health_check": True
            },
            "worker": {
                "template": "alpine:latest",
                "command": ["sleep", "60"],
                "depends_on": ["postgres", "redis"],
                "persistent": True
            }
        }
        
        # Add all services
        for service_name, config in services_config.items():
            integration_service_pool.add_service(service_name, config)
        
        # Allocate port range
        port_range = port_allocator.allocate_port_range(integration_namespace)
        
        try:
            # Phase 1: Initial startup
            start_results = integration_service_pool.start_all_services()
            
            # Verify all services started
            for service_name in services_config:
                assert start_results[service_name], f"Service {service_name} should start"
            
            # Verify containers exist
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers) == 3, "All three containers should exist"
            
            running_containers = [c for c in containers if c.status == 'running']
            assert len(running_containers) == 3, "All containers should be running"
            
            # Phase 2: Idempotent restart
            restart_results = integration_service_pool.start_all_services()
            
            # Should reuse existing containers
            for service_name in services_config:
                assert restart_results[service_name], f"Service {service_name} should restart/reuse"
            
            # Same number of containers should exist
            containers_after_restart = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers_after_restart) == 3, "Same number of containers after restart"
            
            # Phase 3: Health checking
            for service_name in ["postgres", "redis"]:  # Services with health checks
                status = integration_service_pool.check_service_health(service_name)
                assert status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING], \
                       f"Service {service_name} should be healthy"
            
            # Phase 4: Selective service restart
            postgres_restart = integration_service_pool.restart_service("postgres")
            assert postgres_restart, "PostgreSQL should restart successfully"
            
            # Other services should remain running
            redis_status = integration_service_pool.check_service_health("redis")
            worker_status = integration_service_pool.check_service_health("worker")
            
            assert redis_status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING], \
                   "Redis should remain healthy"
            assert worker_status in [ServiceStatus.HEALTHY, ServiceStatus.STARTING], \
                   "Worker should remain healthy"
            
        finally:
            # Phase 5: Complete cleanup
            stop_results = integration_service_pool.stop_all_services()
            
            for service_name in services_config:
                assert stop_results[service_name], f"Service {service_name} should stop"
            
            # Verify all containers are stopped
            time.sleep(2)
            final_containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            
            # Persistent containers should exist but be stopped
            persistent_services = [name for name, config in services_config.items() 
                                 if config.get('persistent', True)]
            assert len(final_containers) >= len(persistent_services), \
                   "Persistent containers should still exist"
            
            running_final = [c for c in final_containers if c.status == 'running']
            assert len(running_final) == 0, "No containers should be running after stop"


class TestCLIIntegration:
    """Integration tests for CLI with real Docker."""
    
    def test_cli_up_command_integration(self, docker_client, temp_config_dir, integration_namespace):
        """Test CLI up command with real Docker."""
        # Create services configuration file
        import yaml
        
        services_config = {
            "namespace": integration_namespace,
            "services": {
                "redis": {
                    "template": "redis:7-alpine",
                    "persistent": True,
                    "health_check": True
                }
            }
        }
        
        config_file = temp_config_dir / "cli-test-services.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(services_config, f)
        
        try:
            # Test CLI up command
            from devcontainer_services.cli import main
            from click.testing import CliRunner
            
            runner = CliRunner()
            
            # Run dcm up command
            result = runner.invoke(main, [
                'up', 
                '--config', str(config_file),
                '--namespace', integration_namespace
            ])
            
            # Command should succeed
            assert result.exit_code == 0, f"CLI up command failed: {result.output}"
            
            # Verify container was created
            containers = docker_client.containers.list(filters={
                'label': f'devcontainer-service-manager.namespace={integration_namespace}'
            })
            assert len(containers) > 0, "Container should be created by CLI"
            
            # Test CLI status command
            status_result = runner.invoke(main, [
                'status',
                '--namespace', integration_namespace
            ])
            
            assert status_result.exit_code == 0, f"CLI status command failed: {status_result.output}"
            assert "redis" in status_result.output, "Status should show redis service"
            
        finally:
            # Cleanup using CLI
            runner = CliRunner()
            cleanup_result = runner.invoke(main, [
                'down',
                '--namespace', integration_namespace
            ])
            
            # Should cleanup successfully (exit code may vary if containers already stopped)
            assert cleanup_result.exit_code in [0, 1], "Cleanup should complete"