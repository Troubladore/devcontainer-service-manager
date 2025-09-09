#!/usr/bin/env python3
"""
CLI commands for workstation optimization and setup.

Provides commands to optimize development workstations for data engineering,
with special focus on WSL2 performance and Docker optimization.
"""

import click
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

from .setup import WorkstationOptimizer, validate_workstation_setup

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def setup():
    """Workstation optimization and setup commands."""
    pass


@setup.command()
@click.option("--profile", default="data-engineering", help="Optimization profile to apply")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def install(profile, dry_run):
    """Install and configure workstation optimizations."""
    console.print(f"🚀 Setting up workstation optimization (profile: {profile})")
    
    if dry_run:
        console.print("🔍 Dry run mode - no changes will be made")
    
    optimizer = WorkstationOptimizer()
    
    # Show system information
    system_panel = f"""
Platform: {optimizer.system_info['platform']}
Machine: {optimizer.system_info['machine']}
Python: {optimizer.system_info['python_version']}
WSL: {'Yes' if optimizer.system_info['is_wsl'] else 'No'}
Docker: {'Available' if optimizer.system_info['docker_available'] else 'Not Available'}
"""
    
    if optimizer.system_info['is_wsl']:
        system_panel += f"WSL Version: {optimizer.system_info.get('wsl_version', 'unknown')}\n"
        system_panel += f"Windows Build: {optimizer.system_info.get('windows_build', 'unknown')}\n"
    
    console.print(Panel(system_panel, title="System Information"))
    
    if not dry_run:
        if profile == "data-engineering":
            console.print("🔧 Applying data engineering optimizations...")
            
            # Apply optimizations
            if optimizer.system_info['is_wsl']:
                success = optimizer.optimize_wsl2_performance()
                if success:
                    console.print("✅ WSL2 optimizations applied")
                else:
                    console.print("⚠️ Some WSL2 optimizations failed")
            
            console.print("✅ Workstation optimization complete!")
            console.print("💡 Run 'dcm-setup validate' to check your configuration")
        else:
            console.print(f"❌ Unknown profile: {profile}")
            console.print("Available profiles: data-engineering")
    else:
        console.print("Use without --dry-run to apply optimizations")


