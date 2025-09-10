"""Port allocation and conflict detection."""

import socket

import psutil
from pydantic import BaseModel


class PortRange(BaseModel):
    """Represents an allocated port range."""

    start: int
    end: int
    namespace: str
    allocated_ports: list[int] = []


class PortAllocator:
    """Manages port allocation and conflict detection."""

    def __init__(self):
        self.base_port = 8000
        self.range_size = 100
        self.allocated_ranges: dict[str, PortRange] = {}

    def allocate_port_range(self, namespace: str, required_ports: int = 10) -> PortRange:
        """Allocate a port range for a namespace."""
        if namespace in self.allocated_ranges:
            return self.allocated_ranges[namespace]

        # Find next available range
        start_port = self._find_available_range(required_ports)
        end_port = start_port + self.range_size - 1

        port_range = PortRange(start=start_port, end=end_port, namespace=namespace)

        self.allocated_ranges[namespace] = port_range
        return port_range

    def _find_available_range(self, required_ports: int) -> int:
        """Find an available port range of specified size."""
        current_port = self.base_port

        while True:
            # Check if range is available
            if self._is_range_available(current_port, current_port + self.range_size - 1):
                return current_port

            # Move to next potential range
            current_port += self.range_size

            # Prevent infinite loop by capping at reasonable limit
            if current_port > 65000:
                raise RuntimeError("Unable to find available port range")

    def _is_range_available(self, start: int, end: int) -> bool:
        """Check if a port range is available."""
        # Check against already allocated ranges
        for allocated_range in self.allocated_ranges.values():
            if not (end < allocated_range.start or start > allocated_range.end):
                return False

        # Check against currently bound ports
        bound_ports = self._get_bound_ports()
        for port in range(start, end + 1):
            if port in bound_ports:
                return False

        return True

    def _get_bound_ports(self) -> set[int]:
        """Get set of currently bound ports on the system."""
        bound_ports = set()

        try:
            # Get network connections
            connections = psutil.net_connections()
            for conn in connections:
                if conn.laddr and conn.status == psutil.CONN_LISTEN:
                    bound_ports.add(conn.laddr.port)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Fallback to socket testing if psutil fails
            pass

        return bound_ports

    def allocate_port(self, namespace: str, service: str, preferred_port: int | None = None) -> int:
        """Allocate a specific port within a namespace range."""
        if namespace not in self.allocated_ranges:
            self.allocate_port_range(namespace)

        port_range = self.allocated_ranges[namespace]

        # Try preferred port first if specified and in range
        if preferred_port and port_range.start <= preferred_port <= port_range.end:
            if (
                self._is_port_available(preferred_port)
                and preferred_port not in port_range.allocated_ports
            ):
                port_range.allocated_ports.append(preferred_port)
                return preferred_port

        # Find next available port in range
        for port in range(port_range.start, port_range.end + 1):
            if port not in port_range.allocated_ports and self._is_port_available(port):
                port_range.allocated_ports.append(port)
                return port

        raise RuntimeError(
            f"No available ports in range {port_range.start}-{port_range.end} for namespace {namespace}"
        )

    def _is_port_available(self, port: int) -> bool:
        """Test if a specific port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                result = sock.connect_ex(("localhost", port))
                return result != 0
        except Exception:
            return False

    def deallocate_port(self, namespace: str, port: int) -> None:
        """Deallocate a port from a namespace."""
        if namespace in self.allocated_ranges:
            port_range = self.allocated_ranges[namespace]
            if port in port_range.allocated_ports:
                port_range.allocated_ports.remove(port)

    def get_namespace_ports(self, namespace: str) -> list[int]:
        """Get all allocated ports for a namespace."""
        if namespace in self.allocated_ranges:
            return self.allocated_ranges[namespace].allocated_ports.copy()
        return []

    def check_port_conflicts(self, services_config: dict) -> list[str]:
        """Check for potential port conflicts in service configuration."""
        conflicts = []
        requested_ports = []

        for service_name, service_config in services_config.items():
            ports = service_config.get("ports", [])
            for port_mapping in ports:
                if isinstance(port_mapping, str) and ":" in port_mapping:
                    # Format like "webserver:8080" or "8080:8080"
                    parts = port_mapping.split(":")
                    if len(parts) == 2:
                        try:
                            external_port = int(parts[-1])
                            if not self._is_port_available(external_port):
                                conflicts.append(
                                    f"Port {external_port} for service {service_name} is already in use"
                                )
                            elif external_port in requested_ports:
                                conflicts.append(
                                    f"Port {external_port} requested by multiple services"
                                )
                            else:
                                requested_ports.append(external_port)
                        except ValueError:
                            pass

        return conflicts

    def cleanup_namespace(self, namespace: str) -> None:
        """Clean up port allocations for a namespace."""
        if namespace in self.allocated_ranges:
            del self.allocated_ranges[namespace]
