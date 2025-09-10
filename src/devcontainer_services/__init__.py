"""DevContainer Service Manager

Intelligent service management for DevContainers with conflict detection and reuse.
"""

__version__ = "0.1.0"
__author__ = "DevContainer Service Manager"
__email__ = "noreply@example.com"

from .core.health_monitor import HealthMonitor
from .core.namespace_manager import NamespaceManager
from .core.port_allocator import PortAllocator
from .core.service_pool import ServicePool

__all__ = [
    "NamespaceManager",
    "ServicePool",
    "PortAllocator",
    "HealthMonitor",
]