@setup.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed diagnostic information")
@click.option("--debug", is_flag=True, help="Show debug output including detection methods")
def validate(verbose, debug):
    """Validate workstation setup and performance configuration."""
    
    # Configure logging level based on flags
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
        console.print("🐛 Debug mode enabled - showing detailed detection methods")
    elif verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        console.print("📊 Verbose mode enabled - showing detailed information")
    
    console.print("🔍 Validating workstation setup...")
    
    try:
        results = validate_workstation_setup(debug_mode=debug)
        system_info = results["system_info"]
        validation = results["validation"]
        
        # Show overall status
        overall_issues = 0
        overall_recommendations = 0
        
        for category, checks in validation.items():
            if isinstance(checks, dict):
                overall_issues += len(checks.get("issues", []))
                overall_recommendations += len(checks.get("recommendations", []))
        
        if overall_issues == 0:
            status_text = "✅ No critical issues found"
        else:
            status_text = f"⚠️ Found {overall_issues} issues requiring attention"
        
        if overall_recommendations > 0:
            status_text += f"\n💡 {overall_recommendations} recommendations for optimization"
        
        console.print(Panel(status_text, title="Validation Summary"))
        
        # Docker validation
        docker_checks = validation.get("docker", {})
        if docker_checks:
            docker_text = ""
            if docker_checks.get("available"):
                docker_text += "✅ Docker is available and responding\n"
            else:
                docker_text += "❌ Docker is not available or not responding\n"
            
            for issue in docker_checks.get("issues", []):
                docker_text += f"❌ {issue}\n"
            
            for rec in docker_checks.get("recommendations", []):
                docker_text += f"💡 {rec}\n"
            
            # Add Docker-specific documentation link if there are recommendations
            if docker_checks.get("recommendations"):
                docker_text += "\n📖 Docker optimization details: docs/optimization-guide.md#docker-optimizations\n"
            
            if docker_text:
                console.print(Panel(docker_text.strip(), title="Docker Validation"))
        
        # WSL2 validation
        if system_info.get("is_wsl"):
            wsl_checks = validation.get("wsl2", {})
            if wsl_checks:
                wsl_text = f"Version: {wsl_checks.get('version', 'unknown')}\n"
                
                for issue in wsl_checks.get("issues", []):
                    wsl_text += f"❌ {issue}\n"
                
                for rec in wsl_checks.get("recommendations", []):
                    wsl_text += f"💡 {rec}\n"
                
                # Add WSL2-specific documentation link if there are recommendations  
                if wsl_checks.get("recommendations") or wsl_checks.get("issues"):
                    wsl_text += "\n📖 WSL2 optimization details: docs/optimization-guide.md#wsl2-optimizations\n"
                
                console.print(Panel(wsl_text.strip(), title="WSL2 Validation"))
        
        # Filesystem validation
        fs_checks = validation.get("filesystem", {})
        if fs_checks:
            fs_text = f"Location: {fs_checks.get('location', 'unknown')}\n"
            fs_text += f"Performance Tier: {fs_checks.get('performance_tier', 'unknown')}\n"
            
            for issue in fs_checks.get("issues", []):
                fs_text += f"❌ {issue}\n"
            
            for rec in fs_checks.get("recommendations", []):
                fs_text += f"💡 {rec}\n"
            
            # Add filesystem-specific documentation link if there are recommendations
            if fs_checks.get("recommendations") or fs_checks.get("issues"):
                fs_text += "\n📖 Filesystem optimization details: docs/optimization-guide.md#wsl2-filesystem-performance\n"
            
            console.print(Panel(fs_text.strip(), title="Filesystem Performance"))
        
        # Resources validation
        resource_checks = validation.get("resources", {})
        if resource_checks:
            resource_text = ""
            
            if "disk_available" in resource_checks:
                resource_text += f"Disk Available: {resource_checks['disk_available']}\n"
            
            for issue in resource_checks.get("issues", []):
                resource_text += f"❌ {issue}\n"
            
            for rec in resource_checks.get("recommendations", []):
                resource_text += f"💡 {rec}\n"
            
            # Add resource-specific documentation link if there are recommendations
            if resource_checks.get("recommendations") or resource_checks.get("issues"):
                resource_text += "\n📖 Resource optimization details: docs/optimization-guide.md#system-resource-optimizations\n"
            
            if resource_text:
                console.print(Panel(resource_text.strip(), title="System Resources"))
        
        # Final recommendations with documentation links
        if overall_issues == 0 and overall_recommendations == 0:
            console.print("🎉 Your workstation is optimally configured!")
        elif overall_issues > 0:
            console.print(f"🔧 Address the {overall_issues} issues above for optimal performance")
            console.print("🚀 Quick fix: dcm-setup optimize --all")
            console.print("📖 For detailed context and implementation guidance:")
            console.print("   https://github.com/your-repo/devcontainer-service-manager/blob/main/docs/optimization-guide.md")
        else:
            console.print(f"💡 Consider the {overall_recommendations} recommendations for further optimization")
            console.print("🚀 Quick apply: dcm-setup optimize --all")
            console.print("📖 For detailed context and implementation guidance:")
            console.print("   https://github.com/your-repo/devcontainer-service-manager/blob/main/docs/optimization-guide.md")
            
    except Exception as e:
        console.print(f"❌ Validation failed: {e}")
        logger.error(f"Validation error: {e}")


