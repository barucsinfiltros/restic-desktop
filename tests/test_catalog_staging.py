"""Offscreen tests for the isolated staged catalog editor."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog
from core.catalog_domain import LocationSpec, ProfileState
from core.catalog_service import CatalogService
from restic_manager import BackupJobDialog
from ui.catalog_staging import CatalogStagingDialog


class CatalogStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.catalog = CatalogService.create(self.root / "catalog.db")
        self.repo = self.catalog.create_repository(
            "Destino", location=LocationSpec("local", str(self.root / "repo")),
            expected_revision=0,
        )

    def test_existing_profile_form_creates_and_edits_with_uuid_associations(self):
        root = self.root

        class ProfileForm(BackupJobDialog):
            editing = False

            def exec(self):
                self.name_input.setText("Editado" if self.editing else "Perfil")
                self.paths_list.clear()
                self.paths_list.addItem(str(root / ("next" if self.editing else "source")))
                self.repos_list.item(0).setSelected(True)
                self.exclude_input.setPlainText("*.tmp")
                return QDialog.DialogCode.Accepted

        dialog = CatalogStagingDialog(self.catalog, ProfileForm)
        self.addCleanup(dialog.close)
        dialog.create_profile()
        snapshot = self.catalog.snapshot()
        self.assertEqual(len(snapshot.profiles), 1)
        profile = snapshot.profiles[0]
        self.assertEqual(profile.options["paths"], [str(root / "source")])
        self.assertEqual(profile.options["exclude_patterns"], ["*.tmp"])
        self.assertEqual(snapshot.associations[0].repository_id, self.repo)
        dialog.profiles.setCurrentRow(0)
        ProfileForm.editing = True
        dialog.edit_profile()
        edited = self.catalog.snapshot().profiles[0]
        self.assertEqual(edited.profile_id, profile.profile_id)
        self.assertEqual(edited.display_name, "Editado")
        self.assertEqual(edited.options["paths"], [str(root / "next")])
        self.assertEqual(self.catalog.snapshot().associations[0].repository_id, self.repo)

    def test_archive_from_staged_dialog(self):
        profile = self.catalog.create_profile(
            "Perfil", options={"paths": [str(self.root / "source")]},
            repository_ids=[self.repo], expected_revision=1,
        )
        dialog = CatalogStagingDialog(self.catalog, BackupJobDialog)
        self.addCleanup(dialog.close)
        dialog.profiles.setCurrentRow(0)
        with patch("ui.catalog_staging.QMessageBox.question",
                   return_value=__import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes):
            dialog.archive_profile()
        snapshot = self.catalog.snapshot()
        self.assertEqual(snapshot.profiles[0].profile_id, profile)
        self.assertEqual(snapshot.profiles[0].state, ProfileState.ARCHIVED)
        self.assertEqual(snapshot.associations, ())

    def test_repository_registration_records_reference_without_initialization(self):
        dialog = CatalogStagingDialog(self.catalog, BackupJobDialog)
        self.addCleanup(dialog.close)
        with patch("ui.catalog_staging.QInputDialog.getText",
                   side_effect=[("Otro", True), ("synthetic", True)]), \
             patch("ui.catalog_staging.QFileDialog.getExistingDirectory", return_value=str(self.root)), \
             patch("ui.catalog_staging.WindowsCredentialStore") as factory:
            dialog.create_repository()
        vault = factory.return_value
        vault.store.assert_called_once()
        ref, value = vault.store.call_args.args
        self.assertEqual(value, "synthetic")
        snapshot = self.catalog.snapshot()
        location = next(item for item in snapshot.locations if item.spec.credential_ref == ref)
        self.assertEqual(location.spec.locator, str(self.root))
        vault.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
