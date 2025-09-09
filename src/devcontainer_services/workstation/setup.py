#!/usr/bin/env python3
"""
Workstation optimization and setup for data engineering development.

Provides automated setup and optimization for development environments,
with special focus on WSL2, Docker performance, and cross-repository caching.
"""

import subprocess
import platform
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class WorkstationOptimizer:
    """Optimizes development workstation for data engineering workflows."""
    
    def __init__(self):
        self.system_info = self._detect_system_info()
        
    def _detect_system_info(self) -> Dict[str, str]:
        """Detect system information and environment."""
        info = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "is_wsl": self._is_wsl(),
            "docker_available": self._check_docker_available()
        }
        
        if info["is_wsl"]:
            info["wsl_version"] = self._get_wsl_version()
            info["windows_build"] = self._get_windows_build()
        
        return info
    
    def _is_wsl(self) -> bool:
        """Check if running in WSL environment."""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def _get_wsl_version(self) -> str:
        """Get WSL version."""
        try:
            result = subprocess.run([
                'wsl.exe', '--status'
            ], capture_output=True, text=True, timeout=10)
            
            if 'WSL 2' in result.stdout:
                return "2"
            elif 'WSL 1' in result.stdout:
                return "1"
            else:
                return "unknown"
        except:
            return "unknown"
    
    def _get_windows_build(self) -> str:
        """Get Windows build number from WSL."""
        try:
            result = subprocess.run([
                'cmd.exe', '/c', 'ver'
            ], capture_output=True, text=True, timeout=10)
            
            # Extract build number from output
            import re
            match = re.search(r'\[Version ([\d.]+)\]', result.stdout)
            if match:
                return match.group(1)
            return "unknown"
        except:
            return "unknown"
    
    def _check_docker_available(self) -> bool:
        """Check if Docker is available and responding."""
        try:
            result = subprocess.run([
                'docker', 'version', '--format', 'json'
            ], capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0
        except:
            return False
    
    def get_docker_info(self) -> Dict:
        """Get detailed Docker information."""
        try:
            result = subprocess.run([
                'docker', 'info', '--format', 'json'
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    def validate_performance_setup(self) -> Dict[str, any]:
        """Validate workstation performance configuration."""
        checks = {}
        
        # Docker checks
        checks["docker"] = self._validate_docker_setup()
        
        # WSL2 specific checks
        if self.system_info["is_wsl"]:
            checks["wsl2"] = self._validate_wsl2_setup()
        
        # File system performance checks
        checks["filesystem"] = self._validate_filesystem_performance()
        
        # Memory and resource checks
        checks["resources"] = self._validate_resource_availability()
        
        return checks
    
    def _validate_docker_setup(self) -> Dict[str, any]:
        """Validate Docker configuration for optimal performance."""
        validation = {
            "available": self.system_info["docker_available"],
            "issues": [],
            "recommendations": []
        }
        
        if not validation["available"]:
            validation["issues"].append("Docker not available or not responding")
            validation["recommendations"].append("Install Docker Desktop or Docker Engine")
            return validation
        
        # Get Docker info
        docker_info = self.get_docker_info()
        
        if "error" in docker_info:
            validation["issues"].append(f"Failed to get Docker info: {docker_info['error']}")
            return validation
        
        # Check BuildKit support
        if not docker_info.get("BuilderVersion", "").startswith("buildx"):
            validation["recommendations"].append("Enable BuildKit for faster builds (DOCKER_BUILDKIT=1)")
        
        # Check memory allocation (for Docker Desktop)
        if "MemTotal" in docker_info:
            mem_gb = docker_info["MemTotal"] / (1024**3)
            if mem_gb < 6:
                validation["recommendations"].append(f"Consider increasing Docker memory to 8GB+ (currently {mem_gb:.1f}GB)")
        
        # Check storage driver
        storage_driver = docker_info.get("Driver", "unknown")
        if storage_driver not in ["overlay2", "btrfs"]:
            validation["recommendations"].append(f"Consider using overlay2 storage driver (currently {storage_driver})")
        
        return validation
    
    def _validate_wsl2_setup(self) -> Dict[str, any]:
        """Validate WSL2 configuration for optimal Docker performance."""
        validation = {
            "version": self.system_info.get("wsl_version", "unknown"),
            "issues": [],
            "recommendations": []
        }
        
        if validation["version"] != "2":
            validation["issues"].append(f"WSL version is {validation['version']}, but WSL 2 recommended")
            validation["recommendations"].append("Upgrade to WSL 2 for better Docker performance")
        
        # Check file system location
        cwd = Path.cwd()
        if str(cwd).startswith("/mnt/"):
            validation["issues"].append("Working in Windows filesystem (/mnt/c/)")
            validation["recommendations"].append("Move repositories to WSL2 filesystem (e.g., ~/repos/) for 10x faster builds")
        
        # Check .wslconfig
        wslconfig_path = Path.home() / ".wslconfig"
        if self.system_info["platform"] == "Linux" and validation["version"] == "2":
            try:
                # Check if we can access Windows home directory
                windows_home = Path("/mnt/c/Users")
                if windows_home.exists():
                    possible_configs = list(windows_home.glob("*/.wslconfig"))
                    if not possible_configs:
                        validation["recommendations"].append("Consider creating .wslconfig for WSL2 optimization")
            except:
                pass
        
        return validation
    
    def _validate_filesystem_performance(self) -> Dict[str, any]:
        """Test file system performance for development workflows."""
        validation = {
            "location": str(Path.cwd()),
            "performance_tier": "unknown",
            "issues": [],
            "recommendations": []
        }
        
        cwd = Path.cwd()
        
        if str(cwd).startswith("/mnt/"):
            validation["performance_tier"] = "slow"
            validation["issues"].append("Working in cross-filesystem mount (Windows to WSL)")
            validation["recommendations"].append("Move to native WSL2 filesystem for 10x faster I/O")
        elif self.system_info["is_wsl"]:
            validation["performance_tier"] = "fast"
        else:
            validation["performance_tier"] = "native"
        
        return validation
    
    def _validate_resource_availability(self) -> Dict[str, any]:
        """Check available system resources."""
        validation = {
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check available disk space
            result = subprocess.run([
                "df", "-h", "."
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    fields = lines[1].split()
                    if len(fields) >= 4:
                        available = fields[3]
                        validation["disk_available"] = available
                        
                        # Parse available space (rough check)
                        if available.endswith("G"):
                            gb_available = float(available[:-1])
                            if gb_available < 20:
                                validation["issues"].append(f"Low disk space: {available} available")
                                validation["recommendations"].append("Free up disk space for Docker images and builds")
        except:
            pass
        
        return validation
    
    def optimize_wsl2_performance(self) -> bool:
        """Apply WSL2 performance optimizations."""
        if not self.system_info["is_wsl"] or self.system_info.get("wsl_version") != "2":
            logger.warning("WSL2 optimizations only apply to WSL2 environments")
            return False
        
        logger.info("🚀 Applying WSL2 performance optimizations...")
        
        optimizations = [
            self._optimize_git_config,
            self._optimize_shell_config,
            self._create_wslconfig_recommendations
        ]
        
        success = True
        for optimization in optimizations:
            try:
                optimization()
            except Exception as e:
                logger.error(f"Optimization failed: {e}")
                success = False
        
        return success
    
    def _optimize_git_config(self):
        """Optimize Git configuration for WSL2."""
        git_configs = [
            ("core.autocrlf", "input"),
            ("core.filemode", "false"),
            ("credential.helper", "store")
        ]
        
        for key, value in git_configs:
            try:
                subprocess.run([
                    "git", "config", "--global", key, value
                ], check=True, capture_output=True)
                logger.debug(f"Set git config: {key}={value}")
            except subprocess.CalledProcessError:
                logger.warning(f"Failed to set git config: {key}={value}")
    
    def _optimize_shell_config(self):
        """Add helpful aliases and environment variables."""
        shell_additions = '''
# Data Engineering Development Optimizations
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Helpful aliases
alias dcm-status="dcm status && dcm-cache status"
alias docker-cleanup="docker system prune -f && docker volume prune -f"
alias ws-check="dcm-setup validate"
'''
        
        bashrc_path = Path.home() / ".bashrc"
        if bashrc_path.exists():
            content = bashrc_path.read_text()
            if "Data Engineering Development Optimizations" not in content:
                with open(bashrc_path, "a") as f:
                    f.write(shell_additions)
                logger.info("✅ Added development aliases to .bashrc")
    
    def _create_wslconfig_recommendations(self):
        """Generate .wslconfig recommendations."""
        if not self.system_info["is_wsl"]:
            return
        
        wslconfig_content = """# WSL2 Performance Optimization for Data Engineering
[wsl2]
# Memory allocation (adjust based on your system)
memory=8GB
# Processor count (adjust based on your system)  
processors=4
# Swap space
swap=2GB
# Disable page reporting (can improve performance)
pageReporting=false
"""
        
        logger.info("💡 Consider creating C:\\Users\\<username>\\.wslconfig with:")
        for line in wslconfig_content.split('\n'):
            if line.strip():
                logger.info(f"   {line}")


def validate_workstation_setup() -> Dict[str, any]:
    """Validate current workstation setup for data engineering."""
    optimizer = WorkstationOptimizer()
    
    logger.info("🔍 Validating workstation setup...")
    
    # System info
    system_info = optimizer.system_info
    logger.info(f"Platform: {system_info['platform']}")
    if system_info['is_wsl']:
        logger.info(f"WSL Version: {system_info['wsl_version']}")
    logger.info(f"Docker Available: {system_info['docker_available']}")
    
    # Performance validation
    validation_results = optimizer.validate_performance_setup()
    
    return {
        "system_info": system_info,
        "validation": validation_results,
        "optimizer": optimizer
    }