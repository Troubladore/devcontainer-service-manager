#!/usr/bin/env python3
"""
Debug script to test WSL config optimization with detailed logging.
Run this in your WSL2 environment to see exactly what's happening.
"""

import os
import sys

sys.path.insert(0, "src")

from devcontainer_services.workstation.setup import WorkstationOptimizer


def test_wsl_config_debug():
    """Test WSL config optimization with maximum debug output."""
    print("=== WSL Config Optimization Debug Test ===\n")

    # Create optimizer with debug mode enabled
    optimizer = WorkstationOptimizer(debug_mode=True)

    print(f"System Info: {optimizer.system_info}")
    print(f"Is WSL: {optimizer.system_info.get('is_wsl')}")
    print(f"Platform: {optimizer.system_info.get('platform')}")
    print()

    if not optimizer.system_info.get("is_wsl"):
        print("❌ Not running in WSL2 - this test should be run inside WSL2")
        print("💡 If you ARE in WSL2 but this shows False, there may be a detection issue")
        return

    print("🔍 Testing WSL config optimization (DRY RUN)...")
    result_dry = optimizer.apply_wsl_config_optimization(dry_run=True)
    print(f"Dry run result: {result_dry}")
    print()

    print("🔧 Testing WSL config optimization (REAL RUN)...")
    result_real = optimizer.apply_wsl_config_optimization(dry_run=False)
    print(f"Real run result: {result_real}")
    print()

    # Check if .wslconfig was created
    windows_users_dir = "/mnt/c/Users"
    if os.path.exists(windows_users_dir):
        print(f"📁 Windows Users directory found at {windows_users_dir}")
        users = os.listdir(windows_users_dir)
        print(f"   Users: {users}")

        # Check for .wslconfig in each user directory
        for user in users:
            if user not in ["Public", "Default", "Default User", "All Users"]:
                wsl_path = f"{windows_users_dir}/{user}/.wslconfig"
                windows_path = f"C:\\Users\\{user}\\.wslconfig"
                exists = os.path.exists(wsl_path)

                print(f"   {user}/.wslconfig: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
                print(f"      WSL path: {wsl_path}")
                print(f"      Windows path: {windows_path}")

                if exists:
                    file_size = os.path.getsize(wsl_path)
                    with open(wsl_path) as f:
                        content = f.read()
                    print(f"      File size: {file_size} bytes")
                    print("      Content preview:")
                    for _i, line in enumerate(content.split("\n")[:5]):  # First 5 lines
                        print(f"        {line}")
                    print(f"      Verification from Windows: Get-Content '{windows_path}'")
                else:
                    print(f"      File should be created at: {windows_path}")
    else:
        print(f"❌ Windows Users directory not found at {windows_users_dir}")
        print("   This suggests you may not be in WSL2 or there's a mount issue")


if __name__ == "__main__":
    test_wsl_config_debug()
