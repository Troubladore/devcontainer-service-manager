# DevContainer Service Manager

A service orchestration tool for DevContainer-based development environments that addresses common challenges we've observed in multi-project data engineering workflows.

## What It Does

- **Service Coordination** - Manages shared services like PostgreSQL, Redis, and Kafka across projects, handling port conflicts and enabling service reuse
- **Build Optimization** - Implements fingerprint-based Docker layer caching that can significantly reduce build times, particularly for teams working across multiple repositories
- **Environment Setup** - Provides workstation optimization for WSL2 and development toolchain configuration

## The Use Case

In our experience, data engineering projects often require multiple long-running services. Teams frequently encounter port conflicts when switching between projects, duplicate resource usage, and rebuild cycles that can interrupt development flow.

This tool offers a coordination layer that can help with these challenges. Build performance improvements vary by project structure, but we've seen substantial reductions in build times when cache hits are effective.

## Quick Start

```bash
# Install and optimize your workstation
pipx install devcontainer-service-manager[workstation]
pipx ensurepath && source ~/.bashrc

# One-time setup
dcm-setup install --profile data-engineering
dcm-setup validate

# In your project directory
cd /path/to/your/project
dcm up
```

## Documentation

- [User Guide](docs/user-guide.md) - Core concepts and workflows
- [Installation Guide](docs/installation.md) - Setup and configuration
- [Optimization Guide](docs/optimization-guide.md) - Performance tuning for WSL2 and Docker
- [System Architecture](docs/architecture.md) - Technical implementation details

[Complete documentation index](docs/index.md)
