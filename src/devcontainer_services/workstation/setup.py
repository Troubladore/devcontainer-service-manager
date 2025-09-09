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
    
    _instance_count = 0
    
    def __init__(self, debug_mode=False):
        WorkstationOptimizer._instance_count += 1
        self.instance_id = WorkstationOptimizer._instance_count
        self.debug_mode = debug_mode
        self._wsl_detection_result = None  # Cache WSL detection to avoid duplicate debug output
        if debug_mode:
            import traceback
            print(f"DEBUG: WorkstationOptimizer instance #{self.instance_id} created with debug_mode=True")
            print("DEBUG: Call stack:")
            for line in traceback.format_stack()[-3:]:
                print(f"DEBUG:   {line.strip()}")
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
    
    def _debug_print(self, message):
        """Print debug message if debug mode is enabled."""
        if self.debug_mode:
            instance_id = getattr(self, 'instance_id', '?')
            print(f"DEBUG[#{instance_id}]: {message}")
        else:
            logger.debug(message)

    def _is_wsl(self) -> bool:
        """Check if running in WSL environment using multiple detection methods."""
        # Return cached result if available to avoid duplicate debug output
        if self._wsl_detection_result is not None:
            self._debug_print(f"🎯 Using cached WSL detection result: {self._wsl_detection_result}")
            return self._wsl_detection_result
            
        import os
        
        self._debug_print("🔍 Starting WSL2 detection using 6 different methods...")
        
        # Method 1: Check /proc/version for Microsoft/WSL indicators
        self._debug_print("Method 1: Checking /proc/version for Microsoft/WSL indicators")
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                self._debug_print(f"  /proc/version content: {content.strip()}")
                if 'microsoft' in content or 'wsl' in content:
                    self._debug_print("✅ WSL detected via /proc/version - found Microsoft/WSL indicators")
                    self._wsl_detection_result = True
                    return True
                else:
                    self._debug_print("❌ Method 1 failed: No Microsoft/WSL indicators in /proc/version")
        except Exception as e:
            self._debug_print(f"❌ Method 1 failed: Cannot read /proc/version - {e}")
        
        # Method 2: Check WSL environment variables
        self._debug_print("Method 2: Checking WSL environment variables")
        wsl_distro = os.environ.get('WSL_DISTRO_NAME')
        wsl_interop = os.environ.get('WSL_INTEROP')
        self._debug_print(f"  WSL_DISTRO_NAME: {wsl_distro}")
        self._debug_print(f"  WSL_INTEROP: {wsl_interop}")
        if wsl_distro or wsl_interop:
            self._debug_print("✅ WSL detected via environment variables")
            self._wsl_detection_result = True
            return True
        else:
            self._debug_print("❌ Method 2 failed: WSL environment variables not found")
        
        # Method 3: Check /proc/sys/kernel/osrelease
        self._debug_print("Method 3: Checking /proc/sys/kernel/osrelease")
        try:
            with open('/proc/sys/kernel/osrelease', 'r') as f:
                content = f.read().lower()
                self._debug_print(f"  kernel osrelease: {content.strip()}")
                if 'microsoft' in content or 'wsl' in content:
                    self._debug_print("✅ WSL detected via kernel osrelease")
                    self._wsl_detection_result = True
                    return True
                else:
                    self._debug_print("❌ Method 3 failed: No Microsoft/WSL in kernel osrelease")
        except Exception as e:
            self._debug_print(f"❌ Method 3 failed: Cannot read kernel osrelease - {e}")
        
        # Method 4: Check for WSL-specific mount points
        self._debug_print("Method 4: Checking for WSL-specific mount points")
        try:
            result = subprocess.run(['mount'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                mount_output = result.stdout.lower()
                self._debug_print(f"  mount output (first 500 chars): {mount_output[:500]}")
                if '/mnt/c' in mount_output or '/mnt/wsl' in mount_output:
                    self._debug_print("✅ WSL detected via mount points - found /mnt/c or /mnt/wsl")
                    self._wsl_detection_result = True
                    return True
                else:
                    self._debug_print("❌ Method 4 failed: No /mnt/c or /mnt/wsl in mount output")
            else:
                self._debug_print(f"❌ Method 4 failed: mount command failed with code {result.returncode}")
        except Exception as e:
            self._debug_print(f"❌ Method 4 failed: mount command error - {e}")
        
        # Method 5: Check if wsl.exe is available (Windows interop)
        self._debug_print("Method 5: Checking if wsl.exe is available via Windows interop")
        try:
            result = subprocess.run(['which', 'wsl.exe'], capture_output=True, text=True, timeout=5)
            self._debug_print(f"  which wsl.exe result: returncode={result.returncode}, stdout='{result.stdout.strip()}', stderr='{result.stderr.strip()}'")
            if result.returncode == 0:
                self._debug_print("✅ WSL detected via wsl.exe availability")
                self._wsl_detection_result = True
                return True
            else:
                self._debug_print("❌ Method 5 failed: wsl.exe not found in PATH")
        except Exception as e:
            self._debug_print(f"❌ Method 5 failed: wsl.exe check error - {e}")
        
        # Method 6: Check for Windows-specific directories in /mnt
        self._debug_print("Method 6: Checking for Windows directories in /mnt")
        try:
            from pathlib import Path
            mnt_c_exists = Path('/mnt/c').exists()
            mnt_d_exists = Path('/mnt/d').exists()
            self._debug_print(f"  /mnt/c exists: {mnt_c_exists}")
            self._debug_print(f"  /mnt/d exists: {mnt_d_exists}")
            if mnt_c_exists or mnt_d_exists:
                self._debug_print("✅ WSL detected via Windows mount directories")
                self._wsl_detection_result = True
                return True
            else:
                self._debug_print("❌ Method 6 failed: No Windows mount directories found")
        except Exception as e:
            self._debug_print(f"❌ Method 6 failed: Mount directory check error - {e}")
        
        self._debug_print("🚫 WSL NOT DETECTED: All 6 detection methods failed")
        logger.info("WSL2 detection failed - run with --debug flag for detailed method analysis")
        
        # Cache the result
        self._wsl_detection_result = False
        return False
    
    def _get_wsl_version(self) -> str:
        """Get WSL version using multiple detection methods."""
        self._debug_print("🔍 Determining WSL version using multiple methods...")
        
        # Method 1: Check /proc/version for WSL2-specific indicators
        self._debug_print("WSL Version Method 1: Checking /proc/version for version-specific indicators")
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                self._debug_print(f"  /proc/version content: {content.strip()}")
                if 'microsoft-standard-wsl2' in content or '-wsl2' in content:
                    self._debug_print("✅ WSL2 detected via /proc/version - found WSL2-specific indicators")
                    return "2"
                elif 'microsoft' in content and 'wsl' in content:
                    self._debug_print("⚠️ WSL detected but could be WSL1 - /proc/version shows generic Microsoft/WSL")
                    # Continue to other methods
                else:
                    self._debug_print("❌ WSL Version Method 1 failed: No Microsoft/WSL in /proc/version")
        except Exception as e:
            self._debug_print(f"❌ WSL Version Method 1 failed: Cannot read /proc/version - {e}")
        
        # Method 2: Check for WSL2-specific filesystem features
        self._debug_print("WSL Version Method 2: Checking for WSL2-specific filesystem features")
        try:
            import os
            # WSL2 typically has different filesystem layout
            if os.path.exists('/sys/fs/cgroup/memory/memory.limit_in_bytes'):
                self._debug_print("✅ WSL2 likely detected - found WSL2-style cgroup filesystem")
                return "2"
            else:
                self._debug_print("❌ WSL Version Method 2 failed: WSL2-style filesystem not found")
        except Exception as e:
            self._debug_print(f"❌ WSL Version Method 2 failed: {e}")
        
        # Method 3: Try wsl.exe --status (original method)
        self._debug_print("WSL Version Method 3: Trying wsl.exe --status command")
        try:
            result = subprocess.run([
                'wsl.exe', '--status'
            ], capture_output=True, text=True, timeout=10)
            
            self._debug_print(f"  wsl.exe --status output: {result.stdout.strip()}")
            if 'WSL 2' in result.stdout:
                self._debug_print("✅ WSL2 detected via wsl.exe --status")
                return "2"
            elif 'WSL 1' in result.stdout:
                self._debug_print("✅ WSL1 detected via wsl.exe --status") 
                return "1"
            else:
                self._debug_print("❌ WSL Version Method 3 failed: Cannot determine version from wsl.exe output")
        except Exception as e:
            self._debug_print(f"❌ WSL Version Method 3 failed: Cannot run wsl.exe - {e}")
        
        # Method 4: Check kernel version patterns
        self._debug_print("WSL Version Method 4: Analyzing kernel version patterns")
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                # WSL2 typically has newer kernel versions and different patterns
                if 'microsoft' in content:
                    import re
                    # Look for version patterns that indicate WSL2 (typically 4.x+ kernels)
                    kernel_match = re.search(r'linux version (\d+)\.(\d+)', content)
                    if kernel_match:
                        major, minor = int(kernel_match.group(1)), int(kernel_match.group(2))
                        self._debug_print(f"  Detected kernel version: {major}.{minor}")
                        if major >= 4:  # WSL2 typically uses 4.x+ kernels
                            self._debug_print("✅ WSL2 likely detected - kernel version suggests WSL2")
                            return "2"
                        else:
                            self._debug_print("⚠️ WSL1 likely detected - older kernel version suggests WSL1")
                            return "1"
        except Exception as e:
            self._debug_print(f"❌ WSL Version Method 4 failed: {e}")
        
        self._debug_print("🚫 WSL VERSION UNKNOWN: All 4 version detection methods failed")
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
            buildkit_instructions = (
                "Enable Docker BuildKit for faster builds (149x improvement with DCM caching):\n"
                "  🚀 Easy: dcm-setup optimize --docker-buildkit\n"
                "  📖 Manual: export DOCKER_BUILDKIT=1 (add to ~/.bashrc for persistence)"
            )
            validation["recommendations"].append(buildkit_instructions)
        
        # Check memory allocation (for Docker Desktop)
        if "MemTotal" in docker_info:
            mem_gb = docker_info["MemTotal"] / (1024**3)
            if mem_gb < 6:
                memory_instructions = (
                    f"Increase Docker memory allocation (currently {mem_gb:.1f}GB, recommend 8GB+):\n"
                    "  Docker Desktop: Settings → Resources → Memory → Set to 8GB\n"
                    "  Docker Machine: docker-machine stop → VirtualBox settings → System → 8GB\n"
                    "  Linux: Edit /etc/docker/daemon.json: {\"default-runtime\": \"runc\"}\n"
                    "  Then: sudo systemctl restart docker"
                )
                validation["recommendations"].append(memory_instructions)
        
        # Check storage driver
        storage_driver = docker_info.get("Driver", "unknown")
        if storage_driver not in ["overlay2", "btrfs"]:
            storage_instructions = (
                f"Optimize Docker storage driver (currently {storage_driver}, recommend overlay2):\n"
                "  1. Edit /etc/docker/daemon.json:\n"
                '     {\"storage-driver\": \"overlay2\"}\n'
                "  2. Restart Docker: sudo systemctl restart docker\n"
                "  3. Verify: docker info | grep 'Storage Driver'\n"
                "  Note: This will remove existing containers and images"
            )
            validation["recommendations"].append(storage_instructions)
        
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
            wsl2_upgrade_instructions = (
                "Upgrade to WSL 2 for better Docker performance:\n"
                "  1. Open PowerShell as Administrator\n"
                "  2. Enable WSL 2: dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart\n"
                "  3. Download WSL2 kernel: https://aka.ms/wsl2kernel\n"
                "  4. Set WSL 2 as default: wsl --set-default-version 2\n"
                "  5. Convert existing distro: wsl --set-version <distro-name> 2\n"
                "  6. Verify: wsl --list --verbose"
            )
            validation["recommendations"].append(wsl2_upgrade_instructions)
        
        # Check file system location
        cwd = Path.cwd()
        if str(cwd).startswith("/mnt/"):
            validation["issues"].append("Working in Windows filesystem (/mnt/c/)")
            filesystem_migration_instructions = (
                "Move repositories to WSL2 filesystem for 10x faster builds:\n"
                "  🚀 Easy: dcm-setup optimize --filesystem (provides guided migration)\n"
                "  📖 Manual: mkdir -p ~/repos && cp -r /mnt/c/path/to/repo ~/repos/"
            )
            validation["recommendations"].append(filesystem_migration_instructions)
        
        # Check .wslconfig
        wslconfig_path = Path.home() / ".wslconfig"
        if self.system_info["platform"] == "Linux" and validation["version"] == "2":
            try:
                # Check if we can access Windows home directory
                windows_home = Path("/mnt/c/Users")
                if windows_home.exists():
                    possible_configs = list(windows_home.glob("*/.wslconfig"))
                    if not possible_configs:
                        wslconfig_instructions = (
                            "Create .wslconfig for WSL2 optimization (memory, CPU tuning):\n"
                            "  🚀 Easy: dcm-setup optimize --wsl-config\n"
                            "  📖 Manual: Create C:\\Users\\<username>\\.wslconfig with memory=8GB, processors=4"
                        )
                        validation["recommendations"].append(wslconfig_instructions)
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
            filesystem_native_instructions = (
                "Move to native WSL2 filesystem for 10x faster I/O:\n"
                "  1. Create workspace in WSL: mkdir -p ~/workspace\n"
                "  2. Copy project: cp -r /mnt/c/your-project ~/workspace/\n"
                "  3. Or clone fresh: cd ~/workspace && git clone <repo-url>\n"
                "  4. Update VSCode workspace: File → Open Folder → ~/workspace/project\n"
                "  5. Verify: pwd should show /home/username/workspace\n"
                "  6. Performance test: time find . -name '*.js' (should be much faster)"
            )
            validation["recommendations"].append(filesystem_native_instructions)
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
                                disk_cleanup_instructions = (
                                    f"Free up disk space ({available} available, recommend 50GB+):\n"
                                    "  🚀 Easy: dcm-setup optimize --disk-cleanup\n"
                                    "  📖 Manual: docker system prune -a --volumes && sudo apt autoremove"
                                )
                                validation["recommendations"].append(disk_cleanup_instructions)
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

    def apply_docker_buildkit_optimization(self, dry_run=False) -> bool:
        """Apply Docker BuildKit optimization automatically."""
        if dry_run:
            self._debug_print("DRY RUN: Would enable Docker BuildKit")
            return True
            
        try:
            import os
            from pathlib import Path
            
            # Determine shell profile file
            shell_profiles = [".bashrc", ".zshrc", ".profile"]
            home = Path.home()
            
            target_profile = None
            for profile in shell_profiles:
                profile_path = home / profile
                if profile_path.exists():
                    target_profile = profile_path
                    break
            
            if not target_profile:
                # Create .bashrc if no profile exists
                target_profile = home / ".bashrc"
            
            # Check if already configured
            if target_profile.exists():
                content = target_profile.read_text()
                if "DOCKER_BUILDKIT=1" in content:
                    self._debug_print("Docker BuildKit already configured")
                    return True
            
            # Add Docker BuildKit configuration
            buildkit_config = "\n# Docker BuildKit optimization (added by dcm-setup)\nexport DOCKER_BUILDKIT=1\nexport COMPOSE_DOCKER_CLI_BUILD=1\n"
            
            with open(target_profile, "a") as f:
                f.write(buildkit_config)
            
            # Also set for current session
            os.environ["DOCKER_BUILDKIT"] = "1"
            os.environ["COMPOSE_DOCKER_CLI_BUILD"] = "1"
            
            self._debug_print(f"Docker BuildKit enabled in {target_profile}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply Docker BuildKit optimization: {e}")
            return False

    def apply_wsl_config_optimization(self, dry_run=False) -> bool:
        """Apply WSL2 .wslconfig optimization automatically."""
        if not self.system_info.get('is_wsl'):
            self._debug_print("Not in WSL environment, skipping .wslconfig optimization")
            return True
            
        if dry_run:
            self._debug_print("DRY RUN: Would create/update .wslconfig file")
            return True
            
        try:
            # Generate .wslconfig content
            wslconfig_content = """# WSL2 Configuration (added by dcm-setup)
[wsl2]
# Allocate 8GB of memory (adjust based on your system)
memory=8GB

# Use 4 virtual processors (adjust based on your system)
processors=4

# Enable nested virtualization for Docker
nestedVirtualization=true

# Disable swap to improve performance
swap=0

# Limit kernel log messages
kernelCommandLine = loglevel=3 quiet

# Enable systemd (required for some services)
systemd=true
"""
            
            # Create instructions for user to apply on Windows side
            windows_home = "/mnt/c/Users"
            
            # Try to determine Windows username
            windows_user = None
            if os.path.exists(windows_home):
                users = [d for d in os.listdir(windows_home) if os.path.isdir(os.path.join(windows_home, d))]
                # Filter out system directories
                users = [u for u in users if u not in ['Public', 'Default', 'Default User', 'All Users']]
                if len(users) == 1:
                    windows_user = users[0]
            
            if windows_user:
                wslconfig_path = f"/mnt/c/Users/{windows_user}/.wslconfig"
                logger.info(f"Creating .wslconfig at {wslconfig_path}")
                
                with open(wslconfig_path, "w") as f:
                    f.write(wslconfig_content)
                
                logger.info("✅ .wslconfig created successfully")
                logger.info("💡 Restart WSL to apply changes: wsl --shutdown (in Windows)")
                return True
            else:
                # Provide instructions for manual creation
                logger.info("💡 Please create C:\\Users\\<username>\\.wslconfig with the following content:")
                logger.info(wslconfig_content)
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply .wslconfig optimization: {e}")
            # Provide manual instructions as fallback
            logger.info("💡 Please manually create .wslconfig file as shown in validation output")
            return False

    def apply_filesystem_migration_helper(self, dry_run=False) -> bool:
        """Provide guided filesystem migration assistance."""
        if not self.system_info.get('is_wsl'):
            self._debug_print("Not in WSL environment, skipping filesystem optimization")
            return True
            
        if dry_run:
            self._debug_print("DRY RUN: Would provide filesystem migration guidance")
            return True
            
        try:
            # Check current location
            current_dir = os.getcwd()
            
            if current_dir.startswith('/mnt/'):
                logger.info("🚨 You are currently in a Windows-mounted directory (slow performance)")
                logger.info("💡 Migration recommended:")
                logger.info("   1. Create directory in WSL2 filesystem:")
                logger.info("      mkdir -p ~/repos")
                logger.info("   2. Move or clone your projects there:")
                logger.info(f"      cp -r '{current_dir}' ~/repos/")
                logger.info("   3. Work from the new location for 10x faster I/O")
                return True
            else:
                logger.info("✅ You are already using WSL2 native filesystem")
                return True
                
        except Exception as e:
            logger.error(f"Failed to analyze filesystem location: {e}")
            return False

    def apply_disk_cleanup_optimization(self, dry_run=False) -> bool:
        """Apply Docker disk cleanup optimization automatically."""
        if dry_run:
            self._debug_print("DRY RUN: Would clean up Docker resources")
            return True
            
        try:
            import subprocess
            
            # Check if docker is available
            if not self.system_info.get('docker_available'):
                self._debug_print("Docker not available, skipping cleanup")
                return True
            
            logger.info("🧹 Cleaning up Docker resources...")
            
            # Run docker system prune
            result = subprocess.run(
                ['docker', 'system', 'prune', '-f'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info("✅ Docker system cleanup completed")
                if result.stdout.strip():
                    logger.info(f"   Reclaimed space: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"Docker cleanup failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Docker cleanup timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to apply disk cleanup: {e}")
            return False

    def apply_all_safe_optimizations(self, dry_run=False) -> Dict[str, bool]:
        """Apply all safe optimizations automatically."""
        results = {}
        
        logger.info("🚀 Applying all safe optimizations...")
        
        # Docker BuildKit (safe - just environment variables)
        results['docker_buildkit'] = self.apply_docker_buildkit_optimization(dry_run)
        
        # Filesystem migration helper (safe - just guidance)
        results['filesystem_migration'] = self.apply_filesystem_migration_helper(dry_run)
        
        # Disk cleanup (safe - removes unused resources)
        results['disk_cleanup'] = self.apply_disk_cleanup_optimization(dry_run)
        
        # WSL config (requires user action, so just guidance)
        if self.system_info.get('is_wsl'):
            results['wsl_config'] = self.apply_wsl_config_optimization(dry_run)
        
        # Summary
        successful = sum(results.values())
        total = len(results)
        
        if successful == total:
            logger.info(f"✅ All {total} optimizations applied successfully!")
        else:
            logger.info(f"⚠️ {successful}/{total} optimizations applied successfully")
            
        return results


def validate_workstation_setup(debug_mode=False) -> Dict[str, any]:
    """Validate current workstation setup for data engineering."""
    optimizer = WorkstationOptimizer(debug_mode=debug_mode)
    
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