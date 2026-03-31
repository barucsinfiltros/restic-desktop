# Quick Start Guide - License System

## Overview
Your Restic Backup Manager now has a complete license key system that ties licenses to specific machines.

## Files Created

1. **restic_manager.py** (updated)
   - Added license validation on startup
   - License dialog for activation
   - Machine ID generation

2. **license_generator.py** (NEW)
   - Generates license keys
   - Admin/developer tool only
   - Keep this secure!

3. **check_machine_id.py** (NEW)
   - Utility to check machine ID
   - Users can run this to get their ID
   - Helpful for remote support

4. **test_license.py** (NEW)
   - Test license generation
   - Demonstrates the system

5. **LICENSE_SYSTEM.md** (NEW)
   - Complete documentation
   - Security considerations
   - Troubleshooting guide

## Quick Test (5 Minutes)

### Step 1: Get Your Machine ID
```bash
python check_machine_id.py
```
Copy the Machine ID shown.

### Step 2: Generate a Test License
```bash
python license_generator.py "YOUR-MACHINE-ID-HERE" --days 365 --output license.key
```

Replace `YOUR-MACHINE-ID-HERE` with the actual ID from Step 1.

### Step 3: Run the Application
```bash
python restic_manager.py
```

The application should now validate the license and start normally!

## For Production Use

### IMPORTANT: Change the Secret Key!

Before distributing, change the secret key in BOTH files:

**In restic_manager.py** (around line 148):
```python
_SECRET_KEY = b"your-unique-secret-key-change-me-!!!"
```

**In license_generator.py** (around line 14):
```python
_SECRET_KEY = b"your-unique-secret-key-change-me-!!!"
```

Make them match and keep them secret!

## Typical Customer Workflow

### Customer Side:
1. Runs application → License dialog appears
2. Copies Machine ID
3. Emails or submits Machine ID to you
4. Receives license key
5. Pastes into app → Activated!

### Your Side:
1. Receive Machine ID from customer
2. Run: `python license_generator.py "MACHINE_ID" --days 365`
3. Send license key to customer
4. Done!

## License Types

### Unlimited (Perpetual)
```bash
python license_generator.py "MACHINE_ID"
```

### 30-Day Trial
```bash
python license_generator.py "MACHINE_ID" --days 30
```

### 1-Year Subscription
```bash
python license_generator.py "MACHINE_ID" --days 365
```

## Security Features

✓ Machine-bound licenses (can't share)
✓ Cryptographic signatures (can't forge)
✓ Expiration dates (time-limited trials)
✓ Cross-platform (Windows, Linux, macOS)

## Troubleshooting

**"No license key found"**
- Normal on first run
- Enter license in activation dialog

**"License key is not valid for this machine"**
- License was generated for different machine
- Get correct Machine ID and regenerate

**"License expired"**
- Generate new license with more days
- Or use unlimited license

## Distribution Checklist

Before distributing your app:

- [ ] Change secret key in both files
- [ ] Test license generation and activation
- [ ] Decide on license duration (trial/full)
- [ ] Set up customer support for license requests
- [ ] Keep license_generator.py secure (don't distribute)
- [ ] Test on target platforms (Windows/Linux/macOS)

## Support

For detailed documentation, see [LICENSE_SYSTEM.md](LICENSE_SYSTEM.md)
