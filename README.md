# DevContainer Service Manager

Complete development environment optimization for data engineering projects. Provides intelligent service management, Docker build caching, and workstation setup with automatic conflict detection, port allocation, and cross-repository performance optimization.

## Features

### Service Management
- **Conflict-Free Startup**: Automatic port conflict detection and resolution
- **Service Reuse**: Share services across projects and branches to eliminate startup churn
- **Namespace Isolation**: Project+branch namespacing prevents service interference
- **Health Monitoring**: Continuous health checks with automatic service recovery
- **Template System**: Extensible service templates for common development stacks

### Docker Build Caching (NEW)
- **149x Faster Builds**: Fingerprint-based caching system with cross-repository sharing
- **Local Registry**: Automatic setup of local Docker registry for cache storage
- **Smart Fingerprinting**: SHA256-based dependency tracking for intelligent cache invalidation
- **Cross-Repo Benefits**: Share cached builds between projects and branches

### Workstation Optimization (NEW)
- **WSL2 Performance**: Specialized optimizations for Windows development environments
- **Setup Validation**: Comprehensive checks for optimal development configuration
- **Automated Fixes**: Troubleshooting and resolution of common performance issues
- **Resource Management**: Docker resource cleanup and monitoring

## Quick Start

### 🚀 **First-Time Setup (Recommended)**

For optimal data engineering development experience:

```bash
# 1. Install with workstation optimization (globally available)
pipx install devcontainer-service-manager[workstation]

# 2. Ensure pipx binaries are in PATH (required for WSL2/fresh installs)
pipx ensurepath
source ~/.bashrc  # OR: exec $SHELL

# 3. One-time workstation optimization  
dcm-setup install --profile data-engineering

# 4. Validate your setup
dcm-setup validate

# 5. (Optional) Troubleshoot any issues
dcm-setup troubleshoot
```

This provides 149x faster builds, WSL2 optimization, and cross-repository caching.

### Installation Options

```bash
# Basic installation (service management only)
pipx install devcontainer-service-manager

# Full installation with caching and workstation optimization  
pipx install devcontainer-service-manager[workstation]
```

### Basic Usage

```bash
# Start services for current project
dcm up --config .devcontainer/services.yaml

# Check service status
dcm status

# Stop services for current project
dcm down

# Clean up unused services
dcm clean --unused
```

### Project Configuration

Create `.devcontainer/services.yaml` in your project:

```yaml
namespace: "my-project"
port_range: "auto"

services:
  postgres:
    template: "postgres:16"
    persistent: true
    health_check: true
  
  airflow:
    template: "airflow:2.9.3"
    depends_on: ["postgres"]
    persistent: true
    ports: ["webserver:8080"]
```

Update `.devcontainer/devcontainer.json`:

```json
{
  "name": "My DevContainer",
  "initializeCommand": "dcm up --config .devcontainer/services.yaml",
  "shutdownAction": "dcm suspend --namespace my-project"
}
```

## Architecture

The service manager uses a namespace-based architecture where each project+branch combination gets its own isolated service pool:

- **Namespaces**: `{project}_{branch}` format ensures clean isolation
- **Port Ranges**: Automatic allocation of non-conflicting port ranges per namespace
- **Service Templates**: Reusable, parameterized service definitions
- **Health Monitoring**: Background monitoring with automatic restart of failed services

## Service Templates

Built-in templates include:

- **postgres**: PostgreSQL with configurable version and persistence
- **airflow**: Apache Airflow with scheduler and webserver
- **redis**: Redis for caching and session storage
- **mysql**: MySQL with configurable version and schemas

Custom templates can be added in `~/.devcontainer-services/templates/`.

## CLI Commands

### Service Management
```bash
dcm up [--config FILE]              # Start services
dcm down [--namespace NS]           # Stop services  
dcm status [--all]                  # Show service status
dcm clean [--unused] [--force]      # Clean up services
dcm health [--namespace NS]         # Check service health
dcm repair --service SERVICE        # Repair unhealthy service
dcm template list                   # List available templates
dcm namespace list                  # List active namespaces
```

### Docker Build Caching (NEW)
```bash
dcm-cache status                     # Show cache registry status and statistics
dcm-cache configure --project NAME  # Configure project-specific caching
dcm-cache clean --older-than 7d     # Remove old cached images
dcm-cache optimize                   # Pre-build common base images
dcm-cache registry start/stop        # Manage local registry
dcm-cache cleanup PROJECT_NAME      # Clean up project Docker resources
```

### Workstation Setup (NEW)
```bash
dcm-setup install --profile data-engineering  # One-time workstation optimization
dcm-setup validate                            # Validate performance configuration
dcm-setup troubleshoot                        # Diagnose and fix common issues
dcm-setup wsl2-optimize                       # WSL2-specific optimizations
dcm-setup cleanup                             # Clean up Docker resources
```

## 🐛 Troubleshooting

### Common Issues

**WSL2 slow builds:**
```bash
# Check if you're in Windows filesystem (slow)
pwd  # Should show /home/user/... not /mnt/c/...

# Move to WSL2 filesystem for 10x faster performance
mkdir -p ~/repos && cd ~/repos
```

