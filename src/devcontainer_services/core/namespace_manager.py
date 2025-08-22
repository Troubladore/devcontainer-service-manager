"""Namespace management for project+branch isolation."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Set, List, Dict
from pydantic import BaseModel
import hashlib

# Import docker at module level for mocking in tests
try:
    import docker
except ImportError:
    docker = None


class NamespaceInfo(BaseModel):
    """Information about a service namespace."""
    name: str
    project: str
    branch: str
    working_dir: str
    port_range_start: int
    port_range_end: int
    active_services: List[str] = []


class NamespaceManager:
    """Manages project+branch namespaces for service isolation."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".devcontainer-services"
        self.config_dir.mkdir(exist_ok=True)
        self.namespaces_file = self.config_dir / "namespaces.yaml"
    
    def get_current_namespace(self, project_name: Optional[str] = None) -> str:
        """Generate namespace for current project+branch context."""
        if not project_name:
            project_name = self._detect_project_name()
        
        branch = self._get_current_branch()
        return f"{project_name}_{branch}"
    
    def _detect_project_name(self) -> str:
        """Detect project name from current directory or git repo."""
        cwd = Path.cwd()
        
        # Try to get from git repo name
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=cwd
            )
            if result.returncode == 0:
                repo_path = Path(result.stdout.strip())
                return repo_path.name
        except FileNotFoundError:
            pass
        
        # Fall back to directory name
        return cwd.name
    
    def _get_current_branch(self) -> str:
        """Get current git branch, fallback to 'main'."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            if result.returncode == 0 and result.stdout.strip():
                # Sanitize branch name for use in Docker container names
                branch = result.stdout.strip()
                return self._sanitize_name(branch)
        except FileNotFoundError:
            pass
        
        return "main"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in Docker container/network names."""
        # Replace invalid characters with hyphens
        sanitized = ""
        for char in name:
            if char.isalnum() or char in "-_":
                sanitized += char.lower()
            else:
                sanitized += "-"
        
        # Remove leading/trailing hyphens and limit length
        sanitized = sanitized.strip("-")[:50]
        
        # If name becomes empty, use hash of original
        if not sanitized:
            hash_obj = hashlib.md5(name.encode())
            sanitized = f"ns-{hash_obj.hexdigest()[:8]}"
        
        return sanitized
    
    def register_namespace(self, namespace: str, info: NamespaceInfo) -> None:
        """Register a namespace with its configuration."""
        # In a real implementation, this would persist to a registry
        # For now, we'll use Docker labels to track namespaces
        pass
    
    def list_active_namespaces(self) -> List[NamespaceInfo]:
        """List all currently active namespaces."""
        try:
            if docker is None:
                return []
            client = docker.from_env()
            
            namespaces = {}
            
            # Find containers with devcontainer-service-manager labels
            containers = client.containers.list(all=True)
            for container in containers:
                labels = container.labels
                if "devcontainer-service-manager.namespace" in labels:
                    ns_name = labels["devcontainer-service-manager.namespace"]
                    
                    if ns_name not in namespaces:
                        namespaces[ns_name] = NamespaceInfo(
                            name=ns_name,
                            project=labels.get("devcontainer-service-manager.project", "unknown"),
                            branch=labels.get("devcontainer-service-manager.branch", "unknown"),
                            working_dir=labels.get("devcontainer-service-manager.working_dir", ""),
                            port_range_start=int(labels.get("devcontainer-service-manager.port_start", "8000")),
                            port_range_end=int(labels.get("devcontainer-service-manager.port_end", "8099")),
                            active_services=[]
                        )
                    
                    service_name = labels.get("devcontainer-service-manager.service", container.name)
                    namespaces[ns_name].active_services.append(service_name)
            
            return list(namespaces.values())
            
        except Exception:
            return []
    
    def cleanup_namespace(self, namespace: str) -> None:
        """Clean up all resources for a namespace."""
        try:
            if docker is None:
                return
            client = docker.from_env()
            
            # Stop and remove containers in namespace
            containers = client.containers.list(all=True)
            for container in containers:
                if container.labels.get("devcontainer-service-manager.namespace") == namespace:
                    try:
                        container.stop(timeout=10)
                        container.remove()
                    except Exception:
                        pass
            
            # Remove networks in namespace  
            networks = client.networks.list()
            for network in networks:
                if network.name.startswith(f"{namespace}_"):
                    try:
                        network.remove()
                    except Exception:
                        pass
                        
        except Exception:
            pass
    
    def get_namespace_info(self, namespace: str) -> Optional[NamespaceInfo]:
        """Get information about a specific namespace."""
        active_namespaces = self.list_active_namespaces()
        for ns_info in active_namespaces:
            if ns_info.name == namespace:
                return ns_info
        return None