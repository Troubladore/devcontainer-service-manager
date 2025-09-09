# Workstation Optimization Guide

Complete reference for understanding and implementing workstation optimizations detected by `dcm-setup validate`.

## Overview

The DevContainer Service Manager can detect and recommend various workstation optimizations to significantly improve your development environment performance. Each optimization addresses specific bottlenecks common in data engineering and containerized development workflows.

**Performance Impact**: These optimizations can provide 10x-149x performance improvements depending on your current setup and bottlenecks.

---

## Docker Optimizations

### Docker BuildKit

**What it is**: Docker BuildKit is Docker's next-generation build engine that provides significant performance and feature improvements over the legacy builder.

**Why it matters for DCM**: 
- **149x faster builds** when combined with our caching system
- **Parallel layer building** reduces build times dramatically  
- **Advanced caching** enables more efficient layer reuse
- **Build secrets** support for secure dependency installation

**When to use**: 
- ✅ **Always recommended** - no downsides, only benefits
- ✅ **Especially critical** for data engineering projects with heavy dependencies (Python ML libraries, R packages, etc.)
- ✅ **Essential** when using DevContainer Service Manager's cross-repository caching

**Implementation**: 
```bash
# Permanent setup (recommended)
echo 'export DOCKER_BUILDKIT=1' >> ~/.bashrc
source ~/.bashrc

# Verify
echo $DOCKER_BUILDKIT  # Should output "1"
```

**Verification**: Your next `docker build` command will show "Building with BuildKit" and significantly faster performance.

---

### Docker Memory Allocation

**What it is**: The amount of RAM allocated to Docker for running containers and builds.

**Why it matters for DCM**:
- **Large builds** in data engineering often require substantial memory
- **Multiple containers** running simultaneously need adequate resource allocation
- **Build failures** often occur due to insufficient memory during dependency compilation

**Default vs Recommended**:
- **Docker Desktop default**: 2GB (insufficient for data workloads)
- **DCM recommendation**: 8GB+ (optimal for data engineering)

**When to increase**:
- ✅ **Data engineering projects** with heavy Python/R dependencies
- ✅ **Multiple services** running simultaneously
- ✅ **Build failures** with out-of-memory errors
- ⚠️  **Consider your system**: Only if you have 16GB+ total RAM

**Implementation**:

**Docker Desktop (Windows/Mac)**:
```
1. Open Docker Desktop
2. Settings → Resources → Memory
3. Set to 8GB (or 6GB minimum)
4. Click "Apply & Restart"
```

**Linux**:
```bash
# Edit daemon configuration
sudo nano /etc/docker/daemon.json

# Add memory limit (8GB = 8589934592 bytes)
{
  "default-runtime": "runc",
  "memory": "8g"
}

# Restart Docker
sudo systemctl restart docker
```

**Trade-offs**:
- ✅ **Pros**: Faster builds, fewer build failures, can run more containers
- ⚠️ **Cons**: Less RAM available for other applications

---

### Docker Storage Driver

**What it is**: The underlying storage technology Docker uses to store container images and layers.

**Why overlay2 is recommended**:
- **Fastest performance** for layer operations
- **Best caching efficiency** for DevContainer Service Manager
- **Standard in modern Docker** installations
- **Memory efficient** compared to older drivers

**When to optimize**:
- ✅ **Legacy Docker installations** using devicemapper or aufs
- ✅ **Performance issues** with image operations
- ⚠️ **Caution**: This will remove all existing containers and images

**Implementation**:
```bash
# Check current driver
docker info | grep 'Storage Driver'

# If not overlay2, configure it
sudo nano /etc/docker/daemon.json

# Add storage driver configuration
{
  "storage-driver": "overlay2"
}

# Restart Docker (WARNING: removes all containers/images)
sudo systemctl restart docker

# Verify
docker info | grep 'Storage Driver'
```

**Important**: This optimization requires rebuilding all your images, so plan accordingly.

---

## WSL2 Optimizations

### WSL2 Version Upgrade

**What it is**: Windows Subsystem for Linux 2 (WSL2) uses a real Linux kernel for better performance compared to WSL1.

**Why it matters for data engineering**:
- **10x faster file I/O** compared to WSL1
- **Native Docker integration** without performance penalties
- **Better memory management** for data processing workloads
- **Full Linux compatibility** for development tools

**Performance difference**:
- **WSL1**: File operations through Windows filesystem (~100MB/s)
- **WSL2**: Native Linux filesystem performance (~1GB/s)

**When to upgrade**:
- ✅ **Always recommended** if still on WSL1
- ✅ **Critical for Docker performance** on Windows
- ✅ **Required** for optimal DevContainer Service Manager performance

**Implementation**:
```powershell
# Run in PowerShell as Administrator

# 1. Enable WSL2 feature
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# 2. Download WSL2 kernel update
# Visit: https://aka.ms/wsl2kernel

# 3. Set WSL2 as default
wsl --set-default-version 2

# 4. Convert existing distribution
wsl --list --verbose
wsl --set-version <distro-name> 2

# 5. Verify upgrade
wsl --list --verbose  # Version should show "2"
```