**Docker registry won't start:**
```bash
# Check what's using port 5000
sudo netstat -tuln | grep 5000

# Use alternative port if needed  
dcm-cache registry stop
# Edit ~/.devcontainer-services/config.yaml to change port
```

**Permission errors:**
```bash
# Fix Docker permissions (Linux/WSL2)
sudo usermod -aG docker $USER
# Logout and login again

# If pipx installation fails due to permissions
pipx reinstall devcontainer-service-manager[workstation]
```

**Cache not working:**
```bash
# Verify registry status
dcm-cache status

# Restart registry
dcm-cache registry stop && dcm-cache registry start
```

## 🔄 Updating DCM

### Recommended: Update in Place

For most cases, you can update DCM without a full uninstall:

```bash
# Update to latest version (preserves configuration)
pipx upgrade devcontainer-service-manager[workstation]

# OR if that fails, reinstall over existing
pipx install --force devcontainer-service-manager[workstation]

# Verify new version
dcm --version
dcm-setup validate
```

### State-Safe Updates

DCM is designed to handle version updates gracefully:
- **Configuration**: Preserved across updates in `~/.devcontainer-services/`
- **Running Services**: Continue running during updates
- **Cache Registry**: Persists with existing cached images
- **Backward Compatibility**: Newer versions handle older state gracefully

## 🗑️ Complete Uninstall

For testing, development, or when you need to completely remove DCM from your system (including when DCM commands are broken or unavailable).

### 🚀 Recommended: Standalone Uninstall Script

**Problem**: Manual uninstall steps require DCM commands to be working, but you might need to uninstall DCM precisely because it's broken!

**Solution**: Use our standalone uninstall script that works independently of DCM installation status:

```bash
# Option 1: Download and run directly from repository
curl -fsSL https://raw.githubusercontent.com/Troubladore/devcontainer-service-manager/remove_podman/uninstall-dcm.sh | bash

# Option 2: Download, inspect, then run
curl -fsSL https://raw.githubusercontent.com/Troubladore/devcontainer-service-manager/remove_podman/uninstall-dcm.sh -o uninstall-dcm.sh
chmod +x uninstall-dcm.sh
./uninstall-dcm.sh

# Option 3: Force mode (no prompts)
curl -fsSL https://raw.githubusercontent.com/Troubladore/devcontainer-service-manager/remove_podman/uninstall-dcm.sh | bash -s -- --force
```

**Key advantages:**
- ✅ **Works without DCM**: Doesn't require `dcm` commands to be functional
- ✅ **Version independent**: Handles state from any DCM version (current, old, or broken)
- ✅ **Comprehensive**: 8-step process covers all possible DCM remnants
- ✅ **Safe**: Shows what will be removed and asks for confirmation
- ✅ **Validates**: Confirms complete removal at the end

### Manual Uninstall (Fallback)

If the script doesn't work for your setup, manual steps:

```bash
# 1. Force stop/remove all DCM Docker resources
docker ps -aq --filter "label=devcontainer-service-manager" | xargs -r docker rm -f
docker images -q --filter "label=devcontainer-service-manager" | xargs -r docker rmi -f  
docker volume ls -q --filter "label=devcontainer-service-manager" | xargs -r docker volume rm
docker stop dcm-cache-registry && docker rm dcm-cache-registry
docker volume rm dcm-cache-registry-data

# 2. Remove configuration
rm -rf ~/.devcontainer-services ~/.config/devcontainer-service-manager ~/.cache/devcontainer-service-manager

# 3. Uninstall package
pipx uninstall devcontainer-service-manager
```

### Validation After Uninstall

Verify complete removal:

```bash
# Check commands are gone
dcm --version  # Should show "command not found"
dcm-setup --version  # Should show "command not found"  
dcm-cache --version  # Should show "command not found"

# Check Docker resources are cleaned
docker ps -a --filter "label=devcontainer-service-manager"  # Should be empty
docker images --filter "label=devcontainer-service-manager"  # Should be empty
docker volume ls --filter "label=devcontainer-service-manager"  # Should be empty

# Check configuration directories are gone
ls ~/.devcontainer-services 2>/dev/null || echo "✅ Config directory removed"
ls ~/.config/devcontainer-service-manager 2>/dev/null || echo "✅ XDG config removed"
ls ~/.cache/devcontainer-service-manager 2>/dev/null || echo "✅ Cache directory removed"
```

### Fresh Reinstall

After complete uninstall, for a fresh installation:

```bash
# Install fresh version
pipx install devcontainer-service-manager[workstation]

# Verify installation
dcm --version
dcm-setup --version
dcm-cache --version

# Run initial setup
dcm-setup install --profile data-engineering
dcm-setup validate
```

### What Gets Removed

The uninstall process removes:
- ✅ All running DCM services and containers
- ✅ DCM-created Docker images, volumes, and networks  
- ✅ Local Docker registry for caching
- ✅ All DCM configuration files and directories
- ✅ DCM package installation (pipx/pip/uv)
- ✅ Cache registry data and volumes

**Note**: The uninstall process is designed to be comprehensive for testing and development scenarios. It does not remove Docker itself or non-DCM containers/images.

### Getting Help

```bash
# Validate your setup
dcm-setup validate

# Automated troubleshooting
dcm-setup troubleshoot

# Check resource usage
dcm-cache status
```

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.