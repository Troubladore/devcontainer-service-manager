#!/bin/bash
# Standalone DCM Uninstall Script
# This script works independently of DCM installation status and can be run directly
# Usage: bash uninstall-dcm.sh [--force]

set -euo pipefail

FORCE_MODE=false
if [ "${1:-}" = "--force" ]; then
    FORCE_MODE=true
fi

echo "🗑️  DevContainer Service Manager - Standalone Uninstall Script"
echo "=============================================================="
echo
echo "This script will completely remove DCM from your system without requiring"
echo "DCM commands to be functional. It works even with broken/old installations."
echo
echo "📋 Will remove both correct and corrupted DCM installations:"
echo "   Correct commands: dcm, dcm-setup, dcm-cache"
echo "   Corrupted variants: dcmworkspace, dcm-setupworkspace, dcm-cacheworkspace"
echo "   Package names: devcontainer-service-manager, devcontainer-service-managerworkspace"
echo

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if command exists (for validation - more thorough)
command_exists_validation() {
    # Try multiple methods to avoid cache issues
    local cmd="$1"

    # Method 1: Try to run the command (most definitive test)
    if timeout 3 "$cmd" --version >/dev/null 2>&1 || timeout 3 "$cmd" --help >/dev/null 2>&1 || timeout 3 "$cmd" help >/dev/null 2>&1; then
        return 0
    fi

    # Method 2: Check if executable file exists in PATH locations
    local path_dirs
    path_dirs=$(echo "$PATH" | tr ':' '\n' | sort -u)
    while IFS= read -r location; do
        if [ -d "$location" ] && [ -f "$location/$cmd" ] && [ -x "$location/$cmd" ]; then
            # Double-check: try to execute it to make sure it's not a broken shim
            if timeout 3 "$location/$cmd" --help >/dev/null 2>&1 || timeout 3 "$location/$cmd" --version >/dev/null 2>&1; then
                return 0
            fi
        fi
    done <<< "$path_dirs"

    # If we get here, the command is not functionally available
    return 1
}

# Function to ask for confirmation
confirm() {
    if [ "$FORCE_MODE" = true ]; then
        return 0
    fi

    local message="$1"
    echo -n "$message (y/N): "
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            echo "❌ Operation cancelled by user"
            exit 1
            ;;
    esac
}

# Show what will be cleaned up
echo "🔍 Scanning for DCM resources..."
echo

# Check Docker resources that will be affected
echo "📋 Docker Resources (that will be removed):"
echo "   Containers with DCM labels:"
docker ps -a --filter "label=devcontainer-service-manager" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null || echo "     None found"

echo "   Images with DCM labels:"
docker images --filter "label=devcontainer-service-manager" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null || echo "     None found"

echo "   Cache registry containers:"
docker ps -a --filter "name=dcm-cache-registry" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null || echo "     None found"

echo "   Volumes with DCM labels:"
docker volume ls --filter "label=devcontainer-service-manager" --format "table {{.Name}}\t{{.Size}}" 2>/dev/null || echo "     None found"

echo "   Networks with DCM labels:"
docker network ls --filter "label=devcontainer-service-manager" --format "table {{.Name}}\t{{.Driver}}" 2>/dev/null || echo "     None found"

echo "   DCM-named containers:"
docker ps -a --filter "name=dcm-" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null || echo "     None found"

echo

# Show configuration directories
echo "📋 Configuration directories (that will be removed):"
config_dirs=(
    "$HOME/.devcontainer-services"
    "$HOME/.config/devcontainer-service-manager"
    "$HOME/.dcm"
    "$HOME/.cache/devcontainer-service-manager"
)

found_configs=0
for config_dir in "${config_dirs[@]}"; do
    if [ -d "$config_dir" ]; then
        echo "   📁 $config_dir"
        found_configs=$((found_configs + 1))
    fi
done

if [ $found_configs -eq 0 ]; then
    echo "   ✅ No DCM config directories found"
fi

echo

# Check package installations
echo "📋 Package installations:"
installation_methods=()

if command_exists pipx; then
    if pipx list | grep -q devcontainer-service-manager 2>/dev/null; then
        echo "   ✅ Found pipx installation"
        installation_methods+=("pipx")
    else
        echo "   ❌ Not installed via pipx"
    fi
else
    echo "   ❌ pipx not available"
fi

# Check if DCM commands are available
dcm_commands_available=0
for cmd in dcm dcm-setup dcm-cache; do
    if command_exists "$cmd"; then
        echo "   📋 $cmd command available"
        dcm_commands_available=$((dcm_commands_available + 1))
    fi
