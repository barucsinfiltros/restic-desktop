"""
Test script for license system
This demonstrates the license generation and validation process
"""

import sys
import os

# Add project root to path when running from tools/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from license_generator import generate_license_key


def test_license_system():
    """Test the license generation and validation"""
    
    # Simulate a machine ID (in real app, this comes from get_machine_id())
    test_machine_id = "TEST-MACHINE-12345-USER"
    
    print("=" * 70)
    print("License System Test")
    print("=" * 70)
    print(f"\nTest Machine ID: {test_machine_id}\n")
    
    # Test 1: Unlimited license
    print("\n" + "-" * 70)
    print("TEST 1: Unlimited License")
    print("-" * 70)
    license_unlimited = generate_license_key(test_machine_id, expiry_days=None)
    print(f"License Key: {license_unlimited}")
    print("Expiration: Unlimited")
    
    # Test 2: 30-day license
    print("\n" + "-" * 70)
    print("TEST 2: 30-Day Trial License")
    print("-" * 70)
    license_30day = generate_license_key(test_machine_id, expiry_days=30)
    print(f"License Key: {license_30day}")
    print("Expiration: 30 days from now")
    
    # Test 3: 1-year license
    print("\n" + "-" * 70)
    print("TEST 3: 1-Year License")
    print("-" * 70)
    license_1year = generate_license_key(test_machine_id, expiry_days=365)
    print(f"License Key: {license_1year}")
    print("Expiration: 365 days from now")
    
    # Save test license
    print("\n" + "-" * 70)
    print("Saving test license to 'test_license.key'")
    print("-" * 70)
    with open('test_license.key', 'w') as f:
        f.write(license_unlimited)
    print("✓ License saved successfully")
    
    print("\n" + "=" * 70)
    print("Tests completed!")
    print("=" * 70)
    print("\nTo test in the application:")
    print("1. Copy 'test_license.key' to 'license.key'")
    print("2. Run the main application")
    print("3. If your machine ID matches, it will validate successfully")
    print("\nNote: This test license is for machine ID:", test_machine_id)
    print("It will only work if your actual machine ID matches this value.")
    print("=" * 70)


if __name__ == "__main__":
    test_license_system()
