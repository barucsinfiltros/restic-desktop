"""
GUI License Key Generator for Restic Backup Manager
A simple graphical interface for generating license keys
"""

import sys
import hashlib
import hmac
import base64
from datetime import datetime, timedelta

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
        QRadioButton, QButtonGroup, QGroupBox, QMessageBox
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    print("Error: PyQt6 is not installed.")
    print("Please install it with: pip install PyQt6")
    sys.exit(1)

# SECRET KEY - Must match the one in restic_manager.py
_SECRET_KEY = b"restic-manager-secret-key-change-this-in-production"


def generate_license_key(machine_id: str, expiry_days: int = None) -> str:
    """Generate a license key for a specific machine ID"""
    machine_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
    
    if expiry_days is None:
        expiry_str = "unlimited"
    else:
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        expiry_str = expiry_date.strftime("%Y-%m-%d")
    
    payload = f"{machine_hash}:{expiry_str}"
    signature = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()[:32]
    
    license_data = f"{machine_hash}:{expiry_str}:{signature}"
    license_key = base64.b64encode(license_data.encode()).decode('utf-8')
    
    return license_key


class LicenseGeneratorGUI(QMainWindow):
    """GUI for generating license keys"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("License Key Generator - Restic Backup Manager")
        self.setMinimumSize(700, 500)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Title
        title = QLabel("License Key Generator")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Machine ID input
        machine_group = QGroupBox("Customer Machine ID")
        machine_layout = QVBoxLayout()
        machine_group.setLayout(machine_layout)
        
        machine_info = QLabel("Enter the Machine ID from the customer's License Activation dialog:")
        machine_layout.addWidget(machine_info)
        
        self.machine_id_input = QLineEdit()
        self.machine_id_input.setPlaceholderText("Paste or type Machine ID here...")
        self.machine_id_input.setFont(QFont("Courier", 10))
        machine_layout.addWidget(self.machine_id_input)
        
        layout.addWidget(machine_group)
        
        # License type
        type_group = QGroupBox("License Type")
        type_layout = QVBoxLayout()
        type_group.setLayout(type_layout)
        
        self.license_type_group = QButtonGroup()
        
        self.unlimited_radio = QRadioButton("Unlimited (Perpetual License)")
        self.unlimited_radio.setChecked(True)
        self.unlimited_radio.toggled.connect(self.update_ui)
        self.license_type_group.addButton(self.unlimited_radio)
        type_layout.addWidget(self.unlimited_radio)
        
        self.limited_radio = QRadioButton("Time-Limited")
        self.limited_radio.toggled.connect(self.update_ui)
        self.license_type_group.addButton(self.limited_radio)
        type_layout.addWidget(self.limited_radio)
        
        # Days input
        days_layout = QHBoxLayout()
        days_layout.addSpacing(30)
        days_layout.addWidget(QLabel("Valid for:"))
        self.days_spin = QSpinBox()
        self.days_spin.setMinimum(1)
        self.days_spin.setMaximum(3650)
        self.days_spin.setValue(365)
        self.days_spin.setSuffix(" days")
        self.days_spin.setEnabled(False)
        days_layout.addWidget(self.days_spin)
        days_layout.addStretch()
        type_layout.addLayout(days_layout)
        
        layout.addWidget(type_group)
        
        # Generate button
        generate_btn = QPushButton("Generate License Key")
        generate_btn.setMinimumHeight(40)
        generate_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        generate_btn.clicked.connect(self.generate_license)
        layout.addWidget(generate_btn)
        
        # Output
        output_group = QGroupBox("Generated License Key")
        output_layout = QVBoxLayout()
        output_group.setLayout(output_layout)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier", 10))
        self.output_text.setPlaceholderText("License key will appear here...")
        output_layout.addWidget(self.output_text)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_license)
        action_layout.addWidget(copy_btn)
        
        save_btn = QPushButton("Save to File")
        save_btn.clicked.connect(self.save_license)
        action_layout.addWidget(save_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_output)
        action_layout.addWidget(clear_btn)
        
        output_layout.addLayout(action_layout)
        
        layout.addWidget(output_group)
        
        # Status bar
        self.statusBar().showMessage("Ready to generate license keys")
    
    def update_ui(self):
        """Update UI based on license type selection"""
        self.days_spin.setEnabled(self.limited_radio.isChecked())
    
    def generate_license(self):
        """Generate license key based on inputs"""
        machine_id = self.machine_id_input.text().strip()
        
        if not machine_id:
            QMessageBox.warning(
                self,
                "Missing Machine ID",
                "Please enter a Machine ID before generating a license."
            )
            return
        
        # Determine expiry
        expiry_days = None
        if self.limited_radio.isChecked():
            expiry_days = self.days_spin.value()
        
        # Generate license
        try:
            license_key = generate_license_key(machine_id, expiry_days)
            
            # Format output
            output = f"License Key Generated Successfully\n"
            output += f"=" * 70 + "\n\n"
            output += f"Machine ID: {machine_id}\n"
            
            if expiry_days is None:
                output += f"Expiration: Unlimited\n"
            else:
                expiry_date = datetime.now() + timedelta(days=expiry_days)
                output += f"Expiration: {expiry_date.strftime('%Y-%m-%d')} ({expiry_days} days)\n"
            
            output += f"\n" + "-" * 70 + "\n"
            output += f"LICENSE KEY:\n"
            output += f"-" * 70 + "\n"
            output += license_key + "\n"
            output += f"-" * 70 + "\n\n"
            output += "Send this license key to the customer.\n"
            output += "They can enter it in the License Activation dialog."
            
            self.output_text.setText(output)
            self.current_license = license_key
            
            self.statusBar().showMessage("✓ License key generated successfully!", 5000)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Error generating license key:\n{str(e)}"
            )
    
    def copy_license(self):
        """Copy license key to clipboard"""
        if hasattr(self, 'current_license'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_license)
            self.statusBar().showMessage("✓ License key copied to clipboard!", 3000)
        else:
            QMessageBox.information(
                self,
                "No License",
                "Please generate a license key first."
            )
    
    def save_license(self):
        """Save license key to file"""
        if not hasattr(self, 'current_license'):
            QMessageBox.information(
                self,
                "No License",
                "Please generate a license key first."
            )
            return
        
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save License Key",
            "license.key",
            "License Files (*.key);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.current_license)
                self.statusBar().showMessage(f"✓ License saved to {filename}", 5000)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Error saving license:\n{str(e)}"
                )
    
    def clear_output(self):
        """Clear the output"""
        self.output_text.clear()
        if hasattr(self, 'current_license'):
            del self.current_license
        self.statusBar().showMessage("Output cleared", 2000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("License Key Generator")
    app.setApplicationVersion("1.0.0")
    
    window = LicenseGeneratorGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