done

if [ $dcm_commands_available -eq 0 ]; then
    echo "   ℹ️  No DCM commands found (may already be uninstalled or broken)"
fi

echo

# Confirm before proceeding
confirm "⚠️  Proceed with complete DCM uninstall?"

echo
echo "🚀 Starting standalone DCM uninstall process..."
echo

# Step 1: Try to stop DCM services gracefully (if commands work)
echo "1️⃣  Attempting to stop DCM services gracefully..."
if command_exists dcm; then
    echo "   Trying dcm clean --force..."
    if dcm clean --force 2>/dev/null; then
        echo "   ✅ DCM services stopped via dcm clean"
    else
        echo "   ⚠️ dcm clean failed - proceeding with manual cleanup"
    fi
else
    echo "   ℹ️ dcm command not available - skipping graceful shutdown"
fi

# Step 2: Stop cache registry (try both ways)
echo
echo "2️⃣  Stopping cache registry..."
if command_exists dcm-cache; then
    echo "   Trying dcm-cache registry stop..."
    dcm-cache registry stop 2>/dev/null || echo "     dcm-cache registry stop failed or not needed"
fi

echo "   Stopping cache registry containers directly..."
docker stop dcm-cache-registry 2>/dev/null && echo "     ✅ Stopped dcm-cache-registry" || echo "     ℹ️ dcm-cache-registry not running"
docker rm dcm-cache-registry 2>/dev/null && echo "     ✅ Removed dcm-cache-registry container" || echo "     ℹ️ dcm-cache-registry container not found"

# Step 3: Force stop and remove all DCM Docker resources
echo
echo "3️⃣  Force cleaning all DCM Docker resources..."

echo "   Stopping DCM-labeled containers..."
dcm_containers=$(docker ps -q --filter "label=devcontainer-service-manager" 2>/dev/null || true)
if [ -n "$dcm_containers" ]; then
    echo "$dcm_containers" | xargs docker stop 2>/dev/null && echo "     ✅ Stopped DCM containers" || echo "     ⚠️ Some containers may have failed to stop"
else
    echo "     ℹ️ No running DCM containers found"
fi

echo "   Removing DCM-labeled containers..."
dcm_containers_all=$(docker ps -aq --filter "label=devcontainer-service-manager" 2>/dev/null || true)
if [ -n "$dcm_containers_all" ]; then
    echo "$dcm_containers_all" | xargs docker rm -f 2>/dev/null && echo "     ✅ Removed DCM containers" || echo "     ⚠️ Some containers may have failed to remove"
else
    echo "     ℹ️ No DCM containers to remove"
fi

echo "   Removing DCM-labeled images..."
dcm_images=$(docker images -q --filter "label=devcontainer-service-manager" 2>/dev/null || true)
if [ -n "$dcm_images" ]; then
    echo "$dcm_images" | xargs docker rmi -f 2>/dev/null && echo "     ✅ Removed DCM images" || echo "     ⚠️ Some images may be in use"
else
    echo "     ℹ️ No DCM images to remove"
fi

echo "   Removing DCM-labeled volumes..."
dcm_volumes=$(docker volume ls -q --filter "label=devcontainer-service-manager" 2>/dev/null || true)
if [ -n "$dcm_volumes" ]; then
    echo "$dcm_volumes" | xargs docker volume rm 2>/dev/null && echo "     ✅ Removed DCM volumes" || echo "     ⚠️ Some volumes may be in use"
else
    echo "     ℹ️ No DCM volumes to remove"
fi

echo "   Removing DCM-labeled networks..."
dcm_networks=$(docker network ls -q --filter "label=devcontainer-service-manager" 2>/dev/null || true)
if [ -n "$dcm_networks" ]; then
    echo "$dcm_networks" | xargs docker network rm 2>/dev/null && echo "     ✅ Removed DCM networks" || echo "     ⚠️ Some networks may be in use"
else
    echo "     ℹ️ No DCM networks to remove"
fi

# Clean up DCM-named resources (broader sweep for older versions)
echo "   Cleaning DCM-named containers..."
dcm_named_containers=$(docker ps -aq --filter "name=dcm-" 2>/dev/null || true)
if [ -n "$dcm_named_containers" ]; then
    echo "$dcm_named_containers" | xargs docker rm -f 2>/dev/null && echo "     ✅ Removed DCM-named containers" || echo "     ⚠️ Some containers may have failed to remove"
fi

