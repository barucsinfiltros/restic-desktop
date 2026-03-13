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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
    QStackedWidget, QFrame, QMessageBox, QSpinBox, QTextEdit, QPlainTextEdit,
    QFileDialog, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QGridLayout, QProgressBar, QListWidget, QListWidgetItem,
    QSizePolicy, QTabWidget, QDialog, QDialogButtonBox, QSplashScreen, QSpacerItem, QTimeEdit
)
from PyQt6.QtGui import QColor, QFont, QTextCursor, QPixmap
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QTime

import qdarkstyle
from qdarkstyle.light.palette import LightPalette

VERSION = "v1.3.0"
YEAR = datetime.now().year
DEBUG_MODE = False

stylesheet = (
    """
        QScrollBar:vertical {
            width: 10px;
            background: transparent;
        }
        QScrollBar::handle:vertical {
            background: #888;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background: #555;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        
        QScrollBar:horizontal {
            height: 10px;
            background: transparent;
        }
        QScrollBar::handle:horizontal {
            background: #888;
            border-radius: 4px;
            min-width: 20px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #555;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
    """
)
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
                timeout=5
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
                timeout=5
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
            
            return self._verify_license_key(license_key)
        except Exception as e:
            return False, f"Error reading license: {str(e)}"
    
    def _verify_license_key(self, license_key: str) -> Tuple[bool, str]:
        """Verify the license key format and signature"""
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
        # First verify it
        is_valid, message = self._verify_license_key(license_key)
        
        if not is_valid:
            return False, message
        
        # Save to file
        try:
            with open(self.license_file, 'w') as f:
                f.write(license_key)
            return True, "License key activated successfully!"
        except Exception as e:
            return False, f"Error saving license: {str(e)}"
    
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
                env={**os.environ, **(env or {})}
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
                universal_newlines=True
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


