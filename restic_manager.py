"""
Restic Backup Manager - GUI Application for managing Restic backups
Version: 1.0.0
"""

import argparse
from typing import Optional, List, Dict, Tuple, Any
from collections import deque
import json
import os
import sys
import subprocess
import traceback
import base64
import hmac
import hashlib
import tempfile
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import random
import string
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import theme + chrome modules
import themes
import history_db
from title_bar import TitleBar
from framed_dialog import FramedDialog
from rounded_menu import RoundedMenu
from ui import (
    NavSidebar,
    create_dashboard_page,
    create_repositories_page,
    populate_jobs_table,
    populate_repository_table,
)
from ui.snapshots import (
    create_snapshots_page as build_snapshots_page_ui,
    populate_snapshots_table,
    snapshot_data_from_row,
    snapshot_previous_short_id,
    snapshot_short_id_from_row,
    update_snapshots_summary,
)

# Import Windows toast notifications (optional)
try:
    if sys.platform == "win32":
        from winotify import Notification, audio
        NOTIFICATIONS_AVAILABLE = True
    else:
        NOTIFICATIONS_AVAILABLE = False
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
    QStackedWidget, QFrame, QMessageBox, QSpinBox, QTextEdit, QPlainTextEdit,
    QFileDialog, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QGridLayout, QProgressBar, QListWidget, QListWidgetItem,
    QSizePolicy, QTabWidget, QDialog, QDialogButtonBox, QSplashScreen, QSpacerItem, QTimeEdit,
    QProgressDialog, QTreeWidget, QTreeWidgetItem, QInputDialog, QRadioButton, QDateEdit
)
from PyQt6.QtGui import QColor, QCursor, QFont, QMouseEvent, QTextCursor, QPixmap, QPainter, QPainterPath, QPen
from PyQt6.QtCore import Qt, QEvent, QObject, QPoint, QTimer, QThread, pyqtSignal, QTime, QDate, QRectF

# Win32 WM_NCHITTEST result codes for frameless edge resize.
_WINDOW_EDGE = 8
_HTLEFT = 10
_HTRIGHT = 11
_HTTOP = 12
_HTTOPLEFT = 13
_HTTOPRIGHT = 14
_HTBOTTOM = 15
_HTBOTTOMLEFT = 16
_HTBOTTOMRIGHT = 17
_WM_NCHITTEST = 0x0084

try:
    from ctypes import wintypes
except ImportError:
    wintypes = None

# Version and debug settings
VERSION = "v1.6.7"
YEAR = datetime.now().year
DEBUG_MODE = False
_STARTUP_WINDOW_PROBE = None  # installed when --debug; traces flash windows


class _StartupWindowProbe(QObject):
    """Log every top-level window Show during startup (finds the tiny flash)."""

    def __init__(self, app: QApplication, log_path: str = "startup_windows_debug.log"):
        super().__init__(app)
        self._app = app
        self._log_path = log_path
        self._seen: set[int] = set()
        self._enabled = True
        self._phase = "boot"
        try:
            with open(self._log_path, "w", encoding="utf-8") as f:
                f.write(f"=== startup window probe {datetime.now()} ===\n")
        except Exception:
            pass
        app.installEventFilter(self)
        # Catch windows that appear between Qt events (e.g. after processEvents).
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.snapshot)
        self._timer.start()

    def set_phase(self, phase: str) -> None:
        self._phase = phase
        self._log(f"--- phase: {phase} ---")

    def stop(self) -> None:
        self._enabled = False
        self._timer.stop()
        self._log("--- probe stopped (main window shown) ---")
        self.snapshot(force_all=True)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if not self._enabled:
            return False
        try:
            et = event.type()
        except Exception:
            return False
        if et not in (
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
            QEvent.Type.WindowActivate,
            QEvent.Type.Polish,
        ):
            return False
        if not isinstance(obj, QWidget):
            return False
        try:
            if obj.parent() is not None:
                return False
            if not obj.isWindow():
                return False
        except RuntimeError:
            return False
        self._report(obj, trigger=et.name if hasattr(et, "name") else str(et))
        return False

    def snapshot(self, force_all: bool = False) -> None:
        if not self._enabled and not force_all:
            return
        app = QApplication.instance()
        if app is None:
            return
        for w in app.topLevelWidgets():
            try:
                if not w.isVisible():
                    continue
                self._report(w, trigger="snapshot")
            except RuntimeError:
                continue

    def _report(self, widget: QWidget, trigger: str) -> None:
        try:
            wid = int(widget.winId())
        except Exception:
            wid = id(widget)
        key = wid
        if key in self._seen and trigger == "snapshot":
            return
        self._seen.add(key)
        try:
            geom = widget.geometry()
            frame = widget.frameGeometry()
            name = widget.objectName() or "(no objectName)"
            cls = type(widget).__name__
            title = ""
            try:
                title = widget.windowTitle() or ""
            except Exception:
                pass
            flags = int(widget.windowFlags())
            visible = widget.isVisible()
            size_hint = widget.sizeHint()
            line = (
                f"[{self._phase}] {trigger}: {cls} objectName={name!r} title={title!r} "
                f"visible={visible} geom={geom.width()}x{geom.height()}+{geom.x()}+{geom.y()} "
                f"frame={frame.width()}x{frame.height()} sizeHint={size_hint.width()}x{size_hint.height()} "
                f"flags=0x{flags:x} id={key}"
            )
            # Highlight likely "tiny flash" candidates
            if geom.width() < 200 or geom.height() < 120 or frame.width() < 200 or frame.height() < 120:
                line = "!! TINY !! " + line
        except RuntimeError:
            return
        stack = "".join(traceback.format_stack(limit=18))
        self._log(line + "\n" + stack)

    def _log(self, message: str) -> None:
        text = message if message.endswith("\n") else message + "\n"
        try:
            # Console: first line only for readability; full detail goes to the log file.
            first = text.splitlines()[0] if text else ""
            print(f"[STARTUP-WIN] {first}")
        except Exception:
            pass
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(text)
                if not text.endswith("\n"):
                    f.write("\n")
                f.write("\n")
        except Exception:
            pass


def install_startup_window_probe(app: QApplication):
    """Enable when --debug to capture the tiny startup flash window."""
    global _STARTUP_WINDOW_PROBE
    _STARTUP_WINDOW_PROBE = _StartupWindowProbe(app)
    print(f"Startup window probe writing to: {os.path.abspath(_STARTUP_WINDOW_PROBE._log_path)}")
    return _STARTUP_WINDOW_PROBE


def startup_probe_phase(phase: str) -> None:
    if _STARTUP_WINDOW_PROBE is not None:
        _STARTUP_WINDOW_PROBE.set_phase(phase)


def stop_startup_window_probe() -> None:
    global _STARTUP_WINDOW_PROBE
    if _STARTUP_WINDOW_PROBE is not None:
        _STARTUP_WINDOW_PROBE.stop()
        _STARTUP_WINDOW_PROBE = None

# CRASH LOGGING: Unhandled exceptions are logged to "restic_manager_crash.log"
# Check this file if the application closes unexpectedly

""" pyinstaller --noconsole --onefile license_generator_gui.py """
""" pyinstaller --noconsole --onefile restic_manager.py """ # Dont Use
""" pyinstaller restic_manager.spec """


# Windows subprocess helper - prevents console windows from appearing
def get_subprocess_creation_flags():
    """
    Get appropriate creation flags for subprocess to prevent console windows on Windows
    Returns subprocess.CREATE_NO_WINDOW on Windows, 0 on other platforms
    """
    if sys.platform == "win32":
        # Prevent console window from flashing when running subprocesses
        return subprocess.CREATE_NO_WINDOW
    return 0

def generate_password(length: Optional[int] = 32) -> str:
    punctuations_list = ["!", "@", "#", "%", "&", "_", "*"]
    letters_and_digits = string.ascii_letters + string.digits
    punctuations = '!@#%&_*'
    characters = letters_and_digits + punctuations
    password = ''.join(random.choice(characters) for _ in range(length))

    if any(char in password for char in punctuations_list):
        return password
    else:
        # If no punctuation is found, add one randomly to the password
        password += random.choice(punctuations)
        return password


# Application password security functions
def hash_app_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Hash an application password using PBKDF2
    Returns: (base64_encoded_hash, base64_encoded_salt)
    """
    if salt is None:
        salt = os.urandom(32)  # Generate random salt
    
    # Use PBKDF2 with SHA256, 100000 iterations
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    
    # Encode to base64 for storage
    hash_b64 = base64.b64encode(pwd_hash).decode('utf-8')
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    
    return hash_b64, salt_b64


def verify_app_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Verify a password against the stored hash
    Returns: True if password matches, False otherwise
    """
    try:
        # Decode the stored salt
        salt = base64.b64decode(stored_salt)
        
        # Hash the provided password with the stored salt
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        computed_hash = base64.b64encode(pwd_hash).decode('utf-8')
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_hash, stored_hash)
    except Exception as e:
        if DEBUG_MODE:
            print(f"Password verification error: {e}")
        return False


# Windows Credential Manager integration (more secure than JSON storage)
def store_credential_windows(name: str, value: str) -> bool:
    """
    Store a credential in Windows Credential Manager using cmdkey
    Returns: True if successful, False otherwise
    """
    if sys.platform != "win32":
        return False
    
    try:
        # Use cmdkey to store generic credential
        # Format: cmdkey /generic:TargetName /user:Username /pass:Password
        result = subprocess.run(
            ['cmdkey', f'/generic:{name}', f'/user:ResticManager', f'/pass:{value}'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=get_subprocess_creation_flags()
        )
        return result.returncode == 0
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to store credential: {e}")
        return False


def retrieve_credential_windows(name: str) -> Optional[str]:
    """
    Retrieve a credential from Windows Credential Manager using PowerShell
    Returns: The credential value or None if not found
    """
    if sys.platform != "win32":
        return None
    
    try:
        # Use PowerShell to retrieve the credential
        ps_script = f'''
$cred = cmdkey /list:"{name}" 2>&1
if ($cred -match "{name}") {{
    # Credential exists, retrieve it using CredentialManager
    $target = "{name}"
    Add-Type -AssemblyName System.Security
    $encoding = [System.Text.Encoding]::UTF8
    
    # Read credential using Windows API
    $credPtr = [IntPtr]::Zero
    $success = [PInvoke.CredRead]::CredRead($target, 1, 0, [ref]$credPtr)
    
    if ($success) {{
        $cred = [System.Runtime.InteropServices.Marshal]::PtrToStructure($credPtr, [Type][PInvoke.Credential])
        $password = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($cred.CredentialBlob, $cred.CredentialBlobSize / 2)
        [PInvoke.CredRead]::CredFree($credPtr)
        Write-Output $password
    }}
}}
'''
        
        # Simpler approach: Use a temporary file to store/retrieve
        # Since direct retrieval is complex, we'll use a different strategy
        # Store in Credential Manager but also maintain a registry fallback
        
        # For now, return None and use registry storage instead
        return None
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to retrieve credential: {e}")
        return None


def delete_credential_windows(name: str) -> bool:
    """
    Delete a credential from Windows Credential Manager
    Returns: True if successful, False otherwise
    """
    if sys.platform != "win32":
        return False
    
    try:
        result = subprocess.run(
            ['cmdkey', f'/delete:{name}'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=get_subprocess_creation_flags()
        )
        return result.returncode == 0
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to delete credential: {e}")
        return False


# Windows Registry storage (alternative secure storage)
def store_in_registry(key_name: str, value: str) -> bool:
    """
    Store a value in Windows Registry (HKEY_CURRENT_USER)
    Returns: True if successful, False otherwise
    """
    if sys.platform != "win32":
        return False
    
    try:
        import winreg
        # Store in HKCU\Software\ResticManager
        key_path = r"Software\ResticManager"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to store in registry: {e}")
        return False


def retrieve_from_registry(key_name: str) -> Optional[str]:
    """
    Retrieve a value from Windows Registry
    Returns: The value or None if not found
    """
    if sys.platform != "win32":
        return None
    
    try:
        import winreg
        key_path = r"Software\ResticManager"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, key_name)
        winreg.CloseKey(key)
        return value
    except FileNotFoundError:
        return None
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to retrieve from registry: {e}")
        return None


def delete_from_registry(key_name: str) -> bool:
    """
    Delete a value from Windows Registry
    Returns: True if successful, False otherwise
    """
    if sys.platform != "win32":
        return False
    
    try:
        import winreg
        key_path = r"Software\ResticManager"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, key_name)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        if DEBUG_MODE:
            print(f"Failed to delete from registry: {e}")
        return False


def show_notification(title: str, message: str, icon_type: str = "info", duration: str = "short"):
    """
    Show a Windows toast notification
    
    Args:
        title: Notification title
        message: Notification message
        icon_type: Type of icon ("success", "error", "info", "warning")
        duration: Duration ("short" or "long")
    """
    if not NOTIFICATIONS_AVAILABLE:
        return
    
    if sys.platform != "win32":
        return
    
    try:
        # Create notification
        toast = Notification(
            app_id="Restic Backup Manager",
            title=title,
            msg=message,
            duration=duration
        )
        
        # Set icon based on type
        if icon_type == "success":
            toast.set_audio(audio.Default, loop=False)
        elif icon_type == "error":
            toast.set_audio(audio.SMS, loop=False)
        elif icon_type == "warning":
            toast.set_audio(audio.Reminder, loop=False)
        
        # Show notification
        toast.show()
        
        if DEBUG_MODE:
            print(f"Notification shown: {title} - {message}")
    except Exception as e:
        # Silently fail if notification fails
        if DEBUG_MODE:
            print(f"Failed to show notification: {e}")


def make_framed_progress_dialog(
    parent,
    title: str,
    message: str,
    *,
    modal: bool = True,
    min_width: int = 420,
    min_height: Optional[int] = None,
):
    """Framed indeterminate progress dialog matching app chrome."""
    dlg = FramedDialog(
        title,
        parent,
        show_maximize=False,
        show_minimize=False,
        modal=modal,
    )
    dlg.setMinimumWidth(min_width)
    if min_height is not None:
        dlg.setMinimumHeight(min_height)
    dlg.setMaximumWidth(max(min_width + 80, 560))
    dlg.body_layout.setContentsMargins(20, 16, 20, 20)
    dlg.body_layout.setSpacing(14)

    label = QLabel(message)
    label.setObjectName("pageSubtitle")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dlg.body_layout.addWidget(label)

    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setMinimumHeight(10)
    bar.setTextVisible(False)
    dlg.body_layout.addWidget(bar)

    return dlg, label, bar


def make_rounded_splash(
    message: str,
    *,
    bg_color: str,
    text_color: str,
    width: int = 400,
    height: int = 200,
    radius: float = 12.0,
) -> QSplashScreen:
    """Splash screen with rounded corners matching app chrome."""
    pix = QPixmap(width, height)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(0.5, 0.5, width - 1.0, height - 1.0)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, QColor(bg_color))
    border = QColor(text_color)
    border.setAlpha(40)
    painter.setPen(QPen(border, 1.0))
    painter.drawPath(path)
    painter.end()

    splash = QSplashScreen(
        pix,
        Qt.WindowType.SplashScreen
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint,
    )
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    splash.setMask(pix.mask())
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
        QColor(text_color),
    )
    return splash

    
# Password encryption key (derived from machine-specific data)
def get_encryption_key():
    """Generate encryption key from machine-specific system ID (cross-platform)"""
    # Use machine ID as salt
    machine_id = get_machine_id()
    salt = machine_id.encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(b"restic-manager-key"))
    return key

def get_machine_id():
    """Get machine-specific identifier (cross-platform)"""
    import platform
    import uuid
    
    # Get machine-specific identifier based on OS
    machine_id = None
    system = platform.system()
    
    if system == "Linux":
        # Try to read machine-id on Linux
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
        except:
            try:
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    machine_id = f.read().strip()
            except:
                pass
    
    elif system == "Windows":
        # Try to get machine GUID on Windows
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=get_subprocess_creation_flags()
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    machine_id = lines[1].strip()
        except:
            pass
    
    elif system == "Darwin":  # macOS
        # Try to get hardware UUID on macOS
        try:
            result = subprocess.run(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=get_subprocess_creation_flags()
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        machine_id = line.split('"')[3]
                        break
        except:
            pass
    
    # Fallback: use MAC address + hostname + username (cross-platform)
    if not machine_id:
        mac = uuid.getnode()
        hostname = platform.node()
        username = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
        machine_id = f"{mac}-{hostname}-{username}"
    
    return machine_id

class LicenseManager:
    """Manage and validate license keys tied to machine ID"""
    
    # SECRET KEY - In production, keep this secret or use RSA signing
    # For now, this is a shared secret. Change this to your own secret!
    _SECRET_KEY = b"restic-manager-secret-key-change-this-in-production"
    
    def __init__(self, license_file="license.key"):
        self.license_file = license_file
        self.check_file = ".license_check"
        self.machine_id = get_machine_id()
    
    def validate_license(self) -> Tuple[bool, str]:
        """
        Validate the license key
        Returns: (is_valid, message)
        """
        if not os.path.exists(self.license_file):
            return False, "No license key found. Please enter a valid license key."
        
        try:
            with open(self.license_file, 'r') as f:
                license_key = f.read().strip()
            
            # Verify the license and check for clock tampering
            is_valid, message = self._verify_license_key(license_key)
            
            # If valid, update the last check timestamp
            if is_valid:
                self._update_last_check()
            
            return is_valid, message
        except Exception as e:
            return False, f"Error reading license: {str(e)}"
    
    def _verify_license_key(self, license_key: str) -> Tuple[bool, str]:
        """Verify the license key format and signature"""
        try:
            # Check for clock rollback (anti-tampering)
            clock_check = self._check_clock_tampering()
            if not clock_check[0]:
                return clock_check
            
            # License format: BASE64(machine_id_hash:expiry_date:signature)
            decoded = base64.b64decode(license_key).decode('utf-8')
            parts = decoded.split(':')
            
            if len(parts) != 3:
                return False, "Invalid license key format."
            
            machine_hash, expiry_str, signature = parts
            
            # Verify machine ID
            current_machine_hash = hashlib.sha256(self.machine_id.encode()).hexdigest()[:16]
            if machine_hash != current_machine_hash:
                return False, "License key is not valid for this machine."
            
            # Verify signature
            payload = f"{machine_hash}:{expiry_str}"
            expected_sig = hmac.new(
                self._SECRET_KEY,
                payload.encode(),
                hashlib.sha256
            ).hexdigest()[:32]
            
            if signature != expected_sig:
                return False, "License key signature is invalid."
            
            # Check expiration
            if expiry_str != "unlimited":
                try:
                    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                    if datetime.now() > expiry_date:
                        return False, f"License expired on {expiry_str}."
                except ValueError:
                    return False, "Invalid expiration date in license."
            
            # All checks passed
            if expiry_str == "unlimited":
                return True, "License is valid (unlimited)."
            else:
                days_left = (expiry_date - datetime.now()).days
                return True, f"License is valid until {expiry_str} ({days_left} days remaining)."
        
        except Exception as e:
            return False, f"License validation error: {str(e)}"
    
    def save_license(self, license_key: str) -> Tuple[bool, str]:
        """Save and validate a new license key"""
        # First verify it (skip clock check for new license activation)
        try:
            # License format: BASE64(machine_id_hash:expiry_date:signature)
            decoded = base64.b64decode(license_key).decode('utf-8')
            parts = decoded.split(':')
            
            if len(parts) != 3:
                return False, "Invalid license key format."
            
            machine_hash, expiry_str, signature = parts
            
            # Verify machine ID
            current_machine_hash = hashlib.sha256(self.machine_id.encode()).hexdigest()[:16]
            if machine_hash != current_machine_hash:
                return False, "License key is not valid for this machine."
            
            # Verify signature
            payload = f"{machine_hash}:{expiry_str}"
            expected_sig = hmac.new(
                self._SECRET_KEY,
                payload.encode(),
                hashlib.sha256
            ).hexdigest()[:32]
            
            if signature != expected_sig:
                return False, "License key signature is invalid."
            
            # Check expiration
            if expiry_str != "unlimited":
                try:
                    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                    if datetime.now() > expiry_date:
                        return False, f"License expired on {expiry_str}."
                except ValueError:
                    return False, "Invalid expiration date in license."
        except Exception as e:
            return False, f"License validation error: {str(e)}"
        
        # Save to file
        try:
            with open(self.license_file, 'w') as f:
                f.write(license_key)
            # Initialize the check file with current timestamp
            self._update_last_check()
            return True, "License key activated successfully!"
        except Exception as e:
            return False, f"Error saving license: {str(e)}"
    
    def _check_clock_tampering(self) -> Tuple[bool, str]:
        """Check if system clock has been rolled back"""
        try:
            if os.path.exists(self.check_file):
                with open(self.check_file, 'r') as f:
                    last_check_str = f.read().strip()
                    if last_check_str:
                        last_check = datetime.fromisoformat(last_check_str)
                        current_time = datetime.now()
                        
                        # If current time is earlier than last check, clock was rolled back
                        if current_time < last_check:
                            return False, "System clock tampering detected. License validation failed."
            
            return True, "Clock check passed"
        except Exception:
            # If we can't read the check file, allow validation to continue
            return True, "Clock check skipped"
    
    def _update_last_check(self):
        """Update the last validation timestamp"""
        try:
            with open(self.check_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass  # Silently fail if we can't update
    
    def get_machine_id_for_licensing(self) -> str:
        """Get machine ID to share with license generator"""
        return self.machine_id

class PasswordManager:
    """Encrypt and decrypt passwords"""
    
    def __init__(self):
        self.cipher = Fernet(get_encryption_key())
    
    def encrypt(self, password: str) -> str:
        """Encrypt a password"""
        return self.cipher.encrypt(password.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt a password"""
        try:
            return self.cipher.decrypt(encrypted.encode()).decode()
        except:
            return ""

# Restic command wrapper
class ResticCommand:
    """Wrapper for executing Restic commands"""
    
    def __init__(self, restic_path: str = "restic", debug: bool = False):
        self.restic_path = restic_path
        self.debug = debug
    
    def run(self, args: List[str], env: Optional[Dict[str, str]] = None, 
            input_data: Optional[str] = None, timeout: int = 300) -> Tuple[bool, str, str]:
        """
        Execute a restic command
        Returns: (success, stdout, stderr)
        """
        cmd = [self.restic_path] + args
        
        if self.debug:
            print(f"[RESTIC] Running: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_data else None,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                env={**os.environ, **(env or {})},
                creationflags=get_subprocess_creation_flags()
            )
            
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            success = process.returncode == 0
            
            if self.debug:
                print(f"[RESTIC] Return code: {process.returncode}")
                if stdout:
                    print(f"[RESTIC] STDOUT: {stdout[:500]}")
                if stderr:
                    print(f"[RESTIC] STDERR: {stderr[:500]}")
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "", f"Command timeout after {timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def run_with_progress(self, args: List[str], env: Optional[Dict[str, str]] = None,
                         progress_callback=None, timeout: int = 3600) -> Tuple[bool, str, str]:
        """
        Execute a restic command with real-time progress updates
        progress_callback will be called with each line of output
        Returns: (success, stdout, stderr)
        
        NOTE: Uses a ring buffer (maxlen=1000) to prevent memory overflow on large backups.
        Only the most recent 1000 lines are kept in memory.
        """
        cmd = [self.restic_path] + args
        
        if self.debug:
            print(f"[RESTIC] Running: {' '.join(cmd)}")
        
        try:
            import time
            import threading
            from queue import Queue, Empty
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env={**os.environ, **(env or {})},
                bufsize=1,  # Line buffered
                universal_newlines=True,
                creationflags=get_subprocess_creation_flags()
            )
            
            # Use deque with maxlen to prevent memory overflow on large outputs
            # This keeps only the most recent N lines in memory
            stdout_lines = deque(maxlen=1000)
            stderr_lines = deque(maxlen=1000)
            stdout_queue = Queue()
            stderr_queue = Queue()
            
            # Thread to read stdout
            def read_stdout():
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            stdout_queue.put(line)
                    process.stdout.close()
                except:
                    pass
            
            # Thread to read stderr
            def read_stderr():
                try:
                    for line in iter(process.stderr.readline, ''):
                        if line:
                            stderr_queue.put(line)
                    process.stderr.close()
                except:
                    pass
            
            # Start reader threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            
            start_time = time.time()
            
            # Process output as it comes
            while True:
                # Check timeout
                if timeout and (time.time() - start_time) > timeout:
                    process.kill()
                    return False, "".join(stdout_lines), "Command timeout"
                
                # Check if process finished
                poll_result = process.poll()
                
                # Read available stdout
                try:
                    while True:
                        line = stdout_queue.get_nowait()
                        stdout_lines.append(line)
                        if progress_callback:
                            progress_callback(line.rstrip())
                except Empty:
                    pass
                
                # Read available stderr
                try:
                    while True:
                        line = stderr_queue.get_nowait()
                        stderr_lines.append(line)
                        if progress_callback:
                            progress_callback(line.rstrip())
                except Empty:
                    pass
                
                # If process finished and queues are empty, we're done
                if poll_result is not None:
                    # Give threads a moment to finish reading
                    time.sleep(0.1)
                    
                    # Final drain of queues
                    try:
                        while True:
                            line = stdout_queue.get_nowait()
                            stdout_lines.append(line)
                            if progress_callback:
                                progress_callback(line.rstrip())
                    except Empty:
                        pass
                    
                    try:
                        while True:
                            line = stderr_queue.get_nowait()
                            stderr_lines.append(line)
                            if progress_callback:
                                progress_callback(line.rstrip())
                    except Empty:
                        pass
                    
                    break
                
                time.sleep(0.05)  # Small delay to prevent CPU spinning
            
            # Wait for threads to finish
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)
            
            success = process.returncode == 0
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            
            if self.debug:
                print(f"[RESTIC] Return code: {process.returncode}")
            
            return success, stdout, stderr
            
        except Exception as e:
            return False, "", str(e)
    
    def version(self) -> Optional[str]:
        """Get Restic version"""
        success, stdout, _ = self.run(["version"])
        if success:
            return stdout.strip()
        return None
    
    def forget(self, repo_path: str, password: str, args: List[str] = None) -> Optional[str]:
        """
        Execute restic forget command to apply retention policy
        Args:
            repo_path: Path to the repository
            password: Repository password
            args: Additional arguments (keep policies, --prune, --dry-run, etc.)
        Returns:
            Command output if successful, None if it failed
        """
        cmd_args = ["-r", repo_path, "forget"]
        
        if args:
            cmd_args.extend(args)
        
        env = {"RESTIC_PASSWORD": password}
        success, stdout, stderr = self.run(cmd_args, env=env, timeout=600)
        
        # Return output regardless of success so user can see what happened
        output = stdout + ("\n" + stderr if stderr else "")
        
        if success:
            return output
        else:
            # Log error
            if self.debug:
                print(f"[RESTIC] forget failed: {stderr}")
            # Return error message in output, but function returns None to signal failure
            raise Exception(f"Restic forget failed:\n{output}")


# Worker thread for long-running Restic operations
class ResticWorker(QThread):
    """Worker thread for Restic operations without blocking the UI"""
    finished = pyqtSignal(bool, str, str)  # success, stdout, stderr
    progress = pyqtSignal(str)  # progress message
    progress_data = pyqtSignal(dict)  # structured progress data
    
    def __init__(self, restic_cmd: ResticCommand, args: List[str], env: Optional[Dict] = None, 
                 timeout: int = 300, use_progress: bool = False):
        super().__init__()
        self.restic_cmd = restic_cmd
        self.args = args
        self.env = env or {}
        self.timeout = timeout
        self.use_progress = use_progress
    
    def run(self):
        """Execute the Restic command in a separate thread"""
        try:
            if self.use_progress:
                # Use streaming output with progress updates
                success, stdout, stderr = self.restic_cmd.run_with_progress(
                    self.args, self.env, 
                    progress_callback=self._parse_progress,
                    timeout=self.timeout
                )
            else:
                # Standard execution
                success, stdout, stderr = self.restic_cmd.run(self.args, self.env, timeout=self.timeout)
            
            self.finished.emit(success, stdout, stderr)
        except Exception as e:
            # Log the exception to a crash file
            try:
                import traceback
                with open("restic_manager_crash.log", "a") as f:
                    f.write(f"\n\n=== CRASH in ResticWorker Thread at {datetime.now()} ===\n")
                    f.write(f"Exception: {type(e).__name__}: {str(e)}\n")
                    f.write(traceback.format_exc())
            except:
                pass  # Can't even log, just fail gracefully
            
            # Emit error result
            error_msg = f"Worker thread crashed: {type(e).__name__}: {str(e)}"
            self.finished.emit(False, "", error_msg)
    
    def _parse_progress(self, line: str):
        """Parse progress line from restic JSON output"""
        # Always emit the raw line for display in output text
        self.progress.emit(line)
        
        try:
            # Try to parse as JSON for structured progress data
            data = json.loads(line)
            
            if data.get("message_type") == "status":
                # This is a progress update
                progress_info = {
                    "percent": data.get("percent_done", 0) * 100,
                    "files_done": data.get("files_done", 0),
                    "total_files": data.get("total_files", 0),
                    "bytes_done": data.get("bytes_done", 0),
                    "total_bytes": data.get("total_bytes", 0),
                    "current_files": data.get("current_files", []),
                    "eta": data.get("seconds_remaining", 0)
                }
                self.progress_data.emit(progress_info)
            elif data.get("message_type") == "summary":
                # Final summary - emit 100% completion
                progress_info = {
                    "percent": 100,
                    "files_done": data.get("files_new", 0) + data.get("files_changed", 0) + data.get("files_unmodified", 0),
                    "total_files": data.get("files_new", 0) + data.get("files_changed", 0) + data.get("files_unmodified", 0),
                    "bytes_done": data.get("total_bytes_processed", 0),
                    "total_bytes": data.get("total_bytes_processed", 0),
                    "current_files": [],
                    "eta": 0
                }
                self.progress_data.emit(progress_info)
        except json.JSONDecodeError:
            # Not JSON, line already emitted above
            pass


# class MountMonitorThread(QThread):
#     """Monitor file explorer process and request unmount when closed"""
#     unmount_requested = pyqtSignal()
    
#     def __init__(self, mount_info, parent=None):
#         super().__init__(parent)
#         self.mount_info = mount_info
#         self.should_stop = False
    
#     def run(self):
#         """Monitor the explorer process"""
#         explorer_process = self.mount_info.get('explorer_process')
        
#         if not explorer_process:
#             return
        
#         # Wait for explorer process to finish
#         while not self.should_stop:
#             if explorer_process.poll() is not None:
#                 # Explorer has closed
#                 time.sleep(1)  # Brief delay before unmounting
#                 self.unmount_requested.emit()
#                 break
#             time.sleep(1)  # Check every second
    
#     def stop(self):
#         """Stop monitoring"""
#         self.should_stop = True


# Repository Dialog
class RepositoryDialog(FramedDialog):
    """Dialog for adding/editing repositories"""
    
    def __init__(self, parent, settings_manager, existing_repo=None):
        title = "Add Repository" if not existing_repo else "Edit Repository"
        super().__init__(title, parent, show_maximize=False, show_minimize=False)
        self.settings_manager = settings_manager
        self.password_manager = settings_manager.password_manager
        self.existing_repo = existing_repo
        # Set by Test Connection; applied into check_status on save.
        self._test_result: Optional[bool] = None
        self._test_error: str = ""
        
        self.setMinimumWidth(520)
        self.body_layout.setContentsMargins(16, 12, 16, 16)
        layout = self.body_layout
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(10)
        try:
            # Prefer expanding fields so the right-side buttons don't get squeezed.
            form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Repository name
        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(34)
        if existing_repo:
            self.name_input.setText(existing_repo.get("name", ""))
        form_layout.addRow("Name:", self.name_input)
        
        # Repository type
        self.type_combo = QComboBox()
        self.type_combo.setMinimumHeight(34)
        self.type_combo.setMinimumWidth(120)
        self.type_combo.addItems(["local", "sftp", "s3", "b2", "azure", "gs", "rest"])
        if existing_repo:
            self.type_combo.setCurrentText(existing_repo.get("type", "local"))
        form_layout.addRow("Type:", self.type_combo)
        
        # Repository path/URL
        self.path_input = QLineEdit()
        self.path_input.setMinimumHeight(34)
        if existing_repo:
            self.path_input.setText(existing_repo.get("path", ""))
        form_layout.addRow("Path/URL:", self.path_input)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setMinimumHeight(34)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if existing_repo and existing_repo.get("password"):
            decrypted = self.password_manager.decrypt(existing_repo.get("password"))
            self.password_input.setText(decrypted)
        form_layout.addRow("Password:", self.password_input)
        
        # Show password checkbox
        self.show_password_check = QCheckBox("Show password")
        self.show_password_check.stateChanged.connect(self.toggle_password_visibility)
        form_layout.addRow("", self.show_password_check)

        # Card wrapper so the form matches the rest of the modern dashboard UI.
        form_card = QFrame()
        form_card.setObjectName("sectionCard")
        form_card_layout = QVBoxLayout(form_card)
        form_card_layout.setContentsMargins(16, 14, 16, 16)
        form_card_layout.setSpacing(8)
        form_card_layout.addLayout(form_layout)

        # Keep init option inside the card so it isn't cramped against the footer.
        if not existing_repo:
            form_card_layout.addSpacing(8)
            self.init_repo_check = QCheckBox("Initialize repository now")
            self.init_repo_check.setChecked(False)
            form_card_layout.addWidget(self.init_repo_check)

        layout.addWidget(form_card)
        
        # Footer actions — compact, same row as OK/Cancel
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 14, 0, 0)

        test_btn = QPushButton("Test")
        test_btn.setObjectName("dialogSecondary")
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.setToolTip("Test connection to this repository")
        test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(test_btn)

        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("dialogSecondary")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setToolTip("Browse for a local repository folder")
        browse_btn.clicked.connect(self.browse_path)
        button_layout.addWidget(browse_btn)

        generate_btn = QPushButton("Generate")
        generate_btn.setObjectName("dialogSecondary")
        generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        generate_btn.setToolTip("Generate a random repository password")
        generate_btn.clicked.connect(lambda: self.password_input.setText(generate_password()))
        button_layout.addWidget(generate_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("dialogPrimary")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)
    
    def browse_path(self):
        """Browse for local repository path"""
        if self.type_combo.currentText() == "local":
            directory = QFileDialog.getExistingDirectory(self, "Select Repository Directory")
            if directory:
                self.path_input.setText(directory)
    
    def toggle_password_visibility(self, state):
        """Toggle password visibility"""
        if state == Qt.CheckState.Checked.value:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def test_connection(self):
        """Test repository connection"""
        # Get path and password from form
        path = self.path_input.text().strip()
        password = self.password_input.text()
        
        # Validate path
        if not path:
            QMessageBox.warning(self, "Test Connection", "Please enter a repository path.")
            return
        
        # Show progress dialog (framed to match app chrome)
        self._test_progress, _, _ = make_framed_progress_dialog(
            self,
            "Testing Connection",
            "Testing connection to repository…\nPlease wait.",
            min_width=400,
        )
        self._test_progress.show()
        QApplication.processEvents()
        
        # Test connection using restic snapshots command
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", path, "snapshots", "--latest", "1"]
        
        # Get restic_cmd from parent window
        restic_cmd = self.parent().restic_cmd
        
        self._test_worker = ResticWorker(restic_cmd, args, env, timeout=30)
        self._test_worker.finished.connect(self._on_test_completed)
        self._test_worker.start()
    
    def _on_test_completed(self, success, stdout, stderr):
        """Callback when connection test completes"""
        # Close progress dialog
        if hasattr(self, '_test_progress'):
            try:
                self._test_progress.close()
                self._test_progress.deleteLater()
            except:
                pass
        
        if success:
            self._test_result = True
            self._test_error = ""
            QMessageBox.information(
                self, 
                "Connection Successful", 
                "Successfully connected to the repository!\n\nThe repository is accessible and the password is correct."
            )
        else:
            self._test_result = False
            self._test_error = (stderr or "Unknown error").strip()
            error_msg = self._test_error or "Unknown error"
            QMessageBox.warning(
                self, 
                "Connection Failed", 
                f"Failed to connect to repository:\n\n{error_msg}\n\nPlease check the path and password."
            )
    
    def get_repository_data(self):
        """Get repository data from form"""
        encrypted_password = ""
        if self.password_input.text():
            encrypted_password = self.password_manager.encrypt(self.password_input.text())
        
        data = {
            "name": self.name_input.text(),
            "type": self.type_combo.currentText(),
            "path": self.path_input.text(),
            "password": encrypted_password,
        }

        # Preserve identity colour + prior check metadata on edit.
        if self.existing_repo:
            if self.existing_repo.get("color"):
                data["color"] = self.existing_repo["color"]
            data["last_checked"] = self.existing_repo.get("last_checked") or "Never"
            data["check_status"] = self.existing_repo.get("check_status") or "unknown"
            if self.existing_repo.get("check_error"):
                data["check_error"] = self.existing_repo.get("check_error")
        else:
            data["last_checked"] = "Never"
            data["check_status"] = "unknown"

        # Apply in-dialog Test Connection result (if run this session).
        if self._test_result is True:
            data["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data["check_status"] = "healthy"
            data.pop("check_error", None)
        elif self._test_result is False:
            data["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data["check_status"] = "unreachable"
            if self._test_error:
                data["check_error"] = self._test_error[:500]
        
        # Add initialize flag if this is a new repository
        if not self.existing_repo:
            data["initialize"] = self.init_repo_check.isChecked()
        
        return data


class BackupJobDialog(FramedDialog):
    """Dialog for creating/editing backup jobs"""
    
    def __init__(self, parent, settings_manager, existing_job=None):
        title = "New Backup Job" if not existing_job else "Edit Backup Job"
        super().__init__(
            title,
            parent,
            object_name="backupJobDialog",
            show_maximize=True,
            show_minimize=False,
        )
        self.settings_manager = settings_manager
        self.existing_job = existing_job
        
        self.setMinimumWidth(640)
        self.setMinimumHeight(560)
        self.resize(680, 720)
        
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        main_layout = self.body_layout
        
        # Create scroll area for the form content
        scroll_area = QScrollArea()
        scroll_area.setObjectName("backupJobScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        content_widget.setObjectName("backupJobContent")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, stretch=1)

        def _section(section_title: str):
            card = QFrame()
            card.setObjectName("sectionCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 14)
            card_layout.setSpacing(8)
            heading = QLabel(section_title)
            heading.setObjectName("sectionCardTitle")
            card_layout.addWidget(heading)
            return card, card_layout
        
        # Job name
        name_card, name_layout = _section("Job")
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_label = QLabel("Job Name")
        name_label.setMinimumWidth(88)
        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(34)
        self.name_input.setPlaceholderText("e.g. Daily Documents")
        if existing_job:
            self.name_input.setText(existing_job.get("name", ""))
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_input, stretch=1)
        name_layout.addLayout(name_row)
        layout.addWidget(name_card)
        
        # Repositories (multiple selection)
        repos_card, repos_layout = _section("Target Repositories")
        repos_help = QLabel("Select one or more repositories to backup to (for redundancy).")
        repos_help.setObjectName("pageSubtitle")
        repos_help.setWordWrap(True)
        repos_layout.addWidget(repos_help)
        
        self.repos_list = QListWidget()
        self.repos_list.setObjectName("backupJobList")
        self.repos_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.repos_list.setMinimumHeight(120)
        self.repos_list.setMaximumHeight(160)
        repositories = settings_manager.get("repositories")
        for repo in repositories:
            item = QListWidgetItem(repo["name"])
            self.repos_list.addItem(item)
            # Select previously selected repos
            if existing_job:
                # Handle both old single repository format and new multiple format
                selected_repos = existing_job.get("repositories", [])
                if not selected_repos and existing_job.get("repository"):
                    # Old format - single repository
                    selected_repos = [existing_job.get("repository")]
                if repo["name"] in selected_repos:
                    item.setSelected(True)
        repos_layout.addWidget(self.repos_list)
        layout.addWidget(repos_card)
        
        # Paths to backup
        paths_card, paths_layout = _section("Paths to Backup")
        self.paths_list = QListWidget()
        self.paths_list.setObjectName("backupJobList")
        self.paths_list.setMinimumHeight(100)
        self.paths_list.setMaximumHeight(140)
        if existing_job and existing_job.get("paths"):
            for path in existing_job["paths"]:
                self.paths_list.addItem(path)
        paths_layout.addWidget(self.paths_list)
        
        paths_btn_layout = QHBoxLayout()
        paths_btn_layout.setContentsMargins(0, 4, 0, 0)
        paths_btn_layout.setSpacing(8)
        add_path_btn = QPushButton("Add Path")
        add_path_btn.setObjectName("dialogSecondary")
        add_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_path_btn.clicked.connect(self.add_path)
        remove_path_btn = QPushButton("Remove")
        remove_path_btn.setObjectName("dialogSecondary")
        remove_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_path_btn.clicked.connect(self.remove_path)
        paths_btn_layout.addWidget(add_path_btn)
        paths_btn_layout.addWidget(remove_path_btn)
        paths_btn_layout.addStretch()
        paths_layout.addLayout(paths_btn_layout)
        layout.addWidget(paths_card)
        
        # Options
        options_card, options_outer = _section("Options")
        options_layout = QFormLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setHorizontalSpacing(14)
        options_layout.setVerticalSpacing(10)
        try:
            options_layout.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )
        except Exception:
            pass
        options_outer.addLayout(options_layout)
        
        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setMinimumHeight(34)
        self.tags_input.setPlaceholderText("tag1, tag2, tag3")
        if existing_job:
            tags = existing_job.get("tags", [])
            self.tags_input.setText(",".join(tags))
        options_layout.addRow("Tags:", self.tags_input)
        
        # Exclude patterns
        self.exclude_input = QTextEdit()
        self.exclude_input.setPlaceholderText("*.tmp\n*.log\nnode_modules/")
        self.exclude_input.setMinimumHeight(72)
        self.exclude_input.setMaximumHeight(96)
        if existing_job and existing_job.get("exclude_patterns"):
            self.exclude_input.setPlainText("\n".join(existing_job["exclude_patterns"]))
        options_layout.addRow("Exclude Patterns:", self.exclude_input)
        
        # Exclude caches
        self.exclude_caches_check = QCheckBox("Exclude cache directories")
        self.exclude_caches_check.setChecked(existing_job.get("exclude_caches", True) if existing_job else True)
        options_layout.addRow("", self.exclude_caches_check)
        
        # Pack size
        self.pack_size_combo = QComboBox()
        self.pack_size_combo.setMinimumHeight(34)
        self.pack_size_combo.setFixedWidth(120)
        self.pack_size_combo.addItems(["8 MB", "16 MB", "32 MB", "64 MB", "128 MB"])
        # Set current value based on existing job
        if existing_job:
            existing_pack = existing_job.get("pack_size", 8)
            if existing_pack == 8:
                self.pack_size_combo.setCurrentText("8 MB")
            elif existing_pack == 16:
                self.pack_size_combo.setCurrentText("16 MB")
            elif existing_pack == 32:
                self.pack_size_combo.setCurrentText("32 MB")
            elif existing_pack == 64:
                self.pack_size_combo.setCurrentText("64 MB")
            elif existing_pack == 128:
                self.pack_size_combo.setCurrentText("128 MB")
            else:
                self.pack_size_combo.setCurrentText("16 MB")  # Default
        else:
            self.pack_size_combo.setCurrentText("16 MB")  # Default for new jobs
        options_layout.addRow("Pack Size:", self.pack_size_combo)
        
        # One file system
        self.one_file_system_check = QCheckBox("Stay on one file system")
        self.one_file_system_check.setChecked(existing_job.get("one_file_system", False) if existing_job else False)
        options_layout.addRow("", self.one_file_system_check)
        
        # Timeout
        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(8)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimumHeight(34)
        self.timeout_spin.setMinimum(0)
        self.timeout_spin.setMaximum(24)  # Max 24 hours
        # Convert seconds to hours for display
        timeout_seconds = existing_job.get("timeout", 7200) if existing_job else 7200
        self.timeout_spin.setValue(timeout_seconds // 3600 if timeout_seconds > 0 else 0)
        self.timeout_spin.setSuffix(" hours")
        timeout_hint = QLabel("0 = no timeout")
        timeout_hint.setObjectName("pageSubtitle")
        timeout_row.addWidget(self.timeout_spin)
        timeout_row.addWidget(timeout_hint)
        timeout_row.addStretch()
        options_layout.addRow("Backup Timeout:", timeout_row)
        
        # Exclude if present
        self.exclude_if_present_input = QLineEdit()
        self.exclude_if_present_input.setMinimumHeight(34)
        self.exclude_if_present_input.setPlaceholderText(".nobackup")
        if existing_job:
            self.exclude_if_present_input.setText(existing_job.get("exclude_if_present", ""))
        options_layout.addRow("Exclude If Present:", self.exclude_if_present_input)
        
        # Compression
        compression_row = QHBoxLayout()
        compression_row.setSpacing(8)
        self.compression_combo = QComboBox()
        self.compression_combo.setMinimumHeight(34)
        self.compression_combo.setFixedWidth(120)
        self.compression_combo.addItems(["off", "auto", "max"])
        current_compression = existing_job.get("compression", "auto") if existing_job else "auto"
        self.compression_combo.setCurrentText(current_compression)
        compression_hint = QLabel("auto / max")
        compression_hint.setObjectName("pageSubtitle")
        compression_row.addWidget(self.compression_combo)
        compression_row.addWidget(compression_hint)
        compression_row.addStretch()
        options_layout.addRow("Compression:", compression_row)
        
        # No cache
        self.no_cache_check = QCheckBox("No local cache")
        self.no_cache_check.setChecked(existing_job.get("no_cache", False) if existing_job else False)
        self.no_cache_check.setToolTip("Do not use local cache (slower but uses less disk space)")
        options_layout.addRow("", self.no_cache_check)
        
        # Ignore inode
        self.ignore_inode_check = QCheckBox("Ignore inode changes")
        self.ignore_inode_check.setChecked(existing_job.get("ignore_inode", False) if existing_job else False)
        self.ignore_inode_check.setToolTip("Ignore inode number changes when checking for modified files")
        options_layout.addRow("", self.ignore_inode_check)
        
        layout.addWidget(options_card)
        
        # Scheduling options
        schedule_card, schedule_outer = _section("Scheduling")
        schedule_layout = QFormLayout()
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        schedule_layout.setHorizontalSpacing(14)
        schedule_layout.setVerticalSpacing(10)
        schedule_outer.addLayout(schedule_layout)
        
        # Enable scheduling
        self.schedule_enabled_check = QCheckBox("Enable automatic scheduling for this job")
        if existing_job and existing_job.get("schedule"):
            self.schedule_enabled_check.setChecked(existing_job["schedule"].get("enabled", False))
        schedule_layout.addRow(self.schedule_enabled_check)
        
        # Container for schedule settings (enabled/disabled based on checkbox)
        self.schedule_settings_widget = QWidget()
        schedule_settings_layout = QFormLayout()
        schedule_settings_layout.setContentsMargins(0, 0, 0, 0)
        schedule_settings_layout.setHorizontalSpacing(14)
        schedule_settings_layout.setVerticalSpacing(10)
        self.schedule_settings_widget.setLayout(schedule_settings_layout)
        
        # Frequency
        self.frequency_combo = QComboBox()
        self.frequency_combo.setToolTip("How often to run the backup job")
        self.frequency_combo.setMinimumHeight(34)
        self.frequency_combo.setFixedWidth(150)
        self.frequency_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
        if existing_job and existing_job.get("schedule"):
            freq = existing_job["schedule"].get("frequency", "daily")
            self.frequency_combo.setCurrentText(freq.capitalize())
        schedule_settings_layout.addRow("Frequency:", self.frequency_combo)
        
        # Time
        self.time_edit = QTimeEdit()
        self.time_edit.setToolTip("Time to run the backup job")
        self.time_edit.setMinimumHeight(34)
        self.time_edit.setFixedWidth(150)
        self.time_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.time_edit.setDisplayFormat("HH:mm")
        if existing_job and existing_job.get("schedule") and existing_job["schedule"].get("time"):
            from datetime import datetime
            time_str = existing_job["schedule"]["time"]
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            self.time_edit.setTime(time_obj)
        else:
            self.time_edit.setTime(QTime(2, 0))  # Default to 2:00 AM
        schedule_settings_layout.addRow("Time:", self.time_edit)
        
        # Days (for weekly)
        days_layout = QHBoxLayout()
        days_layout.setSpacing(6)
        self.day_checkboxes = {}
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        selected_days = []
        if existing_job and existing_job.get("schedule"):
            selected_days = existing_job["schedule"].get("days", [])
        
        for day in days:
            cb = QCheckBox(day)
            if day in selected_days or not selected_days:  # Default all checked if none specified
                #cb.setChecked(not selected_days)  # Check all by default only if no existing selection
                cb.setChecked(False if not selected_days else True)  # Uncheck if there are specific selected days
            if day in selected_days:
                cb.setChecked(True)
            self.day_checkboxes[day] = cb
            days_layout.addWidget(cb)
        days_layout.addStretch()
        
        self.days_widget = QWidget()
        self.days_widget.setLayout(days_layout)
        self.days_label = QLabel("Days (Weekly):")
        schedule_settings_layout.addRow(self.days_label, self.days_widget)
        
        # Day of month (for monthly)
        self.day_of_month_spin = QSpinBox()
        self.day_of_month_spin.setToolTip("Day of the month to run the backup (1-31)")
        self.day_of_month_spin.setMinimumHeight(34)
        self.day_of_month_spin.setFixedWidth(80)
        self.day_of_month_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.day_of_month_spin.setMinimum(1)
        self.day_of_month_spin.setMaximum(28) # Limit to 28 to avoid issues with shorter months
        if existing_job and existing_job.get("schedule"):
            self.day_of_month_spin.setValue(existing_job["schedule"].get("day_of_month", 1))
        else:
            self.day_of_month_spin.setValue(1)
        
        self.day_of_month_label = QLabel("Day of Month:")
        schedule_settings_layout.addRow(self.day_of_month_label, self.day_of_month_spin)
        
        # Run if missed
        self.run_if_missed_check = QCheckBox("Run at next logon if missed")
        if existing_job and existing_job.get("schedule"):
            self.run_if_missed_check.setChecked(existing_job["schedule"].get("run_if_missed", True))
        else:
            self.run_if_missed_check.setChecked(True)
        schedule_settings_layout.addRow(self.run_if_missed_check)
        
        # Pause after completion
        self.pause_after_completion_check = QCheckBox("Pause after completion (wait for keypress)")
        self.pause_after_completion_check.setToolTip("Keep the window open after backup completes so you can review the results")
        if existing_job and existing_job.get("schedule"):
            self.pause_after_completion_check.setChecked(existing_job["schedule"].get("pause_after_completion", False))
        else:
            self.pause_after_completion_check.setChecked(False)
        schedule_settings_layout.addRow(self.pause_after_completion_check)
        
        schedule_layout.addRow(self.schedule_settings_widget)
        
        # Update days visibility based on frequency
        self.frequency_combo.currentTextChanged.connect(self.update_schedule_ui)
        self.schedule_enabled_check.stateChanged.connect(self.update_schedule_ui)
        
        layout.addWidget(schedule_card)
        layout.addStretch(1)
        
        # Initial UI state
        self.update_schedule_ui()
        
        # Footer actions — always visible below the scroll area
        footer = QFrame()
        footer.setObjectName("backupJobFooter")
        button_layout = QHBoxLayout(footer)
        button_layout.setContentsMargins(16, 10, 16, 12)
        button_layout.setSpacing(8)
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("dialogPrimary")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        main_layout.addWidget(footer)
    
    def update_schedule_ui(self):
        """Update schedule UI based on selections"""
        # Enable/disable schedule settings based on checkbox
        enabled = self.schedule_enabled_check.isChecked()
        self.schedule_settings_widget.setEnabled(enabled)
        
        # Show/hide days based on frequency
        if hasattr(self, 'days_widget'):
            is_weekly = self.frequency_combo.currentText() == "Weekly"
            self.days_widget.setVisible(is_weekly and enabled)
            if hasattr(self, 'days_label'):
                self.days_label.setVisible(is_weekly and enabled)
        
        # Show/hide day of month based on frequency
        if hasattr(self, 'day_of_month_spin'):
            is_monthly = self.frequency_combo.currentText() == "Monthly"
            self.day_of_month_spin.setVisible(is_monthly and enabled)
            if hasattr(self, 'day_of_month_label'):
                self.day_of_month_label.setVisible(is_monthly and enabled)
    
    def add_path(self):
        """Add a path to backup"""
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Backup")
        if path:
            self.paths_list.addItem(path)
    
    def remove_path(self):
        """Remove selected path"""
        current_item = self.paths_list.currentItem()
        if current_item:
            self.paths_list.takeItem(self.paths_list.row(current_item))
    
    def get_job_data(self):
        """Get backup job data from form"""
        # Get paths
        paths = [self.paths_list.item(i).text() 
                for i in range(self.paths_list.count())]
        
        # Get selected repositories
        selected_repos = [item.text() for item in self.repos_list.selectedItems()]
        
        # Get tags
        tags_text = self.tags_input.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []
        
        # Get exclude patterns
        exclude_text = self.exclude_input.toPlainText().strip()
        exclude_patterns = [line.strip() for line in exclude_text.split("\n") if line.strip()] if exclude_text else []
        
        # Get schedule data
        schedule_data = None
        if self.schedule_enabled_check.isChecked():
            # Get selected days for weekly schedule
            selected_days = [day for day, cb in self.day_checkboxes.items() if cb.isChecked()]
            
            schedule_data = {
                "enabled": True,
                "frequency": self.frequency_combo.currentText().lower(),
                "time": self.time_edit.time().toString("HH:mm"),
                "days": selected_days,
                "day_of_month": self.day_of_month_spin.value(),
                "run_if_missed": self.run_if_missed_check.isChecked(),
                "pause_after_completion": self.pause_after_completion_check.isChecked(),
                "last_run": None
            }
        else:
            # Keep disabled flag if schedule was previously enabled
            schedule_data = {
                "enabled": False
            }
        
        data = {
            "name": self.name_input.text().strip(),
            "repositories": selected_repos,  # Changed from single "repository" to list
            "paths": paths,
            "tags": tags,
            "exclude_patterns": exclude_patterns,
            "exclude_caches": self.exclude_caches_check.isChecked(),
            "pack_size": int(self.pack_size_combo.currentText().split()[0]),  # Extract number from "XX MB"
            "one_file_system": self.one_file_system_check.isChecked(),
            "timeout": self.timeout_spin.value() * 3600,  # Convert hours to seconds
            "exclude_if_present": self.exclude_if_present_input.text().strip(),
            "compression": self.compression_combo.currentText(),
            "no_cache": self.no_cache_check.isChecked(),
            "ignore_inode": self.ignore_inode_check.isChecked(),
            "schedule": schedule_data,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return data


# License Activation Dialog
class LicenseDialog(FramedDialog):
    """Dialog for entering and activating license keys"""
    
    def __init__(self, parent=None, machine_id=""):
        super().__init__(
            "License Activation",
            parent,
            show_maximize=False,
            show_minimize=False,
        )
        self.machine_id = machine_id
        self.license_manager = LicenseManager()
        
        self.setMinimumWidth(620)
        self.body_layout.setContentsMargins(16, 12, 16, 16)
        layout = self.body_layout
        
        # Title
        title_label = QLabel("License Activation Required")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Info text
        info_text = QLabel(
            "This application requires a valid license key to run.\n"
            "Please enter your license key below or contact support to purchase a license."
        )
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_text)
        
        layout.addSpacing(20)
        
        # Machine ID display (for requesting license)
        machine_group = QGroupBox("Machine Information")
        machine_layout = QVBoxLayout()
        machine_group.setLayout(machine_layout)
        
        machine_info = QLabel(
            "When requesting a license key, provide the following Machine ID:"
        )
        machine_info.setWordWrap(True)
        machine_layout.addWidget(machine_info)
        
        # Machine ID display with copy button
        machine_id_layout = QHBoxLayout()
        self.machine_id_display = QLineEdit(self.machine_id)
        self.machine_id_display.setReadOnly(True)
        self.machine_id_display.setFont(QFont("Courier", 9))
        machine_id_layout.addWidget(self.machine_id_display)
        
        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("dialogSecondary")
        copy_btn.clicked.connect(self.copy_machine_id)
        machine_id_layout.addWidget(copy_btn)
        
        machine_layout.addLayout(machine_id_layout)
        layout.addWidget(machine_group)
        
        layout.addSpacing(20)
        
        # License key input
        license_group = QGroupBox("License Key")
        license_layout = QVBoxLayout()
        license_group.setLayout(license_layout)
        
        self.license_input = QTextEdit()
        self.license_input.setPlaceholderText("Enter your license key here...")
        self.license_input.setMaximumHeight(100)
        self.license_input.setFont(QFont("Courier", 9))
        license_layout.addWidget(self.license_input)
        
        layout.addWidget(license_group)
        
        # Status message
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        activate_btn = QPushButton("Activate License")
        activate_btn.setObjectName("dialogPrimary")
        activate_btn.setDefault(True)
        activate_btn.clicked.connect(self.activate_license)
        button_layout.addWidget(activate_btn)
        
        quit_btn = QPushButton("Quit Application")
        quit_btn.setObjectName("dialogSecondary")
        quit_btn.clicked.connect(self.reject)
        button_layout.addWidget(quit_btn)
        
        layout.addLayout(button_layout)
    
    def copy_machine_id(self):
        """Copy machine ID to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.machine_id)
        self.status_label.setText("Machine ID copied to clipboard!")
        self.status_label.setStyleSheet("color: green;")
    
    def activate_license(self):
        """Attempt to activate the entered license key"""
        license_key = self.license_input.toPlainText().strip()
        
        if not license_key:
            self.status_label.setText("Please enter a license key.")
            self.status_label.setStyleSheet("color: red;")
            return
        
        # Try to save and validate
        success, message = self.license_manager.save_license(license_key)
        
        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: green;")
            # Give user time to see success message
            QTimer.singleShot(1000, self.accept)
        else:
            self.status_label.setText(f"Activation failed: {message}")
            self.status_label.setStyleSheet("color: red;")


class AppPasswordDialog(FramedDialog):
    """Dialog for entering application password at startup"""
    
    def __init__(self, parent=None):
        super().__init__(
            "Application Password Required",
            parent,
            show_maximize=False,
            show_minimize=False,
        )
        self.setFixedSize(460, 300)
        
        self.body_layout.setContentsMargins(16, 8, 16, 16)
        layout = self.body_layout
        
        layout.addSpacing(8)
        
        # Title
        title = QLabel("Password Required")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(12)
        
        # Info message
        info_label = QLabel("This application is password protected.\nPlease enter your password to continue.")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        
        layout.addSpacing(16)
        
        # Password input (centered form layout)
        form_container = QWidget()
        form_layout = QFormLayout()
        form_layout.setContentsMargins(50, 0, 50, 0)  # Add margins for better centering
        form_layout.setHorizontalSpacing(10)
        form_container.setLayout(form_layout)
        
        self.password_input = QLineEdit()
        self.password_input.setFixedWidth(205)
        self.password_input.setMinimumHeight(30)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter password...")
        self.password_input.returnPressed.connect(self.accept)  # Enter key submits
        
        form_layout.addRow("Password:", self.password_input)
        layout.addWidget(form_container)
        
        layout.addSpacing(10)
        
        # Status message
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setMinimumHeight(20)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        login_btn = QPushButton("Login")
        login_btn.setObjectName("dialogPrimary")
        login_btn.setDefault(True)
        login_btn.setFixedHeight(32)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Exit")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(login_btn)
        button_layout.addSpacing(10)
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addSpacing(8)
        
        # Focus on password field
        self.password_input.setFocus()
    
    def get_password(self):
        """Get the entered password"""
        return self.password_input.text()
    
    def set_error(self, message):
        """Display an error message"""
        self.status_label.setText(message)
        self.password_input.clear()
        self.password_input.setFocus()


# Settings Manager
class ResticSettingsManager:
    """Manager for application settings"""
    
    def __init__(self, filename="restic_settings.json"):
        self.filename = filename
        self.password_manager = PasswordManager()
        self.defaults = {
            "theme": "slate",
            "restic_path": "restic",
            "repositories": [],
            "backup_jobs": [],
            "last_repository": "",
            "auto_refresh_snapshots": True,
            "snapshot_refresh_interval": 60,  # seconds
            "log_level": "info",
            "temp_restore_path": "C:\\temp\\restic_restore",  # Temporary location for restore to original
            "app_password_enabled": False,
            "app_password_hash": "",
            "app_password_salt": ""
        }
        self.settings = self.load_settings()
    
    def load_settings(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self.defaults.copy()
        return self.defaults.copy()
    
    def save_settings(self):
        with open(self.filename, 'w') as f:
            json.dump(self.settings, f, indent=4)
    
    def get(self, key):
        return self.settings.get(key, self.defaults.get(key))
    
    def set(self, key, value):
        self.settings[key] = value


# Scheduler Manager
class SchedulerManager:
    """Cross-platform scheduler manager for Windows Task Scheduler and Linux/macOS cron"""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.is_windows = sys.platform == "win32"
        self.is_linux = sys.platform.startswith("linux")
        self.is_macos = sys.platform == "darwin"
    
    def create_scheduled_task(self, job_name, job_data):
        """Create a scheduled task/cron job for a backup job"""
        schedule = job_data.get("schedule")
        if not schedule or not schedule.get("enabled"):
            return False, "Job does not have scheduling enabled"
        
        if self.is_windows:
            return self._create_windows_task(job_name, job_data)
        elif self.is_linux or self.is_macos:
            return self._create_cron_job(job_name, job_data)
        else:
            return False, f"Scheduling not supported on platform: {sys.platform}"
    
    def update_scheduled_task(self, job_name, job_data):
        """Update an existing scheduled task/cron job"""
        # Delete and recreate
        return self.create_scheduled_task(job_name, job_data)
    
    def delete_scheduled_task(self, task_name_or_job):
        """Delete a scheduled task/cron job"""
        if self.is_windows:
            return self._delete_windows_task(task_name_or_job)
        elif self.is_linux or self.is_macos:
            return self._delete_cron_job(task_name_or_job)
        else:
            return False, f"Scheduling not supported on platform: {sys.platform}"
    
    def get_task_status(self, job_name):
        """Get the status of a scheduled task/cron job"""
        if self.is_windows:
            return self._get_windows_task_status(job_name)
        elif self.is_linux or self.is_macos:
            return self._get_cron_status(job_name)
        else:
            return None
    
    # Windows Task Scheduler Implementation
    def _create_windows_task(self, job_name, job_data):
        """Create a Windows scheduled task"""
        try:
            schedule = job_data.get("schedule")
            
            # Build task name (sanitize for Task Scheduler)
            task_name = f"ResticBackup_{job_name.replace(' ', '_')}"
            
            # Delete existing task if it exists
            self._delete_windows_task(task_name)
            
            # Generate PowerShell script with restic command
            script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduled_tasks")
            os.makedirs(script_dir, exist_ok=True)
            script_file = os.path.join(script_dir, f"{task_name}.ps1")
            
            # Get repository name (support both old and new format)
            repo_name = None
            if "repositories" in job_data and job_data["repositories"]:
                # New format - use first repository
                repo_name = job_data["repositories"][0]
            elif "repository" in job_data:
                # Old format - single repository
                repo_name = job_data["repository"]
            else:
                return False, "No repository configured for this backup job"
            
            # Get repository details
            repositories = self.settings_manager.get("repositories")
            repo = next((r for r in repositories if r["name"] == repo_name), None)
            if not repo:
                return False, f"Repository '{repo_name}' not found"
            
            # Decrypt password
            password = ""
            if repo.get("password"):
                password = self.settings_manager.password_manager.decrypt(repo["password"])
            
            # Get restic path
            restic_path = self.settings_manager.get("restic_path")
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            
            # Build restic command arguments
            restic_args = ["-r", repo["path"], "backup"]
            
            # Add paths
            restic_args.extend(job_data["paths"])
            
            # Add tags
            if job_data.get("tags"):
                for tag in job_data["tags"]:
                    restic_args.extend(["--tag", tag])
            
            # Add exclude patterns
            if job_data.get("exclude_patterns"):
                for pattern in job_data["exclude_patterns"]:
                    restic_args.extend(["--exclude", pattern])
            
            # Add options
            if job_data.get("exclude_caches", True):
                restic_args.append("--exclude-caches")
            
            if job_data.get("pack_size", 0) > 0:
                restic_args.extend(["--pack-size", str(job_data["pack_size"])])
            
            if job_data.get("one_file_system", False):
                restic_args.append("--one-file-system")
            
            if job_data.get("exclude_if_present"):
                restic_args.extend(["--exclude-if-present", job_data["exclude_if_present"]])
            
            # Compression
            compression = job_data.get("compression", "auto")
            if compression and compression != "off":
                restic_args.extend(["--compression", compression])
            
            # No cache
            if job_data.get("no_cache", False):
                restic_args.append("--no-cache")
            
            # Ignore inode
            if job_data.get("ignore_inode", False):
                restic_args.append("--ignore-inode")
            
            # Build PowerShell script content
            note = ""
            if "repositories" in job_data and len(job_data["repositories"]) > 1:
                note = f"\n# Note: This job has {len(job_data['repositories'])} repositories configured, but scheduled tasks only backup to the first one."
            
            # Create encrypted password file using Windows DPAPI
            password_file = os.path.join(script_dir, f"{task_name}.password")
            if password:
                # Use PowerShell to encrypt the password with DPAPI
                ps_encrypt_cmd = f'''
$password = ConvertTo-SecureString -String "{password}" -AsPlainText -Force
$password | ConvertFrom-SecureString | Out-File -FilePath "{password_file}" -Encoding utf8
'''
                try:
                    result = subprocess.run(
                        ["powershell.exe", "-Command", ps_encrypt_cmd],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        creationflags=get_subprocess_creation_flags()
                    )
                    if result.returncode != 0:
                        return False, f"Failed to encrypt password: {result.stderr}"
                except Exception as e:
                    return False, f"Error encrypting password: {str(e)}"
            
            ps_script = f"""# Restic Backup Script for job: {job_name}
# Generated by Restic Manager
# Repository: {repo['path']}{note}

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to show Windows toast notification
function Show-ToastNotification {{
    param(
        [string]$Title,
        [string]$Message
    )
    
    try {{
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $toastXml = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">$Title</text>
            <text id="2">$Message</text>
        </binding>
    </visual>
    <audio src="ms-winsoundevent:Notification.Default"/>
</toast>
"@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($toastXml)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Restic Backup Manager").Show($toast)
    }} catch {{
        # Silently fail if notification fails
        Write-Host "Note: Could not show toast notification"
    }}
}}

# Load and decrypt repository password from encrypted file
$passwordFile = "{password_file}"
if (Test-Path $passwordFile) {{
    $securePassword = Get-Content $passwordFile | ConvertTo-SecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $env:RESTIC_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}} else {{
    Write-Host "Error: Password file not found: $passwordFile"
    Show-ToastNotification "Backup Failed" "Password file not found for job: {job_name}"
    exit 1
}}

# Run restic backup
$resticPath = "{restic_path}"
$arguments = @(
"""
            
            # Add each argument on a new line
            for arg in restic_args:
                # Escape quotes in argument
                escaped_arg = arg.replace('"', '`"')
                ps_script += f'    "{escaped_arg}",\n'
            
            # Remove trailing comma and newline, close the array
            ps_script = ps_script.rstrip(',\n') + '\n)\n\n'
            
            # Add pause after completion if enabled
            pause_code = ""
            if schedule.get("pause_after_completion", False):
                pause_code = "\n    Write-Host ''\n    Write-Host 'Press any key to continue...'\n    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')\n"
            
            ps_script += """# Execute restic
Write-Host "Starting backup job: {job_name}"
Write-Host "Repository: {repo_path}"
Write-Host "Restic command: $resticPath $($arguments -join ' ')"

$startTime = Get-Date
$exitCode = 1
try {{
    & $resticPath $arguments
    $exitCode = $LASTEXITCODE
}} catch {{
    Write-Host "Error running backup: $_"
    $exitCode = 1
}} finally {{
    $duration = [Math]::Max(0, [int]((Get-Date) - $startTime).TotalSeconds)
    $successArg = if ($exitCode -eq 0) {{ "1" }} else {{ "0" }}
    try {{
        & "{python_exe}" "{manager_script}" --record-job-run "{job_name}" --repo-name "{repo_name}" --duration $duration --success $successArg --exit-code $exitCode --source scheduled 2>$null | Out-Null
    }} catch {{
        # History recording is best-effort
    }}
    # Clear password from environment
    Remove-Item Env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
}}

if ($exitCode -eq 0) {{
    Write-Host "Backup completed successfully"
    Show-ToastNotification "Backup Completed ✓" "Job '{job_name}' to '{repo_name}' completed successfully"{pause_code}
    exit 0
}} else {{
    Write-Host "Backup failed with exit code: $exitCode"
    Show-ToastNotification "Backup Failed ✗" "Job '{job_name}' failed with exit code: $exitCode"{pause_code}
    exit $exitCode
}}
""".format(
                job_name=job_name,
                repo_path=repo['path'],
                repo_name=repo['name'],
                pause_code=pause_code,
                python_exe=python_exe,
                manager_script=script_path,
            )
            
            # Write PowerShell script to file
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(ps_script)
            
            # Build command to run PowerShell script
            command = f'powershell.exe -ExecutionPolicy Bypass -File "{script_file}"'
            
            # Build schedule trigger based on frequency
            frequency = schedule.get("frequency", "daily")
            time_str = schedule.get("time", "02:00")
            
            # Build schtasks command
            schtasks_cmd = [
                "schtasks", "/CREATE",
                "/TN", task_name,
                "/TR", command,
            ]
            
            # Add schedule type parameters
            if frequency == "daily":
                schtasks_cmd.extend(["/SC", "DAILY"])
            elif frequency == "weekly":
                days = schedule.get("days", [])
                if not days:
                    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                # Convert to Task Scheduler day format
                day_map = {"Mon": "MON", "Tue": "TUE", "Wed": "WED", "Thu": "THU", 
                          "Fri": "FRI", "Sat": "SAT", "Sun": "SUN"}
                schtasks_days = ",".join([day_map.get(d, d) for d in days])
                schtasks_cmd.extend(["/SC", "WEEKLY", "/D", schtasks_days])
            elif frequency == "monthly":
                day_of_month = schedule.get("day_of_month", 1)
                schtasks_cmd.extend(["/SC", "MONTHLY", "/D", str(day_of_month)])
            else:
                schtasks_cmd.extend(["/SC", "DAILY"])
            
            # Add time and force parameters
            schtasks_cmd.extend(["/ST", time_str, "/F"])
            
            # Execute schtasks command
            result = subprocess.run(
                schtasks_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            if result.returncode == 0:
                password_note = " (password encrypted with DPAPI)" if password else ""
                return True, f"Scheduled task '{task_name}' created successfully{password_note}"
            else:
                return False, f"Failed to create task: {result.stderr}"
        
        except Exception as e:
            return False, f"Error creating Windows task: {str(e)}"
    
    def _delete_windows_task(self, task_name_or_job):
        """Delete a Windows scheduled task"""
        try:
            # If given a job name, convert to task name
            if not task_name_or_job.startswith("ResticBackup_"):
                task_name = f"ResticBackup_{task_name_or_job.replace(' ', '_')}"
            else:
                task_name = task_name_or_job
            
            # Execute schtasks delete command
            result = subprocess.run(
                ["schtasks", "/DELETE", "/TN", task_name, "/F"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            # Delete PowerShell script file if it exists
            script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduled_tasks")
            script_file = os.path.join(script_dir, f"{task_name}.ps1")
            password_file = os.path.join(script_dir, f"{task_name}.password")
            
            if os.path.exists(script_file):
                try:
                    os.remove(script_file)
                except Exception:
                    # Silently ignore if we can't delete the script file
                    pass
            
            if os.path.exists(password_file):
                try:
                    os.remove(password_file)
                except Exception:
                    # Silently ignore if we can't delete the password file
                    pass
            
            # Task deletion succeeds even if task doesn't exist
            return True, f"Task '{task_name}' deleted"
        
        except Exception as e:
            return False, f"Error deleting Windows task: {str(e)}"
    
    def _get_windows_task_status(self, job_name):
        """Get the status of a Windows scheduled task"""
        try:
            task_name = f"ResticBackup_{job_name.replace(' ', '_')}"
            
            result = subprocess.run(
                ["schtasks", "/QUERY", "/TN", task_name, "/FO", "LIST", "/V"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            if result.returncode == 0:
                # Parse output to get task info
                output = result.stdout
                status = {}
                for line in output.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        status[key.strip()] = value.strip()
                return status
            else:
                return None
        
        except Exception:
            return None
    
    # Linux/macOS Cron Implementation
    def _create_cron_job(self, job_name, job_data):
        """Create a cron job for Linux/macOS"""
        try:
            schedule = job_data.get("schedule")
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            
            # Build command to run job
            command = f'"{python_exe}" "{script_path}" --run-job "{job_name}"'
            
            # Generate cron expression
            frequency = schedule.get("frequency", "daily")
            time_str = schedule.get("time", "02:00")
            hour, minute = time_str.split(":")
            
            if frequency == "daily":
                # Run daily at specified time
                cron_schedule = f"{minute} {hour} * * *"
            elif frequency == "weekly":
                days = schedule.get("days", [])
                if not days:
                    # Default to all days
                    cron_schedule = f"{minute} {hour} * * *"
                else:
                    # Convert day names to cron day numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
                    day_map = {"Sun": "0", "Mon": "1", "Tue": "2", "Wed": "3", 
                              "Thu": "4", "Fri": "5", "Sat": "6"}
                    cron_days = ",".join([day_map.get(d, "1") for d in days])
                    cron_schedule = f"{minute} {hour} * * {cron_days}"
            elif frequency == "monthly":
                # Run on specified day of month (default to 1st)
                day_of_month = schedule.get("day_of_month", 1)
                cron_schedule = f"{minute} {hour} {day_of_month} * *"
            else:
                cron_schedule = f"{minute} {hour} * * *"
            
            # Add comment to identify this job
            job_comment = f"# ResticBackup: {job_name.replace(' ', '_')}"
            cron_line = f"{cron_schedule} {command}"
            
            # Read current crontab
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            current_crontab = result.stdout if result.returncode == 0 else ""
            
            # Remove old entry for this job if it exists
            new_crontab_lines = []
            skip_next = False
            for line in current_crontab.split('\n'):
                if skip_next:
                    skip_next = False
                    continue
                if line.strip() == job_comment:
                    skip_next = True  # Skip the next line (the actual cron command)
                    continue
                if line.strip():
                    new_crontab_lines.append(line)
            
            # Add new entry
            new_crontab_lines.append(job_comment)
            new_crontab_lines.append(cron_line)
            new_crontab = '\n'.join(new_crontab_lines) + '\n'
            
            # Write new crontab
            result = subprocess.run(
                ["crontab", "-"],
                input=new_crontab,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            if result.returncode == 0:
                platform_name = "macOS" if self.is_macos else "Linux"
                return True, f"Cron job created successfully ({platform_name} cron)\nSchedule: {cron_schedule}"
            else:
                return False, f"Failed to create cron job: {result.stderr}"
        
        except Exception as e:
            return False, f"Error creating cron job: {str(e)}"
    
    def _delete_cron_job(self, job_name):
        """Delete a cron job for Linux/macOS"""
        try:
            # Sanitize job name for comment
            if not job_name.startswith("ResticBackup_"):
                job_id = f"ResticBackup: {job_name.replace(' ', '_')}"
            else:
                job_id = job_name
            
            job_comment = f"# {job_id}"
            
            # Read current crontab
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            if result.returncode != 0:
                return True, "No crontab found (already deleted)"
            
            current_crontab = result.stdout
            
            # Remove entry for this job
            new_crontab_lines = []
            skip_next = False
            for line in current_crontab.split('\n'):
                if skip_next:
                    skip_next = False
                    continue
                if line.strip() == job_comment:
                    skip_next = True  # Skip the next line (the actual cron command)
                    continue
                if line.strip():
                    new_crontab_lines.append(line)
            
            # Write new crontab
            if new_crontab_lines:
                new_crontab = '\n'.join(new_crontab_lines) + '\n'
                result = subprocess.run(
                    ["crontab", "-"],
                    input=new_crontab,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=get_subprocess_creation_flags()
                )
            else:
                # Remove crontab entirely if no entries left
                result = subprocess.run(
                    ["crontab", "-r"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=get_subprocess_creation_flags()
                )
            
            return True, f"Cron job deleted"
        
        except Exception as e:
            return False, f"Error deleting cron job: {str(e)}"
    
    def _get_cron_status(self, job_name):
        """Get the status of a cron job"""
        try:
            job_comment = f"# ResticBackup: {job_name.replace(' ', '_')}"
            
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=get_subprocess_creation_flags()
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() == job_comment and i + 1 < len(lines):
                        cron_line = lines[i + 1]
                        return {"status": "Scheduled", "schedule": cron_line.split(None, 5)[:5]}
            
            return None
        
        except Exception:
            return None


# Main Application Window
class ResticManagerWindow(QMainWindow):
    # Signal for thread-safe dashboard updates (using str for size to avoid int32 overflow)
    dashboard_update_signal = pyqtSignal(int, str, str, list)
    
    def __init__(self, app, splash=None):
        super().__init__()
        # QMainWindow is a top-level window (visible by default). Keep it hidden
        # until main() calls show(), otherwise splash processEvents() flashes a
        # tiny empty frameless frame during construction.
        self.setVisible(False)
        self.app = app
        self.splash = splash
        self._resize_edges: set[str] = set()
        self._resize_origin: QPoint | None = None
        self._resize_geom = None
        
        # Connect dashboard update signal
        self.dashboard_update_signal.connect(self._update_dashboard_ui_impl)
        
        self._update_splash("Initializing settings...")
        self.settings_manager = ResticSettingsManager()
        self.scheduler_manager = SchedulerManager(self.settings_manager)
        self.restic_cmd = ResticCommand(
            restic_path=self.settings_manager.get("restic_path"),
            debug=DEBUG_MODE
        )
        self.current_repository = None
        self._dashboard_loaded = False  # Track if dashboard has been loaded
        
        self._update_splash("Creating main window...")
        self.setWindowTitle(f"Restic Backup Manager {VERSION}")
        self.setWindowIcon(themes.app_window_icon())
        self.setMinimumSize(1200, 850)
        # Custom chrome — no native Windows title bar.
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Frameless shell: rounded #windowRoot + title bar + content row
        root = QFrame()
        root.setObjectName("windowRoot")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.setMouseTracking(True)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar(
            self,
            title=f"Restic Backup Manager {VERSION}",
            show_refresh=True,
        )
        self.title_bar.refresh_clicked.connect(self._title_bar_refresh)
        self.title_bar.add_repository_clicked.connect(self.add_repository)
        root_layout.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("contentArea")
        main_layout = QHBoxLayout(body)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        root_layout.addWidget(body, stretch=1)
        self.setCentralWidget(root)
        
        # Sidebar menu
        self._update_splash("Building navigation menu...")
        self.create_sidebar(main_layout)
        
        # Content area with stacked widget for different views
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, stretch=1)
        
        # Create pages
        self._update_splash("Loading dashboard...")
        self.create_dashboard_page()
        self._update_splash("Loading repositories view...")
        self.create_repositories_page()
        self._update_splash("Loading snapshots view...")
        self.create_snapshots_page()
        self._update_splash("Loading restore view...")
        self.create_restore_page()
        self._update_splash("Loading backup view...")
        self.create_backup_page()
        self._update_splash("Loading retention view...")
        self.create_retention_page()
        self._update_splash("Loading logs view...")
        self.create_logs_page()
        self._update_splash("Loading settings view...")
        self.create_settings_page()
        
        # Update repository combos after all pages are created
        self._update_splash("Loading repositories...")
        self.update_repository_combos()
        
        # Apply theme
        self._update_splash("Applying theme...")
        self.apply_theme(self.settings_manager.get("theme"))
        self._sync_window_chrome()
        
        # Check Restic installation at startup
        self._update_splash("Checking Restic installation...")
        QTimer.singleShot(100, self._check_restic_at_startup)
    
    def _update_splash(self, message):
        """Update splash screen message if available"""
        startup_probe_phase(f"splash: {message}")
        if self.splash:
            try:
                # Check if splash is still valid (not deleted)
                if not self.splash.isVisible():
                    # Splash may have been closed, but object might still exist
                    return
                
                # Get current theme for text color
                current_theme = self.settings_manager.get("theme") if hasattr(self, 'settings_manager') else "slate"
                _, text_color = themes.theme_splash_colors_for(current_theme)
                
                self.splash.showMessage(
                    f"Restic Backup Manager {VERSION}\n\n{message}\n",
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                    QColor(text_color)
                )
                self.app.processEvents()  # Force UI update
                if _STARTUP_WINDOW_PROBE is not None:
                    _STARTUP_WINDOW_PROBE.snapshot()
            except RuntimeError:
                # Splash has been deleted, silently ignore
                pass
    
    def create_sidebar(self, main_layout):
        """Create modern icon navigation sidebar"""
        theme = themes.get_app_theme(
            themes.resolve_theme_id(self.settings_manager.get("theme"))
        )
        self.nav_sidebar = NavSidebar(
            app_name="Restic Manager",
            version=VERSION,
            year=str(YEAR),
            muted=theme.muted,
            accent=theme.accent,
        )
        self.nav_sidebar.page_requested.connect(self.switch_page)
        self.menu_buttons = self.nav_sidebar.menu_buttons
        main_layout.addWidget(self.nav_sidebar)
    
    def _title_bar_refresh(self) -> None:
        """Route title-bar refresh to the active page."""
        page = self.stacked_widget.currentIndex() if hasattr(self, "stacked_widget") else 0
        if page == 2:
            self.load_snapshots()
        else:
            self.refresh_dashboard()

    def switch_page(self, page_index):
        """Switch to a different page"""
        # Handle Exit action
        if page_index == -1:
            QApplication.instance().quit()
            return
        
        self.stacked_widget.setCurrentIndex(page_index)
        
        if hasattr(self, "title_bar"):
            self.title_bar.set_page_context(page_index)

        if hasattr(self, "nav_sidebar"):
            self.nav_sidebar.set_active_page(page_index)
            theme = themes.get_app_theme(
                themes.resolve_theme_id(self.settings_manager.get("theme"))
            )
            self.nav_sidebar.recolor(theme.muted, theme.accent)
        
        # Refresh dashboard only on first load
        if page_index == 0 and not self._dashboard_loaded:  # Dashboard page
            self.refresh_dashboard()
            self._dashboard_loaded = True
        
        # Load snapshots when switching to Snapshots page (if repository selected)
        if page_index == 2:  # Snapshots page
            if hasattr(self, 'snapshot_repo_combo') and self.snapshot_repo_combo.currentText():
                # Only load if not already loaded or needs refresh
                self.load_snapshots()
        
        # Update retention repo combo with task indicators when switching to Retention page
        if page_index == 5:  # Retention Policy page
            if hasattr(self, 'retention_repo_combo'):
                self.update_retention_repo_combo()
        
        # Load snapshots when switching to Restore page (if repository selected)
        if page_index == 3:  # Restore page
            if hasattr(self, 'restore_repo_combo') and self.restore_repo_combo.currentText():
                self.load_snapshots_for_restore()
    
    def create_dashboard_page(self):
        """Create modern dashboard overview page"""
        page = create_dashboard_page(
            self,
            on_refresh=self.refresh_dashboard,
            on_view_logs=lambda: self.switch_page(6),
        )
        # Hidden compatibility widgets for verify/rebuild/stats helpers
        self.dashboard_repo_combo = QComboBox(self)
        self.dashboard_repo_combo.hide()
        self.repo_stats_text = QTextEdit(self)
        self.repo_stats_text.hide()
        self._ensure_repository_colors()
        populate_jobs_table(self)
        self.stacked_widget.addWidget(page)
        if hasattr(self, "_initialize_empty_charts"):
            self._initialize_empty_charts()
        self._restore_dashboard_from_cache()
    
    def refresh_dashboard(self):
        """Refresh dashboard statistics (runs in background to avoid UI freeze)"""
        self._ensure_repository_colors()
        self._set_dashboard_refreshing(True)

        # Show loading indicator on cards
        if hasattr(self, 'stats_labels'):
            for key, label in self.stats_labels.items():
                if key == "last_backup":
                    label.setText("Loading...")
                elif key != "status":
                    try:
                        label.setText("…")
                    except Exception:
                        pass

        if hasattr(self, "dashboard_subtitle"):
            self.dashboard_subtitle.setText("Refreshing backup statistics…")
        
        if hasattr(self, "refresh_dashboard_jobs_table"):
            self.refresh_dashboard_jobs_table()
        
        # Process events to update UI
        QApplication.processEvents()
        
        # Run dashboard refresh in background worker to prevent UI freeze
        self._start_dashboard_refresh_worker()

    def _set_dashboard_refreshing(self, busy: bool) -> None:
        if hasattr(self, "title_bar"):
            self.title_bar.set_refreshing(busy)
        if not busy and hasattr(self, "dashboard_subtitle"):
            stamp = getattr(self, "_dashboard_last_refreshed", None)
            if stamp:
                self.dashboard_subtitle.setText(f"Last refreshed: {stamp}")
            else:
                self.dashboard_subtitle.setText(
                    "Welcome back! Here's an overview of your backup environment."
                )

    def _restore_dashboard_from_cache(self) -> None:
        """Paint dashboard cards/charts from last SQLite cache (no restic calls)."""
        try:
            cached = history_db.load_dashboard_cache(db_path=self._history_db_path())
        except Exception as exc:
            if DEBUG_MODE:
                print(f"[HISTORY] Failed to load dashboard cache: {exc}")
            return
        if not cached:
            return
        updated_at, payload = cached
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            self._dashboard_last_refreshed = parsed.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            self._dashboard_last_refreshed = updated_at

        total_snapshots = int(payload.get("total_snapshots") or 0)
        total_size = int(payload.get("total_size") or 0)
        last_backup = payload.get("last_backup") or "Never"
        repo_data = payload.get("repo_data") or []
        normalized = []
        for row in repo_data:
            if isinstance(row, (list, tuple)) and len(row) >= 1:
                normalized.append(tuple(row))
        self._apply_dashboard_stats(
            total_snapshots, total_size, last_backup, normalized, persist_history=False
        )
        if hasattr(self, "dashboard_subtitle") and self._dashboard_last_refreshed:
            self.dashboard_subtitle.setText(
                f"Last refreshed: {self._dashboard_last_refreshed}"
            )

    def _persist_dashboard_history(
        self, total_snapshots, total_size, last_backup, repo_data
    ) -> None:
        """Write repo_stats samples + dashboard_cache after a live refresh."""
        try:
            db_path = self._history_db_path()
            samples = []
            for row in repo_data or []:
                if not row or not row[0]:
                    continue
                samples.append(
                    {
                        "repo_name": row[0],
                        "total_size": int(row[1] or 0) if len(row) > 1 else 0,
                        "snapshot_count": int(row[2] or 0) if len(row) > 2 else 0,
                        "last_backup_at": row[3] if len(row) > 3 else None,
                        "last_snapshot_short_id": row[4] if len(row) > 4 else None,
                    }
                )
            if samples:
                history_db.insert_repo_stats_samples(samples, db_path=db_path)
            history_db.save_dashboard_cache(
                {
                    "total_snapshots": int(total_snapshots or 0),
                    "total_size": int(total_size or 0),
                    "last_backup": last_backup,
                    "repo_data": [list(r) for r in (repo_data or [])],
                },
                db_path=db_path,
            )
            self._dashboard_last_refreshed = datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception as exc:
            if DEBUG_MODE:
                print(f"[HISTORY] Failed to persist dashboard history: {exc}")

    def _apply_dashboard_stats(
        self,
        total_snapshots,
        total_size,
        last_backup,
        repo_data,
        *,
        persist_history: bool = True,
    ) -> None:
        """Shared path for live refresh and cache restore."""
        if hasattr(self, 'stats_labels'):
            repos = self.settings_manager.get("repositories") or []
            if "total_repos" in self.stats_labels:
                self.stats_labels["total_repos"].setText(str(len(repos)))
            self.stats_labels["total_snapshots"].setText(str(total_snapshots))
            self.stats_labels["total_size"].setText(
                self.format_bytes(total_size) if total_size > 0 else "—"
            )
            self.stats_labels["last_backup"].setText(
                last_backup if last_backup != "Never" else "Never"
            )

        repo_last = {}
        repo_snaps = {}
        repo_sizes = {}
        for row in repo_data or []:
            if len(row) >= 4 and row[0] and row[3]:
                repo_last[row[0]] = row[3]
            elif len(row) >= 1 and row[0]:
                repo_last.setdefault(row[0], "")
            if len(row) >= 2 and row[0]:
                try:
                    repo_sizes[row[0]] = int(row[1] or 0)
                except (TypeError, ValueError):
                    repo_sizes[row[0]] = 0
            if len(row) >= 6 and row[0] and row[4]:
                repo_snaps[row[0]] = {"short_id": row[4], "id": row[5] or row[4]}
        self._repo_last_backup = repo_last
        self._repo_last_snapshot = repo_snaps
        self._repo_sizes = repo_sizes
        self._sync_job_last_runs_from_repos(repo_last, repo_snaps)

        if repo_data:
            self._update_dashboard_charts(repo_data)
        else:
            self._initialize_empty_charts()

        if persist_history:
            self._persist_dashboard_history(
                total_snapshots, total_size, last_backup, repo_data
            )

        if hasattr(self, "refresh_dashboard_jobs_table"):
            self.refresh_dashboard_jobs_table()
    
    def _start_dashboard_refresh_worker(self):
        """Start background worker to refresh dashboard stats"""
        repositories = self.settings_manager.get("repositories")
        
        # Update total repositories immediately (no need for worker)
        if hasattr(self, 'stats_labels'):
            self.stats_labels["total_repos"].setText(str(len(repositories)))
        
        # If no repositories, just clear stats
        if not repositories:
            if hasattr(self, 'stats_labels'):
                self.stats_labels["total_snapshots"].setText("0")
                self.stats_labels["total_size"].setText("—")
                self.stats_labels["last_backup"].setText("Never")
            self._persist_dashboard_history(0, 0, "Never", [])
            self._set_dashboard_refreshing(False)
            return
        
        # Start worker to gather stats from all repositories
        # This runs in background to avoid freezing UI
        from threading import Thread
        
        def gather_stats():
            total_snapshots = 0
            total_size = 0
            last_backup = "Never"
            
            # Collect per-repository data for charts + last snapshot times/ids
            # Tuple: (name, size, snapshot_count, last_time, short_id, full_id)
            repo_data = []
            
            for repo in repositories:
                repo_name = repo.get("name", "")
                repo_path = repo.get("path", "")
                password = ""
                
                # Initialize repo stats
                repo_size = 0
                repo_snapshot_count = 0
                repo_last_time = ""
                repo_last_short_id = ""
                repo_last_full_id = ""
                
                if repo.get("password"):
                    try:
                        password = self.settings_manager.password_manager.decrypt(repo["password"])
                    except:
                        continue
                
                # Get snapshot count
                env = {"RESTIC_PASSWORD": password} if password else {}
                args = ["-r", repo_path, "snapshots", "--json"]
                
                try:
                    success, stdout, stderr = self.restic_cmd.run(args, env, timeout=30)
                    if success and stdout:
                        try:
                            snapshots = json.loads(stdout)
                            if isinstance(snapshots, list):
                                repo_snapshot_count = len(snapshots)
                                total_snapshots += repo_snapshot_count
                                # Check for most recent snapshot time + id
                                if snapshots:
                                    for snapshot in snapshots:
                                        snapshot_time = snapshot.get("time", "")
                                        if snapshot_time:
                                            if not repo_last_time or snapshot_time > repo_last_time:
                                                repo_last_time = snapshot_time
                                                full_id = snapshot.get("id") or ""
                                                repo_last_full_id = full_id
                                                repo_last_short_id = (
                                                    snapshot.get("short_id")
                                                    or (full_id[:8] if full_id else "")
                                                )
                                            if last_backup == "Never" or snapshot_time > last_backup:
                                                last_backup = snapshot_time
                        except json.JSONDecodeError:
                            pass
                except:
                    pass
                
                # Get repository size
                args = ["-r", repo_path, "stats", "--mode", "raw-data", "--json"]
                try:
                    success, stdout, stderr = self.restic_cmd.run(args, env, timeout=30)
                    if success and stdout:
                        try:
                            stats = json.loads(stdout)
                            repo_size = stats.get("total_size", 0)
                            total_size += repo_size
                        except json.JSONDecodeError:
                            pass
                except:
                    pass
                
                # Keep repos that have any usable info (charts / last-backup map)
                if repo_name and (repo_size > 0 or repo_snapshot_count > 0 or repo_last_time):
                    repo_data.append((
                        repo_name,
                        repo_size,
                        repo_snapshot_count,
                        repo_last_time,
                        repo_last_short_id,
                        repo_last_full_id,
                    ))
            
            if DEBUG_MODE:
                print(f"[DASHBOARD] Stats collected: {total_snapshots} snapshots, {total_size} bytes, {len(repo_data)} repos")
            
            # Emit signal to update UI on main thread (using str to avoid int32 overflow)
            self.dashboard_update_signal.emit(total_snapshots, str(total_size), last_backup, repo_data)
        
        # Start background thread
        if getattr(self, "_dashboard_refresh_thread", None) and self._dashboard_refresh_thread.is_alive():
            return
        self._dashboard_refresh_thread = Thread(target=gather_stats, daemon=True)
        self._dashboard_refresh_thread.start()
    
    def _update_dashboard_ui_impl(self, total_snapshots, total_size_str, last_backup, repo_data):
        """Update dashboard UI with gathered stats (called from main thread via signal)"""
        # Convert size back from string to int
        total_size = int(total_size_str) if total_size_str else 0
        
        if DEBUG_MODE:
            print(f"[DASHBOARD] Updating UI: {total_snapshots} snapshots, {total_size} bytes")
        
        self._apply_dashboard_stats(total_snapshots, total_size, last_backup, repo_data)
        self._set_dashboard_refreshing(False)

    def _sync_job_last_runs_from_repos(self, repo_last: dict, repo_snaps: dict | None = None) -> None:
        """Persist discovered snapshot times/ids onto backup jobs (no SQLite needed)."""
        repo_snaps = repo_snaps or {}
        if not repo_last and not repo_snaps:
            return
        jobs = self.settings_manager.get("backup_jobs") or []
        changed = False
        for job in jobs:
            repos = job.get("repositories") or []
            if not repos and job.get("repository"):
                repos = [job.get("repository")]
            best = ""
            best_snap = None
            for name in repos:
                stamp = repo_last.get(name) or ""
                if stamp and (not best or stamp > best):
                    best = stamp
                    best_snap = repo_snaps.get(name)
            if best:
                prev = (job.get("schedule") or {}).get("last_run") or job.get("last_run")
                if prev != best:
                    job["last_run"] = best
                    if job.get("schedule") is None:
                        job["schedule"] = {"enabled": False}
                    job["schedule"]["last_run"] = best
                    changed = True
            if best_snap:
                short_id = best_snap.get("short_id") or ""
                full_id = best_snap.get("id") or short_id
                if short_id and (
                    job.get("last_snapshot_id") != short_id
                    or job.get("last_snapshot_full_id") != full_id
                ):
                    job["last_snapshot_id"] = short_id
                    job["last_snapshot_full_id"] = full_id
                    changed = True
        if changed:
            self.settings_manager.set("backup_jobs", jobs)
            self.settings_manager.save_settings()
    
    def _chart_theme_kwargs(self) -> dict:
        current_theme = (
            self.settings_manager.get("theme") if hasattr(self, "settings_manager") else "slate"
        )
        colors = themes.get_chart_colors(current_theme)
        bg = colors.get("surface") or colors["bg_color"]
        return {
            "bg": bg,
            "text": colors["text_color"],
            "muted": colors.get("muted") or colors["text_color"],
            "grid": colors["grid_color"],
        }

    def _apply_chart_theme(self) -> None:
        kwargs = self._chart_theme_kwargs()
        if hasattr(self, "repo_size_chart"):
            self.repo_size_chart.set_theme(**kwargs)
        if hasattr(self, "snapshot_count_chart"):
            self.snapshot_count_chart.set_theme(**kwargs)

    def _update_dashboard_charts(self, repo_data):
        """Update dashboard charts with repository data"""
        if not hasattr(self, "repo_size_chart") and not hasattr(self, "snapshot_count_chart"):
            return

        try:
            repo_names = [r[0] for r in repo_data]
            repo_sizes = [r[1] for r in repo_data]
            repo_snapshots = [r[2] for r in repo_data]
            repositories = self.settings_manager.get("repositories") or []
            slice_colors = [
                themes.repo_color_for_name(name, repositories) for name in repo_names
            ]
            self._apply_chart_theme()

            if hasattr(self, "repo_size_chart"):
                total = sum(repo_sizes)
                size_labels = [self.format_bytes(size) for size in repo_sizes]
                self.repo_size_chart.set_data(
                    repo_names,
                    repo_sizes,
                    slice_colors,
                    total_label=self.format_bytes(total) if total > 0 else "—",
                    size_labels=size_labels,
                    empty_message="No data available",
                )

            if hasattr(self, "snapshot_count_chart"):
                self.snapshot_count_chart.set_data(
                    repo_names,
                    repo_snapshots,
                    slice_colors,
                    empty_message="No snapshots found",
                )
        except Exception as e:
            if DEBUG_MODE:
                print(f"[CHART ERROR] Failed to update charts: {str(e)}")
                import traceback
                traceback.print_exc()

    def _initialize_empty_charts(self):
        """Initialize empty charts with current theme colors"""
        if not hasattr(self, "repo_size_chart") and not hasattr(self, "snapshot_count_chart"):
            return
        try:
            self._apply_chart_theme()
            msg = 'Click "Refresh Dashboard" to load data'
            if hasattr(self, "repo_size_chart"):
                self.repo_size_chart.clear(msg)
            if hasattr(self, "snapshot_count_chart"):
                self.snapshot_count_chart.clear(msg)
            if DEBUG_MODE:
                print("[CHART] Initialized empty QPainter charts")
        except Exception as e:
            if DEBUG_MODE:
                print(f"[CHART ERROR] Failed to initialize empty charts: {str(e)}")

    def _refresh_chart_theme(self):
        """Refresh chart chrome when theme changes (keeps current data)."""
        try:
            self._apply_chart_theme()
            if DEBUG_MODE:
                print("[CHART] Refreshed QPainter chart theme")
        except Exception as e:
            if DEBUG_MODE:
                print(f"[CHART ERROR] Failed to refresh chart theme: {str(e)}")
    
    def create_repositories_page(self):
        """Create repositories management page"""
        page = create_repositories_page(self)
        self.refresh_repository_list()
        self.stacked_widget.addWidget(page)
    
    def create_snapshots_page(self):
        """Create snapshots browser page"""
        page = build_snapshots_page_ui(self)
        self.stacked_widget.addWidget(page)
    
    def create_restore_page(self):
        """Create file restore page"""
        page = QWidget()
        page.setVisible(False)  # prevent top-level flash during splash processEvents
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Restore Files")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        
        # Restore form
        form_group = QGroupBox("Restore Configuration")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Repository selection
        self.restore_repo_combo = QComboBox()
        self.restore_repo_combo.setFixedWidth(400)
        
        # Snapshot selection with quick access buttons
        snapshot_row = QHBoxLayout()
        self.restore_snapshot_combo = QComboBox()
        self.restore_snapshot_combo.setFixedWidth(325)
        self.restore_repo_combo.currentTextChanged.connect(self.load_snapshots_for_restore)
        snapshot_row.addWidget(self.restore_snapshot_combo)
        
        # Latest snapshot button
        latest_btn = QPushButton("Latest")
        latest_btn.setFixedWidth(70)
        latest_btn.setToolTip("Jump to the most recent snapshot")
        latest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        latest_btn.clicked.connect(self.select_latest_snapshot)
        snapshot_row.addWidget(latest_btn)
        snapshot_row.addStretch()
        
        
        # Path to restore
        path_layout = QHBoxLayout()
        self.restore_path_input = QLineEdit()
        self.restore_path_input.setPlaceholderText("Leave empty to restore all files")
        self.restore_path_input.setFixedWidth(400)
        path_layout.addWidget(self.restore_path_input)
        browse_btn = QPushButton("Browse Snapshot")
        browse_btn.clicked.connect(self.browse_snapshot_files)
        path_layout.addWidget(browse_btn)
        
        
        # Restore to original location checkbox
        self.restore_to_original_check = QCheckBox("Restore to original location")
        self.restore_to_original_check.setToolTip("When checked, files will be restored to their original paths from the snapshot")
        self.restore_to_original_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_to_original_check.stateChanged.connect(self._on_restore_to_original_changed)
        
        
        
        # Target directory
        target_layout = QHBoxLayout()
        self.restore_target_input = QLineEdit()
        self.restore_target_input.setPlaceholderText("Select target directory for restore")
        self.restore_target_input.setFixedWidth(400)
        target_layout.addWidget(self.restore_target_input)
        
        self.target_browse_btn = QPushButton("Browse")
        self.target_browse_btn.clicked.connect(self.browse_restore_target)
        target_layout.addWidget(self.target_browse_btn)
        
        
        
        form_layout.addRow("Repository:", self.restore_repo_combo)
        form_layout.addRow("Snapshot:", snapshot_row)
        
        # Date-based quick restore
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Quick Select by Date:"))
        date_row.addSpacing(60)

        self.restore_date_edit = QDateEdit()
        self.restore_date_edit.setDate(QDate.currentDate())
        self.restore_date_edit.setCalendarPopup(True)
        self.restore_date_edit.setFixedWidth(200)
        date_row.addWidget(self.restore_date_edit)
        
        find_date_btn = QPushButton("Find Snapshot")
        find_date_btn.setToolTip("Find snapshot closest to selected date")
        find_date_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        find_date_btn.clicked.connect(self.find_snapshot_by_date)
        date_row.addWidget(find_date_btn)
        date_row.addStretch()
        
        form_layout.addRow("", date_row)
        form_layout.addRow("Path to Restore:", path_layout)
        form_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        form_layout.addRow("", self.restore_to_original_check)
        form_layout.addRow("Restore To:", target_layout)
        
        # Global search section
        search_group = QGroupBox("Search Across All Snapshots")
        search_layout = QVBoxLayout()
        search_group.setLayout(search_layout)
        
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Find file/folder:"))
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText("Enter filename or path  pattern (e.g., *.pdf, my_document.txt, /path/to/folder)")
        self.global_search_input.setFixedWidth(400)
        search_row.addWidget(self.global_search_input)
        
        search_btn = QPushButton("Search All Snapshots")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self.search_across_snapshots)
        search_row.addWidget(search_btn)
        search_row.addStretch()
        
        search_layout.addLayout(search_row)
        
        # Search results table
        from PyQt6.QtWidgets import QHeaderView
        self.search_results_table = QTableWidget()
        self.search_results_table.setColumnCount(6)
        self.search_results_table.setHorizontalHeaderLabels(["File/Folder", "Path", "Snapshot ID", "Date/Time", "Size", "Action"])
        self.search_results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.search_results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.search_results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.search_results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.search_results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.search_results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.search_results_table.setMaximumHeight(200)
        #self.search_results_table.setFixedHeight(300)
        self.search_results_table.setVisible(False)  # Hidden until search is performed
        search_layout.addWidget(self.search_results_table)
        
        
        
        # Restore buttons
        restore_btn = QPushButton("Start Restore")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.clicked.connect(self.start_restore)
        
        self.mount_browse_btn = QPushButton("Browse Files")
        self.mount_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mount_browse_btn.clicked.connect(self.mount_and_browse_snapshot)
        self.mount_browse_btn.setToolTip("Browse all snapshots in the repository and restore specific files")
        
        restore_layout = QHBoxLayout()
        restore_layout.addStretch()
        restore_layout.addWidget(self.mount_browse_btn)
        restore_layout.addSpacing(10)
        restore_layout.addWidget(restore_btn)
        restore_layout.addStretch()
        
        
        
        # Progress
        self.restore_progress = QProgressBar()
        self.restore_progress.setVisible(False)
        
        
        # Log output
        log_group = QGroupBox("Restore Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.restore_log = QPlainTextEdit()
        self.restore_log.setReadOnly(True)
        log_layout.addWidget(self.restore_log)
        
        layout.addWidget(title)
        layout.addWidget(form_group)
        layout.addWidget(search_group)
        layout.addLayout(restore_layout)
        layout.addWidget(self.restore_progress)
        layout.addWidget(log_group)
        
        self.stacked_widget.addWidget(page)
    
    def create_backup_page(self):
        """Create backup jobs management page"""
        page = QWidget()
        page.setVisible(False)  # prevent top-level flash during splash processEvents
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title and buttons
        header_layout = QHBoxLayout()
        title = QLabel("Backup Jobs")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        new_job_btn = QPushButton("New Job")
        new_job_btn.clicked.connect(self.add_backup_job)
        header_layout.addWidget(new_job_btn)
        
        layout.addLayout(header_layout)
        
        # Jobs table
        self.backup_jobs_table = QTableWidget()
        self.backup_jobs_table.setColumnCount(5)
        self.backup_jobs_table.setHorizontalHeaderLabels(["Job Name", "Repository", "Paths", "Schedule", "Actions"])
        self.backup_jobs_table.horizontalHeader().setStretchLastSection(False)
        self.backup_jobs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.backup_jobs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.backup_jobs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.backup_jobs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.backup_jobs_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.backup_jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.backup_jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.backup_jobs_table)
        
        # Refresh jobs list
        self.refresh_backup_jobs_list()
        
        self.stacked_widget.addWidget(page)
    
    def refresh_backup_jobs_list(self):
        """Refresh the backup jobs table"""
        self.backup_jobs_table.setRowCount(0)
        jobs = self.settings_manager.get("backup_jobs")
        
        for job in jobs:
            row = self.backup_jobs_table.rowCount()
            self.backup_jobs_table.insertRow(row)
            
            # Job name
            self.backup_jobs_table.setItem(row, 0, QTableWidgetItem(job.get("name", "")))
            
            # Repository (handle both single and multiple repositories)
            repositories = job.get("repositories", [])
            if not repositories:
                # Backwards compatibility with old single "repository" field
                repo = job.get("repository", "")
                repositories = [repo] if repo else []
            
            repo_text = ""
            if repositories:
                if len(repositories) == 1:
                    repo_text = repositories[0]
                else:
                    repo_text = f"{repositories[0]} +{len(repositories)-1} more"
            self.backup_jobs_table.setItem(row, 1, QTableWidgetItem(repo_text))
            
            # Paths (show count and first path)
            paths = job.get("paths", [])
            paths_text = f"{len(paths)} path(s)"
            if paths:
                paths_text += f": {paths[0]}"
                if len(paths) > 1:
                    paths_text += f" +{len(paths)-1} more"
            self.backup_jobs_table.setItem(row, 2, QTableWidgetItem(paths_text))
            
            # Schedule status
            schedule = job.get("schedule")
            if schedule and schedule.get("enabled"):
                freq = schedule.get("frequency", "daily").capitalize()
                time = schedule.get("time", "00:00")
                if freq == "Weekly":
                    days = schedule.get("days", [])
                    days_str = ", ".join(days) if days else "All days"
                    schedule_text = f"â° {freq} at {time}\n({days_str})"
                elif freq == "Monthly":
                    day_of_month = schedule.get("day_of_month", 1)
                    schedule_text = f"â° {freq} at {time}\n(Day {day_of_month})"
                else:
                    schedule_text = f"â° {freq} at {time}"
            else:
                schedule_text = "Manual"
            self.backup_jobs_table.setItem(row, 3, QTableWidgetItem(schedule_text))
            
            # Actions buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_widget.setLayout(actions_layout)
            
            run_btn = QPushButton("Run")
            run_btn.setFixedWidth(60)
            run_btn.clicked.connect(lambda checked, j=job: self.run_backup_job(j))
            actions_layout.addWidget(run_btn)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedWidth(60)
            edit_btn.clicked.connect(lambda checked, j=job: self.edit_backup_job(j))
            actions_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setFixedWidth(60)
            delete_btn.clicked.connect(lambda checked, j=job: self.delete_backup_job(j))
            actions_layout.addWidget(delete_btn)
            
            self.backup_jobs_table.setCellWidget(row, 4, actions_widget)

        if hasattr(self, "refresh_dashboard_jobs_table"):
            self.refresh_dashboard_jobs_table()
    
    def create_retention_page(self):
        """Create retention policy page"""
        page = QWidget()
        page.setVisible(False)  # prevent top-level flash during splash processEvents
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Retention Policy")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Policy form
        form_group = QGroupBox("Retention Configuration")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Repository
        self.retention_repo_combo = QComboBox()
        self.retention_repo_combo.setFixedWidth(300)
        
        
        # Keep policies
        self.keep_last_spin = QSpinBox()
        self.keep_last_spin.setToolTip("Number of most recent snapshots to keep (overrides all other rules)")
        self.keep_last_spin.setFixedWidth(50)
        self.keep_last_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_last_spin.setMinimum(0)
        self.keep_last_spin.setMaximum(1000)
        
        
        self.keep_hourly_spin = QSpinBox()
        self.keep_hourly_spin.setToolTip("Number of hourly snapshots to keep")
        self.keep_hourly_spin.setFixedWidth(50)
        self.keep_hourly_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_hourly_spin.setMinimum(0)
        self.keep_hourly_spin.setMaximum(1000)
        
        
        self.keep_daily_spin = QSpinBox()
        self.keep_daily_spin.setToolTip("Number of daily snapshots to keep")
        self.keep_daily_spin.setFixedWidth(50)
        self.keep_daily_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_daily_spin.setMinimum(0)
        self.keep_daily_spin.setMaximum(365)
        self.keep_daily_spin.setValue(7)
        
        
        self.keep_weekly_spin = QSpinBox()
        self.keep_weekly_spin.setToolTip("Number of weekly snapshots to keep")
        self.keep_weekly_spin.setFixedWidth(50)
        self.keep_weekly_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_weekly_spin.setMinimum(0)
        self.keep_weekly_spin.setMaximum(520)
        self.keep_weekly_spin.setValue(4)
        
        
        self.keep_monthly_spin = QSpinBox()
        self.keep_monthly_spin.setToolTip("Number of monthly snapshots to keep")
        self.keep_monthly_spin.setFixedWidth(50)
        self.keep_monthly_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_monthly_spin.setMinimum(0)
        self.keep_monthly_spin.setMaximum(120)
        self.keep_monthly_spin.setValue(12)
        
        
        self.keep_yearly_spin = QSpinBox()
        self.keep_yearly_spin.setToolTip("Number of yearly snapshots to keep")
        self.keep_yearly_spin.setFixedWidth(50)
        self.keep_yearly_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_yearly_spin.setMinimum(0)
        self.keep_yearly_spin.setMaximum(100)
        
        keep_layout_one = QHBoxLayout()
        keep_layout_one.addWidget(QLabel("Keep Last:"))
        keep_layout_one.addSpacing(17)
        keep_layout_one.addWidget(self.keep_last_spin)
        keep_layout_one.addSpacing(20)
        keep_layout_one.addWidget(QLabel("Keep Hourly:"))
        keep_layout_one.addSpacing(9)
        keep_layout_one.addWidget(self.keep_hourly_spin)
        keep_layout_one.addSpacing(20)
        keep_layout_one.addWidget(QLabel("Keep Daily:"))
        keep_layout_one.addSpacing(5)
        keep_layout_one.addWidget(self.keep_daily_spin)
        keep_layout_one.addStretch()
        
        keep_layout_two = QHBoxLayout()#
        keep_layout_two.addWidget(QLabel("Keep Weekly:"))
        keep_layout_two.addWidget(self.keep_weekly_spin)
        keep_layout_two.addSpacing(20)
        keep_layout_two.addWidget(QLabel("Keep Monthly:"))
        keep_layout_two.addWidget(self.keep_monthly_spin)
        keep_layout_two.addSpacing(20)
        keep_layout_two.addWidget(QLabel("Keep Yearly:"))
        keep_layout_two.addWidget(self.keep_yearly_spin)
        keep_layout_two.addStretch()
        
        
        form_layout.addRow("Repository:", self.retention_repo_combo)
        form_layout.addRow(keep_layout_one)
        form_layout.addRow(keep_layout_two)
        # form_layout.addRow("Keep Last:", self.keep_last_spin)
        # form_layout.addRow("Keep Hourly:", self.keep_hourly_spin)
        # form_layout.addRow("Keep Daily:", self.keep_daily_spin)
        # form_layout.addRow("Keep Weekly:", self.keep_weekly_spin)
        # form_layout.addRow("Keep Monthly:", self.keep_monthly_spin)
        # form_layout.addRow("Keep Yearly:", self.keep_yearly_spin)
        
        layout.addWidget(form_group)
        
        # Scheduling section
        schedule_group = QGroupBox("Schedule Retention (Task Scheduler)")
        schedule_layout = QVBoxLayout()
        schedule_group.setLayout(schedule_layout)
        
        # Frequency
        self.retention_frequency_combo = QComboBox()
        self.retention_frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
        self.retention_frequency_combo.setCurrentText("Weekly")
        self.retention_frequency_combo.setToolTip("Frequency for running the retention policy automatically")
        self.retention_frequency_combo.setFixedWidth(150)
        self.retention_frequency_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retention_frequency_combo.currentTextChanged.connect(self._on_retention_frequency_changed)
        
        
        # Time
        self.retention_time_edit = QTimeEdit()
        self.retention_time_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retention_time_edit.setToolTip("Time of day to run the retention policy")
        self.retention_time_edit.setFixedWidth(70)
        self.retention_time_edit.setTime(QTime(2, 0))  # Default 2:00 AM
        self.retention_time_edit.setDisplayFormat("HH:mm")
        
        
        # Day of week (for weekly)
        self.retention_day_combo = QComboBox()
        self.retention_day_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retention_day_combo.setToolTip("Day of the week to run the retention policy")
        self.retention_day_combo.setFixedWidth(150)
        self.retention_day_combo.addItems(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
        self.retention_day_combo.setCurrentText("Sunday")
        
        
        # Day of month (for monthly)
        self.retention_dom_spin = QSpinBox()
        self.retention_dom_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retention_dom_spin.setToolTip("Day of the month to run the retention policy (1-28)")
        self.retention_dom_spin.setFixedWidth(150)
        self.retention_dom_spin.setMinimum(1)
        self.retention_dom_spin.setMaximum(28)  # Safe for all months
        self.retention_dom_spin.setValue(1)
        self.retention_dom_spin.setSuffix(" of month")
        
        self.retention_dom_spin.setVisible(False)
        
        schedule_form = QFormLayout()
        schedule_form.addRow("Time:", self.retention_time_edit)
        schedule_form.addRow("Frequency:", self.retention_frequency_combo)
        schedule_form.addRow("Day of Week:", self.retention_day_combo)
        schedule_form.addRow("Day of Month:", self.retention_dom_spin)
        # Store reference to form layout for label access
        self._retention_schedule_form = schedule_form
        
        # Hide day of month label initially
        dom_label = schedule_form.labelForField(self.retention_dom_spin)
        if dom_label:
            dom_label.setVisible(False)
        
        schedule_layout.addLayout(schedule_form)
        
        # Task scheduler buttons
        task_btn_layout = QHBoxLayout()
        
        create_task_btn = QPushButton("Create Scheduled Task")
        create_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_task_btn.setToolTip("Create a Windows Task Scheduler task to run retention automatically")
        create_task_btn.clicked.connect(self.create_retention_scheduled_task)
        
        view_tasks_btn = QPushButton("View Tasks")
        view_tasks_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_tasks_btn.setToolTip("Open Task Scheduler to view scheduled tasks")
        view_tasks_btn.clicked.connect(self.open_task_scheduler)
        
        delete_task_btn = QPushButton("Delete Task")
        delete_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_task_btn.setToolTip("Delete the scheduled retention task for this repository")
        delete_task_btn.clicked.connect(self.delete_retention_scheduled_task)
        
        #task_btn_layout.addStretch()
        task_btn_layout.addSpacing(86)
        task_btn_layout.addWidget(create_task_btn)
        task_btn_layout.addWidget(view_tasks_btn)
        task_btn_layout.addWidget(delete_task_btn)
        task_btn_layout.addStretch()
        
        schedule_layout.addLayout(task_btn_layout)
        
        # Info label
        info_label = QLabel("ℹ Creates a system task that runs retention independently of this application")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 10px; padding: 5px;")
        
        info_label_layout = QHBoxLayout()
        info_label_layout.addSpacing(86)  # Align with buttons
        info_label_layout.addWidget(info_label)
        schedule_layout.addLayout(info_label_layout)
        
        layout.addWidget(schedule_group)
        
        # Action buttons (Manual)
        manual_group = QGroupBox("Manual Execution")
        manual_layout = QVBoxLayout()
        manual_group.setLayout(manual_layout)
        
        
        
        dry_run_btn = QPushButton("Dry Run (Preview)")
        dry_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dry_run_btn.clicked.connect(lambda: self.apply_retention(dry_run=True))
        
        
        apply_btn = QPushButton("Apply Policy")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(lambda: self.apply_retention(dry_run=False))
        
        btn_layout = QHBoxLayout()
        btn_layout.addSpacing(86)  # Align with other buttons
        btn_layout.addWidget(dry_run_btn)
        btn_layout.addWidget(apply_btn)
        btn_layout.addStretch()
        
        manual_layout.addLayout(btn_layout)
        layout.addWidget(manual_group)
        
        # Output
        output_group = QGroupBox("Policy Output")
        output_layout = QVBoxLayout()
        output_group.setLayout(output_layout)
        
        self.retention_output = QPlainTextEdit()
        self.retention_output.setReadOnly(True)
        output_layout.addWidget(self.retention_output)
        
        layout.addWidget(output_group)
        
        self.stacked_widget.addWidget(page)
    
    def create_logs_page(self):
        """Create logs viewer page"""
        page = QWidget()
        page.setVisible(False)  # prevent top-level flash during splash processEvents
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title and controls
        title_layout = QHBoxLayout()
        title = QLabel("Logs")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        title_layout.addWidget(clear_btn)
        
        layout.addLayout(title_layout)
        
        # Log viewer
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_viewer)
        
        self.stacked_widget.addWidget(page)
    
    def create_settings_page(self):
        """Create settings page"""
        page = QWidget()
        page.setVisible(False)  # prevent top-level flash during splash processEvents
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        
        
        # Settings form
        form_group = QGroupBox("Application Settings")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Restic path
        
        self.restic_path_input = QLineEdit()
        self.restic_path_input.setText(self.settings_manager.get("restic_path"))
        self.restic_path_input.setFixedWidth(400)
        
        browse_restic_btn = QPushButton("Browse")
        browse_restic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_restic_btn.clicked.connect(self.browse_restic_path)
        
        test_restic_btn = QPushButton("Test")
        test_restic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_restic_btn.clicked.connect(self.test_restic_path)
        test_restic_btn.setToolTip("Test if restic can be executed from this path")
        
        restic_path_layout = QHBoxLayout()
        restic_path_layout.addWidget(self.restic_path_input)
        restic_path_layout.addWidget(browse_restic_btn)
        restic_path_layout.addWidget(test_restic_btn)
        restic_path_layout.addStretch()
        form_layout.addRow("Restic Path:", restic_path_layout)
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(themes.theme_display_names())
        current_theme_id = themes.resolve_theme_id(self.settings_manager.get("theme"))
        current_theme_name = themes.get_app_theme(current_theme_id).name
        idx = self.theme_combo.findText(current_theme_name)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.setFixedWidth(160)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        form_layout.addRow("Theme:", self.theme_combo)
        
        # Auto refresh snapshots
        self.auto_refresh_check = QCheckBox()
        self.auto_refresh_check.setChecked(self.settings_manager.get("auto_refresh_snapshots"))
        form_layout.addRow("Auto Refresh Snapshots:", self.auto_refresh_check)
        
        # Refresh interval
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setMinimum(10)
        self.refresh_interval_spin.setMaximum(3600)
        self.refresh_interval_spin.setValue(self.settings_manager.get("snapshot_refresh_interval"))
        self.refresh_interval_spin.setSuffix(" seconds")
        self.refresh_interval_spin.setFixedWidth(120)
        form_layout.addRow("Refresh Interval:", self.refresh_interval_spin)
        
        # Temporary restore location
        self.temp_restore_path_input = QLineEdit()
        temp_restore_default = self.settings_manager.get("temp_restore_path")
        self.temp_restore_path_input.setText(temp_restore_default)
        self.temp_restore_path_input.setFixedWidth(400)
        
        browse_temp_restore_btn = QPushButton("Browse")
        browse_temp_restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_temp_restore_btn.clicked.connect(self.browse_temp_restore_path)
        
        temp_restore_layout = QHBoxLayout()
        temp_restore_layout.addWidget(self.temp_restore_path_input)
        temp_restore_layout.addWidget(browse_temp_restore_btn)
        temp_restore_layout.addStretch()
        form_layout.addRow("Temp Restore Path:", temp_restore_layout)
        
        # Help text for temp restore path
        temp_restore_help = QLabel("Used for 'Restore to original location' feature (files are moved automatically)")
        temp_restore_help.setStyleSheet("color: gray; font-style: italic; font-size: 9pt;")
        temp_restore_help.setWordWrap(True)
        form_layout.addRow("", temp_restore_help)
        
        layout.addWidget(title)
        layout.addWidget(form_group)
        
        # Security Settings
        security_group = QGroupBox("Security Settings - Application Password")
        security_layout = QVBoxLayout()
        security_group.setLayout(security_layout)
        
        # Status display
        status_container = QHBoxLayout()
        status_label = QLabel("Password Protection Status:")
        status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        status_container.addWidget(status_label)
        
        self.password_status_label = QLabel()
        has_password = False
        storage_location = ""
        
        if sys.platform == "win32":
            # Windows: Registry only
            reg_hash = retrieve_from_registry("AppPasswordHash")
            reg_salt = retrieve_from_registry("AppPasswordSalt")
            if reg_hash and reg_salt:
                has_password = True
                storage_location = " (Registry)"
        else:
            # Non-Windows: JSON storage
            if self.settings_manager.get("app_password_hash"):
                has_password = True
                storage_location = " (Settings file)"
        
        if has_password:
            self.password_status_label.setText(f"🔒 ACTIVE - Password required at startup{storage_location}")
            self.password_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.password_status_label.setText("🔓 INACTIVE")
            self.password_status_label.setStyleSheet("color: orange; font-weight: bold;")
        status_container.addWidget(self.password_status_label)
        status_container.addStretch()
        security_layout.addLayout(status_container)
        
        security_layout.addSpacing(10)
        
        # Help text
        storage_info = ""
        if sys.platform == "win32":
            storage_info = "Password hash is stored in Windows Registry (HKCU\\Software\\ResticManager) for enhanced security. "
        
        password_help = QLabel(
            f"⚠️ Security Note: {storage_info}"
            f"Password protection is enforced by cryptographic hashing. "
            f"To disable password protection, you must authenticate and use the 'Remove Password' button below."
        )
        password_help.setStyleSheet("color: gray; font-style: italic; font-size: 9pt; padding: 5px; background-color: rgba(255, 165, 0, 0.1); border-radius: 3px;")
        password_help.setWordWrap(True)
        security_layout.addWidget(password_help)
        
        security_layout.addSpacing(10)
        
        # Buttons
        password_btn_layout = QHBoxLayout()
        
        # Check if password exists (Registry or JSON)
        password_exists = has_password  # Use the value from status check above
        
        self.set_password_btn = QPushButton("Set Password" if not password_exists else "Change Password")
        self.set_password_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_password_btn.clicked.connect(self.set_app_password)
        password_btn_layout.addWidget(self.set_password_btn)
        
        password_btn_layout.addSpacing(10)
        
        self.remove_password_btn = QPushButton("Remove Password")
        self.remove_password_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_password_btn.clicked.connect(self.remove_app_password)
        self.remove_password_btn.setEnabled(password_exists)
        password_btn_layout.addWidget(self.remove_password_btn)
        
        password_btn_layout.addStretch()
        
        security_layout.addLayout(password_btn_layout)
        
        
        
        
        
        # Buttons layout (Save, Backup, Restore)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        save_btn = QPushButton("Save Settings")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)
        
        backup_btn = QPushButton("Backup Settings")
        backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        backup_btn.clicked.connect(self.backup_settings)
        buttons_layout.addWidget(backup_btn)
        
        restore_btn = QPushButton("Restore Settings")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.clicked.connect(self.restore_settings)
        buttons_layout.addWidget(restore_btn)
        
        buttons_layout.addStretch()
        
        
        # System Dependencies Section
        deps_group = QGroupBox("System Dependencies")
        deps_layout = QVBoxLayout()
        deps_group.setLayout(deps_layout)
        
        # Info label
        info_label = QLabel("Check and install required system dependencies:")
        info_label.setWordWrap(True)
        deps_layout.addWidget(info_label)
        
        # Restic status

        self.restic_status_label = QLabel("Click 'Check' to verify installation")
        self.restic_status_label.setMinimumWidth(200)
        self.restic_status_label.setStyleSheet("color: gray; font-style: italic;")

        
        self.restic_check_btn = QPushButton("Check")
        self.restic_check_btn.clicked.connect(self.check_restic_installation)
        
        
        self.restic_install_btn = QPushButton("Install")
        self.restic_install_btn.clicked.connect(self.install_restic)
        self.restic_install_btn.setVisible(False)
        
        restic_status_layout = QHBoxLayout()
        restic_status_layout.addWidget(QLabel("Restic:"))
        restic_status_layout.addWidget(self.restic_status_label)
        restic_status_layout.addStretch()
        restic_status_layout.addWidget(self.restic_check_btn)
        restic_status_layout.addWidget(self.restic_install_btn)

        
        deps_layout.addLayout(restic_status_layout)
        
        
        
        # Don't auto-check on page load - let users click "Check" manually
        # Auto-checking can cause UI hangs if restic is not properly configured
        # QTimer.singleShot(100, self.check_restic_installation)
        
        # License Management Section
        license_group = QGroupBox("License Information")

        
        # License status
        self.license_status_label = QLabel()
        self.license_status_label.setWordWrap(True)
        
        
        # Machine ID display

        self.machine_id_display = QLineEdit()
        self.machine_id_display.setFixedWidth(400)
        self.machine_id_display.setReadOnly(True)
        self.machine_id_display.setFont(QFont("Courier", 9))
        
        machine_id_display_layout = QHBoxLayout()
        machine_id_display_layout.addWidget(self.machine_id_display)
        machine_id_display_layout.addStretch()
        
        
        
        copy_machine_id_btn = QPushButton("Copy")
        copy_machine_id_btn.clicked.connect(self.copy_machine_id)

        machine_id_layout = QHBoxLayout()
        machine_id_layout.addWidget(QLabel("Machine ID:"))
        machine_id_layout.addLayout(machine_id_display_layout)
        machine_id_layout.addWidget(copy_machine_id_btn)
        machine_id_layout.addStretch()
        
        
        # License action buttons
        
        
        update_license_btn = QPushButton("Update License Key")
        update_license_btn.setFixedWidth(180)
        update_license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        update_license_btn.clicked.connect(self.update_license_key)
        
        
        refresh_license_btn = QPushButton("Refresh Status")
        refresh_license_btn.setFixedWidth(180)
        refresh_license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_license_btn.clicked.connect(self.refresh_license_status)
        
        license_btn_layout = QHBoxLayout()
        license_btn_layout.addSpacing(81)  # Align with other buttons
        license_btn_layout.addWidget(update_license_btn)
        license_btn_layout.addSpacing(33)
        license_btn_layout.addWidget(refresh_license_btn)
        license_btn_layout.addStretch()
        
        license_layout = QVBoxLayout()
        license_group.setLayout(license_layout)
        license_layout.addWidget(self.license_status_label)
        license_layout.addLayout(machine_id_layout)
        license_layout.addLayout(license_btn_layout)
        
        
        
        # Initialize license display
        self.refresh_license_status()
        
        
        
        # Version info
        version_group = QGroupBox("About")
        version_layout = QVBoxLayout()
        version_group.setLayout(version_layout)
        
        version_info = QLabel(
            f"Restic Backup Manager {VERSION}\n"
            f"© {YEAR}\n\n"
            "A PyQt6 GUI for managing Restic backups"
        )
        version_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(version_info)
        
        layout.addWidget(title)
        layout.addWidget(form_group)
        layout.addLayout(buttons_layout)
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addWidget(security_group)
        layout.addWidget(deps_group)
        layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addWidget(license_group)
        layout.addStretch()
        layout.addWidget(version_group)
        
        self.stacked_widget.addWidget(page)
    
    # Repository Management Methods
    def add_repository(self):
        """Add a new repository"""
        dialog = RepositoryDialog(self, self.settings_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            repo_data = dialog.get_repository_data()
            
            # Check if initialization is requested
            should_initialize = repo_data.pop("initialize", False)
            
            if should_initialize:
                # Show framed progress dialog (non-modal so UI doesn't freeze)
                self._add_repo_progress, _, _ = make_framed_progress_dialog(
                    self,
                    "Initializing Repository",
                    (
                        f"Initializing repository “{repo_data['name']}”…\n"
                        "Please wait while the repository is being created."
                    ),
                    modal=False,
                    min_width=500,
                    min_height=320,
                )
                progress_layout = self._add_repo_progress.body_layout
                
                # Add output text area to show real-time progress
                output_text = QPlainTextEdit()
                output_text.setReadOnly(True)
                output_text.setPlaceholderText("Waiting for initialization to start...")
                output_text.setMinimumHeight(140)
                progress_layout.addWidget(output_text)
                
                # Store reference to output text
                self._init_output_text = output_text
                
                # Add close button
                close_btn = QPushButton("Close (initialization continues in background)")
                close_btn.setObjectName("dialogSecondary")
                close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                close_btn.clicked.connect(self._add_repo_progress.accept)
                progress_layout.addWidget(close_btn)
                
                self._add_repo_progress.show()
                QApplication.processEvents()
                
                # Store repo data for callback
                self._pending_repo_data = repo_data
                
                # Initialize repository in background
                password = self.settings_manager.password_manager.decrypt(repo_data["password"]) if repo_data.get("password") else ""
                env = {"RESTIC_PASSWORD": password} if password else {}
                args = ["-r", repo_data["path"], "init"]
                
                # Log to output
                output_text.appendPlainText(f"Starting initialization...\nRepository: {repo_data['path']}\n")
                QApplication.processEvents()
                
                self._init_worker = ResticWorker(self.restic_cmd, args, env, timeout=60, use_progress=True)
                self._init_worker.progress.connect(self._on_init_progress)
                self._init_worker.finished.connect(self._on_repository_initialized)
                self._init_worker.start()
                
                self.log(f"Initializing repository: {repo_data['name']}")
            else:
                # Add repository without initialization
                repositories = self.settings_manager.get("repositories")
                repositories.append(repo_data)
                themes.ensure_repo_colors(repositories)
                self.settings_manager.set("repositories", repositories)
                self.settings_manager.save_settings()
                self.refresh_repository_list()
                self.update_repository_combos()
                self.log(f"Added repository: {repo_data['name']}")
                QMessageBox.information(self, "Success", f"Repository '{repo_data['name']}' added successfully!")
    
    def _on_init_progress(self, line):
        """Handle progress output during repository initialization"""
        if hasattr(self, '_init_output_text'):
            self._init_output_text.appendPlainText(line)
            # Auto-scroll to bottom
            scrollbar = self._init_output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            QApplication.processEvents()  # Keep UI responsive
    
    def _on_repository_initialized(self, success, stdout, stderr):
        """Callback when repository initialization completes"""
        # Append final output to text area
        if hasattr(self, '_init_output_text'):
            if success:
                self._init_output_text.appendPlainText("\n=== Initialization Complete ===")
                if stdout:
                    self._init_output_text.appendPlainText(stdout)
            else:
                self._init_output_text.appendPlainText("\n=== Initialization Failed ===")
                if stderr:
                    self._init_output_text.appendPlainText(f"Error: {stderr}")
                if stdout:
                    self._init_output_text.appendPlainText(stdout)
            QApplication.processEvents()
        
        # Close progress dialog after a brief moment
        QTimer.singleShot(1000, self._close_init_dialog)  # Give user 1 second to see final output
        
        repo_data = self._pending_repo_data
        
        if success:
            # Add repository to list
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            repo_data["last_checked"] = stamp
            repo_data["check_status"] = "healthy"
            repo_data.pop("check_error", None)
            repositories = self.settings_manager.get("repositories")
            repositories.append(repo_data)
            themes.ensure_repo_colors(repositories)
            self.settings_manager.set("repositories", repositories)
            self.settings_manager.save_settings()
            self.refresh_repository_list()
            self.update_repository_combos()
            
            # Show success with initialization details
            details = f"Repository '{repo_data['name']}' has been initialized and added successfully!\n\n"
            if stdout:
                details += f"Output:\n{stdout[:500]}"  # Show first 500 chars
            
            QMessageBox.information(
                self, 
                "Repository Initialized", 
                details
            )
            self.log(f"Successfully initialized and added repository: {repo_data['name']}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            # Also include stdout in case there are warnings
            full_msg = f"Failed to initialize repository:\n\n{error_msg}"
            if stdout:
                full_msg += f"\n\nAdditional output:\n{stdout[:300]}"
            full_msg += f"\n\nRepository path: {repo_data['path']}\n\nThe repository was not added."
            
            QMessageBox.warning(
                self, 
                "Initialization Failed", 
                full_msg
            )
            self.log(f"Failed to initialize repository {repo_data['name']}: {error_msg}")
    
    def _close_init_dialog(self):
        """Close the initialization progress dialog"""
        if hasattr(self, '_add_repo_progress'):
            try:
                self._add_repo_progress.close()
                self._add_repo_progress.deleteLater()
            except:
                pass
    
    def refresh_repository_list(self):
        """Refresh the repository list table"""
        self._ensure_repository_colors()
        populate_repository_table(
            self,
            on_edit=self.edit_repository_by_name,
            on_delete=self.delete_repository_by_name,
            on_check=self.check_repository_by_name,
        )

    def _ensure_repository_colors(self) -> None:
        """Backfill deterministic colours for any repository missing ``color``."""
        repositories = self.settings_manager.get("repositories") or []
        if themes.ensure_repo_colors(repositories):
            self.settings_manager.set("repositories", repositories)
            self.settings_manager.save_settings()

    def _repository_index_by_name(self, name: str) -> int:
        repositories = self.settings_manager.get("repositories") or []
        for i, repo in enumerate(repositories):
            if repo.get("name") == name:
                return i
        return -1

    def edit_repository_by_name(self, name: str) -> None:
        index = self._repository_index_by_name(name)
        if index >= 0:
            self.edit_repository(index)

    def delete_repository_by_name(self, name: str) -> None:
        index = self._repository_index_by_name(name)
        if index >= 0:
            self.delete_repository(index)

    def check_repository_by_name(self, name: str) -> None:
        """Run a quick connectivity check and update Status / Last Checked."""
        index = self._repository_index_by_name(name)
        if index < 0:
            return
        repositories = self.settings_manager.get("repositories") or []
        repo = repositories[index]
        path = repo.get("path") or ""
        if not path:
            QMessageBox.warning(self, "Check Connection", "Repository has no path configured.")
            return

        password = ""
        if repo.get("password"):
            try:
                password = self.settings_manager.password_manager.decrypt(repo["password"])
            except Exception:
                password = ""

        progress, _, _ = make_framed_progress_dialog(
            self,
            "Checking Connection",
            f"Checking “{name}”…\nPlease wait.",
            min_width=400,
        )
        progress.show()
        QApplication.processEvents()

        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", path, "snapshots", "--latest", "1"]
        worker = ResticWorker(self.restic_cmd, args, env, timeout=30)

        def _done(success, stdout, stderr, idx=index, repo_name=name, dlg=progress):
            try:
                dlg.close()
                dlg.deleteLater()
            except Exception:
                pass
            repos = self.settings_manager.get("repositories") or []
            if not (0 <= idx < len(repos)) or repos[idx].get("name") != repo_name:
                return
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            repos[idx]["last_checked"] = stamp
            if success:
                repos[idx]["check_status"] = "healthy"
                repos[idx].pop("check_error", None)
                self.log(f"Repository check OK: {repo_name}")
                show_notification(
                    title="Repository Healthy",
                    message=f"“{repo_name}” is reachable.",
                    icon_type="success",
                    duration="short",
                )
            else:
                err = (stderr or "Unknown error").strip()
                repos[idx]["check_status"] = "unreachable"
                repos[idx]["check_error"] = err[:500]
                self.log(f"Repository check failed: {repo_name}: {err}")
                show_notification(
                    title="Repository Unreachable",
                    message=f"“{repo_name}” check failed.",
                    icon_type="error",
                    duration="long",
                )
            self.settings_manager.set("repositories", repos)
            self.settings_manager.save_settings()
            self.refresh_repository_list()

        worker.finished.connect(_done)
        worker.start()
        self._repo_check_worker = worker  # prevent GC
    
    def edit_repository(self, index):
        """Edit repository at index"""
        repositories = self.settings_manager.get("repositories")
        if 0 <= index < len(repositories):
            repo = repositories[index]
            dialog = RepositoryDialog(self, self.settings_manager, repo)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                repo_data = dialog.get_repository_data()
                repositories[index] = repo_data
                themes.ensure_repo_colors(repositories)
                self.settings_manager.set("repositories", repositories)
                self.settings_manager.save_settings()
                self.refresh_repository_list()
                self.update_repository_combos()
                self.log(f"Updated repository: {repo_data['name']}")
    
    def delete_repository(self, index):
        """Delete repository at index"""
        repositories = self.settings_manager.get("repositories") or []
        if not (0 <= index < len(repositories)):
            return
        repo = repositories[index]
        name = repo.get("name") or "—"
        path = repo.get("path") or "—"
        repo_type = repo.get("type") or "local"

        if not self._framed_confirm(
            title="Remove Repository",
            heading=f"Remove “{name}” from the list?",
            body="This only removes the repository from Restic Manager. Backup data on disk is not deleted.",
            note="You can add the repository again later if the path and password are still available.",
            meta=[
                ("Name", name),
                ("Type", repo_type),
                ("Path", path),
            ],
            confirm_label="Remove",
            danger=True,
        ):
            return

        removed = repositories.pop(index)
        self.settings_manager.set("repositories", repositories)
        self.settings_manager.save_settings()
        self.refresh_repository_list()
        self.update_repository_combos()
        self.log(f"Removed repository: {removed.get('name')}")
    
    def update_repository_combos(self):
        """Update all repository combo boxes"""
        repositories = self.settings_manager.get("repositories")
        repo_names = [repo.get("name", "") for repo in repositories]
        
        # Block signals during update to prevent triggering load_snapshots during initialization
        for combo in [self.snapshot_repo_combo, self.restore_repo_combo, 
                      self.retention_repo_combo, self.dashboard_repo_combo]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(repo_names)
            combo.blockSignals(False)
        
        # Don't auto-refresh dashboard to prevent UI freeze
        # Users can manually click "Refresh Stats" button when needed
    
    def update_retention_repo_combo(self):
        """Update retention repository combo box with scheduled task indicators"""
        import platform
        import subprocess
        
        repositories = self.settings_manager.get("repositories")
        repo_names = [repo.get("name", "") for repo in repositories]
        
        # Store current selection (clean name)
        current_index = self.retention_repo_combo.currentIndex()
        current_repo = ""
        if current_index >= 0:
            current_repo = self.retention_repo_combo.itemData(current_index)
            if not current_repo:  # Fallback if no userData
                current_repo = self.retention_repo_combo.currentText().replace(" ✓", "").strip()
        
        # Get list of repositories with scheduled tasks
        repos_with_tasks = set()
        system = platform.system()
        
        if system == "Windows":
            # Check Windows Task Scheduler for ResticRetention tasks
            try:
                result = subprocess.run(
                    ['schtasks', '/Query', '/FO', 'LIST'],
                    capture_output=True, text=True, timeout=10,
                    creationflags=get_subprocess_creation_flags()
                )
                if result.returncode == 0:
                    # Parse task names
                    for line in result.stdout.split('\n'):
                        if 'TaskName:' in line and 'ResticRetention_' in line:
                            # Extract repo name from task name
                            task_name = line.split('TaskName:')[1].strip()
                            if 'ResticRetention_' in task_name:
                                repo_name_sanitized = task_name.split('ResticRetention_')[-1].strip()
                                # Convert back from sanitized name
                                repo_name_actual = repo_name_sanitized.replace('_', ' ')
                                # Check against actual repo names
                                for repo_name in repo_names:
                                    if repo_name.replace(' ', '_') == repo_name_sanitized:
                                        repos_with_tasks.add(repo_name)
            except:
                pass  # If schtasks fails, just don't show indicators
        
        # Update combo box with indicators
        self.retention_repo_combo.blockSignals(True)
        self.retention_repo_combo.clear()
        
        for repo_name in repo_names:
            if repo_name in repos_with_tasks:
                display_name = f"{repo_name} ✓"  # Add checkmark for repos with scheduled tasks
            else:
                display_name = repo_name
            self.retention_repo_combo.addItem(display_name, userData=repo_name)  # Store clean name in userData
        
        # Restore previous selection if it still exists
        if current_repo:
            # Try to find the repo (with or without indicator)
            for i in range(self.retention_repo_combo.count()):
                if self.retention_repo_combo.itemData(i) == current_repo or \
                   self.retention_repo_combo.itemText(i).startswith(current_repo):
                    self.retention_repo_combo.setCurrentIndex(i)
                    break
        
        self.retention_repo_combo.blockSignals(False)
    
    def get_repository_by_name(self, repo_name):
        """Get repository by name with decrypted password"""
        if not repo_name:
            return None, ""
        
        repositories = self.settings_manager.get("repositories")
        repo = next((r for r in repositories if r["name"] == repo_name), None)
        
        if not repo:
            return None, ""
        
        password = ""
        if repo.get("password"):
            try:
                password = self.settings_manager.password_manager.decrypt(repo["password"])
            except:
                self.log(f"Error: Failed to decrypt password for repository '{repo_name}'")
        
        return repo, password
    
    # Snapshot Methods
    def load_snapshots(self):
        """Load snapshots for selected repository"""
        repo_name = self.snapshot_repo_combo.currentText()
        if not repo_name:
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            return
        
        self.log(f"Loading snapshots for repository: {repo_name}")
        hover = getattr(self, "_snapshots_table_hover", None)
        if hover is not None:
            hover._apply(-1)
        self.snapshots_table.setRowCount(0)
        self._loaded_snapshots = []
        update_snapshots_summary(self, [])
        self.snapshot_details.clear()
        
        # Store for later use
        self._current_snapshot_repo = repo
        self._current_snapshot_repo_name = repo_name
        
        # Execute restic snapshots command in background thread
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "snapshots", "--json"]
        
        self._snapshot_worker = ResticWorker(self.restic_cmd, args, env)
        self._snapshot_worker.finished.connect(self._on_snapshots_loaded)
        self._snapshot_worker.start()
    
    def _on_snapshots_loaded(self, success, stdout, stderr):
        """Callback when snapshots are loaded"""
        if success and stdout:
            try:
                snapshots = json.loads(stdout)

                if not isinstance(snapshots, list):
                    snapshots = [snapshots]

                self._loaded_snapshots = snapshots
                populate_snapshots_table(self)

                self.log(f"Loaded {len(snapshots)} snapshot(s) for {self._current_snapshot_repo_name}")

            except json.JSONDecodeError as e:
                self._loaded_snapshots = []
                update_snapshots_summary(self, [])
                self.snapshots_table.setRowCount(0)
                self.log(f"Error parsing snapshots JSON: {str(e)}")
                QMessageBox.warning(self, "Error", f"Failed to parse snapshots data: {str(e)}")
        else:
            self._loaded_snapshots = []
            update_snapshots_summary(self, [])
            self.snapshots_table.setRowCount(0)
            error_msg = stderr if stderr else "Unknown error"
            self.log(f"Error loading snapshots: {error_msg}")
            if error_msg:
                QMessageBox.warning(self, "Error", f"Failed to load snapshots:\n\n{error_msg}")
    
    def show_snapshot_details(self):
        """Show details for selected snapshot"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        snapshot_data = snapshot_data_from_row(self.snapshots_table, row)
        snapshot_id = snapshot_short_id_from_row(self.snapshots_table, row)
        
        if not snapshot_data:
            self.snapshot_details.setText("No snapshot data available")
            return
        
        # Build detailed snapshot information
        details = []
        
        # Basic Information
        details.append("=== Snapshot Information ===\n")
        
        # Full ID
        full_id = snapshot_data.get("id", "N/A")
        short_id = snapshot_data.get("short_id", full_id[:8] if full_id else "N/A")
        details.append(f"ID: {short_id}")
        details.append(f"Full ID: {full_id}\n")
        
        # Time
        time_str = snapshot_data.get("time", "N/A")
        if time_str and time_str != "N/A":
            # Format: 2026-03-13T05:27:50.7033785Z -> more readable format
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                details.append(f"Created: {formatted_time}")
            except:
                details.append(f"Created: {time_str.replace('T', ' ').split('.')[0]}")
        else:
            details.append(f"Created: {time_str}")
        
        # Host
        hostname = snapshot_data.get("hostname", "N/A")
        details.append(f"Hostname: {hostname}")
        
        # Username
        username = snapshot_data.get("username", "N/A")
        if username != "N/A":
            details.append(f"Username: {username}")
        
        # Tags
        tags = snapshot_data.get("tags", [])
        if tags:
            details.append(f"Tags: {', '.join(tags)}")
        else:
            details.append("Tags: None")
        
        # Paths
        paths = snapshot_data.get("paths", [])
        if paths:
            details.append(f"\nPaths ({len(paths)}):")
            for path in paths:
                details.append(f"  â€¢ {path}")
        else:
            details.append("\nPaths: None")
        
        # Excludes (if available)
        excludes = snapshot_data.get("excludes", [])
        if excludes:
            details.append(f"\nExcludes ({len(excludes)}):")
            for exclude in excludes[:5]:  # Show first 5
                details.append(f"  â€¢ {exclude}")
            if len(excludes) > 5:
                details.append(f"  ... and {len(excludes) - 5} more")
        
        # Summary Statistics
        summary = snapshot_data.get("summary", {})
        if summary:
            details.append("\n=== Statistics ===\n")
            
            # Files
            files_new = summary.get("files_new", 0)
            files_changed = summary.get("files_changed", 0)
            files_unmodified = summary.get("files_unmodified", 0)
            total_files_processed = summary.get("total_files_processed", files_new + files_changed + files_unmodified)
            
            details.append(f"Files New: {files_new:,}")
            details.append(f"Files Changed: {files_changed:,}")
            details.append(f"Files Unmodified: {files_unmodified:,}")
            details.append(f"Total Files: {total_files_processed:,}")
            
            # Directories
            dirs_new = summary.get("dirs_new", 0)
            dirs_changed = summary.get("dirs_changed", 0)
            dirs_unmodified = summary.get("dirs_unmodified", 0)
            if dirs_new or dirs_changed or dirs_unmodified:
                details.append(f"\nDirectories New: {dirs_new:,}")
                details.append(f"Directories Changed: {dirs_changed:,}")
                details.append(f"Directories Unmodified: {dirs_unmodified:,}")
            
            # Data sizes
            data_added = summary.get("data_added", 0)
            data_blobs = summary.get("data_blobs", 0)
            tree_blobs = summary.get("tree_blobs", 0)
            
            details.append(f"\nData Added: {self.format_bytes(data_added)}")
            if data_blobs:
                details.append(f"Data Blobs: {data_blobs:,}")
            if tree_blobs:
                details.append(f"Tree Blobs: {tree_blobs:,}")
            
            # Total bytes processed
            total_bytes = summary.get("total_bytes_processed", 0)
            if total_bytes:
                details.append(f"Total Bytes Processed: {self.format_bytes(total_bytes)}")
        
        # Parent snapshot (if available)
        parent = snapshot_data.get("parent")
        if parent:
            details.append(f"\nParent Snapshot: {parent[:8]}")
        
        # Program version (if available)
        program_version = snapshot_data.get("program_version")
        if program_version:
            details.append(f"Restic Version: {program_version}")
        
        # Set the details text
        self.snapshot_details.setPlainText("\n".join(details))
    
    def browse_snapshot_content(self):
        """Browse files in selected snapshot"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        snapshot_id = snapshot_short_id_from_row(self.snapshots_table, row)
        snapshot_data = snapshot_data_from_row(self.snapshots_table, row)
        
        # Get full snapshot ID from stored data
        full_id = snapshot_data.get("id", snapshot_id) if snapshot_data else snapshot_id
        
        # Get repository info
        repo_name = self.snapshot_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", "Repository not found")
            return
        
        snapshot_time = snapshot_data.get("time", "Unknown") if snapshot_data else "Unknown"
        if snapshot_time and snapshot_time != "Unknown":
            snapshot_time = str(snapshot_time).replace("T", " ").split(".")[0].replace("Z", "")
        snapshot_host = snapshot_data.get("hostname", "Unknown") if snapshot_data else "Unknown"
        snapshot_paths = (
            ", ".join(snapshot_data.get("paths", []))
            if snapshot_data and snapshot_data.get("paths")
            else "Unknown"
        )

        dialog = FramedDialog(
            f"Snapshot Content — {snapshot_id}",
            self,
            show_maximize=True,
            show_minimize=False,
        )
        dialog.setMinimumSize(960, 680)
        dialog.body_layout.setContentsMargins(16, 12, 16, 16)
        dialog.body_layout.setSpacing(12)
        layout = dialog.body_layout

        # Compact meta strip
        meta = QFrame()
        meta.setObjectName("browseMetaStrip")
        meta_row = QHBoxLayout(meta)
        meta_row.setContentsMargins(14, 10, 14, 10)
        meta_row.setSpacing(20)

        def _meta_pair(label: str, value: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            lab = QLabel(label)
            lab.setObjectName("browseMetaLabel")
            val = QLabel(value)
            val.setObjectName("browseMetaValue")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val.setWordWrap(True)
            col.addWidget(lab)
            col.addWidget(val)
            return col

        meta_row.addLayout(_meta_pair("Snapshot ID", snapshot_id))
        meta_row.addLayout(_meta_pair("Time", snapshot_time))
        meta_row.addLayout(_meta_pair("Host", snapshot_host))
        paths_col = _meta_pair("Paths", snapshot_paths)
        meta_row.addLayout(paths_col, stretch=1)
        layout.addWidget(meta)

        # File browser card
        browser_card = QFrame()
        browser_card.setObjectName("sectionCard")
        browser_layout = QVBoxLayout(browser_card)
        browser_layout.setContentsMargins(14, 12, 14, 12)
        browser_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        browser_title = QLabel("File Browser")
        browser_title.setObjectName("sectionCardTitle")
        header_layout.addWidget(browser_title)
        header_layout.addStretch(1)

        size_format_label = QLabel("Size")
        size_format_label.setObjectName("pageSubtitle")
        header_layout.addWidget(size_format_label)

        size_format_combo = QComboBox()
        size_format_combo.addItems(["Bytes", "KB", "MB", "GB", "Auto"])
        size_format_combo.setCurrentText("Auto")
        size_format_combo.setFixedWidth(90)
        size_format_combo.setMinimumHeight(28)
        size_format_combo.setToolTip("Choose how file sizes are displayed")
        header_layout.addWidget(size_format_combo)

        def _tool_btn(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setObjectName("dialogSecondary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            header_layout.addWidget(btn)
            return btn

        expand_all_btn = _tool_btn("Expand All")
        collapse_all_btn = _tool_btn("Collapse All")
        refresh_btn = _tool_btn("Refresh")
        browser_layout.addLayout(header_layout)

        search_input = QLineEdit()
        search_input.setObjectName("browseSearch")
        search_input.setPlaceholderText("Search files and folders…")
        search_input.setMinimumHeight(32)
        search_input.setClearButtonEnabled(True)
        browser_layout.addWidget(search_input)

        file_tree = QTreeWidget()
        file_tree.setObjectName("browseFileTree")
        file_tree.setHeaderLabels(["Name", "Type", "Size", "Modified", "Permissions"])
        file_tree.setColumnWidth(0, 420)
        file_tree.setColumnWidth(1, 80)
        file_tree.setColumnWidth(2, 100)
        file_tree.setColumnWidth(3, 150)
        file_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        file_tree.setSortingEnabled(True)
        file_tree.setAlternatingRowColors(False)
        file_tree.setRootIsDecorated(True)
        file_tree.setUniformRowHeights(True)
        file_tree.setAnimated(True)
        file_tree.setIndentation(18)
        file_tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        file_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        browse_header = file_tree.header()
        browse_header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter
        )
        browse_header.setStretchLastSection(True)

        tree_shell = QFrame()
        tree_shell.setObjectName("browseFileTreeShell")
        tree_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tree_shell_layout = QVBoxLayout(tree_shell)
        tree_shell_layout.setContentsMargins(0, 0, 0, 0)
        tree_shell_layout.setSpacing(0)
        tree_shell_layout.addWidget(file_tree)
        browser_layout.addWidget(tree_shell, stretch=1)
        layout.addWidget(browser_card, stretch=1)

        file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_tree.customContextMenuRequested.connect(
            lambda pos, tree=file_tree, dlg=dialog: self._show_snapshot_browse_context_menu(
                tree, pos, dlg
            )
        )

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        status_label = QLabel("Loading files…")
        status_label.setObjectName("pageSubtitle")
        footer.addWidget(status_label, stretch=1)

        copy_path_btn = QPushButton("Copy Selected Path(s)")
        copy_path_btn.setObjectName("dialogSecondary")
        copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_path_btn.clicked.connect(lambda: self._copy_selected_tree_paths(file_tree))
        footer.addWidget(copy_path_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("dialogPrimary")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        # Store all files for filtering
        dialog._all_files = []
        dialog._file_tree_items = {}  # Map path -> QTreeWidgetItem
        
        # Filter function
        def filter_tree():
            """Filter tree view based on search text"""
            search_text = search_input.text().strip().lower()
            
            def check_item_matches(item, text):
                """Check if item or any child matches search text"""
                if not text:
                    return True
                
                # Check item text
                item_text = item.text(0).lower()
                if text in item_text:
                    return True
                
                # Check children
                for i in range(item.childCount()):
                    if check_item_matches(item.child(i), text):
                        return True
                
                return False
            
            # Filter all root items
            visible_count = 0
            for i in range(file_tree.topLevelItemCount()):
                item = file_tree.topLevelItem(i)
                matches = check_item_matches(item, search_text)
                item.setHidden(not matches)
                if matches:
                    visible_count += 1
                    # Expand to show matching children
                    if search_text:
                        item.setExpanded(True)
            
            # Update status
            if search_text:
                status_label.setText(f"Showing {visible_count} matching items")
            else:
                status_label.setText(f"Loaded {len(dialog._all_files)} files and folders")
        
        # Connect search
        search_input.textChanged.connect(filter_tree)
        
        # Connect expand/collapse buttons
        expand_all_btn.clicked.connect(file_tree.expandAll)
        collapse_all_btn.clicked.connect(file_tree.collapseAll)
        
        # Function to update all file sizes in the tree
        def update_tree_sizes():
            """Update all size displays in the tree according to selected format"""
            format_mode = size_format_combo.currentText()
            
            def update_item_size(item):
                """Recursively update item and children sizes"""
                # Update this item's size
                raw_size = item.data(2, Qt.ItemDataRole.UserRole + 1)
                if raw_size:
                    formatted = self.format_size(raw_size, format_mode)
                    item.setText(2, formatted)
                
                # Update children
                for i in range(item.childCount()):
                    update_item_size(item.child(i))
            
            # Update all root items
            for i in range(file_tree.topLevelItemCount()):
                update_item_size(file_tree.topLevelItem(i))
        
        # Connect size format combo
        size_format_combo.currentTextChanged.connect(lambda: update_tree_sizes())
        
        # Store filter function reference
        dialog._filter_files = filter_tree
        
        # Connect refresh button
        refresh_btn.clicked.connect(lambda: self._load_snapshot_content(file_tree, full_id, repo, password, status_label, dialog))
        
        # Store references for the worker callback
        dialog._file_list = file_tree
        dialog._status_label = status_label
        dialog._repo = repo
        dialog._password = password
        dialog._full_id = full_id
        
        # Load snapshot content
        self._load_snapshot_content(file_tree, full_id, repo, password, status_label, dialog)
        
        self.log(f"Browsing content of snapshot {snapshot_id}")
        dialog.exec()
    
    def _load_snapshot_content(self, file_list, snapshot_id, repo, password, status_label=None, dialog=None):
        """Load files from snapshot using restic ls command"""
        if status_label:
            status_label.setText("Loading files...")
        
        file_list.clear()
        loading_item = QTreeWidgetItem(["Loading snapshot contents...", "", "", ""])
        file_list.addTopLevelItem(loading_item)
        
        # Execute restic ls command in background thread
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "ls", snapshot_id, "--long"]
        
        # Create worker
        worker = ResticWorker(self.restic_cmd, args, env)
        worker.finished.connect(
            lambda success, stdout, stderr: self._on_snapshot_content_loaded(
                success, stdout, stderr, file_list, status_label, dialog
            )
        )
        worker.start()
        
        # Store worker reference to prevent garbage collection
        if not hasattr(self, '_content_workers'):
            self._content_workers = []
        self._content_workers.append(worker)
    
    def _on_snapshot_content_loaded(self, success, stdout, stderr, file_tree, status_label=None, dialog=None):
        """Callback when snapshot content is loaded"""
        file_tree.clear()

        try:
            theme_id = themes.resolve_theme_id(self.settings_manager.get("theme"))
            app_theme = themes.get_app_theme(theme_id)
            muted = themes._mix_hex(app_theme.muted, app_theme.text, 0.18)
            folder_color = app_theme.accent
            primary = app_theme.text
        except Exception:
            muted = "#9aa3b2"
            folder_color = "#4A9EFF"
            primary = "#e8eaed"
        muted_color = QColor(muted)
        folder_qcolor = QColor(folder_color)
        primary_qcolor = QColor(primary)
        
        if success and stdout:
            # Parse the output - each line is a file
            lines = stdout.strip().split('\n')
            
            if lines:
                # First pass: collect all paths and find common date prefix to skip
                all_paths = []
                path_data = []  # Store (path, permissions, size, date, time) tuples
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    # Parse restic ls --long output
                    # Format: <permissions> <links> <size> <date> <time> <path>
                    # The path always starts with "/" - find it and extract from there
                    
                    # Find the path by looking for the first '/' character
                    path_start = line.find('/')
                    if path_start == -1:
                        continue
                    
                    # Extract the fields before the path and the path itself
                    fields_part = line[:path_start].strip()
                    path = line[path_start:]  # Starts with /
                    
                    # Split the fields part into components
                    # Restic ls --long format can vary:
                    # Format 1: permissions links size date time (5 fields)
                    # Format 2: permissions links user group size date time (7 fields)
                    # We need to detect which format and parse accordingly
                    
                    fields = fields_part.split()
                    if len(fields) < 5:
                        # Not enough fields, skip this line
                        continue
                    
                    # The date is always in YYYY-MM-DD format, use this to find it
                    date_index = -1
                    for i, field in enumerate(fields):
                        if len(field) == 10 and field.count('-') == 2:
                            # Looks like a date (YYYY-MM-DD)
                            try:
                                # Verify it's a valid date format
                                parts = field.split('-')
                                if len(parts[0]) == 4 and parts[0].isdigit():
                                    date_index = i
                                    break
                            except:
                                pass
                    
                    if date_index < 2:
                        # Date not found in a valid position, skip
                        continue
                    
                    # Now we know where the date is, we can extract the other fields
                    permissions = fields[0]
                    size = fields[date_index - 1]  # Size is just before the date
                    date = fields[date_index]
                    time_str = fields[date_index + 1] if date_index + 1 < len(fields) else ""
                    
                    # Clean up time string (remove microseconds if present)
                    if time_str and '.' in time_str:
                        time_str = time_str.split('.')[0]
                    
                    if not path:
                        continue
                    
                    # Remove leading slash
                    path = path.lstrip('/')
                    all_paths.append(path)
                    path_data.append((path, permissions, size, date, time_str))
                
                # Detect and remove common date/timestamp prefix
                date_prefix_levels = self._detect_date_prefix(all_paths)
                
                # Build tree structure
                root_items = {}
                file_count = 0
                original_path_map = {}  # Map stripped path to original full path
                
                for path, permissions, size, date, time_str in path_data:
                    # Determine if directory
                    is_dir = permissions.startswith('d')
                    
                    # Store original path
                    original_path = path
                    
                    # Split path into components
                    path_parts = path.split('/')
                    
                    # Skip date prefix levels
                    if date_prefix_levels > 0 and len(path_parts) > date_prefix_levels:
                        path_parts = path_parts[date_prefix_levels:]
                        # If nothing left after skipping, continue
                        if not path_parts:
                            continue
                    
                    # Build tree structure
                    current_path = ""
                    current_original_path_parts = original_path.split('/')
                    parent = None
                    
                    for i, part in enumerate(path_parts):
                        if not part:
                            continue
                        
                        # Build full path up to this point (stripped version)
                        if current_path:
                            current_path += "/" + part
                        else:
                            current_path = part
                        
                        # Build corresponding original path
                        original_index = date_prefix_levels + i
                        original_path_up_to_here = "/".join(current_original_path_parts[:original_index + 1])
                        
                        # Check if this item already exists
                        if current_path not in root_items:
                            # Determine item type
                            is_last = (i == len(path_parts) - 1)
                            item_type = "File" if (is_last and not is_dir) else "Folder"
                            
                            # Create tree item
                            item = QTreeWidgetItem()
                            item.setText(0, part)  # Name
                            item.setText(1, item_type)  # Type
                            
                            # Add size, date, permissions for files
                            if is_last:
                                # Store raw size in UserRole+1, formatted size in column 2
                                item.setData(2, Qt.ItemDataRole.UserRole + 1, size)  # Raw size in bytes
                                item.setText(2, self.format_size(size, "Auto") if not is_dir else "")
                                # Format modified date/time nicely
                                item.setText(3, f"{date} {time_str}")
                                item.setData(3, Qt.ItemDataRole.UserRole, f"{date} {time_str}")  # Store for sorting
                                item.setText(4, permissions)
                                if not is_dir:
                                    file_count += 1
                            else:
                                item.setData(2, Qt.ItemDataRole.UserRole + 1, "0")
                                item.setText(2, "")
                                item.setText(3, "")
                                item.setText(4, "")
                            
                            # Set icon based on type
                            if item_type == "Folder":
                                item.setForeground(0, folder_qcolor)
                            else:
                                item.setForeground(0, primary_qcolor)
                            for col in (1, 2, 3, 4):
                                item.setForeground(col, muted_color)
                            
                            # Store original full path as data (for copying)
                            item.setData(0, Qt.ItemDataRole.UserRole, "/" + original_path_up_to_here)
                            
                            # Add to parent or root
                            if parent:
                                parent.addChild(item)
                            else:
                                file_tree.addTopLevelItem(item)
                            
                            # Store item for future reference
                            root_items[current_path] = item
                            parent = item
                        else:
                            # Item exists, use it as parent for next level
                            parent = root_items[current_path]
                
                # Store all files in dialog for filtering
                if dialog:
                    dialog._all_files = [line for line in lines if line.strip()]
                    dialog._file_tree_items = root_items
                    dialog._date_prefix_levels = date_prefix_levels
                
                # Auto-expand single-child folders to skip unnecessary nesting
                self._auto_expand_single_children(file_tree)
                
                if status_label:
                    status_msg = f"Loaded {file_count} files in {len(root_items)} total items"
                    if date_prefix_levels > 0:
                        status_msg += f" (skipped {date_prefix_levels} date folder level{'s' if date_prefix_levels > 1 else ''})"
                    status_label.setText(status_msg)
                
                self.log(f"Loaded {file_count} files from snapshot (skipped {date_prefix_levels} date folder levels)")
            else:
                # No files
                item = QTreeWidgetItem()
                item.setText(0, "(No files in snapshot)")
                file_tree.addTopLevelItem(item)
                if status_label:
                    status_label.setText("No files found")
        else:
            error_msg = stderr if stderr else "Unknown error"
            item = QTreeWidgetItem()
            item.setText(0, f"Error loading snapshot contents: {error_msg}")
            file_tree.addTopLevelItem(item)
            if status_label:
                status_label.setText("Error loading files")
            self.log(f"Error loading snapshot content: {error_msg}")
    
    def _detect_date_prefix(self, paths):
        """
        Detect how many leading path levels are date/timestamp folders to skip
        
        Date folders typically look like:
        - 2026-03-13 11:10:22
        - 2025-05-01 04:54:48
        - YYYY-MM-DD HH:MM:SS pattern
        
        Returns the number of path levels to skip
        """
        if not paths:
            return 0
        
        import re
        
        # Pattern to match date/timestamp folders
        # Matches: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, timestamps, etc.
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'^\d{2}:\d{2}:\d{2}',  # HH:MM:SS
            r'^\d{4}$',              # Year only (YYYY)
            r'^\d{2}-\d{2}-\d{2}',  # YY-MM-DD
        ]
        
        def is_date_component(component):
            """Check if a path component looks like a date/time"""
            for pattern in date_patterns:
                if re.match(pattern, component):
                    return True
            return False
        
        # Sample first 100 paths to find common date prefix
        sample_paths = paths[:100] if len(paths) > 100 else paths
        
        # Find minimum depth across all paths
        min_depth = min(len(p.split('/')) for p in sample_paths if p)
        
        if min_depth == 0:
            return 0
        
        # Check each level to see if it's consistently a date folder
        skip_levels = 0
        
        for level in range(min_depth):
            components_at_level = set()
            date_count = 0
            total_count = 0
            
            for path in sample_paths:
                parts = path.split('/')
                if len(parts) > level:
                    component = parts[level]
                    components_at_level.add(component)
                    total_count += 1
                    if is_date_component(component):
                        date_count += 1
            
            # If most components at this level are dates, skip it
            # Also check if there are multiple different date values (indicates date folders)
            if total_count > 0:
                date_ratio = date_count / total_count
                # Skip if >80% look like dates, or if there are many different date values
                if date_ratio > 0.8 or (date_count > 0 and len(components_at_level) > 5):
                    skip_levels = level + 1
                else:
                    # Stop at first non-date level
                    break
        
        return skip_levels
    
    def _auto_expand_single_children(self, tree_widget, max_depth=10):
        """
        Auto-expand folders that only have one child to skip unnecessary nesting
        This helps bypass date folders, drive letters, etc. to show meaningful content faster
        
        Args:
            tree_widget: The QTreeWidget to process
            max_depth: Maximum depth to auto-expand (prevents infinite expansion)
        """
        def expand_single_child_recursively(item, depth=0):
            """Recursively expand items that have exactly one child"""
            if depth >= max_depth:
                return
            
            # Only expand folders
            if item.text(1) != "Folder":
                return
            
            # If this item has exactly one child and it's a folder, expand it
            if item.childCount() == 1:
                child = item.child(0)
                item.setExpanded(True)
                # Recursively expand the child if it also has a single child
                expand_single_child_recursively(child, depth + 1)
            # If multiple children, stop expanding but still process them
            # to handle nested single-child chains
            elif item.childCount() > 1:
                # For each child, if it's a single-child chain, expand it too
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.childCount() == 1 and child.text(1) == "Folder":
                        expand_single_child_recursively(child, depth + 1)
        
        # Process all top-level items
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            expand_single_child_recursively(item)
    
    def _show_snapshot_browse_context_menu(self, file_tree, pos, dialog):
        """Right-click menu for snapshot content browser: restore, copy, expand/collapse."""
        item = file_tree.itemAt(pos)
        if item is not None and not item.isSelected():
            file_tree.clearSelection()
            item.setSelected(True)
            file_tree.setCurrentItem(item)

        selected = file_tree.selectedItems()
        has_selection = bool(selected)
        can_expand = any(it.childCount() > 0 for it in selected) if selected else False

        menu = RoundedMenu(file_tree)
        restore_act = menu.addAction("Restore selected…")
        restore_act.setEnabled(has_selection)
        restore_orig_act = menu.addAction("Restore to original location…")
        restore_orig_act.setEnabled(has_selection)
        copy_act = menu.addAction("Copy path(s)")
        copy_act.setEnabled(has_selection)
        menu.addSeparator()
        expand_act = menu.addAction("Expand")
        expand_act.setEnabled(can_expand)
        collapse_act = menu.addAction("Collapse")
        collapse_act.setEnabled(can_expand)

        chosen = menu.exec(file_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen is restore_act:
            self._restore_selected_from_snapshot_browser(file_tree, dialog, to_original=False)
        elif chosen is restore_orig_act:
            self._restore_selected_from_snapshot_browser(file_tree, dialog, to_original=True)
        elif chosen is copy_act:
            self._copy_selected_tree_paths(file_tree, quiet=True)
        elif chosen is expand_act:
            for it in selected:
                it.setExpanded(True)
        elif chosen is collapse_act:
            for it in selected:
                it.setExpanded(False)

    def _paths_from_tree_selection(self, file_tree) -> list[str]:
        """Unique snapshot paths from selected tree items."""
        paths: list[str] = []
        seen = set()
        for item in file_tree.selectedItems():
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if not path:
                continue
            path = str(path)
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
        return paths

    def _restore_selected_from_snapshot_browser(self, file_tree, dialog, *, to_original: bool = False):
        """Restore selected paths from the Snapshot Content browse dialog."""
        paths = self._paths_from_tree_selection(file_tree)
        if not paths:
            QMessageBox.warning(
                dialog,
                "No Selection",
                "Please select files or folders to restore.",
            )
            return

        snapshot_id = getattr(dialog, "_full_id", None)
        repo = getattr(dialog, "_repo", None)
        password = getattr(dialog, "_password", "") or ""
        if not snapshot_id or not repo:
            QMessageBox.warning(dialog, "Error", "Snapshot or repository context is missing.")
            return

        self._restore_paths_from_snapshot(
            paths,
            snapshot_id=snapshot_id,
            repo=repo,
            password=password,
            parent_dialog=dialog,
            to_original=to_original,
        )

    def _move_restored_files_to_original(self, temp_target: str) -> list[str]:
        """
        Move files from a temp restore target into their original absolute paths.

        Restic restores Windows paths under the target as ``D\\folder\\file``;
        this converts that back to ``D:\\folder\\file``.
        """
        moved_files: list[str] = []
        if not temp_target or not os.path.isdir(temp_target):
            return moved_files

        for root, _dirs, files in os.walk(temp_target):
            for filename in files:
                src_file = os.path.join(root, filename)
                rel_path = os.path.relpath(src_file, temp_target)

                if sys.platform == "win32":
                    parts = rel_path.split(os.sep)
                    if len(parts) > 0 and len(parts[0]) == 1 and parts[0].isalpha():
                        drive = parts[0] + ":\\"
                        dest_path = os.path.join(drive, *parts[1:]) if len(parts) > 1 else drive
                    else:
                        self.log(f"Warning: Could not parse drive from path: {rel_path}")
                        continue
                else:
                    dest_path = os.path.join("/", rel_path)

                dest_dir = os.path.dirname(dest_path)
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                shutil.move(src_file, dest_path)
                moved_files.append(dest_path)
                self.log(f"Moved: {dest_path}")

        try:
            shutil.rmtree(temp_target)
            self.log(f"Cleaned up temp directory: {temp_target}")
        except Exception as e:
            self.log(f"Warning: Could not remove temp directory: {e}")

        return moved_files

    def _restore_paths_from_snapshot(
        self,
        paths_to_restore: list[str],
        *,
        snapshot_id: str,
        repo: dict,
        password: str,
        parent_dialog,
        to_original: bool = False,
    ):
        """Restore selected snapshot paths to a chosen folder or original locations."""
        if not paths_to_restore:
            return

        preview = "\n".join([f"  • {p}" for p in paths_to_restore[:10]])
        if len(paths_to_restore) > 10:
            preview += f"\n  … and {len(paths_to_restore) - 10} more"

        if to_original:
            temp_root = (
                self.settings_manager.get("temp_restore_path")
                or os.path.join(tempfile.gettempdir(), "restic_restore")
            )
            target_dir = os.path.join(
                temp_root,
                f"browse_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(
                    parent_dialog,
                    "Temp Path Error",
                    f"Could not create temporary restore folder:\n{target_dir}\n\n{e}",
                )
                return

            result = QMessageBox.warning(
                parent_dialog,
                "Confirm Restore to Original",
                f"Restore {len(paths_to_restore)} item(s) to their ORIGINAL locations?\n\n"
                "This can overwrite existing files.\n\n"
                f"Items:\n{preview}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                try:
                    os.rmdir(target_dir)
                except Exception:
                    pass
                return
            dest_label = "original locations"
        else:
            target_dir = QFileDialog.getExistingDirectory(
                parent_dialog,
                "Select Restore Target Directory",
                os.path.expanduser("~"),
            )
            if not target_dir:
                return

            result = QMessageBox.question(
                parent_dialog,
                "Confirm Restore",
                f"Restore {len(paths_to_restore)} item(s) to:\n{target_dir}\n\n"
                f"Items:\n{preview}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return
            dest_label = target_dir

        short_id = str(snapshot_id)[:8]
        self.log(
            f"Restoring {len(paths_to_restore)} item(s) from snapshot {short_id} "
            f"({'to original via ' + target_dir if to_original else 'to ' + target_dir})"
        )

        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "restore", snapshot_id, "--target", target_dir]
        for path in paths_to_restore:
            include = str(path).strip().lstrip("/")
            if include:
                args.extend(["--include", include])

        progress, progress_label, _ = make_framed_progress_dialog(
            parent_dialog,
            "Restoring Files",
            f"Restoring {len(paths_to_restore)} item(s)…\nPlease wait.",
            modal=True,
            min_width=420,
        )
        progress.show()
        QApplication.processEvents()

        worker = ResticWorker(self.restic_cmd, args, env, timeout=3600, use_progress=True)

        def _on_progress(msg: str, lbl=progress_label) -> None:
            text = (msg or "").strip()
            if text:
                lbl.setText(f"Restoring {len(paths_to_restore)} item(s)…\n{text[:160]}")

        def _on_done(success, stdout, stderr, dlg=progress, temp=target_dir, original=to_original):
            try:
                dlg.close()
                dlg.deleteLater()
            except Exception:
                pass
            if not success:
                err = (stderr or "Unknown error").strip()
                QMessageBox.warning(
                    parent_dialog,
                    "Restore Failed",
                    f"Failed to restore files:\n\n{err[:500]}",
                )
                self.log(f"Restore failed: {err}")
                return

            if original:
                try:
                    QApplication.processEvents()
                    moved = self._move_restored_files_to_original(temp)
                except Exception as e:
                    self.log(f"Error moving files to original locations: {e}")
                    QMessageBox.warning(
                        parent_dialog,
                        "Move Error",
                        f"Files were restored to a temp folder but could not be moved:\n{e}\n\n"
                        f"Files are in:\n{temp}",
                    )
                    return

                if moved:
                    preview_moved = "\n".join(moved[:5])
                    if len(moved) > 5:
                        preview_moved += f"\n… and {len(moved) - 5} more"
                    QMessageBox.information(
                        parent_dialog,
                        "Restore Complete",
                        f"Successfully restored {len(moved)} file(s) to original locations!\n\n"
                        f"{preview_moved}",
                    )
                    self.log(f"Restore to original completed: {len(moved)} file(s)")
                    show_notification(
                        title="Restore Complete",
                        message=f"Restored {len(moved)} file(s) to original locations.",
                        icon_type="success",
                        duration="short",
                    )
                else:
                    QMessageBox.warning(
                        parent_dialog,
                        "Restore Issue",
                        "Restore completed but no files were found to move to original locations.",
                    )
                return

            QMessageBox.information(
                parent_dialog,
                "Restore Complete",
                f"Successfully restored {len(paths_to_restore)} item(s) to:\n{dest_label}",
            )
            self.log(f"Restore completed: {len(paths_to_restore)} item(s) → {dest_label}")
            show_notification(
                title="Restore Complete",
                message=f"Restored {len(paths_to_restore)} item(s).",
                icon_type="success",
                duration="short",
            )

        worker.progress.connect(_on_progress)
        worker.finished.connect(_on_done)
        worker.start()
        parent_dialog._restore_worker = worker
        self._browse_restore_worker = worker  # prevent GC if parent drops ref

    def _copy_selected_tree_paths(self, file_tree, quiet: bool = False):
        """Copy selected file paths from tree to clipboard"""
        selected_items = file_tree.selectedItems()
        if not selected_items:
            return
        
        # Get paths from selected items
        paths = []
        for item in selected_items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths.append(path)
        
        if paths:
            clipboard_text = "\n".join(paths)
            QApplication.clipboard().setText(clipboard_text)
            self.log(f"Copied {len(paths)} path(s) to clipboard")
            if not quiet:
                QMessageBox.information(None, "Copied", f"Copied {len(paths)} path(s) to clipboard")
    
    def _copy_selected_paths(self, file_list):
        """Copy selected file paths to clipboard (legacy list version)"""
        selected_items = file_list.selectedItems()
        if not selected_items:
            return
        
        # Extract paths from the selected items
        paths = []
        for item in selected_items:
            text = item.text()
            # The format from 'ls --long' is typically: <permissions> <size> <timestamp> <path>
            # The path always starts with '/' - find it
            path_start = text.find('/')
            if path_start != -1:
                path = text[path_start:]
                paths.append(path)
            else:
                paths.append(text)
        
        if paths:
            QApplication.clipboard().setText('\n'.join(paths))
            self.log(f"Copied {len(paths)} path(s) to clipboard")
    
    def diff_snapshots(self):
        """Show diff between selected snapshot and previous"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        snapshot_data = snapshot_data_from_row(self.snapshots_table, row)
        snapshot_id = snapshot_short_id_from_row(self.snapshots_table, row)
        snapshots = getattr(self, "_loaded_snapshots", []) or []
        prev_snapshot_id = snapshot_previous_short_id(snapshots, snapshot_data) if snapshot_data else ""
        if not prev_snapshot_id:
            QMessageBox.information(self, "No Previous", "This is the oldest snapshot, no previous snapshot to compare")
            return
        
        # Get repository info
        if not hasattr(self, '_current_snapshot_repo'):
            QMessageBox.warning(self, "Error", "No repository selected")
            return
        
        repo = self._current_snapshot_repo
        repo_name = self._current_snapshot_repo_name
        repo_full, password = self.get_repository_by_name(repo_name)
        
        dialog = FramedDialog(
            f"Diff — {snapshot_id} vs {prev_snapshot_id}",
            self,
            show_maximize=True,
            show_minimize=False,
        )
        dialog.setMinimumSize(900, 640)
        dialog.body_layout.setContentsMargins(16, 12, 16, 16)
        dialog.body_layout.setSpacing(12)
        layout = dialog.body_layout

        # Meta strip
        meta = QFrame()
        meta.setObjectName("browseMetaStrip")
        meta_row = QHBoxLayout(meta)
        meta_row.setContentsMargins(14, 10, 14, 10)
        meta_row.setSpacing(20)

        def _meta_pair(label: str, value: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            lab = QLabel(label)
            lab.setObjectName("browseMetaLabel")
            val = QLabel(value)
            val.setObjectName("browseMetaValue")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            col.addWidget(lab)
            col.addWidget(val)
            return col

        meta_row.addLayout(_meta_pair("Newer", snapshot_id))
        meta_row.addLayout(_meta_pair("Older", prev_snapshot_id))
        meta_row.addLayout(_meta_pair("Repository", repo_name or "—"), stretch=1)
        layout.addWidget(meta)

        # Diff output card
        output_card = QFrame()
        output_card.setObjectName("sectionCard")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(14, 12, 14, 12)
        output_layout.setSpacing(8)

        output_title = QLabel("Changes")
        output_title.setObjectName("sectionCardTitle")
        output_layout.addWidget(output_title)

        diff_output = QPlainTextEdit()
        diff_output.setObjectName("diffOutput")
        diff_output.setReadOnly(True)
        diff_output.setPlainText("Loading diff…\n")
        diff_output.setFont(QFont("Consolas", 10))
        diff_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        output_layout.addWidget(diff_output, stretch=1)
        layout.addWidget(output_card, stretch=1)

        # Footer: stats + close
        footer = QHBoxLayout()
        footer.setSpacing(16)

        added_label = QLabel("Added: 0")
        added_label.setObjectName("diffStatAdded")
        modified_label = QLabel("Modified: 0")
        modified_label.setObjectName("diffStatModified")
        removed_label = QLabel("Removed: 0")
        removed_label.setObjectName("diffStatRemoved")
        footer.addWidget(added_label)
        footer.addWidget(modified_label)
        footer.addWidget(removed_label)
        footer.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("dialogPrimary")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        dialog.show()
        QApplication.processEvents()
        
        # Execute diff command in background
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo_full["path"], "diff", prev_snapshot_id, snapshot_id]
        
        self.log(f"Running diff: {prev_snapshot_id} -> {snapshot_id}")
        
        diff_worker = ResticWorker(self.restic_cmd, args, env, timeout=300)
        diff_worker.finished.connect(lambda success, stdout, stderr: 
                                     self._on_diff_completed(success, stdout, stderr, 
                                                            diff_output, added_label, 
                                                            modified_label, removed_label))
        diff_worker.start()
        
        # Store reference to prevent garbage collection
        self._diff_worker = diff_worker
        
        dialog.exec()
    
    def _on_diff_completed(self, success, stdout, stderr, output_widget, added_label, modified_label, removed_label):
        """Callback when diff command completes"""
        if success or stdout:
            output = stdout if stdout else stderr
            output_widget.setPlainText(output)
            
            # Parse statistics
            added_count = output.count('\n+')
            modified_count = output.count('\nM')
            removed_count = output.count('\n-')
            
            # Try to extract from restic output if available
            lines = output.split('\n')
            for line in lines:
                if 'Added' in line and 'Files' in line:
                    try:
                        added_count = int(line.split(':')[1].strip().split()[0])
                    except:
                        pass
                elif 'Modified' in line and 'Files' in line:
                    try:
                        modified_count = int(line.split(':')[1].strip().split()[0])
                    except:
                        pass
                elif 'Removed' in line and 'Files' in line:
                    try:
                        removed_count = int(line.split(':')[1].strip().split()[0])
                    except:
                        pass
            
            added_label.setText(f"Added: {added_count}")
            modified_label.setText(f"Modified: {modified_count}")
            removed_label.setText(f"Removed: {removed_count}")
        else:
            output_widget.setPlainText(f"Error running diff:\n{stderr}")
            self.log(f"Diff failed: {stderr}")
    
    def forget_snapshot(self):
        """Forget (delete) selected snapshot"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        snapshot_id = snapshot_short_id_from_row(self.snapshots_table, row)
        snapshot_data = snapshot_data_from_row(self.snapshots_table, row)
        
        # Get full snapshot ID from stored data
        full_id = snapshot_data.get("id", snapshot_id) if snapshot_data else snapshot_id
        
        # Get paths / time for display
        paths = snapshot_data.get("paths", []) if snapshot_data else []
        paths_str = ", ".join(paths) if paths else "Unknown"
        snapshot_time = snapshot_data.get("time", "Unknown") if snapshot_data else "Unknown"
        if snapshot_time and snapshot_time != "Unknown":
            snapshot_time = str(snapshot_time).replace("T", " ").split(".")[0].replace("Z", "")
        repo_name = self.snapshot_repo_combo.currentText()

        dialog = FramedDialog(
            "Forget Snapshot",
            self,
            show_maximize=False,
            show_minimize=False,
        )
        dialog.setMinimumWidth(520)
        dialog.body_layout.setContentsMargins(16, 12, 16, 16)
        dialog.body_layout.setSpacing(12)
        layout = dialog.body_layout

        title = QLabel("Forget this snapshot?")
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        subtitle = QLabel(
            "This marks the snapshot for deletion. Run Prune Repository afterward to free disk space."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        meta = QFrame()
        meta.setObjectName("browseMetaStrip")
        meta_row = QHBoxLayout(meta)
        meta_row.setContentsMargins(14, 10, 14, 10)
        meta_row.setSpacing(20)

        def _meta_pair(label: str, value: str, stretch: int = 0) -> None:
            col = QVBoxLayout()
            col.setSpacing(2)
            lab = QLabel(label)
            lab.setObjectName("browseMetaLabel")
            val = QLabel(value)
            val.setObjectName("browseMetaValue")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            col.addWidget(lab)
            col.addWidget(val)
            meta_row.addLayout(col, stretch)

        _meta_pair("Snapshot ID", snapshot_id)
        _meta_pair("Time", snapshot_time)
        _meta_pair("Repository", repo_name or "—")
        _meta_pair("Paths", paths_str, stretch=1)
        layout.addWidget(meta)

        note = QLabel("This cannot be undone without a prune recovery from remaining data.")
        note.setObjectName("copyNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)
        footer.addWidget(cancel_btn)
        forget_btn = QPushButton("Forget")
        forget_btn.setObjectName("dangerBtn")
        forget_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        forget_btn.clicked.connect(dialog.accept)
        footer.addWidget(forget_btn)
        layout.addLayout(footer)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        repo, password = self.get_repository_by_name(repo_name)
        
        if not repo:
            QMessageBox.warning(self, "Error", "Repository not found")
            return
        
        self.log(f"Forgetting snapshot {snapshot_id}...")
        
        # Execute restic forget command
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "forget", full_id]
        
        self._forget_worker = ResticWorker(self.restic_cmd, args, env)
        self._forget_worker.finished.connect(lambda success, stdout, stderr: self._on_forget_complete(success, stdout, stderr, snapshot_id))
        self._forget_worker.start()
    
    def copy_snapshot_to_repository(self):
        """Copy selected snapshot to another repository"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        snapshot_id = snapshot_short_id_from_row(self.snapshots_table, row)
        snapshot_data = snapshot_data_from_row(self.snapshots_table, row)
        
        # Get full snapshot ID from stored data
        full_id = snapshot_data.get("id", snapshot_id) if snapshot_data else snapshot_id
        
        # Get current repository
        source_repo_name = self.snapshot_repo_combo.currentText()
        source_repo, source_password = self.get_repository_by_name(source_repo_name)
        
        if not source_repo:
            QMessageBox.warning(self, "Error", "Source repository not found")
            return
        
        # Get snapshot info for display
        paths = snapshot_data.get("paths", []) if snapshot_data else []
        paths_str = ", ".join(paths) if paths else "Unknown"
        snapshot_time = snapshot_data.get("time", "Unknown") if snapshot_data else "Unknown"
        if snapshot_time and snapshot_time != "Unknown":
            snapshot_time = str(snapshot_time).replace("T", " ").split(".")[0].replace("Z", "")

        repositories = self.settings_manager.get("repositories") or []
        dest_names = [r["name"] for r in repositories if r.get("name") != source_repo_name]
        if not dest_names:
            QMessageBox.warning(
                self,
                "No Destination",
                "No other repositories available. Please add another repository first.",
            )
            return

        dialog = FramedDialog(
            "Copy Snapshot to Repository",
            self,
            show_maximize=False,
            show_minimize=False,
        )
        dialog.setMinimumWidth(560)
        dialog.body_layout.setContentsMargins(16, 12, 16, 16)
        dialog.body_layout.setSpacing(12)
        layout = dialog.body_layout

        # Snapshot meta strip
        meta = QFrame()
        meta.setObjectName("browseMetaStrip")
        meta_row = QHBoxLayout(meta)
        meta_row.setContentsMargins(14, 10, 14, 10)
        meta_row.setSpacing(20)

        def _meta_pair(label: str, value: str, stretch: int = 0) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            lab = QLabel(label)
            lab.setObjectName("browseMetaLabel")
            val = QLabel(value)
            val.setObjectName("browseMetaValue")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            col.addWidget(lab)
            col.addWidget(val)
            meta_row.addLayout(col, stretch)
            return col

        _meta_pair("Snapshot ID", snapshot_id)
        _meta_pair("Time", snapshot_time)
        _meta_pair("Source", source_repo_name)
        _meta_pair("Paths", paths_str, stretch=1)
        layout.addWidget(meta)

        # Options card
        options_card = QFrame()
        options_card.setObjectName("sectionCard")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(14, 12, 14, 12)
        options_layout.setSpacing(12)

        options_title = QLabel("Copy Options")
        options_title.setObjectName("sectionCardTitle")
        options_layout.addWidget(options_title)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        try:
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        except Exception:
            pass

        dest_combo = QComboBox()
        dest_combo.setMinimumHeight(32)
        for name in dest_names:
            dest_combo.addItem(name)
        form.addRow("Destination", dest_combo)

        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(10)
        timeout_spin = QSpinBox()
        timeout_spin.setMinimum(0)
        timeout_spin.setMaximum(24)
        timeout_spin.setValue(6)
        timeout_spin.setSuffix(" hours")
        timeout_spin.setMinimumHeight(32)
        timeout_spin.setFixedWidth(120)
        timeout_hint = QLabel("0 = no timeout (recommended for large snapshots)")
        timeout_hint.setObjectName("pageSubtitle")
        timeout_row.addWidget(timeout_spin)
        timeout_row.addWidget(timeout_hint, stretch=1)
        form.addRow("Timeout", timeout_row)
        options_layout.addLayout(form)

        delete_source_check = QCheckBox("Delete from source after successful copy")
        delete_source_check.setToolTip(
            "Remove the snapshot from the source repository after a successful copy"
        )
        options_layout.addWidget(delete_source_check)

        note = QLabel(
            "Large snapshots may take several hours. Progress is shown in real time during the copy."
        )
        note.setObjectName("copyNote")
        note.setWordWrap(True)
        options_layout.addWidget(note)
        layout.addWidget(options_card)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)
        footer.addWidget(cancel_btn)
        ok_btn = QPushButton("Copy")
        ok_btn.setObjectName("dialogPrimary")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(dialog.accept)
        footer.addWidget(ok_btn)
        layout.addLayout(footer)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dest_repo_name = dest_combo.currentText()
            dest_repo, dest_password = self.get_repository_by_name(dest_repo_name)
            
            if not dest_repo:
                QMessageBox.warning(self, "Error", "Destination repository not found")
                return
            
            delete_after_copy = delete_source_check.isChecked()
            copy_timeout = timeout_spin.value() * 3600  # Convert hours to seconds
            
            self.log(f"Copying snapshot {snapshot_id} from '{source_repo_name}' to '{dest_repo_name}'...")
            if copy_timeout > 0:
                self.log(f"Timeout: {timeout_spin.value()} hours ({copy_timeout} seconds)")
            else:
                self.log(f"Timeout: No limit")
            
            # Show progress dialog
            progress_dialog = QDialog(self)
            progress_dialog.setWindowTitle("Copying Snapshot")
            progress_dialog.setModal(False)  # Non-modal so user can access main window
            progress_dialog.setMinimumWidth(600)
            progress_dialog.setMinimumHeight(400)
            
            progress_layout = QVBoxLayout()
            progress_dialog.setLayout(progress_layout)
            
            info_label = QLabel(
                f"Copying snapshot {snapshot_id}\n"
                f"From: {source_repo_name}\n"
                f"To: {dest_repo_name}\n\n"
                f"This may take a while for large snapshots..."
            )
            progress_layout.addWidget(info_label)
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 0)  # Indeterminate progress
            progress_layout.addWidget(progress_bar)
            
            status_label = QLabel("Starting copy operation...")
            progress_layout.addWidget(status_label)
            
            output_text = QPlainTextEdit()
            output_text.setReadOnly(True)
            output_text.setPlaceholderText("Real-time output will appear here...")
            progress_layout.addWidget(output_text)
            
            # Cancel button
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setEnabled(False)  # Disable for now - copy can't be easily cancelled
            cancel_btn.setCursor(Qt.CursorShape.ForbiddenCursor)
            cancel_btn.setToolTip("Copy operation cannot be cancelled once started")
            progress_layout.addWidget(cancel_btn)
            
            # Store references
            self._copy_progress_dialog = progress_dialog
            self._copy_output_text = output_text
            self._copy_status_label = status_label
            
            progress_dialog.show()
            QApplication.processEvents()
            
            # Execute restic copy command with progress
            env = {
                "RESTIC_PASSWORD": source_password if source_password else "",
                "RESTIC_PASSWORD2": dest_password if dest_password else ""
            }
            args = [
                "-r", source_repo["path"],
                "copy",
                "--repo2", dest_repo["path"],
                full_id
            ]
            
            self._copy_worker = ResticWorker(self.restic_cmd, args, env, timeout=copy_timeout, use_progress=False)
            self._copy_worker.progress.connect(self._on_copy_progress)
            self._copy_worker.finished.connect(
                lambda success, stdout, stderr: self._on_copy_complete(
                    success, stdout, stderr, snapshot_id, dest_repo_name, 
                    delete_after_copy, source_repo, source_password, full_id,
                    progress_dialog
                )
            )
            self._copy_worker.start()
    
    def _on_copy_progress(self, line):
        """Handle progress output from copy operation"""
        if hasattr(self, '_copy_output_text'):
            self._copy_output_text.appendPlainText(line)
            # Auto-scroll to bottom
            scrollbar = self._copy_output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        if hasattr(self, '_copy_status_label'):
            # Update status with last non-empty line
            if line.strip():
                self._copy_status_label.setText(f"Status: {line.strip()[:100]}...")  # First 100 chars
    
    def _on_copy_complete(self, success, stdout, stderr, snapshot_id, dest_repo_name, 
                          delete_after_copy, source_repo, source_password, full_id, progress_dialog):
        """Callback when snapshot copy completes"""
        # Add final output to display
        if hasattr(self, '_copy_output_text'):
            if stdout:
                self._copy_output_text.appendPlainText("\n=== STDOUT ===")
                self._copy_output_text.appendPlainText(stdout)
            if stderr:
                self._copy_output_text.appendPlainText("\n=== STDERR ===")
                self._copy_output_text.appendPlainText(stderr)
        
        # Update status
        if hasattr(self, '_copy_status_label'):
            if success:
                self._copy_status_label.setText("✓ Copy completed successfully!")
                self._copy_status_label.setStyleSheet("color: green;")
            else:
                self._copy_status_label.setText("✗ Copy failed!")
                self._copy_status_label.setStyleSheet("color: red;")
        
        # Wait a moment for user to see final status
        QApplication.processEvents()
        
        # Keep dialog open for a moment if successful, close immediately if failed
        if not success:
            progress_dialog.close()
        
        if success:
            message = f"Snapshot {snapshot_id} successfully copied to '{dest_repo_name}'!"
            
            if delete_after_copy:
                # Delete from source repository
                reply = QMessageBox.question(
                    self, "Delete from Source?",
                    f"Snapshot copied successfully!\n\n"
                    f"Do you want to delete it from the source repository now?\n\n"
                    f"Note: You may want to verify the copy first before deleting.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.log(f"Deleting snapshot {snapshot_id} from source repository...")
                    env = {"RESTIC_PASSWORD": source_password if source_password else ""}
                    args = ["-r", source_repo["path"], "forget", full_id]
                    
                    success_delete, stdout_del, stderr_del = self.restic_cmd.run(args, env)
                    
                    if success_delete:
                        message += f"\n\nSnapshot also deleted from source repository."
                        self.log(f"Snapshot {snapshot_id} deleted from source")
                        self.load_snapshots()  # Refresh list
                    else:
                        message += f"\n\nWarning: Failed to delete from source: {stderr_del}"
                        self.log(f"Failed to delete snapshot from source: {stderr_del}")
            
            progress_dialog.close()
            QMessageBox.information(self, "Copy Complete", message)
            self.log(f"Snapshot copy completed: {snapshot_id} -> {dest_repo_name}")
        else:
            error_msg = stderr if stderr else stdout if stdout else "Unknown error"
            
            # Show detailed error in a scrollable dialog
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Copy Failed")
            error_dialog.setMinimumWidth(500)
            error_dialog.setMinimumHeight(300)
            
            error_layout = QVBoxLayout()
            error_dialog.setLayout(error_layout)
            
            error_label = QLabel(f"Failed to copy snapshot {snapshot_id}")
            error_label.setStyleSheet("color: red; font-weight: bold;")
            error_layout.addWidget(error_label)
            
            error_text = QPlainTextEdit()
            error_text.setReadOnly(True)
            error_text.setPlainText(error_msg)
            error_layout.addWidget(error_text)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(error_dialog.close)
            error_layout.addWidget(close_btn)
            
            error_dialog.exec()
            self.log(f"Snapshot copy failed: {error_msg}")
    
    def _on_forget_complete(self, success, stdout, stderr, snapshot_id):
        """Callback when forget completes"""
        if success:
            QMessageBox.information(self, "Snapshot Forgotten",
                                  f"Snapshot {snapshot_id} has been marked for deletion.\n\n"
                                  "Run 'Prune Repository' to free the disk space.")
            self.log(f"Successfully forgot snapshot {snapshot_id}")
            # Reload snapshots
            self.load_snapshots()
        else:
            error_msg = stderr if stderr else "Unknown error"
            QMessageBox.warning(self, "Forget Failed",
                               f"Failed to forget snapshot:\n\n{error_msg}")
            self.log(f"Failed to forget snapshot {snapshot_id}: {error_msg}")
    
    def _framed_confirm(
        self,
        *,
        title: str,
        heading: str,
        body: str,
        note: str = "",
        meta: list | None = None,
        confirm_label: str = "Continue",
        danger: bool = False,
    ) -> bool:
        """Modern confirm dialog matching Forget / Copy chrome. Returns True if confirmed."""
        dialog = FramedDialog(
            title,
            self,
            show_maximize=False,
            show_minimize=False,
        )
        dialog.setMinimumWidth(520)
        dialog.body_layout.setContentsMargins(16, 12, 16, 16)
        dialog.body_layout.setSpacing(12)
        layout = dialog.body_layout

        heading_lbl = QLabel(heading)
        heading_lbl.setObjectName("pageTitle")
        heading_lbl.setStyleSheet("font-size: 18px;")
        heading_lbl.setWordWrap(True)
        layout.addWidget(heading_lbl)

        body_lbl = QLabel(body)
        body_lbl.setObjectName("pageSubtitle")
        body_lbl.setWordWrap(True)
        layout.addWidget(body_lbl)

        if meta:
            strip = QFrame()
            strip.setObjectName("browseMetaStrip")
            row = QHBoxLayout(strip)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(20)
            for i, (label, value) in enumerate(meta):
                col = QVBoxLayout()
                col.setSpacing(2)
                lab = QLabel(label)
                lab.setObjectName("browseMetaLabel")
                val = QLabel(str(value))
                val.setObjectName("browseMetaValue")
                val.setWordWrap(True)
                val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                col.addWidget(lab)
                col.addWidget(val)
                stretch = 1 if i == len(meta) - 1 else 0
                row.addLayout(col, stretch)
            layout.addWidget(strip)

        if note:
            note_lbl = QLabel(note)
            note_lbl.setObjectName("copyNote")
            note_lbl.setWordWrap(True)
            layout.addWidget(note_lbl)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)
        footer.addWidget(cancel_btn)
        confirm_btn = QPushButton(confirm_label)
        confirm_btn.setObjectName("dangerBtn" if danger else "dialogPrimary")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(dialog.accept)
        footer.addWidget(confirm_btn)
        layout.addLayout(footer)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def prune_repository(self):
        """Prune repository to free disk space"""
        repo_name = self.snapshot_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", "Repository not found")
            return
        
        if not self._framed_confirm(
            title="Prune Repository",
            heading=f"Prune repository “{repo_name}”?",
            body="This removes unreferenced data and frees disk space. The operation can take a long time.",
            note="You can keep using the app while prune runs in the background.",
            meta=[("Repository", repo_name), ("Path", repo.get("path", "—"))],
            confirm_label="Prune",
            danger=True,
        ):
            return

        self.log(f"Pruning repository {repo_name}...")
        
        # Show progress dialog with close button
        self._prune_progress = QDialog(self)
        self._prune_progress.setWindowTitle("Pruning Repository")
        self._prune_progress.setModal(False)
        
        layout = QVBoxLayout()
        self._prune_progress.setLayout(layout)
        
        label = QLabel(f"Pruning {repo_name}...\n\nThis may take several minutes.\n\nYou can continue using the application.")
        layout.addWidget(label)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.setToolTip("Close this dialog. The prune operation will continue running in the background.")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        close_layout.addStretch()
        close_btn.clicked.connect(self._prune_progress.accept)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        layout.addLayout(close_layout)
        
        self._prune_progress.show()
        
        # Execute restic prune command in background with longer timeout (30 minutes)
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "prune"]
        
        self._prune_repo_name = repo_name
        self._prune_worker = ResticWorker(self.restic_cmd, args, env, timeout=1800)  # 30 minutes
        self._prune_worker.finished.connect(self._on_prune_complete)
        self._prune_worker.start()
    
    def _on_prune_complete(self, success, stdout, stderr):
        """Callback when prune completes"""
        repo_name = self._prune_repo_name
        
        # Close progress dialog if still open
        if hasattr(self, '_prune_progress'):
            try:
                self._prune_progress.close()
                self._prune_progress.deleteLater()
            except:
                pass
        
        if success:
            # Update last prune date in repository metadata
            repositories = self.settings_manager.get("repositories")
            for repo in repositories:
                if repo["name"] == repo_name:
                    repo["last_prune"] = datetime.now().isoformat()
                    break
            self.settings_manager.set("repositories", repositories)
            self.settings_manager.save_settings()
            
            # Extract useful info from stdout
            output_preview = stdout[:500] if stdout else "Prune completed successfully"
            QMessageBox.information(self, "Prune Complete",
                                  f"Repository '{repo_name}' has been pruned.\n\n{output_preview}")
            self.log(f"Successfully pruned repository {repo_name}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            QMessageBox.warning(self, "Prune Failed",
                               f"Failed to prune repository:\n\n{error_msg[:500]}")
            self.log(f"Failed to prune repository {repo_name}: {error_msg}")
    
    def unlock_repository(self):
        """Unlock repository to remove stale locks"""
        repo_name = self.snapshot_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", f"Repository '{repo_name}' not found")
            return
        
        if not self._framed_confirm(
            title="Unlock Repository",
            heading=f"Remove locks from “{repo_name}”?",
            body="This removes stale locks left by crashed processes. Only continue if no other restic process is running on this repository.",
            note="Unlocking while another backup is active can corrupt the repository.",
            meta=[("Repository", repo_name), ("Path", repo.get("path", "—"))],
            confirm_label="Unlock",
            danger=True,
        ):
            return

        self.log(f"Unlocking repository {repo_name}...")
        
        # Show progress dialog
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Unlocking Repository")
        progress_dialog.setModal(True)
        progress_dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        progress_dialog.setLayout(layout)
        
        label = QLabel(f"Removing locks from repository '{repo_name}'...\n\nPlease wait...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)
        layout.addWidget(progress_bar)
        
        progress_dialog.show()
        QApplication.processEvents()
        
        # Store for callback
        self._unlock_progress_dialog = progress_dialog
        self._unlock_repo_name = repo_name
        
        # Execute unlock command
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "unlock"]
        
        self._unlock_worker = ResticWorker(self.restic_cmd, args, env, timeout=60)
        self._unlock_worker.finished.connect(self._on_unlock_completed)
        self._unlock_worker.start()
    
    def _on_unlock_completed(self, success, stdout, stderr):
        """Callback when unlock completes"""
        # Close progress dialog
        if hasattr(self, '_unlock_progress_dialog'):
            try:
                self._unlock_progress_dialog.close()
                self._unlock_progress_dialog.deleteLater()
            except:
                pass
        
        repo_name = self._unlock_repo_name
        
        if success:
            QMessageBox.information(
                self,
                "Repository Unlocked",
                f"Successfully removed all locks from repository '{repo_name}'.\n\n"
                "You can now perform operations on this repository."
            )
            self.log(f"Successfully unlocked repository {repo_name}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            QMessageBox.warning(
                self,
                "Unlock Failed",
                f"Failed to unlock repository:\n\n{error_msg[:500]}"
            )
            self.log(f"Failed to unlock repository {repo_name}: {error_msg}")
    
    def load_repository_stats(self):
        """Load statistics for selected repository"""
        repo_name = self.dashboard_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", f"Repository '{repo_name}' not found")
            return
        
        self.repo_stats_text.setText(f"Loading comprehensive stats for {repo_name}...\nThis may take a moment...")
        self.log(f"Loading stats for repository {repo_name}")
        QApplication.processEvents()
        
        # Store repo info
        self._current_stats_repo = repo
        self._current_stats_repo_name = repo_name
        self._current_stats_password = password
        
        # Start loading stats in background
        # We'll gather: snapshots count, repository size, restore size, and check status
        env = {"RESTIC_PASSWORD": password} if password else {}
        
        # First, get snapshot count
        args = ["-r", repo["path"], "snapshots", "--json"]
        self._stats_worker = ResticWorker(self.restic_cmd, args, env)
        self._stats_worker.finished.connect(self._on_snapshots_counted)
        self._stats_worker.start()
    
    def _on_snapshots_counted(self, success, stdout, stderr):
        """Callback when snapshot count is retrieved"""
        snapshot_count = 0
        last_backup = "Never"
        
        if success and stdout:
            try:
                snapshots = json.loads(stdout)
                if isinstance(snapshots, list):
                    snapshot_count = len(snapshots)
                    # Get most recent backup time
                    if snapshots:
                        latest = max(snapshots, key=lambda s: s.get("time", ""))
                        last_backup = latest.get("time", "Unknown")
                        # Format datetime
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(last_backup.replace("Z", "+00:00"))
                            last_backup = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
            except:
                pass
        
        self._stats_snapshot_count = snapshot_count
        self._stats_last_backup = last_backup
        
        # Now get repository size stats (raw data)
        repo = self._current_stats_repo
        password = self._current_stats_password
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "stats", "--mode", "raw-data", "--json"]
        
        self._stats_worker = ResticWorker(self.restic_cmd, args, env)
        self._stats_worker.finished.connect(self._on_raw_stats_loaded)
        self._stats_worker.start()
    
    def _on_raw_stats_loaded(self, success, stdout, stderr):
        """Callback when raw repository size is retrieved (actual on-disk size)"""
        repo_size = 0
        
        if success and stdout:
            try:
                stats = json.loads(stdout)
                repo_size = stats.get("total_size", 0)
            except:
                pass
        
        self._stats_repo_size = repo_size
        
        # Now get restore size (original data size before deduplication and compression)
        repo = self._current_stats_repo
        password = self._current_stats_password
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "stats", "--mode", "restore-size", "--json"]
        
        self._stats_worker = ResticWorker(self.restic_cmd, args, env)
        self._stats_worker.finished.connect(self._on_restore_stats_loaded)
        self._stats_worker.start()
    
    def _on_restore_stats_loaded(self, success, stdout, stderr):
        """Callback when restore size is retrieved - final step"""
        restore_size = 0
        total_files = 0
        
        if success and stdout:
            try:
                stats = json.loads(stdout)
                restore_size = stats.get("total_size", 0)
                total_files = stats.get("total_file_count", 0)
            except:
                pass
        
        self._stats_restore_size = restore_size
        self._stats_total_files = total_files
        
        # Now compile all stats and display
        self._display_comprehensive_stats()
    
    def _display_comprehensive_stats(self):
        """Display all gathered statistics"""
        repo = self._current_stats_repo
        repo_name = self._current_stats_repo_name
        
        snapshot_count = getattr(self, '_stats_snapshot_count', 0)
        last_backup = getattr(self, '_stats_last_backup', 'Never')
        repo_size = getattr(self, '_stats_repo_size', 0)
        restore_size = getattr(self, '_stats_restore_size', 0)
        total_files = getattr(self, '_stats_total_files', 0)
        
        # Calculate total savings (deduplication + compression combined)
        if restore_size > 0 and repo_size > 0:
            total_saved = restore_size - repo_size
            savings_percent = (total_saved / restore_size) * 100 if restore_size > 0 else 0
        else:
            total_saved = 0
            savings_percent = 0
        
        # Get last prune date from repository metadata if available
        last_prune = repo.get("last_prune", "Never")
        if last_prune != "Never":
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_prune)
                days_ago = (datetime.now() - dt).days
                if days_ago == 0:
                    last_prune = "Today"
                elif days_ago == 1:
                    last_prune = "Yesterday"
                else:
                    last_prune = f"{days_ago} days ago"
            except:
                pass
        
        # Format the comprehensive stats display with clear breakdown
        stats_text = f"<b>Repository:</b> {repo_name}<br>"
        stats_text += f"<b>Path:</b> {repo['path']}<br>"
        stats_text += f"<b>Type:</b> {repo.get('type', 'local')}<br><br>"
        
        stats_text += f"<b>Snapshots:</b> {snapshot_count:,}<br>"
        stats_text += f"<b>Last Backup:</b> {last_backup}<br>"
        stats_text += f"<b>Total Files:</b> {total_files:,}<br><br>"
        
        # Storage breakdown section
        stats_text += "<b>=== Storage Breakdown ===</b><br>"
        stats_text += f"<b>Original Data Size:</b> {self.format_bytes(restore_size)}<br>"
        stats_text += f"<b>Repository Size:</b> {self.format_bytes(repo_size)}<br>"
        stats_text += f"<small><i>(After deduplication + compression)</i></small><br>"
        
        if total_saved > 0:
            stats_text += f"<br><b style='color: green;'>Total Saved:</b> <span style='color: green;'>{self.format_bytes(total_saved)} ({savings_percent:.1f}%)</span><br>"
            
            # Calculate storage efficiency ratio
            if restore_size > 0:
                efficiency_ratio = repo_size / restore_size
                stats_text += f"<small><i>Storage efficiency: {efficiency_ratio:.2f}x (storing {self.format_bytes(repo_size)} instead of {self.format_bytes(restore_size)})</i></small><br>"
        else:
            stats_text += f"<br><b>Total Saved:</b> N/A<br>"
        
        stats_text += f"<br><b>Last Prune:</b> {last_prune}<br>"
        stats_text += f"<b>Corruption:</b> <span style='color: green;'>Not checked (click Verify to check)</span>"
        
        if snapshot_count == 0:
            stats_text += "<br><br><i>â„¹ This repository is empty (no snapshots yet).</i>"
        
        self.repo_stats_text.setHtml(stats_text)
        self.log(f"Successfully loaded comprehensive stats for {repo_name}")
    
    def _on_stats_loaded(self, success, stdout, stderr):
        """Legacy callback - not used with new comprehensive stats"""
        pass
    
    def verify_repository(self):
        """Verify repository integrity with options"""
        repo_name = self.dashboard_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", f"Repository '{repo_name}' not found")
            return
        
        # Show options dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Verify Repository")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        info_label = QLabel(f"<b>Repository:</b> {repo_name}<br><br>Choose verification level:")
        layout.addWidget(info_label)
        
        # Radio buttons for verification level
        check_group = QGroupBox("Verification Level")
        check_layout = QVBoxLayout()
        
        quick_radio = QRadioButton("Quick Check (metadata only - fastest)")
        quick_radio.setChecked(True)
        quick_radio.setToolTip("Check repository structure and metadata only")
        check_layout.addWidget(quick_radio)
        
        partial_radio = QRadioButton("Partial Data Check (reads 10% of data packs)")
        partial_radio.setToolTip("Reads a random 10% subset of data to detect corruption")
        check_layout.addWidget(partial_radio)
        
        full_radio = QRadioButton("Full Data Check (reads all data - very slow)")
        full_radio.setToolTip("Reads and verifies all data in repository - may take hours")
        check_layout.addWidget(full_radio)
        
        check_group.setLayout(check_layout)
        layout.addWidget(check_group)
        
        # Warning for full check
        warning_label = QLabel(
            "âš  <b>Note:</b> Full data check can take many hours for large repositories.\n"
            "Partial data check (10%) is recommended for regular maintenance."
        )
        warning_label.setStyleSheet("color: orange;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Determine check type
            if partial_radio.isChecked():
                check_type = "partial"
                check_label = "Partial Data Check (10%)"
                timeout = 3600  # 1 hour
            elif full_radio.isChecked():
                check_type = "full"
                check_label = "Full Data Check"
                timeout = 7200  # 2 hours
            else:
                check_type = "quick"
                check_label = "Quick Check"
                timeout = 1800  # 30 minutes
            
            self.log(f"Running {check_label} on repository {repo_name}...")
            
            # Store repo info for callback
            self._verify_repo_name = repo_name
            self._verify_check_type = check_type
            
            # Show progress dialog with close button
            self._verify_progress = QDialog(self)
            self._verify_progress.setWindowTitle(f"Verifying Repository - {check_label}")
            self._verify_progress.setModal(False)
            
            progress_layout = QVBoxLayout()
            self._verify_progress.setLayout(progress_layout)
            
            progress_label = QLabel(
                f"Running {check_label} on {repo_name}...\n\n"
                f"This may take several minutes.\n\n"
                f"You can continue using the application."
            )
            progress_layout.addWidget(progress_label)
            
            # Add close button
            close_btn = QPushButton("Close (operation continues in background)")
            close_btn.clicked.connect(self._verify_progress.accept)
            progress_layout.addWidget(close_btn)
            
            self._verify_progress.show()
            
            # Build command based on check type
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "check"]
            
            if check_type == "partial":
                args.extend(["--read-data-subset=10%"])
            elif check_type == "full":
                args.extend(["--read-data"])
            # Quick check has no additional args
            
            self._verify_worker = ResticWorker(self.restic_cmd, args, env, timeout=timeout)
            self._verify_worker.finished.connect(self._on_verify_complete)
            self._verify_worker.start()
    
    def _on_verify_complete(self, success, stdout, stderr):
        """Callback when verification completes"""
        repo_name = self._verify_repo_name
        check_type = getattr(self, '_verify_check_type', 'quick')
        
        # Close progress dialog if still open
        if hasattr(self, '_verify_progress'):
            try:
                self._verify_progress.close()
                self._verify_progress.deleteLater()
            except:
                pass
        
        # Check if output suggests rebuilding index
        output_combined = (stdout or "") + (stderr or "")
        should_rebuild_index = (
            "rebuild-index" in output_combined.lower() or 
            "index rebuild" in output_combined.lower() or
            "index is not complete" in output_combined.lower()
        )
        
        if success:
            check_label = {"quick": "Quick Check", "partial": "Partial Data Check", "full": "Full Data Check"}.get(check_type, "Check")
            message = f"Repository '{repo_name}' verified successfully!\n\n{check_label} completed.\n\n{stdout[:400]}"
            
            if should_rebuild_index:
                message += "\n\nâš  Index rebuild recommended. Click 'Rebuild Index' button."
            
            QMessageBox.information(self, "Verification Complete", message)
            self.log(f"Repository {repo_name} verified successfully ({check_type})")
            
            if should_rebuild_index:
                self.log(f"Warning: Index rebuild recommended for {repo_name}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            
            if should_rebuild_index:
                reply = QMessageBox.question(
                    self,
                    "Verification Failed - Index Issues Detected",
                    f"Repository verification failed with index issues:\n\n{error_msg[:400]}\n\n"
                    "The index may need to be rebuilt. Rebuild now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.rebuild_index()
            else:
                QMessageBox.warning(self, "Verification Failed",
                                   f"Repository verification failed:\n\n{error_msg[:500]}")
            
            self.log(f"Repository {repo_name} verification failed: {error_msg}")
    
    def rebuild_index(self):
        """Rebuild repository index"""
        repo_name = self.dashboard_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", f"Repository '{repo_name}' not found")
            return
        
        reply = QMessageBox.question(
            self, "Rebuild Index",
            f"Rebuild index for repository '{repo_name}'?\n\n"
            "This recreates the repository index from scratch.\n"
            "Useful after errors, corruption, or when recommended by verify.\n\n"
            "This operation is safe and won't delete any data.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log(f"Rebuilding index for repository {repo_name}...")
            
            # Store repo info for callback
            self._rebuild_index_repo_name = repo_name
            
            # Show progress dialog
            self._rebuild_index_progress = QDialog(self)
            self._rebuild_index_progress.setWindowTitle("Rebuilding Index")
            self._rebuild_index_progress.setModal(False)
            
            layout = QVBoxLayout()
            self._rebuild_index_progress.setLayout(layout)
            
            label = QLabel(
                f"Rebuilding index for {repo_name}...\n\n"
                f"This may take several minutes.\n\n"
                f"You can continue using the application."
            )
            layout.addWidget(label)
            
            # Add close button
            close_btn = QPushButton("Close (operation continues in background)")
            close_btn.clicked.connect(self._rebuild_index_progress.accept)
            layout.addWidget(close_btn)
            
            self._rebuild_index_progress.show()
            
            # Execute restic rebuild-index command
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "rebuild-index"]
            
            self._rebuild_index_worker = ResticWorker(self.restic_cmd, args, env, timeout=1800)  # 30 minutes
            self._rebuild_index_worker.finished.connect(self._on_rebuild_index_complete)
            self._rebuild_index_worker.start()
    
    def _on_rebuild_index_complete(self, success, stdout, stderr):
        """Callback when index rebuild completes"""
        repo_name = self._rebuild_index_repo_name
        
        # Close progress dialog if still open
        if hasattr(self, '_rebuild_index_progress'):
            try:
                self._rebuild_index_progress.close()
                self._rebuild_index_progress.deleteLater()
            except:
                pass
        
        if success:
            QMessageBox.information(
                self, "Index Rebuilt",
                f"Repository index for '{repo_name}' rebuilt successfully!\n\n{stdout[:500]}"
            )
            self.log(f"Repository index rebuilt successfully for {repo_name}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            QMessageBox.warning(
                self, "Rebuild Failed",
                f"Failed to rebuild repository index:\n\n{error_msg[:500]}"
            )
            self.log(f"Repository index rebuild failed for {repo_name}: {error_msg}")
    
    def load_snapshots_for_restore(self):
        """Load snapshots into restore dropdown"""
        self.restore_snapshot_combo.clear()
        self.restore_snapshot_combo.addItem("Loading...")
        
        repo_name = self.restore_repo_combo.currentText()
        if not repo_name:
            self.restore_snapshot_combo.clear()
            self.restore_snapshot_combo.addItem("Select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            self.restore_snapshot_combo.clear()
            self.restore_snapshot_combo.addItem("Repository not found")
            return
        
        # Load snapshots
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "snapshots", "--json"]
        
        # Store worker reference to prevent garbage collection
        self._restore_snapshot_worker = ResticWorker(self.restic_cmd, args, env)
        self._restore_snapshot_worker.finished.connect(lambda success, stdout, stderr: self._on_restore_snapshots_loaded(success, stdout, stderr))
        self._restore_snapshot_worker.start()
    
    def _on_restore_snapshots_loaded(self, success, stdout, stderr):
        """Callback when snapshots are loaded for restore"""
        self.restore_snapshot_combo.clear()
        
        if not success:
            self.restore_snapshot_combo.addItem("Failed to load snapshots")
            self.log(f"Error loading snapshots: {stderr}")
            return
        
        try:
            snapshots = json.loads(stdout)
            if not isinstance(snapshots, list) or len(snapshots) == 0:
                self.restore_snapshot_combo.addItem("No snapshots available")
                return
            
            # Store snapshots for search functionality
            self._restore_snapshots_cache = snapshots
            
            # Add snapshots to combo box
            for snapshot in reversed(snapshots):  # Most recent first
                snap_id = snapshot.get("short_id", snapshot.get("id", "unknown")[:8])
                snap_time = snapshot.get("time", "unknown")
                snap_host = snapshot.get("hostname", "unknown")
                snap_paths = snapshot.get("paths", [])
                
                # Format time
                try:
                    dt = datetime.fromisoformat(snap_time.replace("Z", "+00:00"))
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = snap_time
                
                # Create description
                paths_str = ", ".join(snap_paths[:2])
                if len(snap_paths) > 2:
                    paths_str += f" (+{len(snap_paths)-2} more)"
                
                display = f"{snap_id} - {time_str} - {snap_host} - {paths_str}"
                self.restore_snapshot_combo.addItem(display, snapshot.get("id", snap_id))
            
            # Auto-select the latest snapshot (first item = most recent)
            if self.restore_snapshot_combo.count() > 0:
                self.restore_snapshot_combo.setCurrentIndex(0)
                self.log(f"Auto-selected latest snapshot: {self.restore_snapshot_combo.currentText()}")
        
        except Exception as e:
            self.restore_snapshot_combo.addItem("Error parsing snapshots")
            self.log(f"Error parsing snapshots: {str(e)}")
    
    def select_latest_snapshot(self):
        """Select the most recent snapshot in the dropdown"""
        if self.restore_snapshot_combo.count() > 0:
            self.restore_snapshot_combo.setCurrentIndex(0)
            self.log("Selected latest snapshot")
        else:
            QMessageBox.information(self, "No Snapshots", "No snapshots available to select")
    
    def find_snapshot_by_date(self):
        """Find snapshot closest to selected date"""
        if not hasattr(self, '_restore_snapshots_cache') or not self._restore_snapshots_cache:
            QMessageBox.warning(self, "No Snapshots", "No snapshots loaded. Please select a repository first.")
            return
        
        # Get target date from date picker
        target_date = self.restore_date_edit.date()
        target_datetime = datetime(target_date.year(), target_date.month(), target_date.day())
        
        # Find closest snapshot
        closest_snapshot = None
        closest_diff = None
        
        for snapshot in self._restore_snapshots_cache:
            snap_time = snapshot.get("time", "")
            try:
                snap_datetime = datetime.fromisoformat(snap_time.replace("Z", "+00:00"))
                snap_datetime = snap_datetime.replace(tzinfo=None)  # Remove timezone for comparison
                diff = abs((snap_datetime - target_datetime).total_seconds())
                
                if closest_diff is None or diff < closest_diff:
                    closest_diff = diff
                    closest_snapshot = snapshot
            except:
                continue
        
        if closest_snapshot:
            # Find and select this snapshot in the combo box
            snap_id = closest_snapshot.get("id", "")
            for i in range(self.restore_snapshot_combo.count()):
                if self.restore_snapshot_combo.itemData(i) == snap_id:
                    self.restore_snapshot_combo.setCurrentIndex(i)
                    self.log(f"Selected snapshot closest to {target_date.toString('yyyy-MM-dd')}: {self.restore_snapshot_combo.currentText()}")
                    break
        else:
            QMessageBox.information(self, "No Match", "Could not find a snapshot near the selected date.")
    
    def search_across_snapshots(self):
        """Search for files/folders across all snapshots"""
        search_pattern = self.global_search_input.text().strip()
        if not search_pattern:
            QMessageBox.warning(self, "No Search Term", "Please enter a filename or path pattern to search for.")
            return
        
        if not hasattr(self, '_restore_snapshots_cache') or not self._restore_snapshots_cache:
            QMessageBox.warning(self, "No Snapshots", "No snapshots loaded. Please select a repository first.")
            return
        
        repo_name = self.restore_repo_combo.currentText()
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            return
        
        self.log(f"Searching all snapshots for '{search_pattern}'...")
        self.search_results_table.setRowCount(0)
        self.search_results_table.setVisible(True)
        QApplication.processEvents()
        
        # Search each snapshot
        results = []
        import fnmatch
        
        for snapshot in self._restore_snapshots_cache:
            snap_id = snapshot.get("short_id", snapshot.get("id", "unknown")[:8])
            snap_time = snapshot.get("time", "unknown")
            
            # Use restic ls to list files in this snapshot
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "ls", snap_id, "--long"]
            
            success, stdout, stderr = self.restic_cmd.run(args, env=env, timeout=60)
            
            if success and stdout:
                # Parse output and look for pattern
                for line in stdout.split('\n'):
                    if not line.strip():
                        continue
                    
                    # Parse ls output (format: permissions user group size date time path)
                    parts = line.split(None, 6)
                    if len(parts) >= 7:
                        file_path = parts[6]
                        file_size = parts[3]
                        
                        # Check if path matches pattern
                        file_name = file_path.split('/')[-1] if '/' in file_path else file_path
                        
                        # Match against pattern (case-insensitive)
                        if fnmatch.fnmatch(file_name.lower(), search_pattern.lower()) or \
                           fnmatch.fnmatch(file_path.lower(), search_pattern.lower()) or \
                           search_pattern.lower() in file_path.lower():
                            results.append({
                                'name': file_name,
                                'path': file_path,
                                'snapshot_id': snap_id,
                                'snapshot_full_id': snapshot.get('id'),
                                'time': snap_time,
                                'size': file_size
                            })
        
        # Display results
        if results:
            self.search_results_table.setRowCount(len(results))
            for row, result in enumerate(results):
                # Format time
                try:
                    dt = datetime.fromisoformat(result['time'].replace("Z", "+00:00"))
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = result['time']
                
                # Format size
                try:
                    size_bytes = int(result['size'])
                    size_str = self.format_bytes(size_bytes)
                except (ValueError, TypeError):
                    size_str = result['size']
                
                self.search_results_table.setItem(row, 0, QTableWidgetItem(result['name']))
                self.search_results_table.setItem(row, 1, QTableWidgetItem(result['path']))
                self.search_results_table.setItem(row, 2, QTableWidgetItem(result['snapshot_id']))
                self.search_results_table.setItem(row, 3, QTableWidgetItem(time_str))
                self.search_results_table.setItem(row, 4, QTableWidgetItem(size_str))
                
                # Add restore button
                restore_btn = QPushButton("Restore")
                restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                restore_btn.clicked.connect(lambda checked, r=result: self._restore_from_search(r))
                self.search_results_table.setCellWidget(row, 5, restore_btn)
            
            self.log(f"Found {len(results)} match(es) across {len(self._restore_snapshots_cache)} snapshots")
        else:
            self.search_results_table.setVisible(False)
            QMessageBox.information(self, "No Results", f"No files matching '{search_pattern}' found in any snapshot.")
            self.log(f"No matches found for '{search_pattern}'")
    
    def _restore_from_search(self, result):
        """Restore a specific file from search results"""
        # Set the snapshot and path
        snap_full_id = result['snapshot_full_id']
        file_path = result['path']
        
        # Find and select the snapshot
        for i in range(self.restore_snapshot_combo.count()):
            if self.restore_snapshot_combo.itemData(i) == snap_full_id:
                self.restore_snapshot_combo.setCurrentIndex(i)
                break
        
        # Set the path to restore
        self.restore_path_input.setText(file_path)
        
        # Show message
        QMessageBox.information(
            self,
            "Ready to Restore",
            f"Selected file for restore:\n\n"
            f"File: {result['name']}\n"
            f"Path: {file_path}\n"
            f"Snapshot: {result['snapshot_id']}\n\n"
            f"Please select a restore location and click 'Start Restore'."
        )
        
        self.log(f"Prepared to restore: {file_path} from snapshot {result['snapshot_id']}")
    
    # Restore Methods
    def browse_snapshot_files(self):
        """Browse files in selected snapshot (uses tree view like browse_snapshot_content)"""
        repo_name = self.restore_repo_combo.currentText()
        snapshot_text = self.restore_snapshot_combo.currentText()
        
        if not repo_name or snapshot_text == "Select a snapshot" or not snapshot_text:
            QMessageBox.warning(self, "Selection Required", "Please select a repository and snapshot first")
            return
        
        # Get snapshot ID
        snapshot_id = self.restore_snapshot_combo.currentData()
        if not snapshot_id:
            snapshot_id = snapshot_text.split(" - ")[0]
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            return
        
        # Parse snapshot info from combo text
        try:
            parts = snapshot_text.split(" - ")
            snapshot_time = parts[1] if len(parts) > 1 else "Unknown"
            snapshot_host = parts[2] if len(parts) > 2 else "Unknown"
            snapshot_paths = parts[3] if len(parts) > 3 else "Unknown"
        except:
            snapshot_time = snapshot_host = snapshot_paths = "Unknown"
        
        # Build snapshot data
        snapshot_data = {
            "id": snapshot_id,
            "short_id": snapshot_id[:8] if len(snapshot_id) > 8 else snapshot_id,
            "time": snapshot_time,
            "hostname": snapshot_host,
            "paths": [snapshot_paths]
        }
        
        # Show dialog with file tree (reuse the browse_snapshot_content dialog logic)
        self._show_snapshot_browser_for_restore(snapshot_id, snapshot_data, repo, password, repo_name)
    
    def _show_snapshot_browser_for_restore(self, snapshot_id, snapshot_data, repo, password, repo_name):
        """Show snapshot browser dialog for restore page"""
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Browse Snapshot - {snapshot_id[:8]}")
        dialog.setMinimumSize(900, 650)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Snapshot info table
        info_table = QTableWidget()
        info_table.setRowCount(1)
        info_table.setColumnCount(4)
        info_table.setHorizontalHeaderLabels(["Snapshot ID", "Time", "Host", "Paths"])
        info_table.verticalHeader().setVisible(False)
        info_table.setMaximumHeight(80)
        info_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        
        # Populate snapshot info
        snapshot_time = snapshot_data.get("time", "Unknown")
        snapshot_host = snapshot_data.get("hostname", "Unknown")
        snapshot_paths = ", ".join(snapshot_data.get("paths", []))
        
        info_table.setItem(0, 0, QTableWidgetItem(snapshot_id[:8]))
        info_table.setItem(0, 1, QTableWidgetItem(snapshot_time))
        info_table.setItem(0, 2, QTableWidgetItem(snapshot_host))
        info_table.setItem(0, 3, QTableWidgetItem(snapshot_paths))
        
        info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(info_table)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>File Browser</b>"))
        header_layout.addStretch()
        
        # Add size format selector
        size_format_label = QLabel("Size:")
        header_layout.addWidget(size_format_label)
        
        size_format_combo = QComboBox()
        size_format_combo.addItems(["Bytes", "KB", "MB", "GB", "Auto"])
        size_format_combo.setCurrentText("Auto")
        size_format_combo.setFixedWidth(80)
        size_format_combo.setToolTip("Choose how file sizes are displayed")
        header_layout.addWidget(size_format_combo)
        
        header_layout.addSpacing(10)
        
        # Add expand/collapse buttons
        expand_all_btn = QPushButton("Expand All")
        header_layout.addWidget(expand_all_btn)
        
        collapse_all_btn = QPushButton("Collapse All")
        header_layout.addWidget(collapse_all_btn)
        
        # Add refresh button
        refresh_btn = QPushButton("Refresh")
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Search controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search files/folders...")
        search_input.setFixedWidth(450)
        search_input.setToolTip("Enter text to filter the tree view")
        search_layout.addWidget(search_input)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # File tree view
        file_tree = QTreeWidget()
        file_tree.setHeaderLabels(["Name", "Type", "Size", "Modified", "Permissions"])
        file_tree.setColumnWidth(0, 400)
        file_tree.setColumnWidth(1, 80)
        file_tree.setColumnWidth(2, 100)
        file_tree.setColumnWidth(3, 150)
        file_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        file_tree.setSortingEnabled(True)
        file_tree.setAlternatingRowColors(True)
        layout.addWidget(file_tree)
        
        # Status label
        status_label = QLabel("Loading files...")
        layout.addWidget(status_label)
        
        # Store all files for filtering
        dialog._all_files = []
        dialog._file_tree_items = {}  # Map path -> QTreeWidgetItem
        
        # Filter function
        def filter_tree():
            """Filter tree view based on search text"""
            search_text = search_input.text().strip().lower()
            
            def check_item_matches(item, text):
                """Check if item or any child matches search text"""
                if not text:
                    return True
                
                # Check item text
                item_text = item.text(0).lower()
                if text in item_text:
                    return True
                
                # Check children
                for i in range(item.childCount()):
                    if check_item_matches(item.child(i), text):
                        return True
                
                return False
            
            # Filter all root items
            visible_count = 0
            for i in range(file_tree.topLevelItemCount()):
                item = file_tree.topLevelItem(i)
                matches = check_item_matches(item, search_text)
                item.setHidden(not matches)
                if matches:
                    visible_count += 1
                    # Expand to show matching children
                    if search_text:
                        item.setExpanded(True)
            
            # Update status
            if search_text:
                status_label.setText(f"Showing {visible_count} matching items")
            else:
                status_label.setText(f"Loaded {len(dialog._all_files)} files and folders")
        
        # Connect search
        search_input.textChanged.connect(filter_tree)
        
        # Connect expand/collapse buttons
        expand_all_btn.clicked.connect(file_tree.expandAll)
        collapse_all_btn.clicked.connect(file_tree.collapseAll)
        
        # Function to update all file sizes in the tree
        def update_tree_sizes():
            """Update all size displays in the tree according to selected format"""
            format_mode = size_format_combo.currentText()
            
            def update_item_size(item):
                """Recursively update item and children sizes"""
                # Update this item's size
                raw_size = item.data(2, Qt.ItemDataRole.UserRole + 1)
                if raw_size:
                    formatted = self.format_size(raw_size, format_mode)
                    item.setText(2, formatted)
                
                # Update children
                for i in range(item.childCount()):
                    update_item_size(item.child(i))
            
            # Update all root items
            for i in range(file_tree.topLevelItemCount()):
                update_item_size(file_tree.topLevelItem(i))
        
        # Connect size format combo
        size_format_combo.currentTextChanged.connect(lambda: update_tree_sizes())
        
        # Store filter function reference
        dialog._filter_files = filter_tree
        
        # Connect refresh button
        refresh_btn.clicked.connect(lambda: self._load_snapshot_content(file_tree, snapshot_id, repo, password, status_label, dialog))
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        copy_path_btn = QPushButton("Copy Selected Path(s)")
        copy_path_btn.setToolTip("Copy the full paths of selected files/folders to clipboard (or set in restore input if single selection)")
        copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_path_btn.clicked.connect(lambda: self._copy_paths_to_restore_input(file_tree))
        btn_layout.addWidget(copy_path_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Store references for the worker callback
        dialog._file_list = file_tree
        dialog._status_label = status_label
        dialog._repo = repo
        dialog._password = password
        dialog._full_id = snapshot_id
        
        # Load snapshot content
        self._load_snapshot_content(file_tree, snapshot_id, repo, password, status_label, dialog)
        
        self.log(f"Browsing content of snapshot {snapshot_id[:8]}")
        dialog.exec()
    
    def _copy_paths_to_restore_input(self, file_tree):
        """Copy selected file paths from tree to restore path input"""
        selected_items = file_tree.selectedItems()
        if not selected_items:
            return
        
        # Get paths from selected items
        paths = []
        for item in selected_items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths.append(path)
        
        if paths:
            # If single file, put in restore path input
            # If multiple, copy to clipboard
            if len(paths) == 1:
                self.restore_path_input.setText(paths[0])
                self.log(f"Path set in restore input: {paths[0]}")
                QMessageBox.information(None, "Path Set", f"Path has been set in the restore input field")
            else:
                clipboard_text = "\n".join(paths)
                QApplication.clipboard().setText(clipboard_text)
                self.log(f"Copied {len(paths)} path(s) to clipboard")
                QMessageBox.information(None, "Copied", f"Copied {len(paths)} path(s) to clipboard")
    
    def _on_restore_to_original_changed(self, state):
        """Handle restore to original location checkbox state change"""
        is_checked = bool(state)
        
        # Enable/disable target input and browse button
        self.restore_target_input.setEnabled(not is_checked)
        self.target_browse_btn.setEnabled(not is_checked)
        
        # Update placeholder text
        if is_checked:
            self.restore_target_input.setPlaceholderText("Files will be restored to their original locations")
            self.restore_target_input.clear()
        else:
            self.restore_target_input.setPlaceholderText("Select target directory for restore")
    
    def browse_restore_target(self):
        """Browse for restore target directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Restore Target Directory"
        )
        if directory:
            self.restore_target_input.setText(directory)
    
    def start_restore(self):
        """Start file restore operation"""
        repo_name = self.restore_repo_combo.currentText()
        snapshot_text = self.restore_snapshot_combo.currentText()
        restore_path = self.restore_path_input.text().strip()
        restore_to_original = self.restore_to_original_check.isChecked()
        
        if not repo_name or snapshot_text == "Select a snapshot" or not snapshot_text:
            QMessageBox.warning(self, "Incomplete", "Please select a repository and snapshot")
            return
        
        # Determine target directory
        if restore_to_original:
            # Use temporary restore location, then move files to original
            temp_restore_path = self.settings_manager.get("temp_restore_path")
            target = temp_restore_path
            self.log(f"Using temporary restore location: {target}")
        else:
            target = self.restore_target_input.text()
            if not target:
                QMessageBox.warning(self, "Incomplete", "Please select a target directory or check 'Restore to original location'")
                return
        
        # Check available disk space on target location
        import shutil
        try:
            # Get disk usage statistics for the target path
            # If path doesn't exist, check its parent or drive
            check_path = target
            import os
            while not os.path.exists(check_path) and check_path:
                parent = os.path.dirname(check_path)
                if parent == check_path:  # Reached root
                    break
                check_path = parent
            
            if not check_path:
                # Fallback to checking the drive letter on Windows
                import platform
                if platform.system() == "Windows" and len(target) > 2:
                    check_path = target[:3]  # e.g., "C:\"
                else:
                    check_path = "/"
            
            total, used, free = shutil.disk_usage(check_path)
            free_gb = free / (1024**3)
            
            # Warn if less than 1GB free
            if free_gb < 1:
                reply = QMessageBox.warning(self, "Low Disk Space",
                    f"Warning: Only {free_gb:.2f} GB free space available on target location.\n\n"
                    f"Target: {target}\n\n"
                    "Continue with restore anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return
            else:
                self.log(f"Available space on target: {free_gb:.2f} GB")
        except Exception as e:
            self.log(f"Warning: Could not check disk space: {e}")
        
        # Get snapshot ID
        snapshot_id = self.restore_snapshot_combo.currentData()
        if not snapshot_id:
            # Try to extract from text
            snapshot_id = snapshot_text.split(" - ")[0]
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", "Repository not found")
            return
        
        # Confirm restore
        if restore_to_original:
            location_msg = "ORIGINAL LOCATIONS (this will overwrite existing files!)"
            warning_emoji = "âš ï¸ "
        else:
            location_msg = target
            warning_emoji = ""
        
        if restore_path:
            msg = f"{warning_emoji}Restore '{restore_path}' from snapshot {snapshot_id} to:\n{location_msg}?"
        else:
            msg = f"{warning_emoji}Restore ALL FILES from snapshot {snapshot_id} to:\n{location_msg}?\n\nThis may take a long time!"
        
        reply = QMessageBox.question(self, "Confirm Restore", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.restore_progress.setVisible(True)
        self.restore_progress.setRange(0, 0)  # Indeterminate
        self.restore_log.clear()
        
        # Build restore command
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "restore", snapshot_id, "--target", target]
        
        # Use --include filter when a specific path is selected
        if restore_path:
            # Clean up the path - remove leading/trailing slashes and whitespace
            restore_path_clean = restore_path.strip().lstrip('/')
            
            # Use the exact path as stored in the snapshot
            args.extend(["--include", restore_path_clean])
            
            self.log(f"Restore path filter (include): {restore_path_clean}")
        
        self.log(f"Full restore command: restic {' '.join(args)}")
        
        # Log restore information
        if restore_to_original:
            self.log(f"Starting restore from {repo_name}/{snapshot_id} to temp location (will move to original)")
        else:
            self.log(f"Starting restore from {repo_name}/{snapshot_id} to {target}")
        
        if restore_path:
            self.log(f"Restoring path: {restore_path}")
        else:
            self.log("Restoring all files from snapshot...")
        
        # Store restore metadata for completion callback
        self._restore_metadata = {
            "restore_to_original": restore_to_original,
            "restore_path": restore_path,
            "temp_target": target
        }
        
        # Start restore worker with progress monitoring
        self._restore_worker = ResticWorker(self.restic_cmd, args, env, timeout=3600, use_progress=True)
        self._restore_worker.progress.connect(lambda text: self.restore_log.appendPlainText(text))
        self._restore_worker.progress_data.connect(self._on_restore_progress)
        self._restore_worker.finished.connect(self._on_restore_complete)
        self._restore_worker.start()
    
    def _on_restore_progress(self, progress_info):
        """Update restore progress bar"""
        percent = progress_info.get("percent", 0)
        self.restore_progress.setRange(0, 100)
        self.restore_progress.setValue(int(percent))
    
    def _on_restore_complete(self, success, stdout, stderr):
        """Callback when restore is complete"""
        self.restore_progress.setVisible(False)
        
        if success:
            # Show the actual restic output to verify files were restored
            if stdout:
                self.log(f"Restic output: {stdout}")
            if stderr:
                self.log(f"Restic stderr: {stderr}")
            
            # Check if we need to move files to original location
            if hasattr(self, '_restore_metadata') and self._restore_metadata.get('restore_to_original'):
                temp_target = self._restore_metadata['temp_target']
                
                self.log("Moving files from temp location to original locations...")
                
                try:
                    moved_files = self._move_restored_files_to_original(temp_target)
                    
                    if moved_files:
                        self.log(f"Successfully moved {len(moved_files)} file(s) to original location(s)")
                        QMessageBox.information(self, "Restore Complete", 
                            f"Successfully restored {len(moved_files)} file(s) to original locations!\n\n" +
                            "\n".join(moved_files[:5]) + 
                            (f"\n... and {len(moved_files) - 5} more" if len(moved_files) > 5 else ""))
                    else:
                        self.log("Warning: No files were moved (restore may have failed)")
                        QMessageBox.warning(self, "Restore Issue", "Restore completed but no files were found to move.")
                    
                except Exception as e:
                    self.log(f"Error moving files to original locations: {e}")
                    QMessageBox.warning(self, "Move Error", 
                        f"Files were restored to temp location but could not be moved:\n{e}\n\n" +
                        f"Files are in: {temp_target}")
            else:
                # Normal restore (not to original location)
                self.log("Restore completed successfully!")
                QMessageBox.information(self, "Restore Complete", f"Files have been restored successfully!\n\n{stderr if stderr else stdout}")
        else:
            self.log(f"Restore failed: {stderr}")
            QMessageBox.warning(self, "Restore Failed", f"Restore operation failed:\n{stderr}")
    
    def mount_and_browse_snapshot(self):
        """Browse repository snapshots using restic ls --json (no mounting required)"""
        repo_name = self.restore_repo_combo.currentText()
        
        if not repo_name:
            QMessageBox.warning(self, "Selection Required", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            return
        
        self.log(f"Opening snapshot browser for repository: {repo_name}")
        self._browse_repository_snapshots(repo, password, repo_name)
    
    def _browse_repository_snapshots(self, repo, password, repo_name):
        """Show dialog to browse and restore files from snapshots using JSON API"""
        # Create browser dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Browse Snapshots - {repo_name}")
        dialog.setMinimumSize(900, 600)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Snapshot selector at top
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Snapshot:"))
        
        snapshot_combo = QComboBox()
        snapshot_combo.setMinimumWidth(400)
        selector_layout.addWidget(snapshot_combo)
        
        refresh_snapshots_btn = QPushButton("Refresh List")
        selector_layout.addWidget(refresh_snapshots_btn)
        selector_layout.addStretch()
        
        layout.addLayout(selector_layout)
        
        # File tree
        file_tree = QTreeWidget()
        file_tree.setHeaderLabels(["Name", "Size", "Modified", "Type"])
        file_tree.setColumnWidth(0, 400)
        file_tree.setColumnWidth(1, 100)
        file_tree.setColumnWidth(2, 150)
        file_tree.setSortingEnabled(True)
        layout.addWidget(file_tree)
        
        # Status label
        status_label = QLabel("Select a snapshot to browse")
        status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        restore_selected_btn = QPushButton("Restore Selected...")
        restore_selected_btn.setEnabled(False)
        restore_selected_btn.clicked.connect(
            lambda: self._restore_selected_from_browser(file_tree, snapshot_combo, repo, password, dialog)
        )
        btn_layout.addWidget(restore_selected_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Load snapshots function
        def load_snapshots():
            snapshot_combo.clear()
            snapshot_combo.addItem("Loading snapshots...")
            status_label.setText("Loading snapshots...")
            
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "snapshots", "--json"]
            
            worker = ResticWorker(self.restic_cmd, args, env)
            worker.finished.connect(
                lambda success, stdout, stderr: _on_snapshots_loaded(success, stdout, stderr)
            )
            worker.start()
            
            # Store worker reference
            dialog._snapshot_worker = worker
        
        def _on_snapshots_loaded(success, stdout, stderr):
            snapshot_combo.clear()
            
            if success and stdout:
                try:
                    import json
                    snapshots = json.loads(stdout)
                    
                    if snapshots:
                        for snap in reversed(snapshots):  # Most recent first
                            snap_id = snap.get("short_id", snap.get("id", ""))[:8]
                            snap_time = snap.get("time", "")[:19].replace("T", " ")
                            snap_host = snap.get("hostname", "unknown")
                            snap_paths = ", ".join(snap.get("paths", []))[:50]
                            
                            display_text = f"{snap_time} | {snap_host} | {snap_paths}"
                            snapshot_combo.addItem(display_text, snap.get("id"))
                        
                        status_label.setText(f"Loaded {len(snapshots)} snapshots")
                    else:
                        snapshot_combo.addItem("No snapshots found")
                        status_label.setText("No snapshots in repository")
                
                except json.JSONDecodeError as e:
                    snapshot_combo.addItem("Error loading snapshots")
                    status_label.setText(f"Error parsing snapshot data: {str(e)}")
                    self.log(f"JSON decode error: {str(e)}")
            else:
                snapshot_combo.addItem("Error loading snapshots")
                status_label.setText(f"Failed to load snapshots")
                if stderr:
                    self.log(f"Snapshot load error: {stderr}")
        
        # Load files for selected snapshot
        def load_snapshot_files():
            file_tree.clear()
            restore_selected_btn.setEnabled(False)
            
            if snapshot_combo.currentIndex() < 0 or not snapshot_combo.currentData():
                return
            
            snapshot_id = snapshot_combo.currentData()
            status_label.setText(f"Loading files from snapshot {snapshot_id[:8]}...")
            
            loading_item = QTreeWidgetItem(["Loading...", "", "", ""])
            file_tree.addTopLevelItem(loading_item)
            
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "ls", snapshot_id, "--json"]
            
            worker = ResticWorker(self.restic_cmd, args, env)
            worker.finished.connect(
                lambda success, stdout, stderr: _on_files_loaded(success, stdout, stderr, snapshot_id)
            )
            worker.start()
            
            # Store worker reference
            dialog._files_worker = worker
        
        def _on_files_loaded(success, stdout, stderr, snapshot_id):
            file_tree.clear()
            
            if success and stdout:
                try:
                    import json
                    
                    # Parse JSON lines
                    items = {}
                    file_count = 0
                    
                    for line in stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        
                        try:
                            entry = json.loads(line)
                            path = entry.get("path", "")
                            
                            if not path or path == "/":
                                continue
                            
                            # Remove leading slash
                            path = path.lstrip('/')
                            
                            # Get entry details
                            entry_type = entry.get("type", "file")
                            size = entry.get("size", 0)
                            mtime = entry.get("mtime", "")[:19].replace("T", " ")
                            
                            # Format size
                            size_str = self._format_size(size) if entry_type == "file" else ""
                            
                            # Build tree structure
                            parts = path.split('/')
                            current_path = ""
                            parent = None
                            
                            for i, part in enumerate(parts):
                                if not part:
                                    continue
                                
                                if current_path:
                                    current_path += "/" + part
                                else:
                                    current_path = part
                                
                                # Create item if it doesn't exist
                                if current_path not in items:
                                    is_last = (i == len(parts) - 1)
                                    
                                    if is_last:
                                        # This is the actual entry
                                        item = QTreeWidgetItem([
                                            part,
                                            size_str,
                                            mtime,
                                            "Folder" if entry_type == "dir" else "File"
                                        ])
                                    else:
                                        # This is an intermediate directory
                                        item = QTreeWidgetItem([part, "", "", "Folder"])
                                    
                                    # Store full path in first column's data
                                    item.setData(0, Qt.ItemDataRole.UserRole, current_path)
                                    
                                    if parent:
                                        parent.addChild(item)
                                    else:
                                        file_tree.addTopLevelItem(item)
                                    
                                    items[current_path] = item
                                    
                                    if is_last:
                                        file_count += 1
                                
                                parent = items[current_path]
                        
                        except json.JSONDecodeError:
                            continue
                    
                    status_label.setText(f"Loaded {file_count} files from snapshot {snapshot_id[:8]}")
                    restore_selected_btn.setEnabled(True)
                    
                    # Sort tree
                    file_tree.sortItems(0, Qt.SortOrder.AscendingOrder)
                
                except Exception as e:
                    status_label.setText(f"Error parsing files: {str(e)}")
                    self.log(f"File tree error: {str(e)}")
            else:
                status_label.setText("Failed to load files")
                if stderr:
                    self.log(f"File load error: {stderr}")
        
        # Connect signals
        refresh_snapshots_btn.clicked.connect(load_snapshots)
        snapshot_combo.currentIndexChanged.connect(load_snapshot_files)
        
        # Load initial snapshots
        load_snapshots()
        
        # Show dialog
        dialog.exec()
    
    def _restore_selected_from_browser(self, file_tree, snapshot_combo, repo, password, parent_dialog):
        """Restore selected files from the browser"""
        paths_to_restore = self._paths_from_tree_selection(file_tree)
        if not paths_to_restore:
            QMessageBox.warning(parent_dialog, "No Selection", "Please select files or folders to restore")
            return

        snapshot_id = snapshot_combo.currentData()
        if not snapshot_id:
            return

        self._restore_paths_from_snapshot(
            paths_to_restore,
            snapshot_id=snapshot_id,
            repo=repo,
            password=password or "",
            parent_dialog=parent_dialog,
        )
    
    def _format_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def _unmount_snapshot(self, mount_info):
        """Unmount a mounted repository"""
        try:
            mount_dir = mount_info['mount_dir']
            mount_process = mount_info['mount_process']
            use_drive_letter = mount_info.get('use_drive_letter', False)
            repo_name = mount_info.get('repo_name', 'repository')
            
            self.log(f"Unmounting '{repo_name}' from {mount_dir}...")
            
            # Stop the monitor thread if it exists
            if 'monitor_thread' in mount_info:
                monitor_thread = mount_info['monitor_thread']
                if monitor_thread.isRunning():
                    monitor_thread.stop()
                    monitor_thread.wait(2000)  # Wait up to 2 seconds
            
            # Terminate the mount process
            if mount_process and mount_process.poll() is None:
                mount_process.terminate()
                try:
                    mount_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    mount_process.kill()
            
            # Clean up mount directory (only if it's a temp directory, not a drive letter)
            time.sleep(1)  # Give it a moment to unmount
            if not use_drive_letter:
                try:
                    if os.path.exists(mount_dir):
                        shutil.rmtree(mount_dir)
                except Exception as e:
                    self.log(f"Warning: Could not remove mount directory: {e}")
            
            # Remove from tracked mounts
            if hasattr(self, '_mounted_snapshots'):
                if mount_info in self._mounted_snapshots:
                    self._mounted_snapshots.remove(mount_info)
            
            self.log(f"Repository '{repo_name}' unmounted successfully")
        
        except Exception as e:
            self.log(f"Error unmounting repository: {str(e)}")
    
    # Backup Job Management Methods
    def add_backup_job(self):
        """Add a new backup job"""
        dialog = BackupJobDialog(self, self.settings_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            job_data = dialog.get_job_data()
            
            # Validate job data
            if not job_data["name"]:
                QMessageBox.warning(self, "Invalid Job", "Please enter a job name.")
                return
            
            if not job_data["paths"]:
                QMessageBox.warning(self, "Invalid Job", "Please add at least one path to backup.")
                return
            
            # Check for duplicate names
            jobs = self.settings_manager.get("backup_jobs")
            if any(j["name"] == job_data["name"] for j in jobs):
                QMessageBox.warning(self, "Duplicate Job", f"A job named '{job_data['name']}' already exists.")
                return
            
            # Add job
            jobs.append(job_data)
            self.settings_manager.set("backup_jobs", jobs)
            self.settings_manager.save_settings()
            
            # Create scheduled task if scheduling is enabled
            if job_data.get("schedule", {}).get("enabled"):
                success, message = self.scheduler_manager.create_scheduled_task(job_data["name"], job_data)
                if success:
                    self.log(f"Created scheduled task for job: {job_data['name']}")
                else:
                    QMessageBox.warning(self, "Scheduling Error", 
                                      f"Job created, but failed to create scheduled task:\n{message}")
                    self.log(f"Failed to create scheduled task: {message}")
            
            self.refresh_backup_jobs_list()
            self.log(f"Added backup job: {job_data['name']}")
            QMessageBox.information(self, "Job Created", f"Backup job '{job_data['name']}' created successfully!")
    
    def edit_backup_job(self, job):
        """Edit an existing backup job"""
        dialog = BackupJobDialog(self, self.settings_manager, job)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            job_data = dialog.get_job_data()
            
            # Validate job data
            if not job_data["name"]:
                QMessageBox.warning(self, "Invalid Job", "Please enter a job name.")
                return
            
            if not job_data["paths"]:
                QMessageBox.warning(self, "Invalid Job", "Please add at least one path to backup.")
                return
            
            # Update job
            jobs = self.settings_manager.get("backup_jobs")
            old_job_name = job["name"]
            for i, j in enumerate(jobs):
                if j["name"] == old_job_name:
                    jobs[i] = job_data
                    break
            
            self.settings_manager.set("backup_jobs", jobs)
            self.settings_manager.save_settings()
            
            # Update scheduled task
            # First delete the old task (in case job name changed)
            if old_job_name != job_data["name"]:
                self.scheduler_manager.delete_scheduled_task(old_job_name)
            
            # Create/update scheduled task if scheduling is enabled
            if job_data.get("schedule", {}).get("enabled"):
                success, message = self.scheduler_manager.update_scheduled_task(job_data["name"], job_data)
                if success:
                    self.log(f"Updated scheduled task for job: {job_data['name']}")
                else:
                    QMessageBox.warning(self, "Scheduling Error", 
                                      f"Job updated, but failed to update scheduled task:\n{message}")
                    self.log(f"Failed to update scheduled task: {message}")
            else:
                # Delete scheduled task if scheduling was disabled
                self.scheduler_manager.delete_scheduled_task(job_data["name"])
            
            self.refresh_backup_jobs_list()
            if hasattr(self, "refresh_dashboard_jobs_table"):
                self.refresh_dashboard_jobs_table()
            self.log(f"Updated backup job: {job_data['name']}")
            QMessageBox.information(self, "Job Updated", f"Backup job '{job_data['name']}' updated successfully!")
    
    def delete_backup_job(self, job):
        """Delete a backup job"""
        reply = QMessageBox.question(
            self, "Delete Job",
            f"Are you sure you want to delete the backup job '{job['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete scheduled task first
            self.scheduler_manager.delete_scheduled_task(job["name"])
            
            jobs = self.settings_manager.get("backup_jobs")
            jobs = [j for j in jobs if j["name"] != job["name"]]
            self.settings_manager.set("backup_jobs", jobs)
            self.settings_manager.save_settings()
            self.refresh_backup_jobs_list()
            if hasattr(self, "refresh_dashboard_jobs_table"):
                self.refresh_dashboard_jobs_table()
            self.log(f"Deleted backup job and scheduled task: {job['name']}")
    
    def run_backup_job(self, job):
        """Run a backup job (supports multiple repositories)"""
        # Get repository/repositories list
        # Support both old format (single "repository") and new format (multiple "repositories")
        if "repositories" in job and job["repositories"]:
            repositories_to_backup = job["repositories"]
        elif "repository" in job:
            # Backwards compatibility with single repository
            repositories_to_backup = [job["repository"]]
        else:
            QMessageBox.warning(self, "No Repository", "No repository selected for this backup job.")
            return
        
        if not repositories_to_backup:
            QMessageBox.warning(self, "No Repository", "No repository selected for this backup job.")
            return
        
        # Initialize state for multi-repo backup
        self._current_repo_index = 0
        self._total_repos = len(repositories_to_backup)
        self._repositories_to_backup = repositories_to_backup
        self._backup_job = job
        self._backup_all_succeeded = True
        
        # Start first repository backup
        self._run_single_repository_backup(job, repositories_to_backup[0], 0)
    
    def _run_single_repository_backup(self, job, repo_name, repo_index):
        """Run backup for a single repository"""
        # Get repository
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            error_msg = f"Repository '{repo_name}' not found."
            QMessageBox.warning(self, "Repository Not Found", error_msg)
            self.log(error_msg)
            self._backup_all_succeeded = False
            self._record_job_run(
                job_name=job.get("name", ""),
                repo_name=repo_name,
                started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                duration_sec=0,
                success=False,
                exit_code=1,
                source="gui",
                error_summary=error_msg,
            )
            
            # Try next repository if any remain
            self._try_next_repository()
            return
        
        # Build restic backup command arguments
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "backup", "--json"]
        
        # Add paths
        args.extend(job["paths"])
        
        # Add tags
        if job.get("tags"):
            for tag in job["tags"]:
                args.extend(["--tag", tag])
        
        # Add exclude patterns
        if job.get("exclude_patterns"):
            for pattern in job["exclude_patterns"]:
                args.extend(["--exclude", pattern])
        
        # Add options
        if job.get("exclude_caches", True):
            args.append("--exclude-caches")
        
        if job.get("pack_size", 0) > 0:
            args.extend(["--pack-size", str(job["pack_size"])])
        
        if job.get("one_file_system", False):
            args.append("--one-file-system")
        
        if job.get("exclude_if_present"):
            args.extend(["--exclude-if-present", job["exclude_if_present"]])
        
        # Compression
        compression = job.get("compression", "auto")
        if compression and compression != "off":
            args.extend(["--compression", compression])
        
        # No cache
        if job.get("no_cache", False):
            args.append("--no-cache")
        
        # Ignore inode
        if job.get("ignore_inode", False):
            args.append("--ignore-inode")
        
        # Show progress dialog (create once for first repo, reuse for others)
        if not hasattr(self, '_backup_progress_dialog') or not self._backup_progress_dialog.isVisible():
            self._backup_progress_dialog = QDialog(self)
            self._backup_progress_dialog.setWindowTitle(f"Running Backup Job: {job['name']}")
            self._backup_progress_dialog.setModal(False)
            self._backup_progress_dialog.setMinimumWidth(500)
            self._backup_progress_dialog.setMinimumHeight(350)
            
            dialog_layout = QVBoxLayout()
            self._backup_progress_dialog.setLayout(dialog_layout)
            
            # Multi-repo progress indicator
            multi_repo_label = QLabel()
            dialog_layout.addWidget(multi_repo_label)
            self._multi_repo_label = multi_repo_label
            
            info_label = QLabel()
            dialog_layout.addWidget(info_label)
            self._backup_info_label = info_label
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            dialog_layout.addWidget(progress_bar)
            self._backup_progress_bar = progress_bar
            
            status_label = QLabel("Starting backup...")
            dialog_layout.addWidget(status_label)
            self._backup_status_label = status_label
            
            # Current file label
            current_file_label = QLabel("")
            current_file_label.setWordWrap(True)
            current_file_label.setMaximumHeight(40)
            dialog_layout.addWidget(current_file_label)
            self._backup_current_file_label = current_file_label
            
            output_text = QPlainTextEdit()
            output_text.setReadOnly(True)
            output_text.setStyleSheet(themes.STYLESHEET_SCROLL)
            dialog_layout.addWidget(output_text)
            self._backup_output_text = output_text
            
            # Buttons layout
            buttons_layout = QHBoxLayout()
            
            cancel_btn = QPushButton("Cancel Backup")
            cancel_btn.setToolTip("Cancel the running backup job. This will stop the backup and unlock the repository.")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.clicked.connect(lambda: self._cancel_backup())
            buttons_layout.addWidget(cancel_btn)
            self._backup_cancel_btn = cancel_btn
            
            buttons_layout.addStretch()
            
            close_btn = QPushButton("Close")
            close_btn.setEnabled(False)
            close_btn.setToolTip("Close this dialog. The backup will continue running in the background.")
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(self._backup_progress_dialog.close)
            buttons_layout.addWidget(close_btn)
            self._backup_close_btn = close_btn
            
            dialog_layout.addLayout(buttons_layout)
            
            # Override close event to warn about active backup
            def closeEvent(event):
                if hasattr(self, '_backup_worker') and self._backup_worker.isRunning():
                    reply = QMessageBox.question(
                        self._backup_progress_dialog,
                        "Backup In Progress",
                        "Backup is still running. Closing this window will not stop the backup.\n\n"
                        "The backup will continue in the background and locks will remain until completion.\n\n"
                        "Do you want to close anyway?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        event.ignore()
                        return
                event.accept()
            
            self._backup_progress_dialog.closeEvent = closeEvent
            
            self._backup_progress_dialog.show()
        
        # Update dialog for current repository
        if self._total_repos > 1:
            self._multi_repo_label.setText(f"ðŸ“¦ Repository {repo_index + 1} of {self._total_repos}")
            self._multi_repo_label.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 11pt;")
        else:
            self._multi_repo_label.setText("")
        
        self._backup_info_label.setText(
            f"Backup Job: {job['name']}\n"
            f"Repository: {repo_name}\n\n"
            f"Paths:\n" + "\n".join(f"  â€¢ {p}" for p in job["paths"])
        )
        
        self._backup_progress_bar.setValue(0)
        self._backup_status_label.setText("Starting backup...")
        self._backup_current_file_label.setText("")
        self._backup_close_btn.setEnabled(False)
        self._backup_cancel_btn.setEnabled(True)
        
        QApplication.processEvents()
        
        # Store repo info for callback
        self._backup_job_name = job['name']
        self._backup_repo = repo
        self._backup_repo_name = repo_name
        self._backup_repo_password = password
        self._backup_is_cancelled = False
        self._backup_started_at = time.time()
        self._backup_started_at_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        
        # Start backup
        backup_timeout = job.get("timeout", 7200)  # Default 2 hours if not set
        self.log(f"Starting backup job: {job['name']} â†’ Repository {repo_index + 1}/{self._total_repos}: {repo_name}") 
        self.log(f"Command: restic {' '.join(args)}")
        self.log(f"Timeout: {backup_timeout} seconds ({backup_timeout // 60} minutes)")
        
        self._backup_worker = ResticWorker(self.restic_cmd, args, env, timeout=backup_timeout, use_progress=True)
        self._backup_worker.finished.connect(self._on_backup_completed)
        self._backup_worker.progress_data.connect(self._on_backup_progress)
        self._backup_worker.progress.connect(self._on_backup_output)
        self._backup_worker.start()
    
    def _history_db_path(self) -> str:
        return history_db.history_db_path(self.settings_manager.filename)

    def _record_job_run(
        self,
        *,
        job_name: str,
        repo_name: str,
        started_at: str,
        duration_sec: Optional[float],
        success: bool,
        exit_code: Optional[int] = None,
        source: str = "gui",
        error_summary: Optional[str] = None,
        snapshot_short_id: Optional[str] = None,
    ) -> None:
        try:
            history_db.insert_job_run(
                job_name=job_name,
                repo_name=repo_name,
                started_at=started_at,
                duration_sec=duration_sec,
                success=success,
                exit_code=exit_code,
                source=source,
                error_summary=error_summary,
                snapshot_short_id=snapshot_short_id,
                db_path=self._history_db_path(),
            )
        except Exception as exc:
            if DEBUG_MODE:
                print(f"[HISTORY] Failed to record job run: {exc}")
    
    def _try_next_repository(self):
        """Try backing up to the next repository in the list"""
        if not hasattr(self, '_repositories_to_backup') or not hasattr(self, '_backup_job'):
            return
        
        self._current_repo_index += 1
        
        if self._current_repo_index < len(self._repositories_to_backup):
            # More repositories to backup
            next_repo = self._repositories_to_backup[self._current_repo_index]
            self._run_single_repository_backup(self._backup_job, next_repo, self._current_repo_index)
        else:
            # All repositories completed
            self.log(f"Backup job '{self._backup_job['name']}' completed for all {self._total_repos} repositories")
            if getattr(self, "_backup_all_succeeded", False):
                self._stamp_job_last_run(self._backup_job)
            elif hasattr(self, "refresh_dashboard_jobs_table"):
                self.refresh_dashboard_jobs_table()
            if hasattr(self, '_backup_close_btn'):
                self._backup_close_btn.setEnabled(True)
            if hasattr(self, '_backup_cancel_btn'):
                self._backup_cancel_btn.setEnabled(False)

    def _stamp_job_last_run(self, job) -> None:
        """Record last successful run time on the job for dashboard relative times."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        job["last_run"] = stamp
        if job.get("schedule") is None:
            job["schedule"] = {"enabled": False}
        job["schedule"]["last_run"] = stamp
        jobs = self.settings_manager.get("backup_jobs") or []
        for i, existing in enumerate(jobs):
            if existing.get("name") == job.get("name"):
                jobs[i] = job
                break
        self.settings_manager.set("backup_jobs", jobs)
        self.settings_manager.save_settings()
        if hasattr(self, "refresh_dashboard_jobs_table"):
            self.refresh_dashboard_jobs_table()
        if hasattr(self, "refresh_backup_jobs_list"):
            self.refresh_backup_jobs_list()
    
    def _cancel_backup(self):
        """Cancel the running backup"""
        if not hasattr(self, '_backup_worker') or not self._backup_worker.isRunning():
            return
        
        reply = QMessageBox.question(
            self._backup_progress_dialog,
            "Cancel Backup",
            "Are you sure you want to cancel this backup?\n\n"
            "The backup will be stopped and the repository will be unlocked.\n\n"
            "Any partial data may remain in the repository.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._backup_is_cancelled = True
            
            # Terminate the worker thread
            if hasattr(self, '_backup_worker'):
                self._backup_worker.terminate()
                self._backup_worker.wait(2000)  # Wait up to 2 seconds
                if self._backup_worker.isRunning():
                    self._backup_worker.terminate()  # Force terminate
            
            # Update UI
            if hasattr(self, '_backup_status_label'):
                self._backup_status_label.setText("âš  Backup cancelled by user")
            
            if hasattr(self, '_backup_progress_bar'):
                self._backup_progress_bar.setRange(0, 100)
                self._backup_progress_bar.setValue(0)
            
            if hasattr(self, '_backup_cancel_btn'):
                self._backup_cancel_btn.setEnabled(False)
            
            if hasattr(self, '_backup_close_btn'):
                self._backup_close_btn.setEnabled(True)
            
            self.log(f"Backup job '{self._backup_job_name}' cancelled by user")
            
            # Auto-unlock the repository
            self._auto_unlock_after_cancel()
    
    def _auto_unlock_after_cancel(self):
        """Automatically unlock repository after backup cancellation"""
        if not hasattr(self, '_backup_repo') or not hasattr(self, '_backup_repo_password'):
            return
        
        self.log(f"Auto-unlocking repository after cancellation...")
        
        # Execute unlock command in background
        env = {"RESTIC_PASSWORD": self._backup_repo_password} if self._backup_repo_password else {}
        args = ["-r", self._backup_repo["path"], "unlock"]
        
        unlock_worker = ResticWorker(self.restic_cmd, args, env, timeout=30)
        unlock_worker.finished.connect(lambda success, stdout, stderr: self._on_auto_unlock_completed(success, stderr, "cancel"))
        unlock_worker.start()
        
        # Store reference to prevent garbage collection
        self._cancel_unlock_worker = unlock_worker
    
    def _on_backup_progress(self, progress_info):
        """Callback for backup progress updates"""
        if not hasattr(self, '_backup_progress_bar'):
            return
        
        # Throttle updates to prevent UI freezing (max 10 updates per second)
        import time
        current_time = time.time()
        if hasattr(self, '_last_progress_update'):
            if current_time - self._last_progress_update < 0.1:
                return
        self._last_progress_update = current_time
        
        # Update progress bar
        percent = progress_info.get('percent', 0)
        self._backup_progress_bar.setValue(int(percent))
        
        # Format status message
        files_done = progress_info.get('files_done', 0)
        total_files = progress_info.get('total_files', 0)
        bytes_done = progress_info.get('bytes_done', 0)
        total_bytes = progress_info.get('total_bytes', 0)
        eta = progress_info.get('eta', 0)
        
        # Format bytes to human readable
        def format_bytes(b):
            if b < 1024:
                return f"{b} B"
            elif b < 1024**2:
                return f"{b/1024:.1f} KB"
            elif b < 1024**3:
                return f"{b/1024**2:.1f} MB"
            else:
                return f"{b/1024**3:.2f} GB"
        
        # Format ETA
        def format_time(seconds):
            if seconds < 60:
                return f"{int(seconds)}s"
            elif seconds < 3600:
                mins = int(seconds / 60)
                secs = int(seconds % 60)
                return f"{mins}m {secs}s"
            else:
                hours = int(seconds / 3600)
                mins = int((seconds % 3600) / 60)
                return f"{hours}h {mins}m"
        
        status_text = f"Progress: {percent:.1f}% | Files: {files_done}/{total_files} | "
        status_text += f"Size: {format_bytes(bytes_done)}/{format_bytes(total_bytes)}"
        
        if eta > 0:
            status_text += f" | ETA: {format_time(eta)}"
        
        self._backup_status_label.setText(status_text)
        
        # Show current files being processed
        current_files = progress_info.get('current_files', [])
        if current_files:
            # Show just the first file (or up to 2)
            file_text = "Processing: " + current_files[0]
            if len(current_files) > 1:
                file_text += f" (+{len(current_files)-1} more)"
            self._backup_current_file_label.setText(file_text)
        
        # Force UI update
        QApplication.processEvents()
    
    def _on_backup_output(self, line: str):
        """Callback for raw output lines during backup"""
        if not hasattr(self, '_backup_output_text'):
            return
        
        # Always append the line (don't lose any output)
        self._backup_output_text.appendPlainText(line)
        
        # Throttle scrolling to prevent UI overwhelming (max 20 scrolls per second)
        import time
        current_time = time.time()
        if not hasattr(self, '_last_output_scroll') or (current_time - self._last_output_scroll) >= 0.05:
            self._last_output_scroll = current_time
            # Auto-scroll to bottom to show latest output
            scrollbar = self._backup_output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_backup_completed(self, success, stdout, stderr):
        """Callback when backup completes"""
        # Don't process if cancelled
        if hasattr(self, '_backup_is_cancelled') and self._backup_is_cancelled:
            return

        started_mono = getattr(self, "_backup_started_at", None)
        duration_sec = (time.time() - started_mono) if started_mono is not None else None
        started_iso = getattr(self, "_backup_started_at_iso", None) or datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S")
        error_summary = None if success else ((stderr or stdout or "Unknown error")[:500])
        snap_id = history_db.extract_snapshot_short_id(stdout or "") if success else None
        self._record_job_run(
            job_name=getattr(self, "_backup_job_name", "") or "",
            repo_name=getattr(self, "_backup_repo_name", "") or "",
            started_at=started_iso,
            duration_sec=duration_sec,
            success=bool(success),
            exit_code=0 if success else 1,
            source="gui",
            error_summary=error_summary,
            snapshot_short_id=snap_id,
        )
        if not success:
            self._backup_all_succeeded = False
        
        # Update dialog
        if hasattr(self, '_backup_progress_bar'):
            self._backup_progress_bar.setRange(0, 100)
            self._backup_progress_bar.setValue(100)
        
        # Add completion message to output (output already displayed dynamically)
        if hasattr(self, '_backup_output_text'):
            self._backup_output_text.appendPlainText("")
            self._backup_output_text.appendPlainText("=" * 60)
            if success:
                self._backup_output_text.appendPlainText(f"✓ Backup to '{self._backup_repo_name}' completed successfully!")
            else:
                self._backup_output_text.appendPlainText(f"✗ Backup to '{self._backup_repo_name}' failed!")
            self._backup_output_text.appendPlainText("=" * 60)
            # Auto-scroll to bottom
            scrollbar = self._backup_output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        if success:
            if hasattr(self, '_backup_status_label'):
                self._backup_status_label.setText(f"✓ Backup to '{self._backup_repo_name}' completed successfully!")
            
            self.log(f"Backup job '{self._backup_job_name}' â†’ '{self._backup_repo_name}' completed successfully")
            
            # Show success notification
            show_notification(
                title="Backup Completed Successfully ✓",
                message=f"Backup job '{self._backup_job_name}' to '{self._backup_repo_name}' completed successfully.",
                icon_type="success",
                duration="short"
            )
            
            # Auto-unlock if locks exist (check and unlock)
            self._auto_unlock_after_completion()
            
            # Refresh snapshots if on snapshots page
            if hasattr(self, 'snapshots_table'):
                QTimer.singleShot(1000, self.load_snapshots)
        else:
            if hasattr(self, '_backup_status_label'):
                self._backup_status_label.setText(f"✗ Backup to '{self._backup_repo_name}' failed!")
            
            error_msg = stderr if stderr else "Unknown error"
            self.log(f"Backup job '{self._backup_job_name}' â†’ '{self._backup_repo_name}' failed: {error_msg}")
            
            # Show failure notification
            show_notification(
                title="Backup Failed ✗",
                message=f"Backup job '{self._backup_job_name}' to '{self._backup_repo_name}' failed. Check logs for details.",
                icon_type="error",
                duration="long"
            )
            
            # Also try to unlock on failure in case lock is stuck
            if "locked" in error_msg.lower():
                self._auto_unlock_after_completion()
        
        # Try next repository if any remain (for multi-repo backups)
        # Use QTimer to give UI a chance to update before starting next backup
        QTimer.singleShot(500, self._try_next_repository)
    
    def _auto_unlock_after_completion(self):
        """Automatically check and unlock repository if locks exist"""
        if not hasattr(self, '_backup_repo') or not hasattr(self, '_backup_repo_password'):
            return
        
        # First check if there are any locks
        env = {"RESTIC_PASSWORD": self._backup_repo_password} if self._backup_repo_password else {}
        args = ["-r", self._backup_repo["path"], "list", "locks"]
        
        check_worker = ResticWorker(self.restic_cmd, args, env, timeout=15)
        check_worker.finished.connect(self._on_lock_check_completed)
        check_worker.start()
        
        # Store reference
        self._lock_check_worker = check_worker
    
    def _on_lock_check_completed(self, success, stdout, stderr):
        """Check if locks exist and unlock if needed"""
        # If there are locks listed, unlock them
        if success and stdout and stdout.strip():
            self.log(f"Stale locks detected, auto-unlocking repository...")
            
            env = {"RESTIC_PASSWORD": self._backup_repo_password} if self._backup_repo_password else {}
            args = ["-r", self._backup_repo["path"], "unlock"]
            
            unlock_worker = ResticWorker(self.restic_cmd, args, env, timeout=30)
            unlock_worker.finished.connect(lambda success, stdout, stderr: self._on_auto_unlock_completed(success, stderr, "completion"))
            unlock_worker.start()
            
            # Store reference
            self._auto_unlock_worker = unlock_worker
    
    def _on_auto_unlock_completed(self, success, stderr, context):
        """Callback when auto-unlock completes"""
        if success:
            self.log(f"Repository auto-unlocked after backup {context}")
        else:
            # Only log error, don't show message box since this is automatic
            if stderr:
                self.log(f"Auto-unlock after {context} failed: {stderr}")
    
    
    # Retention Methods
    def _on_retention_frequency_changed(self, frequency):
        """Toggle between day of week and day of month based on frequency"""
        is_weekly = frequency == "Weekly"
        is_monthly = frequency == "Monthly"
        
        # Show/hide day of week
        if hasattr(self, 'retention_day_combo') and hasattr(self, '_retention_schedule_form'):
            self.retention_day_combo.setVisible(is_weekly)
            label = self._retention_schedule_form.labelForField(self.retention_day_combo)
            if label:
                label.setVisible(is_weekly)
        
        # Show/hide day of month
        if hasattr(self, 'retention_dom_spin') and hasattr(self, '_retention_schedule_form'):
            self.retention_dom_spin.setVisible(is_monthly)
            label = self._retention_schedule_form.labelForField(self.retention_dom_spin)
            if label:
                label.setVisible(is_monthly)
    
    def _get_retention_command_args(self):
        """Build restic forget command arguments from retention settings"""
        args = []
        
        # Add keep policies
        if self.keep_last_spin.value() > 0:
            args.extend(["--keep-last", str(self.keep_last_spin.value())])
        if self.keep_hourly_spin.value() > 0:
            args.extend(["--keep-hourly", str(self.keep_hourly_spin.value())])
        if self.keep_daily_spin.value() > 0:
            args.extend(["--keep-daily", str(self.keep_daily_spin.value())])
        if self.keep_weekly_spin.value() > 0:
            args.extend(["--keep-weekly", str(self.keep_weekly_spin.value())])
        if self.keep_monthly_spin.value() > 0:
            args.extend(["--keep-monthly", str(self.keep_monthly_spin.value())])
        if self.keep_yearly_spin.value() > 0:
            args.extend(["--keep-yearly", str(self.keep_yearly_spin.value())])
        
        # Add prune flag
        args.append("--prune")
        
        return args
    
    def _get_current_retention_repo(self):
        """Get current retention repository name (clean, without task indicator)"""
        # Get userData which has the clean repo name (without checkmark)
        current_index = self.retention_repo_combo.currentIndex()
        if current_index >= 0:
            repo_name = self.retention_repo_combo.itemData(current_index)
            if repo_name:
                return repo_name
        # Fallback to text and strip indicator
        text = self.retention_repo_combo.currentText()
        return text.replace(" ✓", "").strip() if text else ""
    
    def create_retention_scheduled_task(self):
        """Create a scheduled task for retention policy"""
        repo_name = self._get_current_retention_repo()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Repository Not Found", f"Repository '{repo_name}' not found")
            return
        
        # Validate at least one retention policy is set
        command_args = self._get_retention_command_args()
        if len(command_args) == 1:  # Only --prune, no keep policies
            QMessageBox.warning(
                self, 
                "No Retention Policies", 
                "Please configure at least one retention policy (Keep Last, Daily, Weekly, etc.)"
            )
            return
        
        # Get schedule settings
        frequency = self.retention_frequency_combo.currentText()
        time = self.retention_time_edit.time()
        day_of_week = self.retention_day_combo.currentText()
        day_of_month = self.retention_dom_spin.value()
        
        # Build task name
        task_name = f"ResticRetention_{repo_name.replace(' ', '_')}"
        
        # Determine platform
        import platform
        system = platform.system()
        
        if system == "Windows":
            success = self._create_windows_scheduled_task(
                task_name, repo, password, command_args, 
                frequency, time, day_of_week, day_of_month
            )
        elif system == "Linux":
            success = self._create_linux_cron_job(
                task_name, repo, password, command_args,
                frequency, time, day_of_week, day_of_month
            )
        elif system == "Darwin":  # macOS
            success = self._create_macos_launchd(
                task_name, repo, password, command_args,
                frequency, time, day_of_week, day_of_month
            )
        else:
            QMessageBox.warning(self, "Unsupported Platform", f"Scheduled tasks not supported on {system}")
            return
        
        if success:
            self.log(f"Created scheduled task: {task_name}")
            # Refresh repo combo to show task indicator
            self.update_retention_repo_combo()
    
    def _create_windows_scheduled_task(self, task_name, repo, password, command_args, frequency, time, day_of_week, day_of_month):
        """Create Windows Task Scheduler task"""
        import subprocess
        
        # Build restic command arguments
        restic_cmd = self.restic_cmd
        
        # Save PowerShell script to scheduled_tasks folder (same as backup jobs)
        import os
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduled_tasks")
        os.makedirs(script_dir, exist_ok=True)
        script_path = os.path.join(script_dir, f"{task_name}.ps1")
        
        # Create encrypted password file using Windows DPAPI (same as backup jobs)
        password_file = os.path.join(script_dir, f"{task_name}.password")
        if password:
            # Use PowerShell to encrypt the password with DPAPI
            ps_encrypt_cmd = f'''
$password = ConvertTo-SecureString -String "{password}" -AsPlainText -Force
$password | ConvertFrom-SecureString | Out-File -FilePath "{password_file}" -Encoding utf8
'''
            try:
                result = subprocess.run(
                    ["powershell.exe", "-Command", ps_encrypt_cmd],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=get_subprocess_creation_flags()
                )
                if result.returncode != 0:
                    QMessageBox.critical(self, "Password Encryption Failed", f"Failed to encrypt password:\n{result.stderr}")
                    return False
            except Exception as e:
                QMessageBox.critical(self, "Password Encryption Failed", f"Error encrypting password:\n{str(e)}")
                return False
        
        # Build PowerShell script content with encrypted password loading
        ps_script = f"""# Restic Retention Task - {repo['name']}
# Generated by Restic Manager

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to show Windows toast notification
function Show-ToastNotification {{
    param(
        [string]$Title,
        [string]$Message
    )
    
    try {{
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $toastXml = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">$Title</text>
            <text id="2">$Message</text>
        </binding>
    </visual>
    <audio src="ms-winsoundevent:Notification.Default"/>
</toast>
"@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($toastXml)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Restic Backup Manager").Show($toast)
    }} catch {{
        # Silently fail if notification fails
        Write-Host "Note: Could not show toast notification"
    }}
}}

# Load and decrypt repository password from encrypted file
$passwordFile = "{password_file}"
if (Test-Path $passwordFile) {{
    $securePassword = Get-Content $passwordFile | ConvertTo-SecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $env:RESTIC_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}} else {{
    Write-Host "Error: Password file not found: $passwordFile"
    Show-ToastNotification "Retention Failed" "Password file not found for repository: {repo['name']}"
    exit 1
}}

# Run restic retention/forget command
Write-Host "Starting retention policy for repository: {repo['name']}"
Write-Host "Repository: {repo['path']}"

try {{
    & "{restic_cmd}" -r "{repo['path']}" forget {" ".join(command_args)}
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {{
        Write-Host "Retention policy applied successfully"
        Show-ToastNotification "Retention Completed ✓" "Repository '{repo['name']}' retention policy applied successfully"
        exit 0
    }} else {{
        Write-Host "Retention policy failed with exit code: $exitCode"
        Show-ToastNotification "Retention Failed ✗" "Repository '{repo['name']}' failed with exit code: $exitCode"
        exit $exitCode
    }}
}} catch {{
    Write-Host "Error running retention policy: $_"
    Show-ToastNotification "Retention Failed ✗" "Repository '{repo['name']}' error: $_"
    exit 1
}} finally {{
    # Clear password from environment
    Remove-Item env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
}}
"""
        
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(ps_script)
        except Exception as e:
            QMessageBox.critical(self, "Script Creation Failed", f"Failed to create PowerShell script:\n{e}")
            return False
        
        # Build schtasks command
        hour = time.hour()
        minute = time.minute()
        start_time = f"{hour:02d}:{minute:02d}"
        
        # Build schedule parameters
        if frequency == "Daily":
            schedule_params = f'/SC DAILY /ST {start_time}'
        elif frequency == "Weekly":
            day_map = {"Sunday": "SUN", "Monday": "MON", "Tuesday": "TUE", 
                      "Wednesday": "WED", "Thursday": "THU", "Friday": "FRI", "Saturday": "SAT"}
            schedule_params = f'/SC WEEKLY /D {day_map[day_of_week]} /ST {start_time}'
        elif frequency == "Monthly":
            schedule_params = f'/SC MONTHLY /D {day_of_month} /ST {start_time}'
        else:
            schedule_params = f'/SC DAILY /ST {start_time}'
        
        # Create task using schtasks
        schtasks_cmd = [
            'schtasks', '/Create',
            '/TN', task_name,
            '/TR', f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"',
            '/F',  # Force create (overwrite if exists)
        ] + schedule_params.split()
        
        try:
            result = subprocess.run(schtasks_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                password_note = " (password encrypted with DPAPI)" if password else ""
                QMessageBox.information(
                    self,
                    "Task Created Successfully",
                    f"Scheduled task '{task_name}' created successfully{password_note}!\n\n"
                    f"Schedule: {frequency} at {start_time}\n"
                    f"Repository: {repo['name']}\n\n"
                    f"Script location: {script_path}\n\n"
                    f"You can view/manage it in Task Scheduler."
                )
                return True
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                QMessageBox.critical(
                    self,
                    "Task Creation Failed",
                    f"Failed to create scheduled task:\n\n{error_msg}"
                )
                return False
        except Exception as e:
            QMessageBox.critical(self, "Task Creation Failed", f"Error creating scheduled task:\n{e}")
            return False
    
    def _create_linux_cron_job(self, task_name, repo, password, command_args, frequency, time, day_of_week, day_of_month):
        """Create Linux cron job"""
        import subprocess
        
        # Build restic command
        full_command = f'RESTIC_PASSWORD="{password}" {self.restic_cmd} -r "{repo["path"]}" forget {" ".join(command_args)}'
        
        # Build cron schedule
        hour = time.hour()
        minute = time.minute()
        
        if frequency == "Daily":
            cron_schedule = f"{minute} {hour} * * *"
        elif frequency == "Weekly":
            day_map = {"Sunday": "0", "Monday": "1", "Tuesday": "2", 
                      "Wednesday": "3", "Thursday": "4", "Friday": "5", "Saturday": "6"}
            cron_schedule = f"{minute} {hour} * * {day_map[day_of_week]}"
        elif frequency == "Monthly":
            cron_schedule = f"{minute} {hour} {day_of_month} * *"
        else:
            cron_schedule = f"{minute} {hour} * * *"
        
        # Build cron entry with comment
        cron_entry = f"# {task_name}\n{cron_schedule} {full_command}\n"
        
        # Show cron entry to user for manual addition
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Cron Job Configuration")
        msg.setText("Add the following line to your crontab:\n\n(Run 'crontab -e' in terminal)")
        msg.setDetailedText(cron_entry)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add copy button
        copy_btn = msg.addButton("Copy to Clipboard", QMessageBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(cron_entry))
        
        msg.exec()
        
        self.log(f"Cron job details provided for {task_name}")
        return True
    
    def _create_macos_launchd(self, task_name, repo, password, command_args, frequency, time, day_of_week, day_of_month):
        """Create macOS launchd plist"""
        # Similar to Linux - provide instructions for manual setup
        full_command = f'RESTIC_PASSWORD="{password}" {self.restic_cmd} -r "{repo["path"]}" forget {" ".join(command_args)}'
        
        hour = time.hour()
        minute = time.minute()
        
        # Build launchd plist
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.restic.{task_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>{full_command}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
</dict>
</plist>
"""
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("LaunchAgent Configuration")
        msg.setText(f"Save the following as:\n~/Library/LaunchAgents/com.restic.{task_name}.plist\n\nThen run:\nlaunchctl load ~/Library/LaunchAgents/com.restic.{task_name}.plist")
        msg.setDetailedText(plist_content)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        copy_btn = msg.addButton("Copy to Clipboard", QMessageBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(plist_content))
        
        msg.exec()
        
        self.log(f"LaunchAgent details provided for {task_name}")
        return True
    
    def open_task_scheduler(self):
        """Open Task Scheduler GUI"""
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == "Windows":
                os.startfile('taskschd.msc')
                self.log("Opened Task Scheduler")
            elif system == "Linux":
                # Try various cron GUIs
                for cmd in ['gnome-schedule', 'kcron', 'crontab -e']:
                    try:
                        if ' ' in cmd:
                            subprocess.Popen(cmd.split())
                        else:
                            subprocess.Popen([cmd])
                        self.log(f"Opened cron editor: {cmd}")
                        return
                    except:
                        continue
                QMessageBox.information(self, "No GUI Available", "Please use 'crontab -e' in terminal to manage cron jobs")
            elif system == "Darwin":
                QMessageBox.information(self, "No GUI Available", "Please manage LaunchAgents manually in ~/Library/LaunchAgents/")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open task scheduler:\n{e}")
    
    def delete_retention_scheduled_task(self):
        """Delete scheduled retention task"""
        repo_name = self._get_current_retention_repo()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        task_name = f"ResticRetention_{repo_name.replace(' ', '_')}"
        
        reply = QMessageBox.question(
            self,
            "Delete Scheduled Task",
            f"Delete scheduled task '{task_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == "Windows":
                result = subprocess.run(
                    ['schtasks', '/Delete', '/TN', task_name, '/F'],
                    capture_output=True, text=True, timeout=10,
                    creationflags=get_subprocess_creation_flags()
                )
                if result.returncode == 0:
                    # Also delete the PowerShell script and password file
                    import os
                    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduled_tasks")
                    script_file = os.path.join(script_dir, f"{task_name}.ps1")
                    password_file = os.path.join(script_dir, f"{task_name}.password")
                    
                    files_deleted = []
                    if os.path.exists(script_file):
                        os.remove(script_file)
                        files_deleted.append(".ps1")
                    if os.path.exists(password_file):
                        os.remove(password_file)
                        files_deleted.append(".password")
                    
                    files_msg = f" (also removed {', '.join(files_deleted)} files)" if files_deleted else ""
                    QMessageBox.information(self, "Task Deleted", f"Scheduled task '{task_name}' deleted successfully{files_msg}")
                    self.log(f"Deleted scheduled task: {task_name}{files_msg}")
                    
                    # Refresh the repository combo to update indicators
                    self.update_retention_repo_combo()
                else:
                    error_msg = result.stderr if result.stderr else "Task not found"
                    QMessageBox.warning(self, "Delete Failed", f"Failed to delete task:\n{error_msg}")
            else:
                QMessageBox.information(
                    self, 
                    "Manual Deletion Required", 
                    f"Please manually remove the cron job for '{task_name}'\n\nRun: crontab -e"
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to delete task:\n{e}")
    
    def apply_retention(self, dry_run=True):
        """Apply retention policy"""
        repo_name = self._get_current_retention_repo()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Repository Not Found", f"Repository '{repo_name}' not found")
            return
        
        # Get retention command arguments
        command_args = self._get_retention_command_args()
        
        # Check if at least one retention policy is set
        if len(command_args) == 1:  # Only --prune, no keep policies
            QMessageBox.warning(
                self, 
                "No Retention Policies", 
                "Please configure at least one retention policy (Keep Last, Daily, Weekly, etc.)"
            )
            return
        
        # Add dry-run flag if preview mode
        if dry_run:
            command_args.append("--dry-run")
        
        mode_text = "Preview" if dry_run else "Applying"
        self.log(f"{mode_text} retention policy for {repo_name}")
        
        # Show initial message
        self.retention_output.setPlainText(
            f"{mode_text} retention policy...\n\n"
            f"Repository: {repo['name']}\n"
            f"Path: {repo['path']}\n"
            f"Command: restic forget {' '.join(command_args)}\n\n"
            f"Running...\n"
        )
        QApplication.processEvents()
        
        # Execute restic forget command
        try:
            result = self.restic_cmd.forget(
                repo_path=repo["path"],
                password=password,
                args=command_args
            )
            
            if result:
                output_text = (
                    f"{'✓' if not dry_run else 'ℹ'} {mode_text} completed successfully!\n\n"
                    f"Repository: {repo['name']}\n"
                    f"Path: {repo['path']}\n"
                    f"Command: restic forget {' '.join(command_args)}\n\n"
                    f"{'--- DRY RUN MODE (No changes made) ---' if dry_run else '--- CHANGES APPLIED ---'}\n\n"
                    f"{result}\n"
                )
                self.retention_output.setPlainText(output_text)
                
                if dry_run:
                    self.log(f"Retention policy preview completed for {repo_name}")
                else:
                    self.log(f"Retention policy applied successfully for {repo_name}")
                    QMessageBox.information(
                        self,
                        "Policy Applied",
                        f"Retention policy applied successfully to '{repo_name}'!\n\n"
                        f"Check the output below for details."
                    )
            else:
                error_msg = "Failed to run retention policy. Check logs for details."
                self.retention_output.setPlainText(
                    f"✗ Error {mode_text.lower()} retention policy\n\n"
                    f"Repository: {repo['name']}\n\n"
                    f"{error_msg}"
                )
                self.log(f"Error applying retention policy: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            self.retention_output.setPlainText(
                f"✗ Error {mode_text.lower()} retention policy\n\n"
                f"Repository: {repo['name']}\n\n"
                f"Error: {error_msg}"
            )
            self.log(f"Error applying retention policy: {error_msg}")
            QMessageBox.critical(
                self,
                "Retention Error",
                f"Failed to apply retention policy:\n\n{error_msg}"
            )
    
    # Settings Methods
    def browse_restic_path(self):
        """Browse for Restic executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Restic Executable", "", 
            "Executable Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self.restic_path_input.setText(file_path)
    
    def test_restic_path(self):
        """Test if the restic executable is accessible and working"""
        restic_path = self.restic_path_input.text().strip()
        if not restic_path:
            QMessageBox.warning(self, "No Path", "Please enter a restic path first")
            return
        
        # Create temporary ResticCommand with the test path
        test_cmd = ResticCommand(restic_path=restic_path, debug=False)
        
        # Try to get version
        version = test_cmd.version()
        
        if version:
            QMessageBox.information(
                self, 
                "Restic Found",
                f"âœ… Restic executable is working!\n\n"
                f"Path: {restic_path}\n"
                f"Version: {version}\n\n"
                f"You can now save settings to use this path."
            )
            self.log(f"Restic test successful: {version}")
        else:
            QMessageBox.warning(
                self,
                "Restic Not Found",
                f"âŒ Failed to execute restic from this path.\n\n"
                f"Path: {restic_path}\n\n"
                f"Please check:\n"
                f"â€¢ The path is correct\n"
                f"â€¢ The file exists and is executable\n"
                f"â€¢ Restic is installed\n\n"
                f"For Windows: Try 'restic' if it's in your PATH,\n"
                f"or provide the full path like 'C:\\Program Files\\restic\\restic.exe'"
            )
            self.log(f"Restic test failed for path: {restic_path}")
    
    def browse_temp_restore_path(self):
        """Browse for temporary restore directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Temporary Restore Directory"
        )
        if directory:
            self.temp_restore_path_input.setText(directory)
    
    def change_theme(self, theme):
        """Change application theme"""
        self.apply_theme(theme)
    
    def save_settings(self):
        """Save application settings"""
        self.settings_manager.set("restic_path", self.restic_path_input.text())
        theme_id = themes.resolve_theme_id(self.theme_combo.currentText())
        self.settings_manager.set("theme", theme_id)
        self.settings_manager.set("auto_refresh_snapshots", self.auto_refresh_check.isChecked())
        self.settings_manager.set("snapshot_refresh_interval", self.refresh_interval_spin.value())
        self.settings_manager.set("temp_restore_path", self.temp_restore_path_input.text())
        
        self.settings_manager.save_settings()
        
        # Update Restic command
        self.restic_cmd = ResticCommand(
            restic_path=self.settings_manager.get("restic_path"),
            debug=DEBUG_MODE
        )
        
        QMessageBox.information(self, "Success", "Settings saved successfully!")
        self.log("Settings saved")
    
    def set_app_password(self):
        """Set or change application password"""
        # Check if password already exists
        has_password = False
        stored_hash = None
        stored_salt = None
        
        if sys.platform == "win32":
            # Windows: Registry only
            stored_hash = retrieve_from_registry("AppPasswordHash")
            stored_salt = retrieve_from_registry("AppPasswordSalt")
            if stored_hash and stored_salt:
                has_password = True
        else:
            # Non-Windows: JSON storage
            stored_hash = self.settings_manager.get("app_password_hash")
            stored_salt = self.settings_manager.get("app_password_salt")
            if stored_hash and stored_salt:
                has_password = True
        
        # If password already exists, verify old password first
        if has_password:
            old_password, ok = QInputDialog.getText(
                self,
                "Verify Current Password",
                "Enter your current password:",
                QLineEdit.EchoMode.Password
            )
            
            if not ok:
                return
            
            # Verify old password
            
            if not verify_app_password(old_password, stored_hash, stored_salt):
                QMessageBox.warning(self, "Incorrect Password", "The current password you entered is incorrect.")
                return
        
        # Ask for new password
        new_password, ok = QInputDialog.getText(
            self,
            "Set Application Password",
            "Enter a new password for the application:\n(Minimum 8 characters)",
            QLineEdit.EchoMode.Password
        )
        
        if not ok or not new_password:
            return
        
        # Validate password length
        if len(new_password) < 8:
            QMessageBox.warning(self, "Password Too Short", "Password must be at least 8 characters long.")
            return
        
        # Confirm new password
        confirm_password, ok = QInputDialog.getText(
            self,
            "Confirm Password",
            "Confirm the new password:",
            QLineEdit.EchoMode.Password
        )
        
        if not ok or new_password != confirm_password:
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match!")
            return
        
        # Hash the password
        pwd_hash, pwd_salt = hash_app_password(new_password)
        
        # Store password
        if sys.platform == "win32":
            # Windows: Registry only
            store_in_registry("AppPasswordHash", pwd_hash)
            store_in_registry("AppPasswordSalt", pwd_salt)
            storage_location = "Windows Registry (HKCU\\Software\\ResticManager)"
        else:
            # Non-Windows: JSON storage
            self.settings_manager.set("app_password_hash", pwd_hash)
            self.settings_manager.set("app_password_salt", pwd_salt)
            self.settings_manager.save_settings()
            storage_location = "Settings file"
        
        # Update UI
        self.set_password_btn.setText("Change Password")
        self.remove_password_btn.setEnabled(True)
        status_suffix = " (Registry)" if sys.platform == "win32" else " (Settings file)"
        self.password_status_label.setText(f"🔒 ACTIVE")
        self.password_status_label.setStyleSheet("color: green; font-weight: bold;")
        
        QMessageBox.information(
            self,
            "Password Set Successfully",
            f"Your application password has been set successfully.\n\n"
            f"Storage location: {storage_location}\n\n"
            f"This password will be required the next time you start the application."
        )
        self.log(f"Application password updated (stored in {storage_location})")
    
    def remove_app_password(self):
        """Remove application password protection (requires authentication)"""
        # Retrieve current password from storage
        stored_hash = None
        stored_salt = None
        
        if sys.platform == "win32":
            # Windows: Registry only
            stored_hash = retrieve_from_registry("AppPasswordHash")
            stored_salt = retrieve_from_registry("AppPasswordSalt")
        else:
            # Non-Windows: JSON storage
            stored_hash = self.settings_manager.get("app_password_hash")
            stored_salt = self.settings_manager.get("app_password_salt")
        
        if not stored_hash or not stored_salt:
            QMessageBox.information(self, "No Password Set", "No password is currently set.")
            return
        
        current_password, ok = QInputDialog.getText(
            self,
            "Verify Password",
            "Enter your current password to remove password protection:",
            QLineEdit.EchoMode.Password
        )
        
        if not ok:
            return
        
        # Verify password
        if not verify_app_password(current_password, stored_hash, stored_salt):
            QMessageBox.warning(self, "Incorrect Password", "The password you entered is incorrect.")
            return
        
        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Confirm Password Removal",
            "Are you sure you want to remove password protection?\n\n"
            "The application will no longer require a password at startup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Remove password from storage
        if sys.platform == "win32":
            # Windows: Registry only
            delete_from_registry("AppPasswordHash")
            delete_from_registry("AppPasswordSalt")
        else:
            # Non-Windows: JSON storage
            self.settings_manager.set("app_password_hash", "")
            self.settings_manager.set("app_password_salt", "")
            self.settings_manager.save_settings()
        
        # Update UI
        self.set_password_btn.setText("Set Password")
        self.remove_password_btn.setEnabled(False)
        self.password_status_label.setText("🔓 INACTIVE")
        self.password_status_label.setStyleSheet("color: orange; font-weight: bold;")
        
        QMessageBox.information(
            self,
            "Password Removed",
            "Password protection has been removed successfully.\n\n"
            "The application will no longer require a password at startup."
        )
        storage_type = "Registry" if sys.platform == "win32" else "Settings file"
        self.log(f"Application password removed from {storage_type}")
    
    def backup_settings(self):
        """Backup settings to an encrypted file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Backup Settings", 
            f"restic_settings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.encrypted",
            "Encrypted Files (*.encrypted);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # Get current settings as JSON
            settings_json = json.dumps(self.settings_manager.settings, indent=4)
            
            # Encrypt the settings using Fernet
            from cryptography.fernet import Fernet
            import base64
            import hashlib
            
            # Ask for encryption password
            password, ok = QInputDialog.getText(
                self, "Encryption Password", 
                "Enter a password to encrypt the backup:",
                QLineEdit.EchoMode.Password
            )
            
            if not ok or not password:
                return
            
            # Confirm password
            password_confirm, ok = QInputDialog.getText(
                self, "Confirm Password", 
                "Confirm the encryption password:",
                QLineEdit.EchoMode.Password
            )
            
            if not ok or password != password_confirm:
                QMessageBox.warning(self, "Password Mismatch", "Passwords do not match!")
                return
            
            # Derive key from password
            key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
            cipher = Fernet(key)
            
            # Encrypt the settings
            encrypted_data = cipher.encrypt(settings_json.encode())
            
            # Save to file
            with open(file_path, 'wb') as f:
                f.write(encrypted_data)
            
            QMessageBox.information(self, "Backup Complete", 
                f"Settings backed up successfully to:\n{file_path}")
            self.log(f"Settings backed up to {file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "Backup Failed", f"Failed to backup settings:\n{e}")
            self.log(f"Settings backup failed: {e}")
    
    def restore_settings(self):
        """Restore settings from an encrypted backup file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Restore Settings",
            "",
            "Encrypted Files (*.encrypted);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # Read encrypted file
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Ask for decryption password
            password, ok = QInputDialog.getText(
                self, "Decryption Password", 
                "Enter the password to decrypt the backup:",
                QLineEdit.EchoMode.Password
            )
            
            if not ok or not password:
                return
            
            # Decrypt the settings
            from cryptography.fernet import Fernet
            import base64
            import hashlib
            
            key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
            cipher = Fernet(key)
            
            try:
                decrypted_data = cipher.decrypt(encrypted_data)
                settings_json = decrypted_data.decode()
                restored_settings = json.loads(settings_json)
            except Exception as e:
                QMessageBox.warning(self, "Decryption Failed", 
                    "Failed to decrypt backup. Incorrect password or corrupted file.")
                return
            
            # Confirm restore
            reply = QMessageBox.question(
                self, "Confirm Restore",
                "This will replace all current settings with the backup.\n\n"
                "The application will restart after restore.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Restore the settings
            self.settings_manager.settings = restored_settings
            self.settings_manager.save_settings()
            
            QMessageBox.information(self, "Restore Complete", 
                "Settings restored successfully!\n\n"
                "The application will now restart.")
            self.log(f"Settings restored from {file_path}")
            
            # Restart application
            import sys
            QApplication.quit()
            os.execl(sys.executable, sys.executable, *sys.argv)
            
        except Exception as e:
            QMessageBox.warning(self, "Restore Failed", f"Failed to restore settings:\n{e}")
            self.log(f"Settings restore failed: {e}")
    
    # System Dependencies Methods
    def check_restic_installation(self):
        """Check if Restic is installed and accessible"""
        import platform
        
        try:
            # Verify UI elements exist
            if not hasattr(self, 'restic_status_label'):
                self.log("ERROR: restic_status_label widget not found!")
                return
            
            self.log("Starting restic installation check...")
            self.restic_status_label.setText("Checking...")
            self.restic_status_label.setStyleSheet("")
            self.restic_check_btn.setEnabled(False)
            self.restic_install_btn.setVisible(False)
            QApplication.processEvents()
            
            # Try the configured path first
            restic_path = self.settings_manager.get("restic_path")
            
            self.log(f"Checking restic at: {restic_path}")
            
            # Use shell=True on Windows for better PATH resolution
            use_shell = platform.system() == "Windows"
            
            # Use longer timeout and explicit error handling
            result = subprocess.run(
                [restic_path, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=use_shell,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            self.log(f"Restic check completed: returncode={result.returncode}")
            
            if result.returncode == 0 and result.stdout:
                # Extract version
                version_line = result.stdout.strip().split('\n')[0]
                self.restic_status_label.setText(f"✓ Installed: {version_line}")
                self.restic_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.restic_install_btn.setVisible(False)
                self.log(f"Restic check SUCCESS: {version_line}")
            else:
                # Command ran but failed
                error_msg = result.stderr if result.stderr else "Command returned error"
                self.restic_status_label.setText("✗ Check failed")
                self.restic_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.restic_install_btn.setVisible(True)
                self.log(f"Restic check FAILED: {error_msg}")
        
        except subprocess.TimeoutExpired:
            self.restic_status_label.setText("✗ Check timed out")
            self.restic_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.restic_install_btn.setVisible(True)
            self.log("Restic check TIMEOUT after 10 seconds")
        
        except FileNotFoundError as e:
            self.restic_status_label.setText("✗ Not found in PATH")
            self.restic_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.restic_install_btn.setVisible(True)
            self.log(f"Restic executable NOT FOUND: {restic_path}")
            self.log(f"FileNotFoundError: {str(e)}")
            self.log("Try: 1) Installing restic, or 2) Setting full path in Settings (e.g., C:\\\\Program Files\\\\restic\\\\restic.exe)")
        
        except Exception as e:
            self.restic_status_label.setText(f"✗ Error: {str(e)[:30]}")
            self.restic_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.restic_install_btn.setVisible(True)
            self.log(f"Restic check EXCEPTION: {type(e).__name__}: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        finally:
            self.restic_check_btn.setEnabled(True)
            QApplication.processEvents()
            self.log("Restic check completed (finally block)")
    
    def install_restic(self):
        """Install Restic using winget (Windows) or apt (Linux)"""
        import platform
        system = platform.system()
        
        if system == "Windows":
            self._install_with_winget("restic")
        elif system == "Linux":
            self._install_with_apt("restic")
        else:
            QMessageBox.information(
                self,
                "Manual Installation Required",
                f"Automatic installation is not supported on {system}.\n\n"
                "Please install Restic manually:\n"
                "macOS: brew install restic\n"
                "Or download from: https://restic.net/"
            )
    
    
    def _install_with_winget(self, package_name):
        """Install a package using Windows Package Manager (winget)"""
        # Map package names
        package_map = {
            "restic": "restic.restic",
            "WinFsp.WinFsp": "WinFsp.WinFsp"
        }
        
        winget_package = package_map.get(package_name, package_name)
        
        reply = QMessageBox.question(
            self,
            "Install with winget",
            f"This will install {package_name} using Windows Package Manager (winget).\n\n"
            "A PowerShell window will open. You may need to accept UAC prompts.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.log(f"Starting winget installation of {winget_package}")
            
            # Create a simple PowerShell script
            ps_script = f"""
Write-Host "Installing {winget_package}..." -ForegroundColor Cyan
Write-Host ""
winget install --id {winget_package} --accept-package-agreements --accept-source-agreements
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to close this window..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"""
            
            # Save script to temp file
            import tempfile
            import os
            temp_dir = tempfile.gettempdir()
            script_path = os.path.join(temp_dir, f"install_{winget_package.replace('.', '_')}.ps1")
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(ps_script)
            
            self.log(f"Created install script: {script_path}")
            
            # Launch PowerShell with the script
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-NoProfile",
                    "-File", script_path
                ],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            QMessageBox.information(
                self,
                "Installation Started",
                f"Installation of {winget_package} has started in a new window.\n\n"
                "Please accept any UAC prompts and follow the installation.\n\n"
                "After installation completes, click 'Check' to verify."
            )
            
            self.log(f"Launched winget installation of {winget_package}")
        
        except Exception as e:
            error_msg = str(e)
            QMessageBox.warning(
                self,
                "Installation Failed",
                f"Failed to start installation:\n{error_msg}\n\n"
                "Please install manually or check if winget is available.\n\n"
                "You can also install manually from:\n"
                f"- Restic: https://restic.net/\n"
                f"- WinFsp: https://winfsp.dev/"
            )
            self.log(f"Failed to install {winget_package}: {error_msg}")
    
    def _install_with_apt(self, package_name):
        """Install a package using apt (Linux)"""
        reply = QMessageBox.question(
            self,
            "Install with apt",
            f"This will install {package_name} using apt package manager.\n\n"
            "A terminal window will open. You may need to enter your password.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Try to find a suitable terminal emulator
            terminals = [
                'gnome-terminal',
                'konsole',
                'xfce4-terminal',
                'xterm'
            ]
            
            terminal_cmd = None
            for term in terminals:
                try:
                    subprocess.run(['which', term], capture_output=True, check=True)
                    terminal_cmd = term
                    break
                except:
                    continue
            
            if not terminal_cmd:
                raise Exception("No suitable terminal emulator found")
            
            # Build command based on terminal type
            if terminal_cmd == 'gnome-terminal':
                cmd = [terminal_cmd, '--', 'bash', '-c', 
                       f'sudo apt update && sudo apt install -y {package_name}; echo "\\nInstallation complete. Press Enter to close."; read']
            elif terminal_cmd == 'konsole':
                cmd = [terminal_cmd, '-e', 'bash', '-c',
                       f'sudo apt update && sudo apt install -y {package_name}; echo "\\nInstallation complete. Press Enter to close."; read']
            else:
                cmd = [terminal_cmd, '-e', 'bash', '-c',
                       f'sudo apt update && sudo apt install -y {package_name}; echo "\\nInstallation complete. Press Enter to close."; read']
            
            subprocess.Popen(cmd)
            
            QMessageBox.information(
                self,
                "Installation Started",
                f"Installation of {package_name} has started in a new terminal.\n\n"
                "Please follow the prompts and enter your password if requested.\n\n"
                "After installation completes, click 'Check' to verify."
            )
            
            self.log(f"Started apt installation of {package_name}")
        
        except Exception as e:
            QMessageBox.warning(
                self,
                "Installation Failed",
                f"Failed to start installation:\n{str(e)}\n\n"
                "Please install manually using:\nsudo apt install {package_name}"
            )
            self.log(f"Failed to install {package_name}: {str(e)}")
    
    # License Management Methods
    def refresh_license_status(self):
        """Refresh and display license status"""
        license_manager = LicenseManager()
        is_valid, message = license_manager.validate_license()
        
        # Update machine ID display
        machine_id = license_manager.get_machine_id_for_licensing()
        if hasattr(self, 'machine_id_display'):
            self.machine_id_display.setText(machine_id)
        
        # Update status label with color coding
        if hasattr(self, 'license_status_label'):
            if is_valid:
                self.license_status_label.setText(f"✓ {message}")
                self.license_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.license_status_label.setText(f"✗ {message}")
                self.license_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def copy_machine_id(self):
        """Copy machine ID to clipboard"""
        if hasattr(self, 'machine_id_display'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.machine_id_display.text())
            QMessageBox.information(
                self,
                "Machine ID Copied",
                "Machine ID has been copied to clipboard.\n\nYou can send this to your license provider to request a new license key."
            )
            self.log("Machine ID copied to clipboard")
    
    def update_license_key(self):
        """Show dialog to update/change license key"""
        license_manager = LicenseManager()
        machine_id = license_manager.get_machine_id_for_licensing()
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Update License Key")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Info text
        info_label = QLabel(
            "Enter your new license key below.\n"
            "If you need a new license key, send your Machine ID to your license provider."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Machine ID display
        machine_group = QGroupBox("Your Machine ID")
        machine_layout = QHBoxLayout()
        machine_group.setLayout(machine_layout)
        
        machine_display = QLineEdit(machine_id)
        machine_display.setReadOnly(True)
        machine_display.setFont(QFont("Courier", 9))
        machine_layout.addWidget(machine_display)
        
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(machine_id))
        machine_layout.addWidget(copy_btn)
        
        layout.addWidget(machine_group)
        
        # License key input
        license_group = QGroupBox("New License Key")
        license_layout = QVBoxLayout()
        license_group.setLayout(license_layout)
        
        license_input = QTextEdit()
        license_input.setPlaceholderText("Paste your license key here...")
        license_input.setMaximumHeight(100)
        license_input.setFont(QFont("Courier", 9))
        license_layout.addWidget(license_input)
        
        layout.addWidget(license_group)
        
        # Status message
        status_label = QLabel("")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        activate_btn = QPushButton("Activate License")
        activate_btn.clicked.connect(lambda: self._activate_new_license(
            license_input.toPlainText().strip(),
            status_label,
            dialog
        ))
        button_layout.addWidget(activate_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _activate_new_license(self, license_key, status_label, dialog):
        """Activate a new license key"""
        if not license_key:
            status_label.setText("Please enter a license key.")
            status_label.setStyleSheet("color: red;")
            return
        
        license_manager = LicenseManager()
        success, message = license_manager.save_license(license_key)
        
        if success:
            status_label.setText(f"✓ {message}")
            status_label.setStyleSheet("color: green; font-weight: bold;")
            self.log("License key updated successfully")
            
            # Refresh license status in settings page
            self.refresh_license_status()
            
            # Close dialog after short delay
            QTimer.singleShot(1500, dialog.accept)
            
            # Show success message
            QMessageBox.information(
                self,
                "License Activated",
                "Your license key has been updated successfully!"
            )
        else:
            status_label.setText(f"✗ {message}")
            status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log(f"License activation failed: {message}")
    
    # Theme Methods
    def apply_theme(self, theme: str):
        """Apply a theme to the application - delegates to themes module."""
        theme_id = themes.apply_theme(self.app, self.settings_manager, theme, window=self)
        app_theme = themes.get_app_theme(theme_id)
        # Keep settings combo in sync with resolved id/name.
        if hasattr(self, "theme_combo"):
            name = app_theme.name
            if self.theme_combo.currentText() != name:
                self.theme_combo.blockSignals(True)
                idx = self.theme_combo.findText(name)
                if idx >= 0:
                    self.theme_combo.setCurrentIndex(idx)
                self.theme_combo.blockSignals(False)

        if hasattr(self, "nav_sidebar"):
            self.nav_sidebar.recolor(app_theme.muted, app_theme.accent)

        if hasattr(self, "_jobs_table_hover"):
            # No grey row wash — descriptions only lighten slightly on hover.
            self._jobs_table_hover.set_paint_background(False)
            self._jobs_table_hover.set_nudge_foreground(True)
        
        # Refresh charts with new theme colors
        if hasattr(self, "repo_size_chart") or hasattr(self, "snapshot_count_chart"):
            self._refresh_chart_theme()
        
        # Refresh status widgets if they exist
        self.refresh_status_widget_themes()

    # ------------------------------------------------------------------
    # Frameless window chrome (match ssh-terminal-client)
    # ------------------------------------------------------------------
    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "title_bar"):
            self.title_bar.sync_max_button()
            self._sync_window_chrome()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_window_chrome()

    def _sync_window_chrome(self) -> None:
        """Square corners when maximized; rounded mask when floating."""
        root = self.centralWidget()
        if root is None or root.objectName() != "windowRoot":
            return
        maximized = self.isMaximized() or self.isFullScreen()
        root.setProperty("maximized", "1" if maximized else "0")
        root.style().unpolish(root)
        root.style().polish(root)
        if maximized:
            root.clearMask()
        else:
            from PyQt6.QtCore import QRectF
            from PyQt6.QtGui import QPainterPath, QRegion

            radius = 10.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(root.rect()), radius, radius)
            root.setMask(QRegion(path.toFillPolygon().toPolygon()))
        root.update()

    def _hit_resize_edges(self, pos: QPoint) -> set[str]:
        if self.isMaximized() or self.isFullScreen():
            return set()
        rect = self.rect()
        edges: set[str] = set()
        if pos.x() <= _WINDOW_EDGE:
            edges.add("left")
        if pos.x() >= rect.width() - _WINDOW_EDGE:
            edges.add("right")
        if pos.y() <= _WINDOW_EDGE:
            edges.add("top")
        if pos.y() >= rect.height() - _WINDOW_EDGE:
            edges.add("bottom")
        return edges

    def _edges_to_qt(self, edges: set[str]) -> Qt.Edge:
        qt_edges = Qt.Edge(0)
        if "left" in edges:
            qt_edges |= Qt.Edge.LeftEdge
        if "right" in edges:
            qt_edges |= Qt.Edge.RightEdge
        if "top" in edges:
            qt_edges |= Qt.Edge.TopEdge
        if "bottom" in edges:
            qt_edges |= Qt.Edge.BottomEdge
        return qt_edges

    def _cursor_for_edges(self, edges: set[str]):
        if not edges:
            return Qt.CursorShape.ArrowCursor
        if edges == {"left"} or edges == {"right"}:
            return Qt.CursorShape.SizeHorCursor
        if edges == {"top"} or edges == {"bottom"}:
            return Qt.CursorShape.SizeVerCursor
        if edges == {"left", "top"} or edges == {"right", "bottom"}:
            return Qt.CursorShape.SizeFDiagCursor
        return Qt.CursorShape.SizeBDiagCursor

    def _begin_edge_resize(self, edges: set[str]) -> bool:
        handle = self.windowHandle()
        if handle is None or not edges:
            return False
        qt_edges = self._edges_to_qt(edges)
        if int(qt_edges) == 0:
            return False
        return bool(handle.startSystemResize(qt_edges))

    def nativeEvent(self, eventType, message):  # noqa: N802
        # Frameless windows don't get OS resize borders; answer WM_NCHITTEST
        # so Windows still shows resize cursors over the edge.
        try:
            et = bytes(eventType)
        except Exception:
            et = b""
        if (
            wintypes is not None
            and et == b"windows_generic_MSG"
            and not self.isMaximized()
            and not self.isFullScreen()
        ):
            try:
                msg = wintypes.MSG.from_address(int(message))
            except (TypeError, ValueError, OverflowError):
                return False, 0
            if msg.message == _WM_NCHITTEST:
                pos = self.mapFromGlobal(QCursor.pos())
                edges = self._hit_resize_edges(pos)
                if not edges:
                    return False, 0
                if edges == {"left", "top"}:
                    return True, _HTTOPLEFT
                if edges == {"right", "top"}:
                    return True, _HTTOPRIGHT
                if edges == {"left", "bottom"}:
                    return True, _HTBOTTOMLEFT
                if edges == {"right", "bottom"}:
                    return True, _HTBOTTOMRIGHT
                if edges == {"left"}:
                    return True, _HTLEFT
                if edges == {"right"}:
                    return True, _HTRIGHT
                if edges == {"top"}:
                    return True, _HTTOP
                if edges == {"bottom"}:
                    return True, _HTBOTTOM
        return False, 0

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            edges = self._hit_resize_edges(event.position().toPoint())
            if edges and self._begin_edge_resize(edges):
                event.accept()
                return
            if edges:
                self._resize_edges = edges
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geom = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._resize_edges and self._resize_origin is not None and self._resize_geom is not None:
            delta = event.globalPosition().toPoint() - self._resize_origin
            geom = self._resize_geom
            x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            if "left" in self._resize_edges:
                new_w = max(min_w, w - delta.x())
                x = x + (w - new_w)
                w = new_w
            if "right" in self._resize_edges:
                w = max(min_w, w + delta.x())
            if "top" in self._resize_edges:
                new_h = max(min_h, h - delta.y())
                y = y + (h - new_h)
                h = new_h
            if "bottom" in self._resize_edges:
                h = max(min_h, h + delta.y())
            self.setGeometry(x, y, w, h)
            event.accept()
            return

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            edges = self._hit_resize_edges(pos)
            if edges:
                self.setCursor(self._cursor_for_edges(edges))
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._resize_edges = set()
        self._resize_origin = None
        self._resize_geom = None
        super().mouseReleaseEvent(event)

    def refresh_status_widget_themes(self):
        """Refresh the theme styling of all status widgets."""
        if hasattr(self, 'service_widgets'):
            colors = self.get_theme_colors()
            
            for service_name, widget in self.service_widgets.items():
                # Update main widget style
                widget.setStyleSheet(f"""
                    QWidget {{
                        border: 2px solid {colors['widget_border']};
                        border-radius: 8px;
                        background-color: {colors['widget_bg']};
                        margin: 3px;
                    }}
                """)
                
                # Update child labels
                name_labels = widget.findChildren(QLabel)
                for label in name_labels:
                    object_name = label.objectName()
                    if object_name == "status_circle":
                        # Keep current color for status circle (green/red/yellow)
                        current_style = label.styleSheet()
                        if "green" in current_style or "#4CAF50" in current_style:
                            label.setStyleSheet("color: #4CAF50; font-size: 16px;")
                        elif "red" in current_style or "#F44336" in current_style or "#a3332a" in current_style:
                            label.setStyleSheet("color: #a3332a; font-size: 16px;")
                        elif "yellow" in current_style or "#FFC107" in current_style:
                            label.setStyleSheet("color: #FFC107; font-size: 16px;")
                        else:
                            label.setStyleSheet(f"color: {colors['status_ready']}; font-size: 16px;")
                    elif object_name == "status_text":
                        # Keep current color logic but update font properties
                        current_style = label.styleSheet()
                        if "green" in current_style or "#4CAF50" in current_style:
                            label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")
                        elif "red" in current_style or "#F44336" in current_style:
                            label.setStyleSheet("color: #F44336; font-size: 12px; font-weight: bold;")
                        elif "yellow" in current_style or "#FFC107" in current_style:
                            label.setStyleSheet("color: #FFC107; font-size: 12px; font-weight: bold;")
                        else:
                            label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {colors['status_ready']};")
                    elif object_name == "details_label":
                        label.setStyleSheet(f"font-size: 9px; color: {colors['details_color']};")
                    elif not object_name:  # This is likely the service name label
                        label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {colors['name_color']};")
                        
    # Utility Methods
    def _check_restic_at_startup(self):
        """Check if Restic is installed and accessible (startup check only)"""
        version = self.restic_cmd.version()
        if version:
            self.log(f"Restic found: {version}")
        else:
            QMessageBox.warning(
                self,
                "Restic Not Found",
                "Restic executable not found!\n\n"
                "Please install Restic or configure the path in Settings.\n\n"
                "Download from: https://restic.net/"
            )
            self.log("ERROR: Restic not found!")
    
    def log(self, message: str):
        """Add message to log viewer"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)
        self.log_viewer.insertPlainText(log_entry)
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)
        
        # Add to recent activity (keep last 20 items)
        if hasattr(self, 'activity_list'):
            # Remove "No recent activity" placeholder if present
            if self.activity_list.count() == 1:
                first_item = self.activity_list.item(0)
                if first_item and first_item.text() == "No recent activity":
                    self.activity_list.clear()
            
            # Add new activity at top
            self.activity_list.insertItem(0, f"{timestamp}: {message}")
            
            # Keep only last 20 items
            while self.activity_list.count() > 20:
                self.activity_list.takeItem(self.activity_list.count() - 1)
    
    def format_bytes(self, bytes_value):
        """Format bytes into human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def format_size(self, size_bytes, format_mode="Auto"):
        """Format file size according to the specified mode
        
        Args:
            size_bytes: Size in bytes (int or str)
            format_mode: One of "Bytes", "KB", "MB", "GB", "Auto"
        
        Returns:
            Formatted size string
        """
        try:
            size = int(size_bytes)
        except (ValueError, TypeError):
            return ""
        
        if size == 0:
            return ""
        
        if format_mode == "Bytes":
            return f"{size:,}"
        elif format_mode == "KB":
            return f"{size / 1024:.2f}"
        elif format_mode == "MB":
            return f"{size / (1024 ** 2):.2f}"
        elif format_mode == "GB":
            return f"{size / (1024 ** 3):.2f}"
        else:  # Auto
            return self.format_bytes(size)
    
    def clear_logs(self):
        """Clear log viewer"""
        self.log_viewer.clear()
    
    def closeEvent(self, event):
        """Handle application close - cleanup mounted repositories and running threads"""
        # Check if any critical operations are running
        running_operations = []
        
        # Check for running backup
        if hasattr(self, '_backup_worker') and self._backup_worker.isRunning():
            running_operations.append("Backup job")
        
        # Check for running restore
        if hasattr(self, '_restore_worker') and self._restore_worker.isRunning():
            running_operations.append("Restore operation")
        
        # Check for running copy
        if hasattr(self, '_copy_worker') and self._copy_worker.isRunning():
            running_operations.append("Copy operation")
        
        # Warn about running operations
        if running_operations:
            reply = QMessageBox.question(
                self,
                "Operations In Progress",
                f"The following operations are still running:\nâ€¢ " + "\nâ€¢ ".join(running_operations) + 
                "\n\nClosing now may leave the repository in a locked state.\n\n"
                "Do you want to close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        # Unmount any mounted repositories
        if hasattr(self, '_mounted_snapshots') and self._mounted_snapshots:
            reply = QMessageBox.question(
                self,
                "Mounted Repositories",
                f"There are {len(self._mounted_snapshots)} mounted repository/repositories.\n\n"
                "Do you want to unmount them before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                for mount_info in self._mounted_snapshots.copy():
                    self._unmount_snapshot(mount_info)
        
        # Wait for all worker threads to finish (with timeout)
        self._cleanup_worker_threads()
        
        event.accept()
    
    def _cleanup_worker_threads(self):
        """Clean up all running worker threads before application exit"""
        worker_attrs = [
            '_snapshot_worker', '_restore_snapshot_worker', '_browse_files_worker',
            '_diff_worker', '_forget_worker', '_copy_worker', '_prune_worker',
            '_unlock_worker', '_stats_worker', '_verify_worker', '_restore_worker',
            '_backup_worker', '_init_worker', '_test_worker', '_lock_check_worker',
            '_auto_unlock_worker', '_cancel_unlock_worker'
        ]
        
        threads_to_wait = []
        
        for attr in worker_attrs:
            if hasattr(self, attr):
                worker = getattr(self, attr)
                if isinstance(worker, QThread) and worker.isRunning():
                    threads_to_wait.append(worker)
        
        # Also wait for content workers
        if hasattr(self, '_content_workers'):
            for worker in self._content_workers:
                if isinstance(worker, QThread) and worker.isRunning():
                    threads_to_wait.append(worker)
        
        # Wait for all threads with a reasonable timeout
        if threads_to_wait:
            for thread in threads_to_wait:
                # Try to quit gracefully first
                thread.quit()
                thread.wait(1000)  # Wait 1 second per thread
                
                # If still running, terminate
                if thread.isRunning():
                    thread.terminate()
                    thread.wait(500)  # Wait another 500ms after termination


def show_exception_dialog(exc_type, exc_value, exc_traceback):
    """
    Display an exception dialog with copyable traceback information.
    This function is called when an unhandled exception occurs.
    """
    # Format the exception information
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # Create a dialog to display the error
    error_dialog = QDialog()
    error_dialog.setWindowTitle("Application Error")
    error_dialog.setModal(True)
    error_dialog.resize(700, 500)
    
    layout = QVBoxLayout()
    
    # Add error message label
    error_label = QLabel("<b>An unexpected error has occurred:</b>")
    layout.addWidget(error_label)
    
    # Add text area with the full traceback (copyable)
    error_text = QTextEdit()
    error_text.setPlainText(error_message)
    error_text.setReadOnly(True)
    error_text.setFont(QFont("Courier", 9))
    layout.addWidget(error_text)
    
    # Add instruction label
    instruction_label = QLabel("You can select and copy the error message above to report this issue.")
    instruction_label.setWordWrap(True)
    layout.addWidget(instruction_label)
    
    # Add buttons
    button_layout = QHBoxLayout()
    
    copy_button = QPushButton("Copy to Clipboard")
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(error_message))
    button_layout.addWidget(copy_button)
    
    close_button = QPushButton("Close")
    close_button.clicked.connect(error_dialog.accept)
    button_layout.addWidget(close_button)
    
    layout.addLayout(button_layout)
    error_dialog.setLayout(layout)
    
    # Show the dialog
    error_dialog.exec()

# Main entry point
def run_job_cli(job_name):
    """Run a backup job from command line (for scheduled tasks)"""
    print(f"[Restic Manager CLI] Starting backup job: {job_name}")
    print(f"[Restic Manager CLI] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load settings
        settings_manager = ResticSettingsManager()
        db_path = history_db.history_db_path(settings_manager.filename)
        restic_cmd = ResticCommand(
            restic_path=settings_manager.get("restic_path"),
            debug=DEBUG_MODE
        )
        
        # Find the job
        jobs = settings_manager.get("backup_jobs")
        job = next((j for j in jobs if j["name"] == job_name), None)
        
        if not job:
            print(f"[ERROR] Job '{job_name}' not found!")
            return 1
        
        # Get repository (support old single + new multi format; CLI backs up first)
        repositories = settings_manager.get("repositories")
        if job.get("repositories"):
            repo_name = job["repositories"][0]
        else:
            repo_name = job.get("repository")
        repo = next((r for r in repositories if r["name"] == repo_name), None) if repo_name else None
        
        if not repo:
            print(f"[ERROR] Repository '{repo_name}' not found!")
            return 1
        
        # Decrypt password
        password = ""
        if repo.get("password"):
            password = settings_manager.password_manager.decrypt(repo["password"])
        
        # Build command
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "backup", "--json"]
        
        # Add paths
        args.extend(job["paths"])
        
        # Add tags
        if job.get("tags"):
            for tag in job["tags"]:
                args.extend(["--tag", tag])
        
        # Add exclude patterns
        if job.get("exclude_patterns"):
            for pattern in job["exclude_patterns"]:
                args.extend(["--exclude", pattern])
        
        # Add options
        if job.get("exclude_caches", True):
            args.append("--exclude-caches")
        
        if job.get("pack_size", 0) > 0:
            args.extend(["--pack-size", str(job["pack_size"])])
        
        if job.get("one_file_system", False):
            args.append("--one-file-system")
        
        if job.get("exclude_if_present"):
            args.extend(["--exclude-if-present", job["exclude_if_present"]])
        
        # Compression
        compression = job.get("compression", "auto")
        if compression and compression != "off":
            args.extend(["--compression", compression])
        
        # No cache
        if job.get("no_cache", False):
            args.append("--no-cache")
        
        # Ignore inode
        if job.get("ignore_inode", False):
            args.append("--ignore-inode")
        
        print(f"[Restic Manager CLI] Running backup...")
        print(f"[Restic Manager CLI] Repository: {repo['path']}")
        print(f"[Restic Manager CLI] Paths: {', '.join(job['paths'])}")
        
        # Run backup
        backup_timeout = job.get("timeout", 7200)  # Default 2 hours if not set
        print(f"[Restic Manager CLI] Timeout: {backup_timeout} seconds ({backup_timeout // 60} minutes)")
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        started_mono = time.time()
        success, stdout, stderr = restic_cmd.run(args, env, timeout=backup_timeout)
        duration_sec = time.time() - started_mono

        try:
            history_db.insert_job_run(
                job_name=job_name,
                repo_name=repo_name,
                started_at=started_at,
                duration_sec=duration_sec,
                success=bool(success),
                exit_code=0 if success else 1,
                source="cli",
                error_summary=None if success else ((stderr or "Unknown error")[:500]),
                snapshot_short_id=history_db.extract_snapshot_short_id(stdout or "") if success else None,
                db_path=db_path,
            )
        except Exception as exc:
            print(f"[WARN] Failed to record job run: {exc}")
        
        # Stamp last_run only on success
        if success:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            job["last_run"] = stamp
            if job.get("schedule") is None:
                job["schedule"] = {"enabled": False}
            job["schedule"]["last_run"] = stamp
            for i, j in enumerate(jobs):
                if j["name"] == job_name:
                    jobs[i] = job
                    break
            settings_manager.set("backup_jobs", jobs)
            settings_manager.save_settings()
        
        if success:
            print(f"[Restic Manager CLI] ✓ Backup completed successfully!")
            print(f"[Restic Manager CLI] Output saved to log")
            return 0
        else:
            print(f"[Restic Manager CLI] ✗ Backup failed!")
            print(f"[ERROR] {stderr}")
            return 1
    
    except Exception as e:
        print(f"[ERROR] Exception occurred: {str(e)}")
        traceback.print_exc()
        return 1


def record_job_run_cli(args) -> int:
    """Record a job run into history DB (used by Windows scheduled PowerShell)."""
    try:
        settings_manager = ResticSettingsManager()
        db_path = history_db.history_db_path(settings_manager.filename)
        success = str(args.success).strip().lower() in ("1", "true", "yes")
        duration = float(args.duration) if args.duration is not None else None
        finished = datetime.now(timezone.utc)
        if duration is not None:
            started = finished - timedelta(seconds=max(0.0, duration))
            started_at = started.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            started_at = finished.strftime("%Y-%m-%dT%H:%M:%S")
        history_db.insert_job_run(
            job_name=args.record_job_run,
            repo_name=args.repo_name or "",
            started_at=started_at,
            finished_at=finished.strftime("%Y-%m-%dT%H:%M:%S"),
            duration_sec=duration,
            success=success,
            exit_code=args.exit_code,
            source=args.source or "scheduled",
            error_summary=args.error_summary,
            snapshot_short_id=args.snapshot_id,
            db_path=db_path,
        )
        if success:
            jobs = settings_manager.get("backup_jobs") or []
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for i, job in enumerate(jobs):
                if job.get("name") == args.record_job_run:
                    job["last_run"] = stamp
                    if job.get("schedule") is None:
                        job["schedule"] = {"enabled": False}
                    job["schedule"]["last_run"] = stamp
                    jobs[i] = job
                    settings_manager.set("backup_jobs", jobs)
                    settings_manager.save_settings()
                    break
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to record job run: {e}")
        traceback.print_exc()
        return 1


def main():

    parser = argparse.ArgumentParser(
        description=(
            'Restic Backup Manager\n'
            '\nIf no ARGS presented, program will run application\n'
            'For more information, see each option description below.'
        ),
        epilog=(
            "Usage Examples:\n\n"
            "   restic_manager.py --debug\n"
            "       Prints out debug information for the application on console.\n\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    debug_group = parser.add_argument_group("Debug Options")
    debug_group.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode to print debug information to console.'
    )
    
    cli_group = parser.add_argument_group("CLI Options")
    cli_group.add_argument(
        '--run-job',
        type=str,
        metavar='JOB_NAME',
        help='Run a backup job by name without starting the GUI (for scheduled tasks).'
    )
    cli_group.add_argument(
        '--record-job-run',
        type=str,
        metavar='JOB_NAME',
        help='Record a completed job run into the history database (no restic call).'
    )
    cli_group.add_argument('--repo-name', type=str, default='', help='Repository name for --record-job-run.')
    cli_group.add_argument('--duration', type=float, default=None, help='Duration in seconds for --record-job-run.')
    cli_group.add_argument('--success', type=str, default='0', help='1/0 success flag for --record-job-run.')
    cli_group.add_argument('--exit-code', type=int, default=None, help='Exit code for --record-job-run.')
    cli_group.add_argument(
        '--source',
        type=str,
        default='scheduled',
        help='Run source for --record-job-run (gui|cli|scheduled).'
    )
    cli_group.add_argument('--error-summary', type=str, default=None, help='Short error text for --record-job-run.')
    cli_group.add_argument('--snapshot-id', type=str, default=None, help='Snapshot short id for --record-job-run.')
    
    args = parser.parse_args()
    if args.debug:
        global DEBUG_MODE
        DEBUG_MODE = True
        print("Debug mode enabled: Debug information will be printed to console.")
    
    # Handle CLI mode (for scheduled tasks)
    if args.record_job_run:
        return record_job_run_cli(args)
    if args.run_job:
        return run_job_cli(args.run_job)

    app = QApplication(sys.argv)
    # Fusion honors stylesheets for combo popups / tabs on Windows.
    app.setStyle("Fusion")
    app.setFont(QFont(themes.prefer_ui_font(), 10))
    
    # Set application info
    app.setApplicationName("Restic Backup Manager")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("ResticManager")
    app.setWindowIcon(themes.app_window_icon())

    if DEBUG_MODE:
        install_startup_window_probe(app)
        startup_probe_phase("after QApplication")

    # Set up global exception handler to show crashes in a copyable popup
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Wrapper for the exception handler that works with QApplication"""
        # Log to crash file FIRST (in case dialog fails)
        try:
            import traceback
            with open("restic_manager_crash.log", "a") as f:
                f.write(f"\n\n=== UNHANDLED EXCEPTION at {datetime.now()} ===\n")
                f.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        except:
            pass  # Can't even log
        
        # Print to console for debugging
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        
        # Show the dialog
        try:
            show_exception_dialog(exc_type, exc_value, exc_traceback)
        except:
            # Even the error dialog failed, just exit
            pass
        
    sys.excepthook = exception_hook
    
    # Qt-specific exception handler for event loop exceptions
    def qt_exception_hook(exc_type, exc_value, exc_traceback):
        """Handle exceptions that occur in Qt event loop"""
        exception_hook(exc_type, exc_value, exc_traceback)
    
    # Install Qt exception hook (this catches exceptions in signal/slot connections)
    sys.excepthook = qt_exception_hook
    
    # Check for previous crash log
    crash_log_file = "restic_manager_crash.log"
    if os.path.exists(crash_log_file):
        try:
            file_size = os.path.getsize(crash_log_file)
            if file_size > 0:
                # Previous crash detected
                reply = QMessageBox.question(
                    None,
                    "Previous Crash Detected",
                    f"A crash log file was found ({file_size} bytes).\n\n"
                    "This indicates the application crashed previously.\n\n"
                    "Would you like to view the crash log?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Show crash log
                    with open(crash_log_file, 'r') as f:
                        crash_content = f.read()
                    
                    dialog = QDialog()
                    dialog.setWindowTitle("Previous Crash Log")
                    dialog.resize(800, 600)
                    layout = QVBoxLayout()
                    
                    text_edit = QTextEdit()
                    text_edit.setPlainText(crash_content)
                    text_edit.setReadOnly(True)
                    text_edit.setFont(QFont("Courier", 9))
                    layout.addWidget(text_edit)
                    
                    button_layout = QHBoxLayout()
                    copy_btn = QPushButton("Copy to Clipboard")
                    copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(crash_content))
                    button_layout.addWidget(copy_btn)
                    
                    delete_btn = QPushButton("Delete Log")
                    delete_btn.clicked.connect(lambda: (os.remove(crash_log_file), dialog.accept())  
                      
                    if os.path.exists(crash_log_file) else dialog.accept())
                    button_layout.addWidget(delete_btn)
                    
                    close_btn = QPushButton("Close")
                    close_btn.clicked.connect(dialog.accept)
                    button_layout.addWidget(close_btn)
                    
                    layout.addLayout(button_layout)
                    dialog.setLayout(layout)
                    dialog.exec()
        except Exception as e:
            # Silently fail if we can't read crash log
            pass

    # Load settings to get theme
    settings_manager = ResticSettingsManager()
    current_theme = themes.resolve_theme_id(settings_manager.get("theme"))
    settings_manager.set("theme", current_theme)
    
    splash_bg_color, splash_text_color = themes.theme_splash_colors_for(current_theme)
    # Apply chrome stylesheet early so license/password dialogs match.
    early_css = themes.build_stylesheet(themes.get_app_theme(current_theme))
    app.setStyleSheet(early_css)
    
    # Create splash screen
    splash = make_rounded_splash(
        f"Restic Backup Manager {VERSION}\n\nLoading application...\n",
        bg_color=splash_bg_color,
        text_color=splash_text_color,
    )
    splash.show()
    app.processEvents()
    startup_probe_phase("splash shown")

    # Check license before proceeding
    license_manager = LicenseManager()
    is_valid, license_message = license_manager.validate_license()
    
    if not is_valid:
        # Close splash and show license dialog
        splash.close()
        splash.deleteLater()
        app.processEvents()  # Process the deletion
        
        machine_id = license_manager.get_machine_id_for_licensing()
        license_dialog = LicenseDialog(machine_id=machine_id)
        license_dialog.setStyleSheet(early_css)
        
        result = license_dialog.exec()
        
        if result != QDialog.DialogCode.Accepted:
            # User cancelled - exit application
            stop_startup_window_probe()
            return 0
        
        # Re-validate after activation
        is_valid, license_message = license_manager.validate_license()
        if not is_valid:
            QMessageBox.critical(
                None,
                "License Activation Failed",
                f"Could not activate license:\n{license_message}\n\nApplication will now exit."
            )
            stop_startup_window_probe()
            return 1
        
        # Recreate splash screen after successful license activation
        splash = make_rounded_splash(
            f"Restic Backup Manager {VERSION}\n\nLicense activated! Loading application...\n",
            bg_color=splash_bg_color,
            text_color=splash_text_color,
        )
        splash.show()
        app.processEvents()

    # Check application password - if hash exists, ALWAYS require authentication
    # Retrieve password from storage
    stored_hash = None
    stored_salt = None
    storage_source = None
    
    if sys.platform == "win32":
        # Windows: Registry only
        stored_hash = retrieve_from_registry("AppPasswordHash")
        stored_salt = retrieve_from_registry("AppPasswordSalt")
        if stored_hash and stored_salt:
            storage_source = "Windows Registry"
    else:
        # Non-Windows: JSON storage
        stored_hash = settings_manager.get("app_password_hash")
        stored_salt = settings_manager.get("app_password_salt")
        if stored_hash and stored_salt:
            storage_source = "Settings file"
    
    if stored_hash and stored_salt:
        # Password protection active - authenticate required
        # Hide splash screen to show password dialog
        splash.close()
        splash.deleteLater()
        app.processEvents()  # Process the deletion
        
        # Show password dialog
        max_attempts = 3
        attempt = 0
        authenticated = False
        
        while attempt < max_attempts:
            password_dialog = AppPasswordDialog()
            password_dialog.setStyleSheet(early_css)
            
            result = password_dialog.exec()
            
            if result != QDialog.DialogCode.Accepted:
                # User cancelled - exit application
                stop_startup_window_probe()
                return 0
            
            # Verify password
            entered_password = password_dialog.get_password()
            if verify_app_password(entered_password, stored_hash, stored_salt):
                authenticated = True
                break
            else:
                attempt += 1
                remaining = max_attempts - attempt
                if remaining > 0:
                    password_dialog = AppPasswordDialog()
                    password_dialog.setStyleSheet(early_css)
                    password_dialog.set_error(f"Incorrect password. {remaining} attempt(s) remaining.")
                    password_dialog.show()
                    continue
        
        if not authenticated:
            QMessageBox.critical(
                None,
                "Authentication Failed",
                "Maximum login attempts exceeded.\nApplication will now exit."
            )
            stop_startup_window_probe()
            return 1
        
        # Recreate splash screen after successful authentication
        splash = make_rounded_splash(
            f"Restic Backup Manager {VERSION}\n\nAuthenticated! Loading application...\n",
            bg_color=splash_bg_color,
            text_color=splash_text_color,
        )
        splash.show()
        app.processEvents()
        startup_probe_phase("splash after password")

    # Create window and pass splash for dynamic updates
    startup_probe_phase("creating main window")
    window = ResticManagerWindow(app, splash)
    
    splash.finish(window)
    splash.close()  # Explicitly close the splash screen
    splash.deleteLater()  # Schedule splash for deletion

    
    startup_probe_phase("showing main window")
    window.show()
    window.show()
    window.raise_()  # Bring window to front
    window.activateWindow()  # Make it the active window

    app.processEvents()  # Process all pending events to ensure splash is fully gone
    stop_startup_window_probe()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
