"""
Machine ID Checker
Display the machine ID for license generation
"""

import platform
import uuid
import subprocess
import os


def get_machine_id():
    """Get machine-specific identifier (cross-platform)"""
    # Get machine-specific identifier based on OS
    machine_id = None
    system = platform.system()
    
    print(f"Detected OS: {system}")
    print("Checking for machine identifier...\n")
    
    if system == "Linux":
        # Try to read machine-id on Linux
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
                print("✓ Found machine ID in /etc/machine-id")
        except:
            try:
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    machine_id = f.read().strip()
                    print("✓ Found machine ID in /var/lib/dbus/machine-id")
            except:
                print("✗ Could not find machine-id files")
    
    elif system == "Windows":
        # Try to get machine GUID on Windows
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    machine_id = lines[1].strip()
                    print("✓ Found machine UUID via WMIC")
        except:
            print("✗ Could not get machine UUID from WMIC")
    
    elif system == "Darwin":  # macOS
        # Try to get hardware UUID on macOS
        try:
            result = subprocess.run(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        machine_id = line.split('"')[3]
                        print("✓ Found hardware UUID via ioreg")
                        break
        except:
            print("✗ Could not get hardware UUID from ioreg")
    
    # Fallback: use MAC address + hostname + username (cross-platform)
    if not machine_id:
        print("\nUsing fallback identifier (MAC + hostname + user)...")
        mac = uuid.getnode()
        hostname = platform.node()
        username = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
        machine_id = f"{mac}-{hostname}-{username}"
        print("✓ Generated fallback identifier")
    
    return machine_id


def main():
    print("=" * 70)
    print("Machine ID Checker")
    print("Restic Backup Manager - License System")
    print("=" * 70)
    print()
    
    machine_id = get_machine_id()
    
    print("\n" + "=" * 70)
    print("YOUR MACHINE ID:")
    print("=" * 70)
    print(machine_id)
    print("=" * 70)
    
    print("\nWhen requesting a license key:")
    print("1. Copy the Machine ID shown above")
    print("2. Send it to your license provider")
    print("3. They will generate a license key for this specific machine")
    print("4. Enter the license key in the application's License Activation dialog")
    
    print("\n" + "=" * 70)
    
    # Try to copy to clipboard (if pyperclip is available)
    try:
        import pyperclip
        pyperclip.copy(machine_id)
        print("\n✓ Machine ID copied to clipboard!")
    except ImportError:
        print("\nTip: Install 'pyperclip' to auto-copy Machine ID to clipboard")
        print("     pip install pyperclip")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
