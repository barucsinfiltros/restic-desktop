"""
Restic Backup Manager - GUI Application for managing Restic backups
Version: 1.0.0
"""

from typing import Optional, List, Dict, Tuple, Any
import json
import os
import sys
import subprocess
import traceback
import base64
from datetime import datetime, timezone
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
    QSizePolicy, QTabWidget, QDialog, QDialogButtonBox, QSplashScreen
)
from PyQt6.QtGui import QColor, QFont, QTextCursor, QPixmap
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

import qdarkstyle
from qdarkstyle.light.palette import LightPalette

VERSION = "v1.0.0"
YEAR = datetime.now().year

# Password encryption key (derived from machine-specific data)
def get_encryption_key():
    """Generate encryption key from machine-specific data"""
    # Use machine name + username as salt
    salt = f"{os.environ.get('COMPUTERNAME', 'restic')}-{os.environ.get('USERNAME', 'user')}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(b"restic-manager-key"))
    return key

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
    
    def __init__(self, restic_cmd: ResticCommand, args: List[str], env: Optional[Dict] = None, timeout: int = 300):
        super().__init__()
        self.restic_cmd = restic_cmd
        self.args = args
        self.env = env or {}
        self.timeout = timeout
    
    def run(self):
        """Execute the Restic command in a separate thread"""
        success, stdout, stderr = self.restic_cmd.run(self.args, self.env, timeout=self.timeout)
        self.finished.emit(success, stdout, stderr)


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
        QMessageBox.information(self, "Test Connection", "Connection test - to be implemented")
    
    def get_repository_data(self):
        """Get repository data from form"""
        encrypted_password = ""
        if self.password_input.text():
            encrypted_password = self.password_manager.encrypt(self.password_input.text())
        
        return {
            "name": self.name_input.text(),
            "type": self.type_combo.currentText(),
            "path": self.path_input.text(),
            "password": encrypted_password,
            "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


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


# Main Application Window
class ResticManagerWindow(QMainWindow):
    def __init__(self, app, splash=None):
        super().__init__()
        self.app = app
        self.splash = splash
        
        self._update_splash("Initializing settings...")
        self.settings_manager = ResticSettingsManager()
        self.restic_cmd = ResticCommand(
            restic_path=self.settings_manager.get("restic_path"),
            debug=True
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
        self._update_splash("Configuring repositories...")
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
            ("Create Backup", 4),
            ("Retention Policy", 5),
            ("Logs", 6),
            ("Settings", 7)
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
            label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            value = QLabel("—")
            value.setFont(QFont("Arial", 11))
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
        repo_stats_header.addWidget(self.dashboard_repo_combo)
        refresh_stats_btn = QPushButton("Refresh Stats")
        refresh_stats_btn.clicked.connect(self.load_repository_stats)
        repo_stats_header.addWidget(refresh_stats_btn)
        verify_btn = QPushButton("Verify Repository")
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
        self.snapshots_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.snapshots_table)
        
        # Snapshot details
        details_group = QGroupBox("Snapshot Details")
        details_layout = QVBoxLayout()
        details_group.setLayout(details_layout)
        
        self.snapshot_details = QTextEdit()
        self.snapshot_details.setReadOnly(True)
        self.snapshot_details.setMaximumHeight(150)
        details_layout.addWidget(self.snapshot_details)
        
        layout.addWidget(details_group)
        
        # Snapshot actions
        actions_layout = QHBoxLayout()
        
        browse_content_btn = QPushButton("Browse Content")
        browse_content_btn.clicked.connect(self.browse_snapshot_content)
        actions_layout.addWidget(browse_content_btn)
        
        diff_btn = QPushButton("Diff with Previous")
        diff_btn.clicked.connect(self.diff_snapshots)
        actions_layout.addWidget(diff_btn)
        
        forget_btn = QPushButton("Forget (Delete)")
        forget_btn.clicked.connect(self.forget_snapshot)
        actions_layout.addWidget(forget_btn)
        
        prune_btn = QPushButton("Prune Repository")
        prune_btn.clicked.connect(self.prune_repository)
        actions_layout.addWidget(prune_btn)
        
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
        form_layout.addRow("Repository:", self.restore_repo_combo)
        
        # Snapshot selection
        self.restore_snapshot_combo = QComboBox()
        self.restore_repo_combo.currentTextChanged.connect(self.load_snapshots_for_restore)
        form_layout.addRow("Snapshot:", self.restore_snapshot_combo)
        
        # Path to restore
        path_layout = QHBoxLayout()
        self.restore_path_input = QLineEdit()
        self.restore_path_input.setPlaceholderText("Leave empty to restore all files")
        path_layout.addWidget(self.restore_path_input)
        browse_btn = QPushButton("Browse Snapshot")
        browse_btn.clicked.connect(self.browse_snapshot_files)
        path_layout.addWidget(browse_btn)
        form_layout.addRow("Path to Restore:", path_layout)
        
        # Target directory
        target_layout = QHBoxLayout()
        self.restore_target_input = QLineEdit()
        target_layout.addWidget(self.restore_target_input)
        target_browse_btn = QPushButton("Browse")
        target_browse_btn.clicked.connect(self.browse_restore_target)
        target_layout.addWidget(target_browse_btn)
        form_layout.addRow("Restore To:", target_layout)
        
        layout.addWidget(form_group)
        
        # Restore button
        restore_btn = QPushButton("Start Restore")
        restore_btn.setMinimumHeight(40)
        restore_btn.clicked.connect(self.start_restore)
        layout.addWidget(restore_btn)
        
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
        """Create backup configuration page"""
        page = QWidget()
        layout = QVBoxLayout()
        page.setLayout(layout)
        
        # Title
        title = QLabel("Create Backup")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Backup form
        form_group = QGroupBox("Backup Configuration")
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        
        # Repository
        self.backup_repo_combo = QComboBox()
        form_layout.addRow("Repository:", self.backup_repo_combo)
        
        # Paths to backup
        paths_label = QLabel("Paths to Backup:")
        self.backup_paths_list = QListWidget()
        self.backup_paths_list.setMaximumHeight(100)
        
        paths_btn_layout = QHBoxLayout()
        add_path_btn = QPushButton("Add Path")
        add_path_btn.clicked.connect(self.add_backup_path)
        remove_path_btn = QPushButton("Remove")
        remove_path_btn.clicked.connect(self.remove_backup_path)
        paths_btn_layout.addWidget(add_path_btn)
        paths_btn_layout.addWidget(remove_path_btn)
        paths_btn_layout.addStretch()
        
        form_layout.addRow(paths_label, self.backup_paths_list)
        form_layout.addRow("", paths_btn_layout)
        
        # Tags
        self.backup_tags_input = QLineEdit()
        self.backup_tags_input.setPlaceholderText("tag1,tag2,tag3")
        form_layout.addRow("Tags:", self.backup_tags_input)
        
        # Exclude patterns
        self.backup_exclude_input = QTextEdit()
        self.backup_exclude_input.setPlaceholderText("*.tmp\n*.log\nnode_modules/")
        self.backup_exclude_input.setMaximumHeight(80)
        form_layout.addRow("Exclude Patterns:", self.backup_exclude_input)
        
        layout.addWidget(form_group)
        
        # Advanced options
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QFormLayout()
        advanced_group.setLayout(advanced_layout)
        
        # Exclude caches
        self.exclude_caches_check = QCheckBox()
        self.exclude_caches_check.setChecked(True)
        advanced_layout.addRow("Exclude Caches:", self.exclude_caches_check)
        
        # Pack size
        pack_size_layout = QHBoxLayout()
        self.pack_size_spin = QSpinBox()
        self.pack_size_spin.setMinimum(1)
        self.pack_size_spin.setMaximum(1024)
        self.pack_size_spin.setValue(0)
        self.pack_size_spin.setSuffix(" MB")
        pack_size_layout.addWidget(self.pack_size_spin)
        pack_size_layout.addWidget(QLabel("(0 = default)"))
        pack_size_layout.addStretch()
        advanced_layout.addRow("Pack Size:", pack_size_layout)
        
        # One file system
        self.one_file_system_check = QCheckBox()
        advanced_layout.addRow("One File System:", self.one_file_system_check)
        
        # Exclude if present
        self.exclude_if_present_input = QLineEdit()
        self.exclude_if_present_input.setPlaceholderText(".nobackup")
        advanced_layout.addRow("Exclude If Present:", self.exclude_if_present_input)
        
        layout.addWidget(advanced_group)
        
        # Backup button
        backup_btn = QPushButton("Start Backup")
        backup_btn.setMinimumHeight(40)
        backup_btn.clicked.connect(self.start_backup)
        layout.addWidget(backup_btn)
        
        # Progress
        self.backup_progress = QProgressBar()
        self.backup_progress.setVisible(False)
        layout.addWidget(self.backup_progress)
        
        # Log output
        log_group = QGroupBox("Backup Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.backup_log = QPlainTextEdit()
        self.backup_log.setReadOnly(True)
        log_layout.addWidget(self.backup_log)
        
        layout.addWidget(log_group)
        
        self.stacked_widget.addWidget(page)
    
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
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
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
            repositories = self.settings_manager.get("repositories")
            repositories.append(repo_data)
            self.settings_manager.set("repositories", repositories)
            self.settings_manager.save_settings()
            self.refresh_repository_list()
            self.update_repository_combos()
            self.log(f"Added repository: {repo_data['name']}")
    
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
                      self.backup_repo_combo, self.retention_repo_combo,
                      self.dashboard_repo_combo]:
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
        snapshot_id = self.snapshots_table.item(row, 0).text()
        
        self.snapshot_details.setText(f"Snapshot ID: {snapshot_id}\n\nDetails to be implemented...")
    
    def browse_snapshot_content(self):
        """Browse files in selected snapshot"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        snapshot_id = self.snapshots_table.item(row, 0).text()
        
        # Show dialog with file tree
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Snapshot Content - {snapshot_id[:8]}")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        layout.addWidget(QLabel(f"Browsing snapshot: {snapshot_id}"))
        
        # File list (to be populated with actual restic ls command)
        file_list = QListWidget()
        file_list.addItem("Loading... (To be implemented with 'restic ls')")
        layout.addWidget(file_list)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
        self.log(f"Browsing content of snapshot {snapshot_id}")
    
    def diff_snapshots(self):
        """Show diff between selected snapshot and previous"""
        selected = self.snapshots_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a snapshot first")
            return
        
        row = selected[0].row()
        if row >= self.snapshots_table.rowCount() - 1:
            QMessageBox.information(self, "No Previous", "This is the oldest snapshot, no previous snapshot to compare")
            return
        
        snapshot_id = self.snapshots_table.item(row, 0).text()
        prev_snapshot_id = self.snapshots_table.item(row + 1, 0).text()
        
        # Show diff dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Diff: {snapshot_id[:8]} vs {prev_snapshot_id[:8]}")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        layout.addWidget(QLabel(f"Comparing: {snapshot_id} with {prev_snapshot_id}"))
        
        # Diff output
        diff_output = QPlainTextEdit()
        diff_output.setReadOnly(True)
        diff_output.setPlainText("Loading diff... (To be implemented with 'restic diff')\n\n"
                                 "Will show added, modified, and removed files")
        layout.addWidget(diff_output)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
        self.log(f"Viewing diff between {snapshot_id} and {prev_snapshot_id}")
    
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
            close_btn = QPushButton("Close (operation continues in background)")
            close_btn.clicked.connect(self._prune_progress.accept)
            layout.addWidget(close_btn)
            
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
    
    # Backup Methods
    def add_backup_path(self):
        """Add a path to backup"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Backup")
        if directory:
            self.backup_paths_list.addItem(directory)
    
    def remove_backup_path(self):
        """Remove selected backup path"""
        current = self.backup_paths_list.currentRow()
        if current >= 0:
            self.backup_paths_list.takeItem(current)
    
    def start_backup(self):
        """Start backup operation"""
        repo_name = self.backup_repo_combo.currentText()
        if not repo_name:
            QMessageBox.warning(self, "No Repository", "Please select a repository")
            return
        
        paths = [self.backup_paths_list.item(i).text() 
                 for i in range(self.backup_paths_list.count())]
        
        if not paths:
            QMessageBox.warning(self, "No Paths", "Please add at least one path to backup")
            return
        
        self.backup_progress.setVisible(True)
        self.backup_progress.setRange(0, 0)
        
        self.log(f"Starting backup to {repo_name}")
        self.log(f"Paths: {', '.join(paths)}")
        
        # TODO: Implement actual backup
        
        QTimer.singleShot(2000, lambda: self.backup_progress.setVisible(False))
    
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
def main():
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
