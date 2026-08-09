"""
DEPRECATED — obsolete after open-source / free release.

License Key Generator for Restic Desktop
Version: 1.0.0

This script generated license keys tied to specific machine IDs.
The app no longer requires activation; keep only for historical reference.
"""

import hashlib
import hmac
import base64
from datetime import datetime, timedelta
import argparse

# SECRET KEY - Must match the one in restic_manager.py
# KEEP THIS SECRET! Do not distribute this file to users.
_SECRET_KEY = b"restic-manager-secret-key-change-this-in-production"


def generate_license_key(machine_id: str, expiry_days: int = None) -> str:
    """
    Generate a license key for a specific machine ID
    
    Args:
        machine_id: The machine ID to generate license for (from the app)
        expiry_days: Number of days until expiration (None = unlimited)
    
    Returns:
        Base64-encoded license key
    """
    # Create a short hash of machine ID
    machine_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
    
    # Calculate expiry date
    if expiry_days is None:
        expiry_str = "unlimited"
    else:
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        expiry_str = expiry_date.strftime("%Y-%m-%d")
    
    # Create signature
    payload = f"{machine_hash}:{expiry_str}"
    signature = hmac.new(
        _SECRET_KEY,
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    
    # Combine into license key
    license_data = f"{machine_hash}:{expiry_str}:{signature}"
    license_key = base64.b64encode(license_data.encode()).decode('utf-8')
    
    return license_key


def main():
    parser = argparse.ArgumentParser(
        description='Generate license keys for Restic Desktop',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'machine_id',
        type=str,
        help='Machine ID from the application (shown in license dialog)'
    )
    
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=None,
        help='Number of days until expiration (default: unlimited)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file to save license key (optional)'
    )
    
    args = parser.parse_args()
    
    # Generate license key
    license_key = generate_license_key(args.machine_id, args.days)
    
    # Display information
    print("=" * 70)
    print("License Key Generated Successfully")
    print("=" * 70)
    print(f"\nMachine ID: {args.machine_id}")
    
    if args.days is None:
        print(f"Expiration: Unlimited")
    else:
        expiry_date = datetime.now() + timedelta(days=args.days)
        print(f"Expiration: {expiry_date.strftime('%Y-%m-%d')} ({args.days} days)")
    
    print("\n" + "-" * 70)
    print("LICENSE KEY:")
    print("-" * 70)
    print(license_key)
    print("-" * 70)
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(license_key)
        print(f"\nLicense key saved to: {args.output}")
    
    print("\nProvide this license key to the customer.")
    print("They can enter it in the License Activation dialog.")
    print("=" * 70)


if __name__ == "__main__":
    main()
