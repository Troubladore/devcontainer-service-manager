# DevContainer Service Manager

Intelligent service management for DevContainers with automatic conflict detection, port allocation, and service reuse across projects and branches.

## Features

- **Conflict-Free Startup**: Automatic port conflict detection and resolution
- **Service Reuse**: Share services across projects and branches to eliminate startup churn
- **Namespace Isolation**: Project+branch namespacing prevents service interference
- **Health Monitoring**: Continuous health checks with automatic service recovery
- **Template System**: Extensible service templates for common development stacks
- **CLI Management**: Simple command-line interface for service lifecycle management

## Quick Start

### Installation

```bash
pip install devcontainer-service-manager
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

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.