echo "   Cleaning DCM-named images..."
dcm_named_images=$(docker images -q --filter "reference=*dcm*" 2>/dev/null || true)
if [ -n "$dcm_named_images" ]; then
    echo "$dcm_named_images" | xargs docker rmi -f 2>/dev/null && echo "     ✅ Removed DCM-named images" || echo "     ⚠️ Some images may be in use"
fi

# Step 4: Clean up cache registry volumes and data
echo
echo "4️⃣  Cleaning cache registry resources..."
docker volume rm dcm-cache-registry-data 2>/dev/null && echo "   ✅ Removed cache registry data volume" || echo "   ℹ️ Cache registry data volume not found"

# Clean up registry images (be more specific to avoid removing unrelated registries)
registry_images=$(docker images -q localhost:5000/* 2>/dev/null || true)
if [ -n "$registry_images" ]; then
    echo "$registry_images" | xargs docker rmi -f 2>/dev/null && echo "   ✅ Removed cache registry images" || echo "   ⚠️ Some registry images may be in use"
fi

# Step 5: Remove configuration directories
echo
echo "5️⃣  Removing configuration directories..."
for config_dir in "${config_dirs[@]}"; do
    if [ -d "$config_dir" ]; then
        rm -rf "$config_dir" && echo "   ✅ Removed $config_dir" || echo "   ⚠️ Failed to remove $config_dir"
    else
        echo "   ℹ️ $config_dir not found (already removed)"
    fi
done

# Step 6: Aggressive package uninstallation
echo
echo "6️⃣  Aggressively uninstalling DCM packages..."

# Find all potential installation locations for DCM commands (including corrupted variants)
dcm_locations=()
# Correct command names
dcm_commands=("dcm" "dcm-setup" "dcm-cache")
# Corrupted command names (from bad installations)
corrupted_commands=("dcmworkspace" "dcm-setupworkspace" "dcm-cacheworkspace")

echo "   Scanning for DCM commands (correct and corrupted variants)..."
for cmd in "${dcm_commands[@]}" "${corrupted_commands[@]}"; do
    cmd_location=$(which "$cmd" 2>/dev/null || true)
    if [ -n "$cmd_location" ]; then
        dcm_locations+=("$cmd_location")
        echo "   Found $cmd at: $cmd_location"
    fi
done

# Try all package managers aggressively
uninstall_success=false

# Try pipx first (most common) - try both correct and corrupted package names
if command_exists pipx; then
    echo "   Trying pipx uninstall..."
    pipx_uninstalled=false

    # Try correct package name
    if pipx uninstall devcontainer-service-manager 2>/dev/null; then
        echo "   ✅ Uninstalled devcontainer-service-manager via pipx"
        pipx_uninstalled=true
        uninstall_success=true
    fi

    # Try potential corrupted package names
    corrupted_package_names=("devcontainer-service-managerworkspace" "dcm-setupworkspace")
    for pkg_name in "${corrupted_package_names[@]}"; do
        if pipx uninstall "$pkg_name" 2>/dev/null; then
            echo "   ✅ Uninstalled corrupted package $pkg_name via pipx"
            pipx_uninstalled=true
            uninstall_success=true
        fi
    done

    if [ "$pipx_uninstalled" = false ]; then
        echo "   ℹ️ No DCM packages found via pipx"
        # Force remove pipx venvs if they exist (both correct and corrupted names)
        venv_names=("devcontainer-service-manager" "devcontainer-service-managerworkspace" "dcm-setupworkspace")
        for venv_name in "${venv_names[@]}"; do
            pipx_venv_path="$HOME/.local/share/pipx/venvs/$venv_name"
            if [ -d "$pipx_venv_path" ]; then
                rm -rf "$pipx_venv_path" && echo "   ✅ Removed orphaned pipx venv: $venv_name" || echo "   ⚠️ Failed to remove pipx venv: $venv_name"
            fi
        done
    fi
fi

# Try uv - both correct and corrupted package names
if command_exists uv; then
    echo "   Trying uv uninstall..."
    uv_uninstalled=false

    # Try all possible package names
    all_package_names=("devcontainer-service-manager" "devcontainer-service-managerworkspace" "dcm-setupworkspace")
    for pkg_name in "${all_package_names[@]}"; do
        if uv pip uninstall "$pkg_name" --system 2>/dev/null; then
            echo "   ✅ Uninstalled $pkg_name via uv"
            uv_uninstalled=true
            uninstall_success=true
        fi
    done

    if [ "$uv_uninstalled" = false ]; then
        echo "   ℹ️ No DCM packages found via uv"
    fi
fi

# Try pip (system) - both correct and corrupted package names
if command_exists pip; then
    echo "   Trying pip uninstall..."
    pip_uninstalled=false

    for pkg_name in "${all_package_names[@]}"; do
        if pip uninstall "$pkg_name" -y 2>/dev/null; then
            echo "   ✅ Uninstalled $pkg_name via pip"
            pip_uninstalled=true
            uninstall_success=true
        fi
    done

    if [ "$pip_uninstalled" = false ]; then
        echo "   ℹ️ No DCM packages found via system pip"
    fi
fi

# Try pip3 (system) - both correct and corrupted package names
if command_exists pip3; then
    echo "   Trying pip3 uninstall..."
    pip3_uninstalled=false

    for pkg_name in "${all_package_names[@]}"; do
        if pip3 uninstall "$pkg_name" -y 2>/dev/null; then
            echo "   ✅ Uninstalled $pkg_name via pip3"
            pip3_uninstalled=true
            uninstall_success=true
        fi
    done

    if [ "$pip3_uninstalled" = false ]; then
        echo "   ℹ️ No DCM packages found via system pip3"
    fi
fi

# Try user pip installations - both correct and corrupted package names
for python_cmd in python python3; do
    if command_exists "$python_cmd"; then
        echo "   Trying $python_cmd -m pip uninstall (user)..."
        user_uninstalled=false

        for pkg_name in "${all_package_names[@]}"; do
            if "$python_cmd" -m pip uninstall "$pkg_name" -y --user 2>/dev/null; then
                echo "   ✅ Uninstalled $pkg_name user installation via $python_cmd"
                user_uninstalled=true
                uninstall_success=true
            fi
        done

        if [ "$user_uninstalled" = false ]; then
            echo "   ℹ️ No DCM user packages found via $python_cmd"
        fi
    fi
done

# Force remove DCM command files (always do this as package managers might leave shims)
echo "   Force removing DCM command files from all locations..."
for cmd_location in "${dcm_locations[@]}"; do
    if [ -f "$cmd_location" ]; then
        rm -f "$cmd_location" && echo "   ✅ Force removed: $cmd_location" || echo "   ⚠️ Failed to remove: $cmd_location"
    fi
done

# Handle pyenv shims specifically (they might regenerate)
if command_exists pyenv; then
    echo "   Handling pyenv shims..."
    pyenv_shims_dir="$HOME/.pyenv/shims"
    if [ -d "$pyenv_shims_dir" ]; then
        all_commands=("${dcm_commands[@]}" "${corrupted_commands[@]}")
        for cmd in "${all_commands[@]}"; do
            shim_file="$pyenv_shims_dir/$cmd"
            if [ -f "$shim_file" ]; then
                rm -f "$shim_file" && echo "   ✅ Removed pyenv shim: $cmd" || echo "   ⚠️ Failed to remove shim: $cmd"
            fi
        done

        # Rehash pyenv to update shims
        echo "   Rehashing pyenv to remove stale shims..."
        pyenv rehash 2>/dev/null && echo "   ✅ Pyenv rehashed successfully" || echo "   ⚠️ Pyenv rehash failed"
    fi
fi

# Also check and remove from common installation directories (comprehensive sweep)
echo "   Checking common installation paths for any missed commands..."
common_paths=(
    "$HOME/.local/bin"
    "/usr/local/bin"
    "/usr/bin"
    "$HOME/.pyenv/versions/*/bin"
)