@setup.command()
def troubleshoot():
    """Diagnose and fix common workstation issues."""
    console.print("🔧 Running workstation troubleshooting...")
    
    # Run validation first
    try:
        results = validate_workstation_setup(debug_mode=False)  # Don't overwhelm troubleshoot with debug
        validation = results["validation"]
        optimizer = results["optimizer"]
        
        # Common issue fixes
        fixes_applied = 0
        
        # Fix 1: WSL2 filesystem performance
        fs_checks = validation.get("filesystem", {})
        if fs_checks.get("performance_tier") == "slow":
            console.print("🚨 Detected slow filesystem performance (Windows to WSL cross-mount)")
            console.print("💡 Recommendation: Move your repositories to WSL2 filesystem")
            console.print("   Example: mkdir -p ~/repos && cd ~/repos")
            console.print("   Then clone/move your repositories there")
            fixes_applied += 1
        
        # Fix 2: Docker availability
        docker_checks = validation.get("docker", {})
        if not docker_checks.get("available"):
            console.print("🚨 Docker is not available")
            console.print("💡 Troubleshooting steps:")
            console.print("   1. Check if Docker Desktop is running (Windows/Mac)")
            console.print("   2. Check Docker daemon status: systemctl status docker (Linux)")
            console.print("   3. Verify WSL2 integration is enabled (Docker Desktop settings)")
            fixes_applied += 1
        
        # Fix 3: WSL2 version
        if optimizer.system_info.get("is_wsl"):
            wsl_checks = validation.get("wsl2", {})
            if wsl_checks.get("version") != "2":
                console.print("🚨 WSL version is not 2")
                console.print("💡 Upgrade to WSL2:")
                console.print("   Run in Windows PowerShell (as Administrator):")
                console.print("   wsl --set-version <distro-name> 2")
                fixes_applied += 1
        
        # Fix 4: Missing cache registry
        try:
            from ..caching.fingerprint import CrossRepoCacheManager
            cache_manager = CrossRepoCacheManager()
            registry_status = cache_manager.get_registry_status()
            
            if not registry_status.get("running"):
                console.print("🚨 Local Docker registry not running")
                console.print("💡 Starting registry for cross-repo caching:")
                if cache_manager.ensure_local_registry():
                    console.print("✅ Registry started successfully")
                    fixes_applied += 1
                else:
                    console.print("❌ Failed to start registry")
        except ImportError:
            pass
        
        if fixes_applied == 0:
            console.print("✅ No common issues detected - your setup looks good!")
            console.print("💡 Run 'dcm-setup validate' for detailed analysis")
        else:
            console.print(f"🔧 Addressed {fixes_applied} potential issues")
            console.print("💡 Run 'dcm-setup validate' to verify improvements")
            
    except Exception as e:
        console.print(f"❌ Troubleshooting failed: {e}")
        logger.error(f"Troubleshooting error: {e}")


@setup.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed diagnostic information")
@click.option("--debug", is_flag=True, help="Show debug output including detection methods")
def wsl2_optimize(verbose, debug):
    """Apply WSL2-specific performance optimizations."""
    
    # Configure logging level based on flags
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
        console.print("🐛 Debug mode enabled - showing detailed WSL2 detection and optimization steps")
    elif verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        console.print("📊 Verbose mode enabled - showing detailed optimization information")
    
    console.print("🚀 Applying WSL2 performance optimizations...")
    
    optimizer = WorkstationOptimizer(debug_mode=debug)
    
    if not optimizer.system_info.get("is_wsl"):
        console.print("❌ This command only works in WSL environments")
        if debug or verbose:
            console.print("💡 WSL2 detection failed. Run with --debug to see detection method details")
        return
    
    if optimizer.system_info.get("wsl_version") != "2":
        console.print("⚠️ WSL2 not detected, but applying available optimizations...")
        if debug or verbose:
            console.print(f"📊 Detected WSL version: {optimizer.system_info.get('wsl_version')}")
    
    try:
        success = optimizer.optimize_wsl2_performance()
        
        if success:
            console.print("✅ WSL2 optimizations applied successfully")
            console.print("💡 Restart your terminal to apply all changes")
            console.print("💡 Consider restarting WSL: wsl --shutdown (in Windows)")
        else:
            console.print("⚠️ Some optimizations failed - check logs for details")
            
    except Exception as e:
        console.print(f"❌ WSL2 optimization failed: {e}")
        logger.error(f"WSL2 optimization error: {e}")


