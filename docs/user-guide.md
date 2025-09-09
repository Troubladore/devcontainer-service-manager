# User Guide

Complete guide to using DevContainer Service Manager for data engineering development environments.

## Core Concepts

### Service Management
DCM manages development services (databases, message queues, etc.) across projects and branches with automatic conflict resolution and resource sharing.

### Build Caching  
Fingerprint-based Docker build caching system that can provide 149x faster builds by sharing cached layers across repositories and branches.

### Workstation Optimization
Automated detection and configuration of development environment optimizations, especially for WSL2 and Docker performance.

---

## Basic Workflows

### Starting a Development Environment

```bash
# Navigate to your project
cd /path/to/your/data-project

# Initialize DCM (first time only)
dcm init

# Start development services
dcm up

# Check service status
dcm status
```

**What happens**:
1. DCM analyzes your project's service requirements
2. Allocates available ports (avoiding conflicts)
3. Starts services with proper networking
4. Provides connection details

### Working with Services

```bash
# List available service templates
dcm list-templates

# Add a new service to your project
dcm add postgres
dcm add redis
dcm add elasticsearch

# Start specific services
dcm up postgres redis

# View service logs
dcm logs postgres

# Stop services (keeps data)
dcm stop

# Stop and remove services (loses data)
dcm down
```

### Build Caching

```bash
# Enable caching for faster builds
dcm cache enable

# Build with caching (automatically used)
docker build -t my-image .

# Check cache statistics
dcm cache stats

# Clear old cache entries
dcm cache clean --older-than 30d
```

---

## Project Organization

### Namespacing Strategy

DCM uses `project+branch` namespacing to prevent conflicts:

```bash
# Same service, different branches
my-project-main-postgres-5432
my-project-feature-auth-postgres-5433
```

This allows you to:
- Work on multiple branches simultaneously
- Share common services across projects
- Avoid port conflicts automatically

### Configuration Structure

```
your-project/
├── .dcm/
│   ├── config.yaml          # Project-specific configuration
│   ├── templates/           # Custom service templates
│   └── data/               # Persistent service data
├── .devcontainer/
│   └── devcontainer.json   # DevContainer configuration
└── docker-compose.yml      # Standard Docker Compose (optional)
```

---

## Service Templates

### Built-in Templates

DCM includes templates optimized for data engineering:

```bash
# Database services
dcm add postgres      # PostgreSQL 15 with common extensions
dcm add mysql         # MySQL 8 with performance tuning
dcm add mongodb       # MongoDB with replica set
dcm add redis         # Redis 7 with persistence

# Data processing
dcm add kafka         # Kafka with Zookeeper
dcm add elasticsearch # Elasticsearch with Kibana
dcm add spark         # Spark standalone cluster

# Development tools
dcm add jupyter       # JupyterLab with data science libraries
dcm add airflow       # Airflow with LocalExecutor
dcm add mlflow        # MLflow tracking server
```

### Custom Templates

Create your own service templates:

```yaml
# .dcm/templates/my-custom-service.yaml
name: my-custom-service
image: custom/my-service:latest
ports:
  - "8080"
environment:
  - ENV_VAR=value
volumes:
  - my-service-data:/data
health_check:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

```bash
# Use your custom template
dcm add my-custom-service
```

---

## Advanced Usage

### Cross-Repository Service Sharing

Share services between related projects:

```bash
# In project A
dcm up --shared postgres redis

# In project B (automatically connects to shared services)
dcm up --use-shared postgres redis
```

### Environment-Specific Configuration

```yaml
# .dcm/config.yaml
environments:
  development:
    postgres:
      image: postgres:15
      memory_limit: 1g
      
  staging:
    postgres:
      image: postgres:15
      memory_limit: 4g
      cpu_limit: 2
```

```bash
# Use staging configuration
dcm up --env staging
```

### Build Cache Optimization

```bash
# Pre-populate cache from CI builds
dcm cache pull my-image:latest

# Share cache with team
dcm cache export --registry your-team-registry.com

# Import team cache
dcm cache import --registry your-team-registry.com
```

---

## Performance Optimization

### Build Performance

1. **Enable BuildKit** (see [Optimization Guide](optimization-guide.md)):
   ```bash
   export DOCKER_BUILDKIT=1
   ```

2. **Use multi-stage builds**:
   ```dockerfile
   # Optimize Dockerfile for caching
   FROM python:3.11 as deps
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   FROM deps as final
   COPY . .
   ```

3. **Order operations by change frequency**:
   ```dockerfile
   # Less frequently changing operations first
   RUN apt-get update && apt-get install -y ...
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   # More frequently changing operations last
   COPY . .
   ```

### Service Performance

1. **Allocate adequate resources**:
   ```yaml
   services:
     postgres:
       memory_limit: 2g
       cpu_limit: 1
   ```

2. **Use persistent volumes for data**:
   ```yaml
   services:
     postgres:
       volumes:
         - postgres-data:/var/lib/postgresql/data
   ```

3. **Optimize service startup order**:
   ```yaml
   services:
     postgres:
       priority: 1  # Start first
     app:
       priority: 2  # Start after postgres
       depends_on:
         - postgres
   ```

---

## Monitoring and Debugging

### Health Monitoring

```bash
# Check overall service health
dcm health