for bin_pattern in "${common_paths[@]}"; do
    # Handle glob patterns (like pyenv versions)
    for bin_dir in $bin_pattern; do
        if [ -d "$bin_dir" ]; then
            # Check both correct and corrupted command names
            all_commands=("${dcm_commands[@]}" "${corrupted_commands[@]}")
            for cmd in "${all_commands[@]}"; do
                cmd_path="$bin_dir/$cmd"
                if [ -f "$cmd_path" ]; then
                    rm -f "$cmd_path" && echo "   ✅ Removed $cmd_path" || echo "   ⚠️ Failed to remove $cmd_path"
                fi
            done
        fi
    done
done

# Remove Python package directories if they still exist
echo "   Removing any remaining package files..."
python_paths=(
    "$HOME/.local/lib/python*/site-packages/devcontainer_services*"
    "/usr/local/lib/python*/site-packages/devcontainer_services*"
    "$HOME/.pyenv/versions/*/lib/python*/site-packages/devcontainer_services*"
)

for pattern in "${python_paths[@]}"; do
    for path in $pattern; do
        if [ -e "$path" ]; then
            rm -rf "$path" && echo "   ✅ Removed package directory: $path" || echo "   ⚠️ Failed to remove: $path"
        fi
    done
done

# Step 7: Clean shell configurations
echo
echo "7️⃣  Cleaning shell configurations..."
shell_configs=(
    "$HOME/.bashrc"
    "$HOME/.zshrc"
    "$HOME/.profile"
)

