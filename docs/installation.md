# Installation Guide

Complete installation and setup guide for DevContainer Service Manager.

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **Docker** installed and running
- **pipx** (recommended) or pip for installation

### Installing pipx (if needed)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install pipx

# macOS  
brew install pipx

# Windows (PowerShell as admin)
python -m pip install --user pipx
```

---

## Installation Options

### Option 1: Full Installation (Recommended)

Includes all features: service management, build caching, and workstation optimization.

```bash
# Install with all features
pipx install devcontainer-service-manager[workstation]

# Ensure pipx binaries are in PATH (required for WSL2/fresh installs)
pipx ensurepath
source ~/.bashrc  # OR: exec $SHELL

# Verify installation
dcm --version
dcm-setup --version
```

### Option 2: Core Installation

Just service management and build caching, without workstation optimization tools.

```bash
# Install core features only
pipx install devcontainer-service-manager

# Verify installation  
dcm --version
```

### Option 3: Development Installation

For contributors or users who want the latest features.

```bash
# Clone repository
git clone https://github.com/Troubladore/devcontainer-service-manager.git
cd devcontainer-service-manager

# Install in development mode
pipx install -e .[workstation,dev]

# Or with uv (faster)
uv sync --all-extras
```

---

## First-Time Setup

### 1. Workstation Optimization (Recommended)

For optimal data engineering development experience:

```bash
# Run one-time workstation optimization
dcm-setup install --profile data-engineering

# Validate your setup
dcm-setup validate

# (Optional) Troubleshoot any issues
dcm-setup troubleshoot
```

This configures:
- **Docker BuildKit** for 149x faster builds
- **WSL2 optimization** (if on Windows)
- **Local registry** for cross-repository caching
- **Resource allocation** tuning

### 2. Project Setup

In each project where you want to use DCM:

```bash
# Initialize DCM in your project
cd /path/to/your/project
dcm init

# Start your development environment
dcm up

# (Optional) Enable build caching
dcm cache enable
```

---

## Configuration

### Global Configuration

DCM stores global configuration in `~/.dcm/config.yaml`:

```yaml
# Default service timeout
service_timeout: 300

# Registry settings for caching
registry:
  host: localhost
  port: 5000
  
# Workstation optimization preferences  
workstation:
  auto_optimize: true
  profile: data-engineering
```

### Project Configuration

Each project can have a `.dcm/config.yaml`:

```yaml
# Project-specific settings
project:
  name: my-data-project
  namespace: data-engineering
  
services:
  postgres:
    port: 5432
    image: postgres:15
    
  redis:
    port: 6379
    image: redis:7
```

---

## Verification

### Test Basic Functionality

```bash
# Check service management
dcm status
dcm list-templates

# Test build caching (if enabled)
dcm cache status
dcm cache stats

# Validate workstation optimization
dcm-setup validate
```

### Performance Baseline

Before making changes, establish a baseline:

```bash
# Time a typical Docker build
cd /path/to/your/project
time docker build -t test-image .

# Note the build time for comparison after optimization
```

---

## Platform-Specific Setup

### Windows (WSL2)

```bash
# Ensure WSL2 is properly configured
wsl --list --verbose  # Should show version 2

# Install in WSL2 environment (not Windows directly)
# Follow standard installation process inside WSL2

# Verify Docker integration
docker version  # Should work without Docker Desktop if using WSL2 engine
```

### macOS

```bash
# Ensure Docker Desktop is running
docker version

# Install via Homebrew if preferred
# (Note: Not yet available - use pipx for now)
# brew install devcontainer-service-manager

# Standard pipx installation
pipx install devcontainer-service-manager[workstation]
```

### Linux

```bash
# Install Docker if not already installed
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install DCM
pipx install devcontainer-service-manager[workstation]

# Setup is typically straightforward on Linux
dcm-setup install --profile data-engineering
```

---

## Troubleshooting Installation

### Common Issues

**Command not found after installation**:
```bash
# Ensure pipx PATH is configured
pipx ensurepath
source ~/.bashrc
# Or restart your terminal
```

**Permission errors**:
```bash
# Don't use sudo with pipx
# If you used sudo by mistake, clean up:
sudo rm -rf ~/.local/share/pipx
pipx install devcontainer-service-manager[workstation]
```

**Docker connection errors**:
```bash
# Ensure Docker is running
docker version

# Ensure you're in the docker group (Linux)
groups  # Should include 'docker'
sudo usermod -aG docker $USER
newgrp docker
```

**WSL2-specific issues**:
```bash
# Verify WSL2 is properly configured
wsl --list --verbose

# Ensure you're installing inside WSL2, not Windows
# Run `uname -a` - should show Linux kernel
```

### Getting Help

1. **Run diagnostics**:
   ```bash
   dcm-setup validate --debug
   dcm-setup troubleshoot
   ```

2. **Check logs**:
   ```bash
   # Service logs
   dcm logs <service-name>
   
   # DCM operation logs
   tail -f ~/.dcm/logs/dcm.log
   ```

3. **Community support**:
   - GitHub Issues: Report bugs and request features
   - Documentation: Comprehensive guides in `/docs`

---

## Upgrading

### Upgrade DCM

```bash
# Upgrade to latest version
pipx upgrade devcontainer-service-manager

# Or upgrade with new extras
pipx install --force devcontainer-service-manager[workstation]

# Verify upgrade
dcm --version
dcm-setup --version
```

### Migration Between Versions

DCM maintains backward compatibility, but major version changes may require migration:

```bash
# Before upgrading major versions, backup configuration
cp -r ~/.dcm ~/.dcm.backup

# After upgrade, run validation
dcm-setup validate

# If issues, restore backup and report
```

---

## Uninstallation

### Clean Uninstall

```bash
# Stop all DCM services
dcm down --all

# Uninstall the package
pipx uninstall devcontainer-service-manager

# (Optional) Remove configuration and data
rm -rf ~/.dcm

# (Optional) Remove local registry (if you want to free disk space)
docker container stop dcm-registry
docker container rm dcm-registry
docker volume rm dcm-registry-data
```

### Verification Script

DCM includes a verification script to ensure clean uninstallation:

```bash
# Download and run uninstall verification
curl -fsSL https://raw.githubusercontent.com/Troubladore/devcontainer-service-manager/main/scripts/verify-uninstall.sh -o verify-uninstall.sh
chmod +x verify-uninstall.sh
./verify-uninstall.sh
```

The script checks that all DCM components, services, and configurations have been properly removed.

---

## Next Steps

After installation:

1. **📖 Read the [User Guide](user-guide.md)** - Learn core DCM concepts and workflows
2. **⚡ Review [Optimization Guide](optimization-guide.md)** - Understand performance optimizations  
3. **🏗️ Explore [Architecture](architecture.md)** - Deep dive into how DCM works
4. **🤝 Check [Development Guide](development-guide.md)** - Contributing and extending DCM