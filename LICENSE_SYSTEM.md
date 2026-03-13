# License System Documentation

## Overview

The Restic Backup Manager now includes a license key system that ties licenses to specific machines using unique hardware identifiers. This prevents unauthorized sharing of license keys.

## How It Works

1. **Machine ID**: Each machine has a unique identifier based on:
   - **Windows**: Machine UUID from WMIC
   - **Linux**: `/etc/machine-id` or `/var/lib/dbus/machine-id`
   - **macOS**: Hardware UUID from IOPlatformExpertDevice
   - **Fallback**: MAC address + hostname + username

2. **License Key Structure**: 
   - License keys are cryptographically signed using HMAC-SHA256
   - Format: `BASE64(machine_hash:expiry_date:signature)`
   - Cannot be forged or transferred to other machines

3. **Validation**: 
   - The application validates the license on startup
   - Checks machine ID match
   - Verifies cryptographic signature
   - Validates expiration date

## For Developers/Administrators

### Generating License Keys

Use the `license_generator.py` script to create license keys:

```bash
# Generate unlimited license for a specific machine
python license_generator.py "MACHINE_ID_HERE"

# Generate 365-day license
python license_generator.py "MACHINE_ID_HERE" --days 365

# Save to file
python license_generator.py "MACHINE_ID_HERE" --days 365 --output license.key
```

### Getting Machine ID

Users can get their Machine ID from the License Activation dialog that appears when no valid license is found. They can copy it and send it to you for license generation.

### Changing the Secret Key

**IMPORTANT**: Before distributing your application, change the secret key in both files:

1. In `restic_manager.py` (Line ~148):
```python
_SECRET_KEY = b"your-unique-secret-key-here"
```

2. In `license_generator.py` (Line ~14):
```python
_SECRET_KEY = b"your-unique-secret-key-here"
```

The secret keys in both files **MUST match** for license validation to work.

**Security Note**: Keep `license_generator.py` private and secure. Do NOT distribute it to users.

## For End Users

### Activating Your License

1. Launch Restic Backup Manager
2. If no valid license is found, the License Activation dialog will appear
3. Copy your Machine ID using the "Copy" button
4. Send your Machine ID to support to request a license
5. Once you receive your license key, paste it into the "License Key" field
6. Click "Activate License"

### License Storage

License keys are stored in `license.key` in the same directory as the application. This file contains your activated license and should not be deleted.

## Example Workflow

### Customer Request:
1. Customer runs application
2. Gets Machine ID: `ABC123-HOSTNAME-USER` (example)
3. Sends Machine ID to you via email

### You Generate License:
```bash
python license_generator.py "ABC123-HOSTNAME-USER" --days 365
```

### Customer Activation:
1. Customer receives license key via email
2. Pastes into License Activation dialog
3. Clicks "Activate License"
4. Application validates and starts

## License Types

### Unlimited License
```bash
python license_generator.py "MACHINE_ID"
```
- Never expires
- Best for perpetual licenses

### Time-Limited License
```bash
python license_generator.py "MACHINE_ID" --days 30
```
- Expires after specified days
- Good for trials or subscriptions

## Troubleshooting

### "License key is not valid for this machine"
- The license was generated for a different machine
- Request a new license with the correct Machine ID

### "License key signature is invalid"
- Secret keys don't match between app and generator
- License key may be corrupted

### "License expired on YYYY-MM-DD"
- License has expired
- Request a new license or renewal

## Security Considerations

1. **Keep `license_generator.py` secure** - This is your key generation tool
2. **Change the default secret key** - Use a strong, unique secret
3. **Don't commit secret keys to public repos** - Use environment variables if needed
4. **Machine IDs are not secret** - They're used for identification only
5. **License keys are machine-specific** - Cannot be shared between machines

## Advanced: Automation

You can automate license generation and distribution:

```python
from license_generator import generate_license_key

# In your customer management system
machine_id = customer.get_machine_id()
license_key = generate_license_key(machine_id, expiry_days=365)

# Send via email, API, etc.
send_license_to_customer(customer.email, license_key)
```