for shell_config in "${shell_configs[@]}"; do
    if [ -f "$shell_config" ]; then
        # Remove DCM-related lines
        if grep -q "DCM\|devcontainer-service-manager\|dcm-status\|docker-cleanup\|ws-check" "$shell_config" 2>/dev/null; then
            echo "   Cleaning DCM references from $shell_config"
            sed -i.bak '/DCM\|devcontainer-service-manager\|dcm-status\|docker-cleanup\|ws-check/d' "$shell_config" 2>/dev/null || echo "     ⚠️ Failed to clean $shell_config"
        else
            echo "   ℹ️ No DCM references found in $shell_config"
        fi
    fi
done

# Step 8: Final validation
echo
echo "8️⃣  Validating complete removal..."
echo

validation_passed=true
issues=()

echo "📋 Command availability:"
commands_remaining=0
# Check both correct and corrupted command names
all_commands=("${dcm_commands[@]}" "${corrupted_commands[@]}")
for cmd in "${all_commands[@]}"; do
    if command_exists_validation "$cmd"; then
        echo "   ❌ $cmd is still available"
        # Try to show where it's located for debugging
        cmd_location=$(command -v "$cmd" 2>/dev/null || echo "location unknown")
        echo "      Located at: $cmd_location"
        issues+=("Command $cmd still available at $cmd_location")
        validation_passed=false
        commands_remaining=$((commands_remaining + 1))
    else
        echo "   ✅ $cmd successfully removed (or was not present)"
    fi
done

if [ $commands_remaining -eq 0 ]; then
    echo "   ✅ All DCM commands (correct and corrupted variants) successfully removed"
else
    echo "   ❌ $commands_remaining DCM commands still present"
fi

echo
echo "📋 Docker resources:"
dcm_containers_remaining=$(docker ps -aq --filter "label=devcontainer-service-manager" 2>/dev/null | wc -l)
dcm_images_remaining=$(docker images -q --filter "label=devcontainer-service-manager" 2>/dev/null | wc -l)
dcm_volumes_remaining=$(docker volume ls -q --filter "label=devcontainer-service-manager" 2>/dev/null | wc -l)
cache_containers_remaining=$(docker ps -aq --filter "name=dcm-cache-registry" 2>/dev/null | wc -l)

echo "   DCM containers: $dcm_containers_remaining"
echo "   DCM images: $dcm_images_remaining"
echo "   DCM volumes: $dcm_volumes_remaining"
echo "   Cache registry: $cache_containers_remaining"

if [ "$dcm_containers_remaining" -eq 0 ] && [ "$dcm_images_remaining" -eq 0 ] && [ "$dcm_volumes_remaining" -eq 0 ] && [ "$cache_containers_remaining" -eq 0 ]; then
    echo "   ✅ All Docker resources cleaned"
else
    echo "   ⚠️ Some Docker resources remain"
    validation_passed=false
fi

echo
echo "📋 Configuration directories:"
config_remaining=0
for config_dir in "${config_dirs[@]}"; do
    if [ -d "$config_dir" ]; then
        echo "   ❌ $config_dir still exists"
        config_remaining=$((config_remaining + 1))
    fi
done

if [ $config_remaining -eq 0 ]; then
    echo "   ✅ All configuration directories removed"
else
    echo "   ⚠️ $config_remaining configuration directories remain"
    validation_passed=false
fi

echo
echo "=============================================================="
if [ "$validation_passed" = true ]; then
    echo "🎉 DCM Uninstall Complete!"
    echo "✅ All DCM components successfully removed"
    echo "✅ System is clean and ready for fresh DCM installation"
    echo "✅ Zero traces of devcontainer-service-manager remain"
    exit 0
else
    echo "❌ DCM Uninstall FAILED"
    echo "❌ Some DCM components still present - uninstall incomplete:"
    for issue in "${issues[@]}"; do
        echo "   • $issue"
    done
    echo
    echo "💡 This should not happen with the aggressive uninstall script."
    echo "💡 Please report this as a bug with the output above."
    echo "💡 You can try running the script again or manually remove remaining components."
    exit 1
fi

echo
echo "🔄 For fresh DCM installation:"
echo "   pipx install devcontainer-service-manager[workstation]"
echo "   dcm-setup install --profile data-engineering"
echo
