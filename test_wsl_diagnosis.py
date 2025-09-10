#!/usr/bin/env python3
"""
Diagnostic script to debug exactly what happens with WSL config optimization.
Run this to see why the file path isn't being shown.
"""

import os
import sys

sys.path.insert(0, "src")

from devcontainer_services.workstation.setup import WorkstationOptimizer


def diagnose_wsl_config():
    """Diagnose WSL config optimization step by step."""
    print("=== WSL Config Optimization Diagnosis ===\n")

    # Create optimizer with debug mode
    optimizer = WorkstationOptimizer(debug_mode=True)

    print(f"System Info: {optimizer.system_info}")
    print()

    if not optimizer.system_info.get("is_wsl"):
        print("❌ WSL NOT DETECTED - This could be why no file is created")
        print("💡 The optimization only runs in WSL2 environments")
        return

    print("✅ WSL detected, proceeding with diagnosis...")
    print()

    # Check Windows Users directory and username detection
    windows_home = "/mnt/c/Users"
    print(f"🔍 Checking Windows Users directory: {windows_home}")

    if os.path.exists(windows_home):
        print("✅ Windows Users directory exists")

        # Test Method 1: WSL username matching
        try:
            import subprocess

            result = subprocess.run(["whoami"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                wsl_username = result.stdout.strip()
                print(f"👤 WSL username from whoami: {wsl_username}")

                potential_windows_path = os.path.join(windows_home, wsl_username)
                if os.path.isdir(potential_windows_path):
                    print(f"✅ MATCH FOUND: WSL user {wsl_username} exists in Windows Users")
                    print(f"📄 Would create file at: /mnt/c/Users/{wsl_username}/.wslconfig")
                    print(f"🪟 Windows path: C:\\Users\\{wsl_username}\\.wslconfig")
                else:
                    print(f"❌ WSL username {wsl_username} NOT FOUND in Windows Users directory")
                    print("💡 Will fall back to directory enumeration method")
            else:
                print("❌ Failed to get WSL username via whoami")
        except Exception as e:
            print(f"❌ Error getting WSL username: {e}")

        # Test Method 2: Directory enumeration fallback
        print("\n🔍 Testing directory enumeration method...")
        try:
            users = os.listdir(windows_home)
            print(f"📁 Found directories: {users}")

            # Apply same filtering as the code
            filtered_users = [u for u in users if os.path.isdir(os.path.join(windows_home, u))]
            print(f"📂 Directory check: {filtered_users}")

            filtered_users = [
                u
                for u in filtered_users
                if u not in ["Public", "Default", "Default User", "All Users"]
            ]
            print(f"👤 After system filter: {filtered_users}")

            if len(filtered_users) == 1:
                windows_user = filtered_users[0]
                print(f"✅ Single user detected via enumeration: {windows_user}")
                print(f"📄 Would create file at: /mnt/c/Users/{windows_user}/.wslconfig")
                print(f"🪟 Windows path: C:\\Users\\{windows_user}\\.wslconfig")
            elif len(filtered_users) > 1:
                print(f"⚠️ MULTIPLE USERS DETECTED: {filtered_users}")
                print("❌ This causes fallback to manual instructions")
            else:
                print("❌ NO VALID USERS DETECTED after filtering")
                print("💡 This causes fallback to manual instructions")

        except Exception as e:
            print(f"❌ Error listing Windows Users directory: {e}")
    else:
        print("❌ Windows Users directory NOT FOUND")
        print("💡 This is why no file was created - cannot access Windows filesystem")

    print("\n" + "=" * 60)
    print("🧪 Now running actual optimization to see output...")
    print("=" * 60)

    result = optimizer.apply_wsl_config_optimization(dry_run=False)
    print(f"\nOptimization result: {result}")


if __name__ == "__main__":
    diagnose_wsl_config()