@setup.command()
@click.option("--docker-buildkit", is_flag=True, help="Enable Docker BuildKit optimization")
@click.option("--wsl-config", is_flag=True, help="Apply WSL2 .wslconfig optimization")
@click.option("--filesystem", is_flag=True, help="Get filesystem migration guidance")
@click.option("--disk-cleanup", is_flag=True, help="Clean up Docker disk space")
@click.option("--all", "apply_all", is_flag=True, help="Apply all safe optimizations")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def optimize(docker_buildkit, wsl_config, filesystem, disk_cleanup, apply_all, dry_run):
    """Apply workstation optimizations automatically."""
    
    if dry_run:
        console.print("🔍 Dry run mode - no changes will be made")
    
    from .setup import WorkstationOptimizer
    optimizer = WorkstationOptimizer()
    
    # If no specific flags, show help
    if not any([docker_buildkit, wsl_config, filesystem, disk_cleanup, apply_all]):
        console.print("🚀 DCM Workstation Optimization")
        console.print("")
        console.print("Available optimizations:")
        console.print("  --docker-buildkit   Enable Docker BuildKit (149x faster builds)")
        console.print("  --wsl-config        Create optimized .wslconfig file")
        console.print("  --filesystem        Get filesystem migration guidance")
        console.print("  --disk-cleanup      Clean up Docker disk space")
        console.print("  --all               Apply all safe optimizations")
        console.print("")
        console.print("Example usage:")
        console.print("  dcm-setup optimize --docker-buildkit")
        console.print("  dcm-setup optimize --all --dry-run")
        console.print("")
        console.print("💡 Run 'dcm-setup validate' to see what optimizations are recommended")
        return
    
    results = {}
    
    try:
        if apply_all:
            console.print("🚀 Applying all safe optimizations...")
            results = optimizer.apply_all_safe_optimizations(dry_run=dry_run)
        else:
            # Apply individual optimizations
            if docker_buildkit:
                console.print("⚡ Applying Docker BuildKit optimization...")
                results['docker_buildkit'] = optimizer.apply_docker_buildkit_optimization(dry_run=dry_run)
            
            if wsl_config:
                console.print("🪟 Applying WSL2 configuration optimization...")
                results['wsl_config'] = optimizer.apply_wsl_config_optimization(dry_run=dry_run)
            
            if filesystem:
                console.print("📁 Analyzing filesystem performance...")
                results['filesystem'] = optimizer.apply_filesystem_migration_helper(dry_run=dry_run)
            
            if disk_cleanup:
                console.print("🧹 Cleaning up Docker resources...")
                results['disk_cleanup'] = optimizer.apply_disk_cleanup_optimization(dry_run=dry_run)
        
        # Summary
        if results:
            successful = sum(results.values())
            total = len(results)
            
            if successful == total:
                console.print(f"✅ All {total} optimizations applied successfully!")
            else:
                failed = total - successful
                console.print(f"⚠️ {successful}/{total} optimizations successful, {failed} failed")
            
            if not dry_run and any(['docker_buildkit' in results, 'wsl_config' in results]):
                console.print("💡 Some changes require restarting your terminal or WSL")
                console.print("💡 Run 'dcm-setup validate' to verify optimizations")
        
    except Exception as e:
        console.print(f"❌ Optimization failed: {e}")
        logger.error(f"Optimization error: {e}")


@setup.command()
def cleanup():
    """Clean up Docker resources and verify system is clean."""
    console.print("🧹 Cleaning up Docker resources...")
    
    try:
        from ..caching.cleanup import get_resource_usage, emergency_cleanup
        
        # Show current usage
        usage = get_resource_usage()
        console.print(f"Current Docker usage:")
        console.print(f"  Containers: {usage.get('containers', 'unknown')}")
        console.print(f"  Networks: {usage.get('networks', 'unknown')}")
        console.print(f"  Volumes: {usage.get('volumes', 'unknown')}")
        
        # Run emergency cleanup
        emergency_cleanup()
        
        # Show post-cleanup usage
        usage_after = get_resource_usage()
        console.print(f"After cleanup:")
        console.print(f"  Containers: {usage_after.get('containers', 'unknown')}")
        console.print(f"  Networks: {usage_after.get('networks', 'unknown')}")  
        console.print(f"  Volumes: {usage_after.get('volumes', 'unknown')}")
        
        console.print("✅ Cleanup completed")
        
    except ImportError:
        console.print("❌ Cleanup module not available")
    except Exception as e:
        console.print(f"❌ Cleanup failed: {e}")
        logger.error(f"Cleanup error: {e}")


def main():
    """Main entry point for dcm-setup command."""
    setup()


if __name__ == "__main__":
    main()