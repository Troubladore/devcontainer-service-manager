"""Background health monitoring for services."""

import time
import threading
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass
from .service_pool import ServicePool, ServiceStatus, ServiceInfo


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service_name: str
    status: ServiceStatus
    timestamp: float
    error_message: Optional[str] = None


class HealthMonitor:
    """Background health monitor for managed services."""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.monitored_pools: Dict[str, ServicePool] = {}
        self.health_callbacks: List[Callable[[HealthCheckResult], None]] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._running = False
    
    def add_service_pool(self, namespace: str, service_pool: ServicePool) -> None:
        """Add a service pool to monitor."""
        self.monitored_pools[namespace] = service_pool
    
    def remove_service_pool(self, namespace: str) -> None:
        """Remove a service pool from monitoring."""
        if namespace in self.monitored_pools:
            del self.monitored_pools[namespace]
    
    def add_health_callback(self, callback: Callable[[HealthCheckResult], None]) -> None:
        """Add a callback to be called when health status changes."""
        self.health_callbacks.append(callback)
    
    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._running:
            return
        
        self._running = True
        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if not self._running:
            return
        
        self._running = False
        self._stop_monitoring.set()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
    
    def check_all_health(self) -> Dict[str, Dict[str, HealthCheckResult]]:
        """Perform health check on all monitored services."""
        results = {}
        
        for namespace, service_pool in self.monitored_pools.items():
            namespace_results = {}
            
            for service_name in service_pool.services:
                result = self._check_service_health(service_pool, service_name)
                namespace_results[service_name] = result
                
                # Notify callbacks
                for callback in self.health_callbacks:
                    try:
                        callback(result)
                    except Exception:
                        pass  # Don't let callback errors stop monitoring
            
            results[namespace] = namespace_results
        
        return results
    
    def check_service_health(self, namespace: str, service_name: str) -> Optional[HealthCheckResult]:
        """Check health of a specific service."""
        service_pool = self.monitored_pools.get(namespace)
        if not service_pool:
            return None
        
        return self._check_service_health(service_pool, service_name)
    
    def repair_service(self, namespace: str, service_name: str) -> bool:
        """Attempt to repair an unhealthy service."""
        service_pool = self.monitored_pools.get(namespace)
        if not service_pool:
            return False
        
        service = service_pool.get_service(service_name)
        if not service:
            return False
        
        # Try to restart the service
        try:
            success = service_pool.restart_service(service_name)
            if success:
                # Wait a moment and check if it's healthy now
                time.sleep(5)
                result = self._check_service_health(service_pool, service_name)
                return result.status == ServiceStatus.HEALTHY
            return False
        except Exception:
            return False
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                self.check_all_health()
            except Exception:
                pass  # Continue monitoring even if there are errors
            
            # Wait for next check interval or stop signal
            self._stop_monitoring.wait(timeout=self.check_interval)
    
    def _check_service_health(self, service_pool: ServicePool, service_name: str) -> HealthCheckResult:
        """Check health of a specific service in a pool."""
        timestamp = time.time()
        
        try:
            status = service_pool.check_service_health(service_name)
            return HealthCheckResult(
                service_name=service_name,
                status=status,
                timestamp=timestamp
            )
        except Exception as e:
            return HealthCheckResult(
                service_name=service_name,
                status=ServiceStatus.UNHEALTHY,
                timestamp=timestamp,
                error_message=str(e)
            )
    
    def get_health_summary(self) -> Dict[str, Dict[str, str]]:
        """Get a summary of health status for all monitored services."""
        summary = {}
        
        for namespace, service_pool in self.monitored_pools.items():
            namespace_summary = {}
            
            for service_name, service_info in service_pool.services.items():
                # Get latest status
                latest_status = service_pool.check_service_health(service_name)
                namespace_summary[service_name] = latest_status.value
            
            summary[namespace] = namespace_summary
        
        return summary
    
    def get_unhealthy_services(self) -> Dict[str, List[str]]:
        """Get list of unhealthy services by namespace."""
        unhealthy = {}
        
        for namespace, service_pool in self.monitored_pools.items():
            unhealthy_services = []
            
            for service_name in service_pool.services:
                status = service_pool.check_service_health(service_name)
                if status in [ServiceStatus.UNHEALTHY, ServiceStatus.STOPPED, ServiceStatus.MISSING]:
                    unhealthy_services.append(service_name)
            
            if unhealthy_services:
                unhealthy[namespace] = unhealthy_services
        
        return unhealthy
    
    def auto_repair_enabled(self, namespace: str, enable: bool = True) -> None:
        """Enable/disable auto-repair for a namespace."""
        # TODO: Implement auto-repair logic
        # This would automatically restart unhealthy services
        pass