# Repository Dialog
class RepositoryDialog(QDialog):
    """Dialog for adding/editing repositories"""
    
    def __init__(self, parent, settings_manager, existing_repo=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.password_manager = settings_manager.password_manager
        self.existing_repo = existing_repo
        
        self.setWindowTitle("Add Repository" if not existing_repo else "Edit Repository")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Repository name
        self.name_input = QLineEdit()
        if existing_repo:
            self.name_input.setText(existing_repo.get("name", ""))
        form_layout.addRow("Name:", self.name_input)
        
        # Repository type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["local", "sftp", "s3", "b2", "azure", "gs", "rest"])
        if existing_repo:
            self.type_combo.setCurrentText(existing_repo.get("type", "local"))
        form_layout.addRow("Type:", self.type_combo)
        
        # Repository path/URL
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        if existing_repo:
            self.path_input.setText(existing_repo.get("path", ""))
        path_layout.addWidget(self.path_input)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(browse_btn)
        form_layout.addRow("Path/URL:", path_layout)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if existing_repo and existing_repo.get("password"):
            decrypted = self.password_manager.decrypt(existing_repo.get("password"))
            self.password_input.setText(decrypted)
        form_layout.addRow("Password:", self.password_input)
        
        # Show password checkbox
        self.show_password_check = QCheckBox("Show password")
        self.show_password_check.stateChanged.connect(self.toggle_password_visibility)
        form_layout.addRow("", self.show_password_check)
        
        layout.addLayout(form_layout)
        
        # Initialize repository option
        if not existing_repo:
            self.init_repo_check = QCheckBox("Initialize repository now")
            self.init_repo_check.setChecked(False)
            layout.addWidget(self.init_repo_check)
        
        # Buttons
        button_layout = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(test_btn)
        button_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
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
        
        # Show progress dialog
        self._test_progress = QDialog(self)
        self._test_progress.setWindowTitle("Testing Connection")
        self._test_progress.setModal(True)
        self._test_progress.setMinimumWidth(350)
        
        progress_layout = QVBoxLayout()
        self._test_progress.setLayout(progress_layout)
        
        progress_label = QLabel(f"Testing connection to repository...\n\nPlease wait...")
        progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(progress_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)  # Indeterminate progress
        progress_layout.addWidget(progress_bar)
        
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
            QMessageBox.information(
                self, 
                "Connection Successful", 
                "Successfully connected to the repository!\n\nThe repository is accessible and the password is correct."
            )
        else:
            error_msg = stderr if stderr else "Unknown error"
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
            "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add initialize flag if this is a new repository
        if not self.existing_repo:
            data["initialize"] = self.init_repo_check.isChecked()
        
        return data


class BackupJobDialog(QDialog):
    """Dialog for creating/editing backup jobs"""
    
    def __init__(self, parent, settings_manager, existing_job=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.existing_job = existing_job
        
        self.setWindowTitle("New Backup Job" if not existing_job else "Edit Backup Job")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Job name
        self.name_input = QLineEdit()
        if existing_job:
            self.name_input.setText(existing_job.get("name", ""))
        form_layout.addRow("Job Name:", self.name_input)
        
        # Repository
        self.repo_combo = QComboBox()
        repositories = settings_manager.get("repositories")
        for repo in repositories:
            self.repo_combo.addItem(repo["name"])
        if existing_job:
            self.repo_combo.setCurrentText(existing_job.get("repository", ""))
        form_layout.addRow("Repository:", self.repo_combo)
        
        layout.addLayout(form_layout)
        
        # Paths to backup
        paths_group = QGroupBox("Paths to Backup")
        paths_layout = QVBoxLayout()
        paths_group.setLayout(paths_layout)
        
        self.paths_list = QListWidget()
        self.paths_list.setMaximumHeight(120)
        if existing_job and existing_job.get("paths"):
            for path in existing_job["paths"]:
                self.paths_list.addItem(path)
        paths_layout.addWidget(self.paths_list)
        
        paths_btn_layout = QHBoxLayout()
        add_path_btn = QPushButton("Add Path")
        add_path_btn.clicked.connect(self.add_path)
        remove_path_btn = QPushButton("Remove")
        remove_path_btn.clicked.connect(self.remove_path)
        paths_btn_layout.addWidget(add_path_btn)
        paths_btn_layout.addWidget(remove_path_btn)
        paths_btn_layout.addStretch()
        paths_layout.addLayout(paths_btn_layout)
        
        layout.addWidget(paths_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()
        options_group.setLayout(options_layout)
        
        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("tag1,tag2,tag3")
        if existing_job:
            tags = existing_job.get("tags", [])
            self.tags_input.setText(",".join(tags))
        options_layout.addRow("Tags:", self.tags_input)
        
        # Exclude patterns
        self.exclude_input = QTextEdit()
        self.exclude_input.setPlaceholderText("*.tmp\n*.log\nnode_modules/")
        self.exclude_input.setMaximumHeight(80)
        if existing_job and existing_job.get("exclude_patterns"):
            self.exclude_input.setPlainText("\n".join(existing_job["exclude_patterns"]))
        options_layout.addRow("Exclude Patterns:", self.exclude_input)
        
        # Exclude caches
        self.exclude_caches_check = QCheckBox()
        self.exclude_caches_check.setChecked(existing_job.get("exclude_caches", True) if existing_job else True)
        options_layout.addRow("Exclude Caches:", self.exclude_caches_check)
        
        # Pack size
        pack_layout = QHBoxLayout()
        self.pack_size_spin = QSpinBox()
        self.pack_size_spin.setMinimum(0)
        self.pack_size_spin.setMaximum(1024)
        self.pack_size_spin.setValue(existing_job.get("pack_size", 0) if existing_job else 0)
        self.pack_size_spin.setSuffix(" MB")
        pack_layout.addWidget(self.pack_size_spin)
        pack_layout.addWidget(QLabel("(0 = default)"))
        pack_layout.addStretch()
        options_layout.addRow("Pack Size:", pack_layout)
        
        # One file system
        self.one_file_system_check = QCheckBox()
        self.one_file_system_check.setChecked(existing_job.get("one_file_system", False) if existing_job else False)
        options_layout.addRow("One File System:", self.one_file_system_check)
        
        # Exclude if present
        self.exclude_if_present_input = QLineEdit()
        self.exclude_if_present_input.setPlaceholderText(".nobackup")
        if existing_job:
            self.exclude_if_present_input.setText(existing_job.get("exclude_if_present", ""))
        options_layout.addRow("Exclude If Present:", self.exclude_if_present_input)
        
        layout.addWidget(options_group)
        
        # Scheduling options
        schedule_group = QGroupBox("Scheduling (Optional)")
        schedule_layout = QFormLayout()
        schedule_group.setLayout(schedule_layout)
        
        # Enable scheduling
        self.schedule_enabled_check = QCheckBox("Enable automatic scheduling for this job")
        if existing_job and existing_job.get("schedule"):
            self.schedule_enabled_check.setChecked(existing_job["schedule"].get("enabled", False))
        schedule_layout.addRow(self.schedule_enabled_check)
        
        # Container for schedule settings (enabled/disabled based on checkbox)
        self.schedule_settings_widget = QWidget()
        schedule_settings_layout = QFormLayout()
        self.schedule_settings_widget.setLayout(schedule_settings_layout)
        
        # Frequency
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
        if existing_job and existing_job.get("schedule"):
            freq = existing_job["schedule"].get("frequency", "daily")
            self.frequency_combo.setCurrentText(freq.capitalize())
        schedule_settings_layout.addRow("Frequency:", self.frequency_combo)
        
        # Time
        self.time_edit = QTimeEdit()
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
        self.day_checkboxes = {}
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        selected_days = []
        if existing_job and existing_job.get("schedule"):
            selected_days = existing_job["schedule"].get("days", [])
        
        for day in days:
            cb = QCheckBox(day)
            if day in selected_days or not selected_days:  # Default all checked if none specified
                cb.setChecked(not selected_days)  # Check all by default only if no existing selection
            if day in selected_days:
                cb.setChecked(True)
            self.day_checkboxes[day] = cb
            days_layout.addWidget(cb)
        
        self.days_widget = QWidget()
        self.days_widget.setLayout(days_layout)
        schedule_settings_layout.addRow("Days (Weekly):", self.days_widget)
        
        # Run if missed
        self.run_if_missed_check = QCheckBox("Run at next logon if missed")
        if existing_job and existing_job.get("schedule"):
            self.run_if_missed_check.setChecked(existing_job["schedule"].get("run_if_missed", True))
        else:
            self.run_if_missed_check.setChecked(True)
        schedule_settings_layout.addRow(self.run_if_missed_check)
        
        schedule_layout.addRow(self.schedule_settings_widget)
        
        # Update days visibility based on frequency
        self.frequency_combo.currentTextChanged.connect(self.update_schedule_ui)
        self.schedule_enabled_check.stateChanged.connect(self.update_schedule_ui)
        
        layout.addWidget(schedule_group)
        
        # Initial UI state
        self.update_schedule_ui()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
    
    def update_schedule_ui(self):
        """Update schedule UI based on selections"""
        # Enable/disable schedule settings based on checkbox
        enabled = self.schedule_enabled_check.isChecked()
        self.schedule_settings_widget.setEnabled(enabled)
        
        # Show/hide days based on frequency
        if hasattr(self, 'days_widget'):
            is_weekly = self.frequency_combo.currentText() == "Weekly"
            self.days_widget.setVisible(is_weekly and enabled)
    
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
                "run_if_missed": self.run_if_missed_check.isChecked(),
                "last_run": None
            }
        else:
            # Keep disabled flag if schedule was previously enabled
            schedule_data = {
                "enabled": False
            }
        
        data = {
            "name": self.name_input.text().strip(),
            "repository": self.repo_combo.currentText(),
            "paths": paths,
            "tags": tags,
            "exclude_patterns": exclude_patterns,
            "exclude_caches": self.exclude_caches_check.isChecked(),
            "pack_size": self.pack_size_spin.value(),
            "one_file_system": self.one_file_system_check.isChecked(),
            "exclude_if_present": self.exclude_if_present_input.text().strip(),
            "schedule": schedule_data,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return data


# License Activation Dialog
class LicenseDialog(QDialog):
    """Dialog for entering and activating license keys"""
    
    def __init__(self, parent=None, machine_id=""):
        super().__init__(parent)
        self.machine_id = machine_id
        self.license_manager = LicenseManager()
        
        self.setWindowTitle("License Activation")
        self.setMinimumWidth(600)
        self.setModal(True)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
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
        copy_btn.setFixedWidth(80)
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
        activate_btn.setDefault(True)
        activate_btn.clicked.connect(self.activate_license)
        button_layout.addWidget(activate_btn)
        
        quit_btn = QPushButton("Quit Application")
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


# Settings Manager
class ResticSettingsManager:
    """Manager for application settings"""
    
    def __init__(self, filename="restic_settings.json"):
        self.filename = filename
        self.password_manager = PasswordManager()
        self.defaults = {
            "theme": "light",
            "restic_path": "restic",
            "repositories": [],
            "backup_jobs": [],
            "last_repository": "",
            "auto_refresh_snapshots": True,
            "snapshot_refresh_interval": 60,  # seconds
            "log_level": "info"
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
    
    def __init__(self):
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
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            
            # Build command to run job
            command = f'"{python_exe}" "{script_path}" --run-job "{job_name}"'
            
            # Build task name (sanitize for Task Scheduler)
            task_name = f"ResticBackup_{job_name.replace(' ', '_')}"
            
            # Delete existing task if it exists
            self._delete_windows_task(task_name)
            
            # Build schedule trigger based on frequency
            frequency = schedule.get("frequency", "daily")
            time_str = schedule.get("time", "02:00")
            
            if frequency == "daily":
                schedule_type = "/SC DAILY"
            elif frequency == "weekly":
                days = schedule.get("days", [])
                if not days:
                    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                # Convert to Task Scheduler day format
                day_map = {"Mon": "MON", "Tue": "TUE", "Wed": "WED", "Thu": "THU", 
                          "Fri": "FRI", "Sat": "SAT", "Sun": "SUN"}
                schtasks_days = ",".join([day_map.get(d, d) for d in days])
                schedule_type = f'/SC WEEKLY /D {schtasks_days}'
            elif frequency == "monthly":
                schedule_type = "/SC MONTHLY"
            else:
                schedule_type = "/SC DAILY"
            
            # Build schtasks command
            schtasks_cmd = [
                "schtasks", "/CREATE",
                "/TN", task_name,
                "/TR", command,
                schedule_type,
                "/ST", time_str,
                "/F"  # Force create, overwrite if exists
            ]
            
            # Add "run if missed" setting
            if schedule.get("run_if_missed", True):
                schtasks_cmd.extend(["/Z"])  # Run after missed schedule
            
            # Execute schtasks command
            result = subprocess.run(
                schtasks_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                return True, f"Scheduled task '{task_name}' created successfully (Windows Task Scheduler)"
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
                errors='replace'
            )
            
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
                errors='replace'
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
                # Run on first day of month
                cron_schedule = f"{minute} {hour} 1 * *"
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
                errors='replace'
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
                errors='replace'
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
                    errors='replace'
                )
            else:
                # Remove crontab entirely if no entries left
                result = subprocess.run(
                    ["crontab", "-r"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
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
                errors='replace'
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
    def __init__(self, app, splash=None):
        super().__init__()
        self.app = app
        self.splash = splash
        
        self._update_splash("Initializing settings...")
        self.settings_manager = ResticSettingsManager()
        self.scheduler_manager = SchedulerManager()
        self.restic_cmd = ResticCommand(
            restic_path=self.settings_manager.get("restic_path"),
            debug=DEBUG_MODE
        )
        self.current_repository = None
        
        self._update_splash("Creating main window...")
        self.setWindowTitle(f"Restic Backup Manager {VERSION}")
        self.setMinimumSize(1200, 700)
        
        # Main layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
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
        
        # Check Restic installation
        self._update_splash("Checking Restic installation...")
        QTimer.singleShot(100, self.check_restic_installation)
    
    def _update_splash(self, message):
        """Update splash screen message if available"""
        if self.splash:
            try:
                # Check if splash is still valid (not deleted)
                if not self.splash.isVisible():
                    # Splash may have been closed, but object might still exist
                    return
                
                # Get current theme for text color
                current_theme = self.settings_manager.get("theme") if hasattr(self, 'settings_manager') else "dark"
                
                # Map themes to text colors
                theme_text_colors = {
                    "light": "#333333",
                    "light-green": "#222423",
                    "light-blue": "#1a2b3c",
                    "sunset-orange": "#552200"
                }
                text_color = theme_text_colors.get(current_theme, "#ffffff")
                
                self.splash.showMessage(
                    f"Restic Backup Manager {VERSION}\n\n{message}\n",
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                    QColor(text_color)
                )
                self.app.processEvents()  # Force UI update
            except RuntimeError:
                # Splash has been deleted, silently ignore
                pass
    
    def create_sidebar(self, main_layout):
        """Create sidebar navigation menu"""
        # Sidebar scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(220)
        scroll_area.setFrameShape(QFrame.Shape.StyledPanel)
        
        menu_widget = QWidget()
        menu_layout = QVBoxLayout()
        menu_widget.setLayout(menu_layout)
        scroll_area.setWidget(menu_widget)
        
        # Title
        title_label = QLabel("Restic Manager")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menu_layout.addWidget(title_label)
        
        menu_layout.addSpacing(10)
        
        # Menu buttons
        self.menu_buttons = []
        menu_items = [
            ("Dashboard", 0),
            ("Repositories", 1),
            ("Snapshots", 2),
            ("Restore Files", 3),
            ("Backup Jobs", 4),
            ("Retention Policy", 5),
            ("Logs", 6),
            ("Settings", 7),
            ("Exit", -1)
        ]
        
        for label, page_idx in menu_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda checked, idx=page_idx: self.switch_page(idx))
            menu_layout.addWidget(btn)
            self.menu_buttons.append(btn)
        
        menu_layout.addStretch()
        
        # Version footer
        version_label = QLabel(f"Version {VERSION}\n© {YEAR}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #888; font-size: 10px;")
        menu_layout.addWidget(version_label)
        
        main_layout.addWidget(scroll_area)
        
        # Select first page
        self.menu_buttons[0].setChecked(True)
    
    def switch_page(self, page_index):
        """Switch to a different page"""
        # Handle Exit action
        if page_index == -1:
            QApplication.instance().quit()
            return
        
        self.stacked_widget.setCurrentIndex(page_index)
        
        # Update button states
        for i, btn in enumerate(self.menu_buttons):
            btn.setChecked(i == page_index)
        
        # Refresh dashboard when switching to it
        if page_index == 0:  # Dashboard page
            self.refresh_dashboard()
    
    def create_dashboard_page(self):
        """Create dashboard overview page"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Dashboard")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Statistics grid
        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout()
        stats_group.setLayout(stats_layout)
        
        self.stats_labels = {}
        stats = [
            ("Total Repositories", "total_repos"),
            ("Total Snapshots", "total_snapshots"),
            ("Total Size", "total_size"),
            ("Last Backup", "last_backup")
        ]
        
        for i, (label_text, key) in enumerate(stats):
            label = QLabel(f"{label_text}:")
            #label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            value = QLabel("—")
            #value.setFont(QFont("Arial", 11))
            self.stats_labels[key] = value
            
            stats_layout.addWidget(label, i, 0)
            stats_layout.addWidget(value, i, 1)
        
        layout.addWidget(stats_group)
        
        # Repository Stats
        repo_stats_group = QGroupBox("Repository Statistics")
        repo_stats_layout = QVBoxLayout()
        repo_stats_group.setLayout(repo_stats_layout)
        
        # Repository selector for stats
        repo_stats_header = QHBoxLayout()
        repo_stats_header.addWidget(QLabel("Repository:"))
        self.dashboard_repo_combo = QComboBox()
        self.dashboard_repo_combo.setFixedWidth(200)
        
        repo_stats_header.addWidget(self.dashboard_repo_combo)
        refresh_stats_btn = QPushButton("Refresh Stats")
        refresh_stats_btn.setFixedWidth(150)
        refresh_stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_stats_btn.clicked.connect(self.load_repository_stats)
        repo_stats_header.addWidget(refresh_stats_btn)
        
        verify_btn = QPushButton("Verify Repository")
        verify_btn.setFixedWidth(150)
        verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        verify_btn.clicked.connect(self.verify_repository)
        
        repo_stats_header.addWidget(verify_btn)
        repo_stats_header.addStretch()
        repo_stats_layout.addLayout(repo_stats_header)
        
        # Stats display
        self.repo_stats_text = QTextEdit()
        self.repo_stats_text.setReadOnly(True)
        self.repo_stats_text.setMaximumHeight(150)
        self.repo_stats_text.setText("Select a repository and click Refresh Stats")
        repo_stats_layout.addWidget(self.repo_stats_text)
        
        layout.addWidget(repo_stats_group)
        
        # Recent activity
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout()
        activity_group.setLayout(activity_layout)
        
        self.activity_list = QListWidget()
        self.activity_list.addItem("No recent activity")
        activity_layout.addWidget(self.activity_list)
        
        layout.addWidget(activity_group)
        layout.addStretch()
        
        self.stacked_widget.addWidget(page)
    
    def refresh_dashboard(self):
        """Refresh dashboard statistics"""
        repositories = self.settings_manager.get("repositories")
        
        # Update total repositories
        self.stats_labels["total_repos"].setText(str(len(repositories)))
        
        # Calculate total snapshots and size from all repositories
        total_snapshots = 0
        total_size = 0
        
        for repo in repositories:
            repo_name = repo.get("name", "")
            repo_path = repo.get("path", "")
            password = ""
            
            if repo.get("password"):
                try:
                    password = self.settings_manager.password_manager.decrypt(repo["password"])
                except:
                    continue
            
            # Get snapshot count
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo_path, "snapshots", "--json"]
            
            try:
                success, stdout, stderr = self.restic_cmd.run(args, env)
                if success and stdout:
                    try:
                        snapshots = json.loads(stdout)
                        if isinstance(snapshots, list):
                            total_snapshots += len(snapshots)
                    except json.JSONDecodeError:
                        pass
            except:
                pass
            
            # Get repository size
            args = ["-r", repo_path, "stats", "--json"]
            try:
                success, stdout, stderr = self.restic_cmd.run(args, env)
                if success and stdout:
                    try:
                        stats = json.loads(stdout)
                        total_size += stats.get("total_size", 0)
                    except json.JSONDecodeError:
                        pass
            except:
                pass
        
        self.stats_labels["total_snapshots"].setText(str(total_snapshots))
        self.stats_labels["total_size"].setText(self.format_bytes(total_size) if total_size > 0 else "—")
        
        # Last backup (check most recent repository last_checked)
        last_backup = "Never"
        if repositories:
            last_checked_times = [repo.get("last_checked", "") for repo in repositories if repo.get("last_checked")]
            if last_checked_times:
                last_backup = max(last_checked_times)
        self.stats_labels["last_backup"].setText(last_backup)
    
    def create_repositories_page(self):
        """Create repositories management page"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title and actions
        title_layout = QHBoxLayout()
        title = QLabel("Repositories")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        add_btn = QPushButton("Add Repository")
        add_btn.clicked.connect(self.add_repository)
        title_layout.addWidget(add_btn)
        
        layout.addLayout(title_layout)
        
        # Repository list
        self.repo_table = QTableWidget()
        self.repo_table.setColumnCount(5)
        self.repo_table.setHorizontalHeaderLabels([
            "Name", "Path", "Type", "Last Checked", "Actions"
        ])
        self.repo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.repo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.repo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.repo_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.repo_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.repo_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.repo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.repo_table)
        
        self.refresh_repository_list()
        
        self.stacked_widget.addWidget(page)
    
    def create_snapshots_page(self):
        """Create snapshots browser page"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title and controls
        title_layout = QHBoxLayout()
        title = QLabel("Snapshots")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # Repository selector
        title_layout.addWidget(QLabel("Repository:"))
        self.snapshot_repo_combo = QComboBox()
        self.snapshot_repo_combo.currentTextChanged.connect(self.load_snapshots)
        title_layout.addWidget(self.snapshot_repo_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_snapshots)
        title_layout.addWidget(refresh_btn)
        
        layout.addLayout(title_layout)
        
        # Snapshots table
        self.snapshots_table = QTableWidget()
        self.snapshots_table.setColumnCount(6)
        self.snapshots_table.setHorizontalHeaderLabels([
            "ID", "Time", "Host", "Tags", "Paths", "Size"
        ])
        self.snapshots_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.snapshots_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.snapshots_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.snapshots_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.snapshots_table)
        
        # Snapshot details
        details_group = QGroupBox("Snapshot Details")
        details_layout = QVBoxLayout()
        details_group.setLayout(details_layout)
        
        self.snapshot_details = QTextEdit()
        self.snapshot_details.setReadOnly(True)
        self.snapshot_details.setFont(QFont("Courier", 9))
        #self.snapshot_details.setMaximumHeight(150)
        # self.snapshot_details.setStyleSheet("""
        #     QScrollBar:vertical {
        #         width: 10px;
        #         background: transparent;
        #     }
        #     QScrollBar::handle:vertical {
        #         background: #888;
        #         border-radius: 4px;
        #         min-height: 20px;
        #     }
        #     QScrollBar::handle:vertical:hover {
        #         background: #555;
        #     }
        #     QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        #         background: none;
        #     }
            
        #     QScrollBar:horizontal {
        #         height: 10px;
        #         background: transparent;
        #     }
        #     QScrollBar::handle:horizontal {
        #         background: #888;
        #         border-radius: 4px;
        #         min-width: 20px;
        #     }
        #     QScrollBar::handle:horizontal:hover {
        #         background: #555;
        #     }
        #     QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        #         background: none;
        #     }
        # """)
        self.snapshot_details.setStyleSheet(stylesheet)
        
        details_layout.addWidget(self.snapshot_details)
        
        layout.addWidget(details_group)
        
        # Snapshot actions
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        browse_content_btn = QPushButton("Browse Content")
        browse_content_btn.setFixedWidth(150)
        browse_content_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_content_btn.clicked.connect(self.browse_snapshot_content)
        actions_layout.addWidget(browse_content_btn)
        
        diff_btn = QPushButton("Diff with Previous")
        diff_btn.setFixedWidth(150)
        diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diff_btn.clicked.connect(self.diff_snapshots)
        actions_layout.addWidget(diff_btn)
        
        forget_btn = QPushButton("Forget (Delete)")
        forget_btn.setFixedWidth(150)
        forget_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        forget_btn.clicked.connect(self.forget_snapshot)
        actions_layout.addWidget(forget_btn)
        
        prune_btn = QPushButton("Prune Repository")
        prune_btn.setFixedWidth(150)
        prune_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prune_btn.clicked.connect(self.prune_repository)
        actions_layout.addWidget(prune_btn)
        
        unlock_btn = QPushButton("Unlock Repository")
        unlock_btn.setFixedWidth(150)
        unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        unlock_btn.clicked.connect(self.unlock_repository)
        actions_layout.addWidget(unlock_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        self.snapshots_table.itemSelectionChanged.connect(self.show_snapshot_details)
        
        self.stacked_widget.addWidget(page)
    
    def create_restore_page(self):
        """Create file restore page"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Restore Files")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Restore form
        form_group = QGroupBox("Restore Configuration")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Repository selection
        self.restore_repo_combo = QComboBox()
        self.restore_repo_combo.setFixedWidth(400)
        form_layout.addRow("Repository:", self.restore_repo_combo)
        
        # Snapshot selection
        self.restore_snapshot_combo = QComboBox()
        self.restore_snapshot_combo.setFixedWidth(400)
        self.restore_repo_combo.currentTextChanged.connect(self.load_snapshots_for_restore)
        form_layout.addRow("Snapshot:", self.restore_snapshot_combo)
        
        # Path to restore
        path_layout = QHBoxLayout()
        self.restore_path_input = QLineEdit()
        self.restore_path_input.setPlaceholderText("Leave empty to restore all files")
        self.restore_path_input.setFixedWidth(400)
        path_layout.addWidget(self.restore_path_input)
        browse_btn = QPushButton("Browse Snapshot")
        browse_btn.setFixedWidth(150)
        browse_btn.clicked.connect(self.browse_snapshot_files)
        path_layout.addWidget(browse_btn)
        form_layout.addRow("Path to Restore:", path_layout)
        
        # Target directory
        target_layout = QHBoxLayout()
        self.restore_target_input = QLineEdit()
        self.restore_target_input.setPlaceholderText("Select target directory for restore")
        self.restore_target_input.setFixedWidth(400)
        target_layout.addWidget(self.restore_target_input)
        
        target_browse_btn = QPushButton("Browse")
        target_browse_btn.setFixedWidth(150)
        target_browse_btn.clicked.connect(self.browse_restore_target)
        target_layout.addWidget(target_browse_btn)
        form_layout.addRow("Restore To:", target_layout)
        
        layout.addWidget(form_group)
        
        # Restore button
        restore_btn = QPushButton("Start Restore")
        restore_btn.setFixedWidth(150)
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        restore_layout = QHBoxLayout()
        restore_layout.addStretch()
        restore_layout.addWidget(restore_btn)
        restore_layout.addStretch()
        
        restore_btn.clicked.connect(self.start_restore)
        layout.addLayout(restore_layout)
        
        # Progress
        self.restore_progress = QProgressBar()
        self.restore_progress.setVisible(False)
        layout.addWidget(self.restore_progress)
        
        # Log output
        log_group = QGroupBox("Restore Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.restore_log = QPlainTextEdit()
        self.restore_log.setReadOnly(True)
        log_layout.addWidget(self.restore_log)
        
        layout.addWidget(log_group)
        
        self.stacked_widget.addWidget(page)
    
    def create_backup_page(self):
        """Create backup jobs management page"""
        page = QWidget()
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
            
            # Repository
            self.backup_jobs_table.setItem(row, 1, QTableWidgetItem(job.get("repository", "")))
            
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
                    schedule_text = f"⏰ {freq} at {time}\n({days_str})"
                else:
                    schedule_text = f"⏰ {freq} at {time}"
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
    
    def create_retention_page(self):
        """Create retention policy page"""
        page = QWidget()
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
        form_layout.addRow("Repository:", self.retention_repo_combo)
        
        # Keep policies
        self.keep_last_spin = QSpinBox()
        self.keep_last_spin.setMinimum(0)
        self.keep_last_spin.setMaximum(1000)
        form_layout.addRow("Keep Last:", self.keep_last_spin)
        
        self.keep_hourly_spin = QSpinBox()
        self.keep_hourly_spin.setMinimum(0)
        self.keep_hourly_spin.setMaximum(1000)
        form_layout.addRow("Keep Hourly:", self.keep_hourly_spin)
        
        self.keep_daily_spin = QSpinBox()
        self.keep_daily_spin.setMinimum(0)
        self.keep_daily_spin.setMaximum(365)
        self.keep_daily_spin.setValue(7)
        form_layout.addRow("Keep Daily:", self.keep_daily_spin)
        
        self.keep_weekly_spin = QSpinBox()
        self.keep_weekly_spin.setMinimum(0)
        self.keep_weekly_spin.setMaximum(520)
        self.keep_weekly_spin.setValue(4)
        form_layout.addRow("Keep Weekly:", self.keep_weekly_spin)
        
        self.keep_monthly_spin = QSpinBox()
        self.keep_monthly_spin.setMinimum(0)
        self.keep_monthly_spin.setMaximum(120)
        self.keep_monthly_spin.setValue(12)
        form_layout.addRow("Keep Monthly:", self.keep_monthly_spin)
        
        self.keep_yearly_spin = QSpinBox()
        self.keep_yearly_spin.setMinimum(0)
        self.keep_yearly_spin.setMaximum(100)
        form_layout.addRow("Keep Yearly:", self.keep_yearly_spin)
        
        layout.addWidget(form_group)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        dry_run_btn = QPushButton("Dry Run (Preview)")
        dry_run_btn.clicked.connect(lambda: self.apply_retention(dry_run=True))
        btn_layout.addWidget(dry_run_btn)
        
        apply_btn = QPushButton("Apply Policy")
        apply_btn.clicked.connect(lambda: self.apply_retention(dry_run=False))
        btn_layout.addWidget(apply_btn)
        
        layout.addLayout(btn_layout)
        
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
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Settings form
        form_group = QGroupBox("Application Settings")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Restic path
        restic_path_layout = QHBoxLayout()
        self.restic_path_input = QLineEdit()
        self.restic_path_input.setText(self.settings_manager.get("restic_path"))
        restic_path_layout.addWidget(self.restic_path_input)
        browse_restic_btn = QPushButton("Browse")
        browse_restic_btn.clicked.connect(self.browse_restic_path)
        restic_path_layout.addWidget(browse_restic_btn)
        form_layout.addRow("Restic Path:", restic_path_layout)
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([
            "light", "dark", "dark-cyan", "dark-navy", "dark-green", "light-green",
            "dark-purple", "solarized-dark", "light-blue", "monokai-dark",
            "dark-indigo", "dark-magenta", "sunset-orange", "forest-moss", "cool-grey",
            "pure-black", "midnight-blue", "cyberpunk-neon", "github-dark", "vscode-dark",
            "material-dark", "dracula", "nord-dark", "amoled-black", "matrix-green"
        ])
        current_theme = self.settings_manager.get("theme")
        self.theme_combo.setCurrentText(current_theme)
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
        form_layout.addRow("Refresh Interval:", self.refresh_interval_spin)
        
        layout.addWidget(form_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedWidth(150)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        save_btn_layout = QHBoxLayout()
        save_btn_layout.addStretch()
        save_btn_layout.addWidget(save_btn)
        save_btn_layout.addStretch()
        
        save_btn.clicked.connect(self.save_settings)
        layout.addLayout(save_btn_layout)
        
        # License Management Section
        license_group = QGroupBox("License Information")
        license_layout = QVBoxLayout()
        license_group.setLayout(license_layout)
        
        # License status
        self.license_status_label = QLabel()
        self.license_status_label.setWordWrap(True)
        license_layout.addWidget(self.license_status_label)
        
        # Machine ID display
        machine_id_layout = QHBoxLayout()
        machine_id_layout.addWidget(QLabel("Machine ID:"))
        self.machine_id_display = QLineEdit()
        self.machine_id_display.setFixedWidth(400)
        self.machine_id_display.setReadOnly(True)
        self.machine_id_display.setFont(QFont("Courier", 9))
        
        machine_id_display_layout = QHBoxLayout()
        machine_id_display_layout.addWidget(self.machine_id_display)
        machine_id_display_layout.addStretch()
        
        machine_id_layout.addLayout(machine_id_display_layout)
        
        copy_machine_id_btn = QPushButton("Copy")
        copy_machine_id_btn.setFixedWidth(80)
        copy_machine_id_btn.clicked.connect(self.copy_machine_id)
        machine_id_layout.addWidget(copy_machine_id_btn)
        license_layout.addLayout(machine_id_layout)
        
        # License action buttons
        license_btn_layout = QHBoxLayout()
        
        update_license_btn = QPushButton("Update License Key")
        update_license_btn.setFixedWidth(180)
        update_license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        update_license_btn.clicked.connect(self.update_license_key)
        license_btn_layout.addWidget(update_license_btn)
        
        refresh_license_btn = QPushButton("Refresh Status")
        refresh_license_btn.setFixedWidth(180)
        refresh_license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_license_btn.clicked.connect(self.refresh_license_status)
        license_btn_layout.addWidget(refresh_license_btn)
        
        license_layout.addLayout(license_btn_layout)
        
        layout.addWidget(license_group)
        
        # Initialize license display
        self.refresh_license_status()
        
        layout.addStretch()
        
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
                # Show progress dialog
                self._add_repo_progress = QDialog(self)
                self._add_repo_progress.setWindowTitle("Initializing Repository")
                self._add_repo_progress.setModal(True)
                self._add_repo_progress.setMinimumWidth(400)
                
                progress_layout = QVBoxLayout()
                self._add_repo_progress.setLayout(progress_layout)
                
                progress_label = QLabel(f"Initializing repository '{repo_data['name']}'...\n\nPlease wait...")
                progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                progress_layout.addWidget(progress_label)
                
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 0)  # Indeterminate progress
                progress_layout.addWidget(progress_bar)
                
                self._add_repo_progress.show()
                QApplication.processEvents()
                
                # Store repo data for callback
                self._pending_repo_data = repo_data
                
                # Initialize repository in background
                password = self.settings_manager.password_manager.decrypt(repo_data["password"]) if repo_data.get("password") else ""
                env = {"RESTIC_PASSWORD": password} if password else {}
                args = ["-r", repo_data["path"], "init"]
                
                self._init_worker = ResticWorker(self.restic_cmd, args, env, timeout=60)
                self._init_worker.finished.connect(self._on_repository_initialized)
                self._init_worker.start()
                
                self.log(f"Initializing repository: {repo_data['name']}")
            else:
                # Add repository without initialization
                repositories = self.settings_manager.get("repositories")
                repositories.append(repo_data)
                self.settings_manager.set("repositories", repositories)
                self.settings_manager.save_settings()
                self.refresh_repository_list()
                self.update_repository_combos()
                self.log(f"Added repository: {repo_data['name']}")
                QMessageBox.information(self, "Success", f"Repository '{repo_data['name']}' added successfully!")
    
    def _on_repository_initialized(self, success, stdout, stderr):
        """Callback when repository initialization completes"""
        # Close progress dialog
        if hasattr(self, '_add_repo_progress'):
            try:
                self._add_repo_progress.close()
                self._add_repo_progress.deleteLater()
            except:
                pass
        
        repo_data = self._pending_repo_data
        
        if success:
            # Add repository to list
            repositories = self.settings_manager.get("repositories")
            repositories.append(repo_data)
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
    
    def refresh_repository_list(self):
        """Refresh the repository list table"""
        repositories = self.settings_manager.get("repositories")
        self.repo_table.setRowCount(len(repositories))
        
        for i, repo in enumerate(repositories):
            self.repo_table.setItem(i, 0, QTableWidgetItem(repo.get("name", "")))
            self.repo_table.setItem(i, 1, QTableWidgetItem(repo.get("path", "")))
            self.repo_table.setItem(i, 2, QTableWidgetItem(repo.get("type", "local")))
            self.repo_table.setItem(i, 3, QTableWidgetItem(repo.get("last_checked", "Never")))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_widget.setLayout(btn_layout)
            
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda checked, idx=i: self.edit_repository(idx))
            btn_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, idx=i: self.delete_repository(idx))
            btn_layout.addWidget(delete_btn)
            
            self.repo_table.setCellWidget(i, 4, btn_widget)
    
    def edit_repository(self, index):
        """Edit repository at index"""
        repositories = self.settings_manager.get("repositories")
        if 0 <= index < len(repositories):
            repo = repositories[index]
            dialog = RepositoryDialog(self, self.settings_manager, repo)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                repo_data = dialog.get_repository_data()
                repositories[index] = repo_data
                self.settings_manager.set("repositories", repositories)
                self.settings_manager.save_settings()
                self.refresh_repository_list()
                self.update_repository_combos()
                self.log(f"Updated repository: {repo_data['name']}")
    
    def delete_repository(self, index):
        """Delete repository at index"""
        reply = QMessageBox.question(
            self, "Delete Repository",
            "Are you sure you want to remove this repository from the list?\n"
            "(This will not delete the actual backup data)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            repositories = self.settings_manager.get("repositories")
            if 0 <= index < len(repositories):
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
        
        for combo in [self.snapshot_repo_combo, self.restore_repo_combo, 
                      self.retention_repo_combo, self.dashboard_repo_combo]:
            combo.clear()
            combo.addItems(repo_names)
        
        # Refresh dashboard after updating combos
        self.refresh_dashboard()
    
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
        self.snapshots_table.setRowCount(0)
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
                
                self.snapshots_table.setRowCount(len(snapshots))
                
                for i, snapshot in enumerate(snapshots):
                    # ID (short)
                    snapshot_id = snapshot.get("short_id", snapshot.get("id", "")[:8])
                    self.snapshots_table.setItem(i, 0, QTableWidgetItem(snapshot_id))
                    
                    # Time
                    time_str = snapshot.get("time", "")
                    if time_str:
                        # Format: 2026-03-13T05:27:50.7033785Z -> 2026-03-13 05:27:50
                        time_str = time_str.replace("T", " ").split(".")[0]
                    self.snapshots_table.setItem(i, 1, QTableWidgetItem(time_str))
                    
                    # Host
                    host = snapshot.get("hostname", "")
                    self.snapshots_table.setItem(i, 2, QTableWidgetItem(host))
                    
                    # Tags
                    tags = ", ".join(snapshot.get("tags", []))
                    self.snapshots_table.setItem(i, 3, QTableWidgetItem(tags))
                    
                    # Paths
                    paths = "\n".join(snapshot.get("paths", []))
                    self.snapshots_table.setItem(i, 4, QTableWidgetItem(paths))
                    
                    # Size (if available in summary)
                    summary = snapshot.get("summary", {})
                    data_added = summary.get("data_added", 0)
                    size_str = self.format_bytes(data_added) if data_added > 0 else "—"
                    self.snapshots_table.setItem(i, 5, QTableWidgetItem(size_str))
                    
                    # Store full snapshot data in first cell for later use
                    item = self.snapshots_table.item(i, 0)
                    item.setData(Qt.ItemDataRole.UserRole, snapshot)
                
                self.log(f"Loaded {len(snapshots)} snapshot(s) for {self._current_snapshot_repo_name}")
                
            except json.JSONDecodeError as e:
                self.log(f"Error parsing snapshots JSON: {str(e)}")
                QMessageBox.warning(self, "Error", f"Failed to parse snapshots data: {str(e)}")
        else:
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
        snapshot_item = self.snapshots_table.item(row, 0)
        snapshot_data = snapshot_item.data(Qt.ItemDataRole.UserRole)
        
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
                details.append(f"  • {path}")
        else:
            details.append("\nPaths: None")
        
        # Excludes (if available)
        excludes = snapshot_data.get("excludes", [])
        if excludes:
            details.append(f"\nExcludes ({len(excludes)}):")
            for exclude in excludes[:5]:  # Show first 5
                details.append(f"  • {exclude}")
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
        snapshot_item = self.snapshots_table.item(row, 0)
        snapshot_id = snapshot_item.text()
        snapshot_data = snapshot_item.data(Qt.ItemDataRole.UserRole)
        
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
        
        # Show dialog with file list
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Snapshot Content - {snapshot_id}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<b>Browsing snapshot:</b> {snapshot_id}"))
        header_layout.addStretch()
        
        # Add refresh button
        refresh_btn = QPushButton("Refresh")
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Search controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search files... (use '|' for OR, '&' for AND)")
        search_input.setFixedWidth(450)
        search_input.setToolTip("Enter text to filter files. Use '|' for OR (any match) or '&' for AND (all must match).")
        search_layout.addWidget(search_input)
        
        search_filter_dropdown = QComboBox()
        search_filter_dropdown.addItems(["Contains", "Not Contain"])
        search_filter_dropdown.setCurrentText("Contains")
        search_filter_dropdown.setFixedWidth(110)
        search_filter_dropdown.setToolTip("Select the type of search filter to apply.")
        search_layout.addWidget(search_filter_dropdown)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # File list
        file_list = QListWidget()
        file_list.setFont(QFont("Courier", 9))
        file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(file_list)
        
        # Status label (define before filter function)
        status_label = QLabel("Loading files...")
        layout.addWidget(status_label)
        
        # Store all files for filtering
        dialog._all_files = []
        
        # Filter function
        def filter_files():
            """Filter file list based on search text"""
            search_text = search_input.text().strip()
            
            # Start with all files
            filtered_files = dialog._all_files[:]
            
            if search_text:
                # Check if using AND logic (&) or OR logic (|)
                if '&' in search_text and '|' not in search_text:
                    # AND logic: all terms must be present
                    search_terms = [term.strip().lower() for term in search_text.split('&')]
                    
                    if search_filter_dropdown.currentText() == "Contains":
                        # Match if ALL terms are found in the line
                        filtered_files = [line for line in filtered_files if all(term in line.lower() for term in search_terms)]
                    else:
                        # Match if NOT ALL terms are found (at least one term is missing)
                        filtered_files = [line for line in filtered_files if not all(term in line.lower() for term in search_terms)]
                else:
                    # OR logic (default): split by '|' to support multiple search terms
                    search_terms = [term.strip().lower() for term in search_text.split('|')]
                    
                    if search_filter_dropdown.currentText() == "Contains":
                        # Match if ANY term is found in the line
                        filtered_files = [line for line in filtered_files if any(term in line.lower() for term in search_terms)]
                    else:
                        # Match if NONE of the terms are found in the line
                        filtered_files = [line for line in filtered_files if not any(term in line.lower() for term in search_terms)]
            
            # Update file list
            file_list.clear()
            if not filtered_files and search_text:
                file_list.addItem(f"No files found matching '{search_text}'")
            else:
                for line in filtered_files:
                    file_list.addItem(line)
            
            # Update status
            if search_text:
                status_label.setText(f"Showing {len(filtered_files)} of {len(dialog._all_files)} files")
            else:
                status_label.setText(f"Loaded {len(filtered_files)} files")
        
        # Connect search input and dropdown to filter function
        search_input.textChanged.connect(filter_files)
        search_filter_dropdown.currentIndexChanged.connect(filter_files)
        
        # Store filter function reference
        dialog._filter_files = filter_files
        
        # Connect refresh button (after defining file_list)
        refresh_btn.clicked.connect(lambda: self._load_snapshot_content(file_list, full_id, repo, password, status_label, dialog))
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        copy_path_btn = QPushButton("Copy Selected Path")
        copy_path_btn.clicked.connect(lambda: self._copy_selected_paths(file_list))
        btn_layout.addWidget(copy_path_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Store references for the worker callback
        dialog._file_list = file_list
        dialog._status_label = status_label
        dialog._repo = repo
        dialog._password = password
        dialog._full_id = full_id
        
        # Load snapshot content
        self._load_snapshot_content(file_list, full_id, repo, password, status_label, dialog)
        
        self.log(f"Browsing content of snapshot {snapshot_id}")
        dialog.exec()
    
    def _load_snapshot_content(self, file_list, snapshot_id, repo, password, status_label=None, dialog=None):
        """Load files from snapshot using restic ls command"""
        if status_label:
            status_label.setText("Loading files...")
        
        file_list.clear()
        file_list.addItem("Loading snapshot contents...")
        
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
    
    def _on_snapshot_content_loaded(self, success, stdout, stderr, file_list, status_label=None, dialog=None):
        """Callback when snapshot content is loaded"""
        file_list.clear()
        
        if success and stdout:
            # Parse the output - each line is a file
            lines = stdout.strip().split('\n')
            
            if lines:
                # Store all files in dialog for filtering
                if dialog:
                    dialog._all_files = [line for line in lines if line.strip()]
                    # Apply current filter
                    if hasattr(dialog, '_filter_files'):
                        dialog._filter_files()
                else:
                    # Fallback if no dialog (shouldn't happen)
                    for line in lines:
                        if line.strip():
                            file_list.addItem(line)
                
                if status_label:
                    status_label.setText(f"Loaded {len(lines)} items")
                
                self.log(f"Loaded {len(lines)} items from snapshot")
            else:
                file_list.addItem("(No files in snapshot)")
                if status_label:
                    status_label.setText("No files found")
        else:
            error_msg = stderr if stderr else "Unknown error"
            file_list.addItem(f"Error loading snapshot contents:\n{error_msg}")
            if status_label:
                status_label.setText("Error loading files")
            self.log(f"Error loading snapshot content: {error_msg}")
    
    def _copy_selected_paths(self, file_list):
        """Copy selected file paths to clipboard"""
        selected_items = file_list.selectedItems()
        if not selected_items:
            return
        
        # Extract paths from the selected items
        paths = []
        for item in selected_items:
            text = item.text()
            # The format from 'ls --long' is typically: <permissions> <size> <date> <time> <path>
            # Extract just the path (last part)
            parts = text.split()
            if len(parts) >= 5:
                # Join everything after the time as the path (handles paths with spaces)
                path = ' '.join(parts[4:])
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
        # Snapshots are in chronological order (oldest first)
        # Row 0 = oldest, Row N-1 = newest
        if row == 0:
            QMessageBox.information(self, "No Previous", "This is the oldest snapshot, no previous snapshot to compare")
            return
        
        # Current snapshot (newer)
        snapshot_id = self.snapshots_table.item(row, 0).text()
        # Previous snapshot (older) - one row before
        prev_snapshot_id = self.snapshots_table.item(row - 1, 0).text()
        
        # Get repository info
        if not hasattr(self, '_current_snapshot_repo'):
            QMessageBox.warning(self, "Error", "No repository selected")
            return
        
        repo = self._current_snapshot_repo
        repo_name = self._current_snapshot_repo_name
        repo_full, password = self.get_repository_by_name(repo_name)
        
        # Show diff dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Diff: {snapshot_id} vs {prev_snapshot_id}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        info_label = QLabel(f"Comparing snapshot {snapshot_id} (newer) with {prev_snapshot_id} (older)")
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(info_label)
        
        # Diff output
        diff_output = QPlainTextEdit()
        diff_output.setReadOnly(True)
        diff_output.setPlainText("Loading diff...\n")
        diff_output.setFont(QFont("Consolas", 9))
        layout.addWidget(diff_output)
        
        # Statistics labels
        stats_layout = QHBoxLayout()
        added_label = QLabel("Added: 0")
        modified_label = QLabel("Modified: 0")
        removed_label = QLabel("Removed: 0")
        stats_layout.addWidget(added_label)
        stats_layout.addWidget(modified_label)
        stats_layout.addWidget(removed_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(120)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        close_btn_layout = QHBoxLayout()
        close_btn_layout.addStretch()
        close_btn_layout.addWidget(close_btn)
        close_btn_layout.addStretch()
        
        close_btn.clicked.connect(dialog.accept)
        layout.addLayout(close_btn_layout)
        
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
            
            # Color code the labels
            added_label.setStyleSheet("color: #28a745; font-weight: bold;")
            modified_label.setStyleSheet("color: #ffc107; font-weight: bold;")
            removed_label.setStyleSheet("color: #dc3545; font-weight: bold;")
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
        snapshot_item = self.snapshots_table.item(row, 0)
        snapshot_id = snapshot_item.text()
        snapshot_data = snapshot_item.data(Qt.ItemDataRole.UserRole)
        
        # Get full snapshot ID from stored data
        full_id = snapshot_data.get("id", snapshot_id) if snapshot_data else snapshot_id
        
        # Get paths for display
        paths = snapshot_data.get("paths", []) if snapshot_data else []
        paths_str = "\n  • ".join(paths) if paths else "Unknown"
        
        reply = QMessageBox.question(
            self, "Forget Snapshot",
            f"Are you sure you want to forget (delete) this snapshot?\n\n"
            f"Snapshot ID: {snapshot_id}\n"
            f"Paths:\n  • {paths_str}\n\n"
            "This marks the snapshot for deletion.\n"
            "Run 'Prune Repository' afterward to free disk space.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            repo_name = self.snapshot_repo_combo.currentText()
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
        
        reply = QMessageBox.question(
            self, "Prune Repository",
            f"Prune repository '{repo_name}'?\n\n"
            "This will remove unreferenced data and free disk space.\n"
            "This operation can take a long time.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
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
            close_btn.setFixedWidth(120)
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
        
        reply = QMessageBox.question(
            self, "Unlock Repository",
            f"Remove all locks from repository '{repo_name}'?\n\n"
            "This will remove stale locks that may have been left by crashed processes.\n"
            "Only do this if you're sure no other restic process is currently running.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
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
        
        self.repo_stats_text.setText(f"Loading stats for {repo_name}...")
        self.log(f"Loading stats for repository {repo_name}")
        
        # Store repo info for callback
        self._current_stats_repo = repo
        self._current_stats_repo_name = repo_name
        
        # Execute restic stats command in background thread
        env = {"RESTIC_PASSWORD": password} if password else {}
        args = ["-r", repo["path"], "stats", "--json"]
        
        # Create and start worker thread
        self._stats_worker = ResticWorker(self.restic_cmd, args, env)
        self._stats_worker.finished.connect(self._on_stats_loaded)
        self._stats_worker.start()
    
    def _on_stats_loaded(self, success, stdout, stderr):
        """Callback when stats loading completes"""
        repo = self._current_stats_repo
        repo_name = self._current_stats_repo_name
        
        # Log raw output for debugging
        self.log(f"Stats result for {repo_name}: success={success}, stdout_len={len(stdout) if stdout else 0}, stderr_len={len(stderr) if stderr else 0}")
        
        if success and stdout:
            try:
                stats = json.loads(stdout)
                
                # Log the parsed stats for debugging
                self.log(f"Parsed stats: {stats}")
                
                # Format stats display
                total_size = stats.get("total_size", 0)
                total_file_count = stats.get("total_file_count", 0)
                
                # Convert size to human readable
                size_str = self.format_bytes(total_size)
                
                stats_text = f"Repository: {repo_name}\n"
                stats_text += f"Path: {repo['path']}\n"
                stats_text += f"Type: {repo.get('type', 'local')}\n\n"
                stats_text += f"Total Size: {size_str}\n"
                stats_text += f"Total Files: {total_file_count:,}\n"
                
                # Add info if repository is empty
                if total_size == 0 and total_file_count == 0:
                    stats_text += f"\nℹ This repository is empty (no snapshots yet).\n"
                    stats_text += f"Create a backup to this repository to see statistics."
                
                self.repo_stats_text.setText(stats_text)
                self.log(f"Successfully loaded stats for {repo_name}")
                
            except json.JSONDecodeError as e:
                # Try parsing plain text output
                self.log(f"JSON decode error: {str(e)}")
                self.repo_stats_text.setText(f"Repository: {repo_name}\n"
                                             f"Path: {repo['path']}\n\n"
                                             f"Stats Output:\n{stdout}")
                self.log(f"Stats loaded (plain text) for {repo_name}")
        else:
            error_msg = stderr if stderr else "Unknown error"
            self.repo_stats_text.setText(f"Error loading stats for {repo_name}:\n\n{error_msg}")
            self.log(f"Error loading stats for {repo_name}: {error_msg}")
    
    def verify_repository(self):
        """Verify repository integrity"""
        repo_name = self.dashboard_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository first")
            return
        
        repo, password = self.get_repository_by_name(repo_name)
        if not repo:
            QMessageBox.warning(self, "Error", f"Repository '{repo_name}' not found")
            return
        
        reply = QMessageBox.question(
            self, "Verify Repository",
            f"Verify integrity of repository '{repo_name}'?\n\n"
            "This will check all data and may take a long time.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log(f"Verifying repository {repo_name}...")
            
            # Store repo info for callback
            self._verify_repo_name = repo_name
            
            # Show progress dialog with close button
            self._verify_progress = QDialog(self)
            self._verify_progress.setWindowTitle("Verifying Repository")
            self._verify_progress.setModal(False)
            
            layout = QVBoxLayout()
            self._verify_progress.setLayout(layout)
            
            label = QLabel(f"Verifying {repo_name}...\n\nThis may take several minutes.\n\nYou can continue using the application.")
            layout.addWidget(label)
            
            # Add close button
            close_btn = QPushButton("Close (operation continues in background)")
            close_btn.clicked.connect(self._verify_progress.accept)
            layout.addWidget(close_btn)
            
            self._verify_progress.show()
            
            # Execute restic check command in background thread with longer timeout (30 minutes)
            env = {"RESTIC_PASSWORD": password} if password else {}
            args = ["-r", repo["path"], "check"]
            
            self._verify_worker = ResticWorker(self.restic_cmd, args, env, timeout=1800)  # 30 minutes
            self._verify_worker.finished.connect(self._on_verify_complete)
            self._verify_worker.start()
    
    def _on_verify_complete(self, success, stdout, stderr):
        """Callback when verification completes"""
        repo_name = self._verify_repo_name
        
        # Close progress dialog if still open
        if hasattr(self, '_verify_progress'):
            try:
                self._verify_progress.close()
                self._verify_progress.deleteLater()
            except:
                pass
        
        if success:
            QMessageBox.information(self, "Verification Complete",
                                  f"Repository '{repo_name}' verified successfully!\n\n{stdout[:500]}")
            self.log(f"Repository {repo_name} verified successfully")
        else:
            error_msg = stderr if stderr else "Unknown error"
            QMessageBox.warning(self, "Verification Failed",
                               f"Repository verification failed:\n\n{error_msg[:500]}")
            self.log(f"Repository {repo_name} verification failed: {error_msg}")
            self.log(f"Repository {repo_name} verification failed: {error_msg}")
    
    def load_snapshots_for_restore(self):
        """Load snapshots into restore dropdown"""
        self.restore_snapshot_combo.clear()
        # TODO: Load actual snapshots
        self.restore_snapshot_combo.addItem("Select a snapshot")
    
    # Restore Methods
    def browse_snapshot_files(self):
        """Browse files in selected snapshot"""
        self.log("Snapshot file browser - to be implemented")
    
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
        snapshot = self.restore_snapshot_combo.currentText()
        target = self.restore_target_input.text()
        
        if not all([repo_name, snapshot, target]):
            QMessageBox.warning(self, "Incomplete", "Please fill all required fields")
            return
        
        self.restore_progress.setVisible(True)
        self.restore_progress.setRange(0, 0)  # Indeterminate
        
        self.log(f"Starting restore from {repo_name}/{snapshot} to {target}")
        # TODO: Implement actual restore
        
        QTimer.singleShot(2000, lambda: self.restore_progress.setVisible(False))
    
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
            self.log(f"Deleted backup job and scheduled task: {job['name']}")
    
    def run_backup_job(self, job):
        """Run a backup job"""
        # Get repository
        repo, password = self.get_repository_by_name(job["repository"])
        if not repo:
            QMessageBox.warning(self, "Repository Not Found", f"Repository '{job['repository']}' not found.")
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
        
        # Show progress dialog
        self._backup_progress_dialog = QDialog(self)
        self._backup_progress_dialog.setWindowTitle(f"Running Backup Job: {job['name']}")
        self._backup_progress_dialog.setModal(True)
        self._backup_progress_dialog.setMinimumWidth(500)
        self._backup_progress_dialog.setMinimumHeight(300)
        
        dialog_layout = QVBoxLayout()
        self._backup_progress_dialog.setLayout(dialog_layout)
        
        info_label = QLabel(f"Backup Job: {job['name']}\nRepository: {job['repository']}\n\nPaths:\n" + "\n".join(f"  • {p}" for p in job["paths"]))
        dialog_layout.addWidget(info_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        dialog_layout.addWidget(progress_bar)
        
        status_label = QLabel("Starting backup...")
        dialog_layout.addWidget(status_label)
        
        # Current file label
        current_file_label = QLabel("")
        current_file_label.setWordWrap(True)
        current_file_label.setMaximumHeight(40)
        dialog_layout.addWidget(current_file_label)
        
        output_text = QPlainTextEdit()
        output_text.setReadOnly(True)
        output_text.setStyleSheet(stylesheet)
        dialog_layout.addWidget(output_text)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel Backup")
        cancel_btn.setToolTip("Cancel the running backup job. This will stop the backup and unlock the repository.")
        cancel_btn.setFixedWidth(120)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(lambda: self._cancel_backup())
        buttons_layout.addWidget(cancel_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setEnabled(False)
        close_btn.setToolTip("Close this dialog. The backup will continue running in the background.")
        close_btn.setFixedWidth(120)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._backup_progress_dialog.close)
        buttons_layout.addWidget(close_btn)
        
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
        QApplication.processEvents()
        
        # Store dialog widgets and repo info for callback
        self._backup_progress_bar = progress_bar
        self._backup_status_label = status_label
        self._backup_current_file_label = current_file_label
        self._backup_output_text = output_text
        self._backup_close_btn = close_btn
        self._backup_cancel_btn = cancel_btn
        self._backup_job_name = job['name']
        self._backup_repo = repo
        self._backup_repo_password = password
        self._backup_is_cancelled = False
        
        # Start backup
        self.log(f"Starting backup job: {job['name']}")
        self.log(f"Command: restic {' '.join(args)}")
        
        self._backup_worker = ResticWorker(self.restic_cmd, args, env, timeout=3600, use_progress=True)
        self._backup_worker.finished.connect(self._on_backup_completed)
        self._backup_worker.progress_data.connect(self._on_backup_progress)
        self._backup_worker.progress.connect(self._on_backup_output)
        self._backup_worker.start()
    
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
                self._backup_status_label.setText("⚠ Backup cancelled by user")
            
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
        
        # Update dialog
        if hasattr(self, '_backup_progress_bar'):
            self._backup_progress_bar.setRange(0, 100)
            self._backup_progress_bar.setValue(100)
        
        # Add completion message to output (output already displayed dynamically)
        if hasattr(self, '_backup_output_text'):
            self._backup_output_text.appendPlainText("")
            self._backup_output_text.appendPlainText("=" * 60)
            if success:
                self._backup_output_text.appendPlainText("✓ Backup completed successfully!")
            else:
                self._backup_output_text.appendPlainText("✗ Backup failed!")
            self._backup_output_text.appendPlainText("=" * 60)
            # Auto-scroll to bottom
            scrollbar = self._backup_output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        if hasattr(self, '_backup_cancel_btn'):
            self._backup_cancel_btn.setEnabled(False)
        
        if hasattr(self, '_backup_close_btn'):
            self._backup_close_btn.setEnabled(True)
        
        if success:
            if hasattr(self, '_backup_status_label'):
                self._backup_status_label.setText("✓ Backup completed successfully!")
            
            self.log(f"Backup job '{self._backup_job_name}' completed successfully")
            
            # Auto-unlock if locks exist (check and unlock)
            self._auto_unlock_after_completion()
            
            # Refresh snapshots if on snapshots page
            if hasattr(self, 'snapshots_table'):
                QTimer.singleShot(1000, self.load_snapshots)
        else:
            if hasattr(self, '_backup_status_label'):
                self._backup_status_label.setText("✗ Backup failed!")
            
            error_msg = stderr if stderr else "Unknown error"
            self.log(f"Backup job '{self._backup_job_name}' failed: {error_msg}")
            
            # Also try to unlock on failure in case lock is stuck
            if "locked" in error_msg.lower():
                self._auto_unlock_after_completion()
    
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
    def apply_retention(self, dry_run=True):
        """Apply retention policy"""
        repo_name = self.retention_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        policy = {
            "last": self.keep_last_spin.value(),
            "hourly": self.keep_hourly_spin.value(),
            "daily": self.keep_daily_spin.value(),
            "weekly": self.keep_weekly_spin.value(),
            "monthly": self.keep_monthly_spin.value(),
            "yearly": self.keep_yearly_spin.value()
        }
        
        mode = "Dry run" if dry_run else "Applying"
        self.log(f"{mode} retention policy for {repo_name}")
        self.log(f"Policy: {policy}")
        
        self.retention_output.setPlainText(
            f"{mode} retention policy...\n\n"
            f"Repository: {repo_name}\n"
            f"Policy: {json.dumps(policy, indent=2)}\n\n"
            "Full implementation needed"
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
    
    def change_theme(self, theme):
        """Change application theme"""
        self.apply_theme(theme)
    
    def save_settings(self):
        """Save application settings"""
        self.settings_manager.set("restic_path", self.restic_path_input.text())
        self.settings_manager.set("theme", self.theme_combo.currentText())
        self.settings_manager.set("auto_refresh_snapshots", self.auto_refresh_check.isChecked())
        self.settings_manager.set("snapshot_refresh_interval", self.refresh_interval_spin.value())
        
        self.settings_manager.save_settings()
        
        # Update Restic command
        self.restic_cmd = ResticCommand(
            restic_path=self.settings_manager.get("restic_path"),
            debug=True
        )
        
        QMessageBox.information(self, "Success", "Settings saved successfully!")
        self.log("Settings saved")
    
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
        copy_btn.setFixedWidth(80)
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
        # Update the theme setting first
        self.settings_manager.set("theme", theme)
        
        if theme == "dark":
            self.app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        elif theme == "dark-cyan":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #001f2f;
                color: #00ffff;
            }

            QPushButton {
                background-color: #003344;
                color: #00ffff;
            }

            QPushButton:hover {
                background-color: #035a70;
                color: #00ffff;
            }

            QPushButton:checked {
                background-color: #00667a;
                color: #ffffff;
                border: 2px solid #00ffff;
            }

            QPushButton:focus {
                outline: none;
                border: 1px solid #00ffff;
            }

            QPushButton:pressed {
                background-color: #022e3a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "dark-navy":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #12233d;
                color: #dadfe6;
            }

            QPushButton {
                background-color: #1f3a5c;
                color: #dadfe6;
            }

            QPushButton:hover {
                background-color: #2d4a70;
                border: 1px solid #70a0ff;
                color: #ffffff;
            }

            QPushButton:checked {
                background-color: #3a5a80;
                border: 2px solid #70a0ff;
                color: #ffffff;
            }

            QPushButton:focus {
                border: 1px solid #70a0ff;
            }

            QPushButton:pressed {
                background-color: #1a2e4a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "dark-green":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #0c2b29;
                color: #dadfe6;
            }

            QPushButton {
                background-color: #145c54;
                color: #dadfe6;
            }

            QPushButton:hover {
                background-color: #1f7a6d;
                border: 1px solid #88ffcc;
                color: #ffffff;
            }

            QPushButton:checked {
                background-color: #258b7d;
                border: 2px solid #88ffcc;
                color: #ffffff;
            }

            QPushButton:focus {
                border: 1px solid #88ffcc;
            }

            QPushButton:pressed {
                background-color: #0f3f3a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "light-green":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
            stylesheet += """
            QWidget {
                background-color: #d5f2e6;
                color: #222423;
            }

            QPushButton {
                background-color: #9fcfbc;
                color: #222423;
            }

            QPushButton:hover {
                background-color: #5c9c87;
                border: 1px solid #3c7a69;
                color: #ffffff;
            }

            QPushButton:checked {
                background-color: #4a8a75;
                border: 2px solid #00cc99;
                color: #ffffff;
            }

            QPushButton:focus {
                border: 1px solid #00cc99;
            }

            QPushButton:pressed {
                background-color: #497d6b;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "dark-purple":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #1c0f2f;
                color: #d4c6f0;
            }
            QPushButton {
                background-color: #2e1a4f;
                color: #d4c6f0;
                border: 1px solid #835fdd;
            }
            QPushButton:hover {
                background-color: #3b2060;
                border: 1px solid #a07bff;
            }
            QPushButton:checked {
                background-color: #472570;
                border: 2px solid #a07bff;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "solarized-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #002b36;
                color: #93a1a1;
            }
            QPushButton {
                background-color: #073642;
                color: #93a1a1;
                border: 1px solid #586e75;
            }
            QPushButton:hover {
                background-color: #0c3b49;
                border: 1px solid #839496;
            }
            QPushButton:checked {
                background-color: #104650;
                border: 2px solid #839496;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)
            
        elif theme == "light-blue":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
            stylesheet += """
            QWidget {
                background-color: #e7f0fb;
                color: #1a2b3c;
            }
            QPushButton {
                background-color: #b6d8f2;
                color: #1a2b3c;
                border: 1px solid #5a9ecf;
            }
            QPushButton:hover {
                background-color: #a0cfee;
                border: 1px solid #397ebd;
            }
            QPushButton:checked {
                background-color: #8fc6ea;
                border: 2px solid #397ebd;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "monokai-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #272822;
                color: #f8f8f2;
            }
            QPushButton {
                background-color: #49483e;
                color: #f8f8f2;
                border: 1px solid #a6e22e;
            }
            QPushButton:hover {
                background-color: #5a594d;
                border: 1px solid #a6e22e;
            }
            QPushButton:checked {
                background-color: #6b6a5c;
                border: 2px solid #a6e22e;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "dark-indigo":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #1a1b3a;
                color: #c3c8f0;
            }
            QPushButton {
                background-color: #2e2f5e;
                color: #c3c8f0;
            }
            QPushButton:hover {
                background-color: #44468f;
                color: #ffffff;
                border: 1px solid #5c5fd2;
            }
            QPushButton:checked {
                background-color: #5052a0;
                border: 2px solid #5c5fd2;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)
            
        elif theme == "dark-magenta":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #2a0a2a;
                color: #f2d9f7;
            }
            QPushButton {
                background-color: #4c1a4c;
                color: #f2d9f7;
            }
            QPushButton:hover {
                background-color: #6e2a6e;
                color: #ffffff;
                border: 1px solid #cc66cc;
            }
            QPushButton:checked {
                background-color: #7d357d;
                border: 2px solid #cc66cc;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "sunset-orange":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
            stylesheet += """
            QWidget {
                background-color: #fff3e6;
                color: #552200;
            }
            QPushButton {
                background-color: #ff884d;
                color: #fff3e6;
            }
            QPushButton:hover {
                background-color: #e67300;
                color: #ffffff;
                border: 1px solid #cc5200;
            }
            QPushButton:checked {
                background-color: #d66500;
                border: 2px solid #cc5200;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "forest-moss":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #1c2d24;
                color: #cfe9cc;
            }
            QPushButton {
                background-color: #355e3b;
                color: #cfe9cc;
            }
            QPushButton:hover {
                background-color: #4b8b5c;
                color: #ffffff;
                border: 1px solid #6bbf59;
            }
            QPushButton:checked {
                background-color: #5a9a6b;
                border: 2px solid #6bbf59;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "cool-grey":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #2e2e38;
                color: #dcdfe6;
            }
            QPushButton {
                background-color: #444653;
                color: #dcdfe6;
            }
            QPushButton:hover {
                background-color: #5a5d6a;
                color: #ffffff;
                border: 1px solid #7c7f8a;
            }
            QPushButton:checked {
                background-color: #6a6d7a;
                border: 2px solid #7c7f8a;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "pure-black":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #000000;
                color: #ffffff;
            }
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #666666;
            }
            QPushButton:hover {
                background-color: #444444;
                border: 1px solid #888888;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #555555;
                border: 2px solid #ffffff;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
            QScrollArea {
                background-color: #000000;
            }
            QFrame {
                background-color: #000000;
                border: 1px solid #333333;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "midnight-blue":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #0d1421;
                color: #e1e5e9;
            }
            QPushButton {
                background-color: #1e2a3a;
                color: #e1e5e9;
                border: 1px solid #3a4f66;
            }
            QPushButton:hover {
                background-color: #2a3847;
                border: 1px solid #5a8fb4;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #3d4e63;
                border: 2px solid #8db9d1;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #152028;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "cyberpunk-neon":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #0a0a0a;
                color: #00f5ff;
            }
            QPushButton {
                background-color: #1a0a1a;
                color: #00f5ff;
                border: 1px solid #ff006e;
            }
            QPushButton:hover {
                background-color: #2a1a2a;
                border: 1px solid #8338ec;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #3a2a3a;
                border: 2px solid #ff006e;
                color: #00f5ff;
            }
            QPushButton:pressed {
                background-color: #0f0510;
            }
            QScrollArea {
                background-color: #0a0a0a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "github-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #0d1117;
                color: #f0f6fc;
            }
            QPushButton {
                background-color: #21262d;
                color: #f0f6fc;
                border: 1px solid #30363d;
            }
            QPushButton:hover {
                background-color: #30363d;
                border: 1px solid #58a6ff;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #388bfd;
                border: 2px solid #58a6ff;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "vscode-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #5a5a5a;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #9cdcfe;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #0e639c;
                border: 2px solid #9cdcfe;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "material-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #212121;
                color: #ffffff;
            }
            QPushButton {
                background-color: #424242;
                color: #ffffff;
                border: 1px solid #616161;
            }
            QPushButton:hover {
                background-color: #515151;
                border: 1px solid #81c784;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #1976d2;
                border: 2px solid #64b5f6;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "dracula":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #282a36;
                color: #f8f8f2;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: 1px solid #6272a4;
            }
            QPushButton:hover {
                background-color: #6272a4;
                border: 1px solid #50fa7b;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #bd93f9;
                border: 2px solid #ff79c6;
                color: #282a36;
            }
            QPushButton:pressed {
                background-color: #21222c;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "nord-dark":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #2e3440;
                color: #eceff4;
            }
            QPushButton {
                background-color: #3b4252;
                color: #eceff4;
                border: 1px solid #434c5e;
            }
            QPushButton:hover {
                background-color: #434c5e;
                border: 1px solid #88c0d0;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #5e81ac;
                border: 2px solid #81a1c1;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #242831;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "amoled-black":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #000000;
                color: #ffffff;
            }
            QPushButton {
                background-color: #111111;
                color: #ffffff;
                border: 1px solid #333333;
            }
            QPushButton:hover {
                background-color: #222222;
                border: 1px solid #bb86fc;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #333333;
                border: 2px solid #03dac6;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0a0a0a;
            }
            QScrollArea {
                background-color: #000000;
            }
            QFrame {
                background-color: #000000;
                border: 1px solid #111111;
            }
            """
            self.app.setStyleSheet(stylesheet)

        elif theme == "matrix-green":
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
            stylesheet += """
            QWidget {
                background-color: #000000;
                color: #00ff41;
            }
            QPushButton {
                background-color: #001100;
                color: #00ff41;
                border: 1px solid #003300;
            }
            QPushButton:hover {
                background-color: #002200;
                border: 1px solid #00cc33;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #003300;
                border: 2px solid #00ff41;
                color: #000000;
            }
            QPushButton:pressed {
                background-color: #000800;
            }
            QScrollArea {
                background-color: #000000;
            }
            QFrame {
                background-color: #000000;
                border: 1px solid #001100;
            }
            """
            self.app.setStyleSheet(stylesheet)
    
        else:
            # Light theme
            stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
            stylesheet += """
            QPushButton:checked {
                background-color: #007acc;
                border: 2px solid #005a9e;
                color: #ffffff;
            }
            """
            self.app.setStyleSheet(stylesheet)
        
        # Refresh status widgets if they exist
        self.refresh_status_widget_themes()

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
    def check_restic_installation(self):
        """Check if Restic is installed and accessible"""
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
    
    def clear_logs(self):
        """Clear log viewer"""
        self.log_viewer.clear()

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
        
        # Get repository
        repositories = settings_manager.get("repositories")
        repo = next((r for r in repositories if r["name"] == job["repository"]), None)
        
        if not repo:
            print(f"[ERROR] Repository '{job['repository']}' not found!")
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
        
        print(f"[Restic Manager CLI] Running backup...")
        print(f"[Restic Manager CLI] Repository: {repo['path']}")
        print(f"[Restic Manager CLI] Paths: {', '.join(job['paths'])}")
        
        # Run backup
        success, stdout, stderr = restic_cmd.run(args, env, timeout=7200)  # 2 hour timeout
        
        # Update last run time in job
        if job.get("schedule"):
            job["schedule"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    
    args = parser.parse_args()
    if args.debug:
        global DEBUG_MODE
        DEBUG_MODE = True
        print("Debug mode enabled: Debug information will be printed to console.")
    
    # Handle CLI mode (for scheduled tasks)
    if args.run_job:
        return run_job_cli(args.run_job)

    app = QApplication(sys.argv)
    
    # Set application info
    app.setApplicationName("Restic Backup Manager")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("ResticManager")

    # Set up global exception handler to show crashes in a copyable popup
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Wrapper for the exception handler that works with QApplication"""
        # Print to console for debugging
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        # Show the dialog
        show_exception_dialog(exc_type, exc_value, exc_traceback)
        
    sys.excepthook = exception_hook
    

    # Load settings to get theme
    settings_manager = ResticSettingsManager()
    current_theme = settings_manager.get("theme")
    
    # Map themes to background colors for splash screen
    theme_splash_colors = {
        "light": "#f9f9f9",
        "dark": "#353535",
        "dark-cyan": "#001f2f",
        "dark-navy": "#12233d",
        "dark-green": "#0c2b29",
        "light-green": "#d5f2e6",
        "dark-purple": "#1c0f2f",
        "solarized-dark": "#002b36",
        "light-blue": "#e7f0fb",
        "monokai-dark": "#272822",
        "dark-indigo": "#1a1b3a",
        "dark-magenta": "#2a0a2a",
        "sunset-orange": "#fff3e6",
        "forest-moss": "#1c2d24",
        "cool-grey": "#2e2e38",
        "pure-black": "#000000",
        "midnight-blue": "#0d1421",
        "cyberpunk-neon": "#0a0a0a",
        "github-dark": "#0d1117",
        "vscode-dark": "#1e1e1e",
        "material-dark": "#212121",
        "dracula": "#282a36",
        "nord-dark": "#2e3440",
        "amoled-black": "#000000",
        "matrix-green": "#000000"
    }
    
    # Map themes to text colors for splash screen
    theme_text_colors = {
        "light": "#333333",
        "light-green": "#222423",
        "light-blue": "#1a2b3c",
        "sunset-orange": "#552200"
    }
    
    splash_bg_color = theme_splash_colors.get(current_theme, "#1a1b3a")
    splash_text_color = theme_text_colors.get(current_theme, "#ffffff")
    
    # Create splash screen
    splash_pix = QPixmap(400, 200)
    splash_pix.fill(QColor(splash_bg_color))
    
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    
    # Add text to splash screen
    splash.showMessage(
        f"Restic Backup Manager {VERSION}\n\nLoading application...\n",
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
        QColor(splash_text_color)
    )
    splash.show()
    app.processEvents()

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
        
        # Apply basic styling to license dialog based on theme
        if current_theme == "dark" or "dark" in current_theme:
            license_dialog.setStyleSheet("QDialog { background-color: #2b2b2b; color: #ffffff; }")
        
        result = license_dialog.exec()
        
        if result != QDialog.DialogCode.Accepted:
            # User cancelled - exit application
            return 0
        
        # Re-validate after activation
        is_valid, license_message = license_manager.validate_license()
        if not is_valid:
            QMessageBox.critical(
                None,
                "License Activation Failed",
                f"Could not activate license:\n{license_message}\n\nApplication will now exit."
            )
            return 1
        
        # Recreate splash screen after successful license activation
        splash_pix = QPixmap(400, 200)
        splash_pix.fill(QColor(splash_bg_color))
        splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
        splash.showMessage(
            f"Restic Backup Manager {VERSION}\n\nLicense activated! Loading application...\n",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            QColor(splash_text_color)
        )
        splash.show()
        app.processEvents()

    # Create window and pass splash for dynamic updates
    window = ResticManagerWindow(app, splash)
    
    splash.finish(window)
    splash.close()  # Explicitly close the splash screen
    splash.deleteLater()  # Schedule splash for deletion

    
    window.show()
    window.show()
    window.raise_()  # Bring window to front
    window.activateWindow()  # Make it the active window

    app.processEvents()  # Process all pending events to ensure splash is fully gone
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