# Detailed service status
dcm status --verbose

# Monitor service logs in real-time
dcm logs --follow postgres

# View resource usage
dcm stats
```

### Troubleshooting

```bash
# Diagnose service issues
dcm diagnose postgres

# View detailed system information
dcm system-info

# Reset problematic services
dcm restart postgres

# Full reset (nuclear option)
dcm reset --all
```

### Log Management

```bash
# View recent logs
dcm logs postgres --tail 100

# Search logs
dcm logs postgres | grep ERROR

# Export logs for analysis
dcm logs postgres --since 1h > postgres-issues.log
```

---

## Integration with Development Tools

### VS Code DevContainers

DCM works seamlessly with VS Code DevContainers:

```json
// .devcontainer/devcontainer.json
{
  "name": "Data Engineering Environment",
  "dockerComposeFile": "../docker-compose.yml",
  "service": "app",
  "workspaceFolder": "/workspace",
  "postStartCommand": "dcm up --background postgres redis",
  "extensions": [
    "ms-python.python",
    "ms-toolsai.jupyter"
  ]
}
```

### JetBrains IDEs

Configure database connections using DCM service info:

```bash
# Get connection details
dcm info postgres
# Host: localhost
# Port: 5432 (or dynamically assigned)
# Database: dev_db
# Username: postgres
# Password: postgres
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Setup development environment
  run: |
    pipx install devcontainer-service-manager
    dcm up --detach postgres redis
    
- name: Run tests
  run: |
    export DATABASE_URL=$(dcm connection-string postgres)
    export REDIS_URL=$(dcm connection-string redis)
    pytest tests/
    
- name: Cleanup
  run: dcm down
```

---

## Data Management

### Persistent Data

```bash
# Create named volumes for persistence
dcm volume create postgres-data
dcm volume create redis-data

# Attach volumes to services
dcm up postgres --volume postgres-data:/var/lib/postgresql/data
```

### Backup and Restore

```bash
# Backup service data
dcm backup postgres --output /backups/postgres-$(date +%Y%m%d).sql

# Restore from backup
dcm restore postgres --input /backups/postgres-20231201.sql

# Export service configuration
dcm export-config --output my-project-config.yaml

# Import configuration
dcm import-config my-project-config.yaml
```

### Data Migration

```bash
# Migrate data between environments
dcm migrate postgres --from development --to staging

# Copy data between services
dcm copy-data old-postgres new-postgres
```

---

## Team Collaboration

### Shared Configuration

```yaml
# .dcm/team-config.yaml (check into version control)
team:
  shared_services:
    - postgres
    - redis
  
  development_standards:
    postgres:
      version: "15"
      extensions:
        - postgis
        - uuid-ossp
    
  resource_limits:
    default_memory: 1g
    default_cpu: 0.5
```

### Service Discovery

```bash
# Register services for team discovery
dcm register my-shared-service --public

# Discover available team services
dcm discover --team

# Connect to shared team services
dcm connect team-postgres
```

### Environment Consistency

```bash
# Generate team environment snapshot
dcm snapshot create --name team-baseline

# Apply team baseline to local environment
dcm snapshot apply team-baseline

# Validate environment matches team standards
dcm validate --against team-baseline
```

---

## Best Practices

### Project Structure

1. **Keep service configurations in version control**
2. **Use environment-specific overrides**, not separate configs
3. **Document custom templates** and their purposes
4. **Use meaningful service names** that reflect their purpose

### Resource Management

1. **Set resource limits** to prevent resource starvation
2. **Use health checks** for reliable service detection
3. **Clean up unused services** regularly
4. **Monitor disk usage** for persistent volumes

### Development Workflow

1. **Start services before development work**
2. **Use `dcm status` frequently** to verify service health
3. **Commit `.dcm/config.yaml`** to share team configuration
4. **Use build caching** for faster iteration cycles

### Security

1. **Don't commit secrets** in service configurations
2. **Use environment variables** for sensitive configuration
3. **Limit service network exposure** to necessary ports only
4. **Regularly update service images** for security patches

---

## Next Steps

- **🔧 [Optimization Guide](optimization-guide.md)** - Maximize development environment performance
- **🏗️ [Architecture](architecture.md)** - Understand how DCM works internally  
- **🤝 [Development Guide](development-guide.md)** - Contribute to DCM or create extensions
- **📚 [API Reference](api-reference.md)** - Complete command and configuration reference