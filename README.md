# DevContainer Service Manager

**149x faster builds** + **intelligent service management** + **workstation optimization** for data engineering development environments.

## Quick Start

```bash
# Install and optimize your workstation
pipx install devcontainer-service-manager[workstation]
pipx ensurepath && source ~/.bashrc

# One-time setup for optimal performance  
dcm-setup install --profile data-engineering
dcm-setup validate

# In your project: start development environment
cd /path/to/your/project
dcm up
```

**Result**: Docker builds 10-149x faster, automatic service management, optimized development environment.

---

## 📚 Documentation

**New to DCM?** Start with the comprehensive guides:

- **[📦 Installation Guide](docs/installation.md)** - Complete setup for all platforms
- **[👤 User Guide](docs/user-guide.md)** - Core concepts and daily workflows  
- **[⚡ Optimization Guide](docs/optimization-guide.md)** - Performance tuning and WSL2 optimization

**Need specific information?**

- **[🏗️ Architecture](docs/architecture.md)** - How DCM works internally
- **[🔌 API Reference](docs/api-reference.md)** - Complete command and configuration reference
- **[🛠️ Development Guide](docs/development-guide.md)** - Contributing and extending DCM

**Having issues?**

- **[🔍 Troubleshooting](docs/troubleshooting.md)** - Common problems and solutions
- **[❓ FAQ](docs/faq.md)** - Frequently asked questions

👉 **[Browse All Documentation](docs/index.md)**

---

## Core Features

### 🏗️ **Service Management**
Automatic port conflict detection, service reuse across projects/branches, health monitoring with auto-recovery.

### ⚡ **Build Caching** 
Fingerprint-based Docker build caching with cross-repository sharing. Up to 149x faster builds.

### 🛠️ **Workstation Optimization**
WSL2 performance tuning, Docker optimization, filesystem performance analysis, automated setup validation.

---

## What's DCM For?

**Data Engineering Teams** building with:
- 🐍 Python (pandas, scikit-learn, jupyter, airflow)  
- ☕ JVM (Spark, Kafka, Elasticsearch)
- 🌊 Stream processing (Kafka, Flink, Storm)
- 🗄️ Databases (PostgreSQL, MySQL, MongoDB, Redis)

**Development Environments** needing:
- Multiple services running simultaneously
- Fast Docker builds and rebuilds
- Branch switching without service conflicts
- Consistent team development setups

---

## Example: Data Pipeline Project

```bash
# Install DCM
pipx install devcontainer-service-manager[workstation]

# Optimize workstation (one-time setup)
dcm-setup install --profile data-engineering
dcm-setup validate  # Shows step-by-step optimizations

# In your data pipeline project
dcm add postgres kafka redis jupyter
dcm up

# Your services are now running with automatic:
# - Port conflict resolution
# - Health monitoring  
# - Cross-project sharing
# - 149x faster Docker builds
```

Services start in seconds, builds are cached across all your projects, and you can switch branches without service conflicts.

---

## Contributing

- **🐛 Issues**: [Report bugs](https://github.com/your-repo/devcontainer-service-manager/issues)
- **🤝 Contributing**: See [Development Guide](docs/development-guide.md)
- **📖 Documentation**: Help improve the [docs](docs/)

---

Built for **data engineering teams** who need **fast, reliable development environments** that **just work**.