**Post-upgrade**: Restart your terminal and verify Docker performance improvement.

---

### WSL2 Filesystem Performance

**What it is**: Where your code repositories are stored affects file I/O performance dramatically in WSL2.

**Location performance tiers**:
1. **Native WSL2 filesystem** (~/): ~1GB/s (fastest)
2. **Windows filesystem via /mnt/c/**: ~100MB/s (10x slower)
3. **Network drives**: Variable, often very slow

**Why location matters**:
- **File watching** (hot reload, tests) can be 10x slower on /mnt/c/
- **Docker builds** are dramatically faster with native filesystem
- **Git operations** are significantly more responsive

**When to migrate**:
- ✅ **Working from /mnt/c/Users/...** (Windows filesystem)
- ✅ **Slow build times** in WSL2
- ✅ **Slow file operations** (ls, find, grep)
- ✅ **Poor IDE responsiveness** in WSL2

**Implementation**:
```bash
# 1. Create workspace in WSL2 native filesystem
mkdir -p ~/workspace

# 2. Option A: Clone fresh repositories
cd ~/workspace
git clone <your-repo-url>

# 2. Option B: Copy existing repositories
cp -r /mnt/c/path/to/your/project ~/workspace/

# 3. Update IDE workspace
# VSCode: File → Open Folder → ~/workspace/project
# JetBrains: Open project from ~/workspace/project

# 4. Verify performance improvement
cd ~/workspace/project
time find . -name "*.py"  # Should be much faster
```

**Performance test**: Compare `time ls -la` between /mnt/c/ and ~/ locations.

---

### WSL2 Configuration (.wslconfig)

**What it is**: Windows configuration file that optimizes WSL2 resource allocation and performance.

**Why configure it**:
- **Memory management**: Prevent WSL2 from consuming all available RAM
- **Swap optimization**: Disable slow swap for better performance  
- **Network performance**: Enable localhost forwarding for development servers
- **CPU allocation**: Optimize processor usage for development workloads

**Default vs Optimized**:
- **Default**: WSL2 can use up to 80% of your RAM and 100% CPU
- **Optimized**: Controlled resource allocation with performance tuning

**Implementation**:
```powershell
# Open PowerShell and create configuration
notepad $env:USERPROFILE\.wslconfig
```

Add this configuration:
```ini
[wsl2]
# Memory allocation (adjust based on your total RAM)
memory=8GB

# Processor allocation (adjust based on your CPU cores)
processors=4

# Disable swap for better performance
swap=0

# Enable localhost forwarding for development servers
localhostForwarding=true

# Network performance
networkingMode=mirrored
```

```powershell
# Apply changes by restarting WSL2
wsl --shutdown
```

**Resource recommendations**:
- **16GB+ system**: 8GB for WSL2
- **32GB+ system**: 16GB for WSL2  
- **CPU cores**: Half of your total cores

---

## System Resource Optimizations

### Disk Space Management

**What it is**: Maintaining adequate free disk space for Docker images, builds, and temporary files.

**Why 50GB+ matters**:
- **Docker images** can be 1-5GB each for data engineering stacks
- **Build caches** require substantial space for performance
- **Temporary files** during builds can consume 10GB+ temporarily
- **System performance** degrades significantly below 20GB free

**Space breakdown for data engineering**:
- **Base OS**: 20GB
- **Docker images**: 20GB (multiple Python/R/Spark environments)
- **Build caches**: 15GB (DevContainer Service Manager caches)
- **Working space**: 15GB (temporary files, builds)
- **Buffer**: 10GB (system performance)

**Implementation**:
```bash
# 1. Clean Docker resources (saves 5-20GB typically)
docker system prune -a --volumes

# 2. Clean package caches
sudo apt autoremove && sudo apt autoclean  # Ubuntu/Debian
brew cleanup  # macOS
choco cleaner  # Windows

# 3. Find large files consuming space
sudo du -h / 2>/dev/null | sort -hr | head -20

# 4. Clean system logs
sudo journalctl --vacuum-time=3d

# 5. Empty trash
rm -rf ~/.local/share/Trash/*

# 6. Verify improvement
df -h /  # Should show 50GB+ available
```

**Monitoring**: Run `df -h` regularly to track disk usage trends.

---

## Performance Impact Summary

| Optimization | Performance Gain | Difficulty | Risk Level |
|--------------|------------------|------------|------------|
| **Docker BuildKit** | 2-5x builds | Easy | None |
| **Filesystem Migration** | 10x file I/O | Medium | Low |
| **WSL2 Upgrade** | 10x overall | Medium | Low |
| **Docker Memory** | 2x builds | Easy | None |
| **WSL2 Config** | 20% overall | Easy | Low |
| **Storage Driver** | 10% images | Hard | Medium |
| **Disk Cleanup** | System stability | Easy | None |

## Getting Help

- **Validation**: Run `dcm-setup validate` to check current optimizations
- **Troubleshooting**: Run `dcm-setup troubleshoot` for automated fixes
- **Debug mode**: Add `--debug` flag for detailed diagnostic information

For specific issues, the validate command provides step-by-step implementation instructions for each optimization needed in your environment.