#!/bin/bash
# DevContainer Service Manager Installation Script

set -e

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
CONFIG_DIR="$HOME/.devcontainer-services"
REPO_URL="https://github.com/devcontainer-service-manager/devcontainer-service-manager"

echo "Installing DevContainer Service Manager..."

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is required but not installed"
        exit 1
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        echo "Error: pip3 is required but not installed"
        exit 1
    fi

    # Check Docker (optional but recommended)
    if ! command -v docker &> /dev/null; then
        echo "Warning: Docker not found. Service management will be limited."
    fi

    echo "✓ Prerequisites check passed"
}

# Install via pip
install_via_pip() {
    echo "Installing devcontainer-service-manager via pip..."

    # Install from PyPI (when published) or from source
    if pip3 show devcontainer-service-manager &> /dev/null; then
        echo "Upgrading existing installation..."
        pip3 install --upgrade devcontainer-service-manager
    else
        echo "Installing from source..."
        # For development, install from local source
        if [ -d "$(dirname "$0")" ]; then
            pip3 install "$(dirname "$0")"
        else
            echo "Error: Could not find package source"
            exit 1
        fi
    fi

    echo "✓ Package installed successfully"
}

# Set up configuration directory
setup_config() {
    echo "Setting up configuration directory..."

    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CONFIG_DIR/templates"

    # Copy default templates if installing from source
    SCRIPT_DIR="$(dirname "$0")"
    if [ -d "$SCRIPT_DIR/src/devcontainer_services/templates" ]; then
        echo "Copying default templates..."
        cp -r "$SCRIPT_DIR/src/devcontainer_services/templates/"* "$CONFIG_DIR/templates/"
    fi

    # Copy default configuration
    if [ -f "$SCRIPT_DIR/src/devcontainer_services/config/default.yaml" ]; then
        echo "Setting up default configuration..."
        cp "$SCRIPT_DIR/src/devcontainer_services/config/default.yaml" "$CONFIG_DIR/config.yaml"
    fi

    echo "✓ Configuration directory set up at $CONFIG_DIR"
}

# Create symlinks for CLI
setup_cli() {
    echo "Setting up CLI access..."

    # Check if dcm command is available via pip installation
    if command -v dcm &> /dev/null; then
        echo "✓ dcm command available via pip installation"
        return
    fi

    # Fall back to local installation
    SCRIPT_DIR="$(dirname "$0")"
    if [ -f "$SCRIPT_DIR/bin/dcm" ]; then
        echo "Creating symlink for dcm command..."

        # Check if we can write to install directory
        if [ -w "$INSTALL_DIR" ]; then
            ln -sf "$SCRIPT_DIR/bin/dcm" "$INSTALL_DIR/dcm"
            echo "✓ dcm command installed to $INSTALL_DIR/dcm"
        else
            echo "Warning: Cannot write to $INSTALL_DIR"
            echo "You can add $SCRIPT_DIR/bin to your PATH or run:"
            echo "  sudo ln -sf $SCRIPT_DIR/bin/dcm $INSTALL_DIR/dcm"
        fi
    fi
}

# Verify installation
verify_installation() {
    echo "Verifying installation..."

    if command -v dcm &> /dev/null; then
        echo "✓ dcm command is available"
        echo "Testing dcm --version..."
        dcm --version
    else
        echo "Warning: dcm command not found in PATH"
    fi

    if [ -d "$CONFIG_DIR" ]; then
        echo "✓ Configuration directory exists"
    fi

    template_count=$(find "$CONFIG_DIR/templates" -name "*.yaml" 2>/dev/null | wc -l)
    echo "✓ Found $template_count service templates"
}

# Show post-installation instructions
show_instructions() {
    echo ""
    echo "=================================================================="
    echo "DevContainer Service Manager installed successfully!"
    echo "=================================================================="
    echo ""
    echo "Quick start:"
    echo "  1. Create a .devcontainer/services.yaml file in your project"
    echo "  2. Run 'dcm up' to start services"
    echo "  3. Run 'dcm status' to check service status"
    echo ""
    echo "Configuration directory: $CONFIG_DIR"
    echo "Default templates: $CONFIG_DIR/templates/"
    echo ""
    echo "For help: dcm --help"
    echo "For documentation: https://github.com/devcontainer-service-manager/devcontainer-service-manager"
    echo ""
}

# Main installation flow
main() {
    check_prerequisites
    install_via_pip
    setup_config
    setup_cli
    verify_installation
    show_instructions
}

# Handle command line arguments
case "${1:-}" in
    "--uninstall")
        echo "Uninstalling DevContainer Service Manager..."
        pip3 uninstall devcontainer-service-manager -y
        rm -f "$INSTALL_DIR/dcm"
        echo "✓ Uninstallation complete"
        echo "Note: Configuration directory $CONFIG_DIR was preserved"
        exit 0
        ;;
    "--help"|"-h")
        echo "DevContainer Service Manager Installation Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --uninstall    Uninstall DevContainer Service Manager"
        echo "  --help, -h     Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  INSTALL_DIR    Installation directory (default: /usr/local/bin)"
        exit 0
        ;;
esac

main "$@"
