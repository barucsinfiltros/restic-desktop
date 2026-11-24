"""Credential store tests use a mocked backend and synthetic data."""

import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from core.catalog_credentials import CredentialStoreError, WindowsCredentialStore
from core.catalog_domain import InvalidCatalogChange


@unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager backend is Windows-only")
class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        from keyring.backends.Windows import WinVaultKeyring

        self.platform = patch("core.catalog_credentials.sys.platform", "win32")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.backend = unittest.mock.create_autospec(WinVaultKeyring, instance=True)
        self.patch_backend = patch("keyring.get_keyring", return_value=self.backend)
        self.patch_backend.start()
        self.addCleanup(self.patch_backend.stop)
        self.store = WindowsCredentialStore()
        self.reference = uuid4()

    def test_stores_and_retrieves_by_opaque_reference(self):
        self.store.store(self.reference, "synthetic-secret")
        self.backend.set_password.assert_called_once_with(
            "ResticDesktop.Catalog", str(self.reference), "synthetic-secret"
        )
        self.backend.get_password.return_value = "synthetic-secret"
        self.assertEqual(self.store.retrieve(self.reference), "synthetic-secret")

    def test_missing_and_backend_errors_are_sanitized(self):
        self.backend.get_password.return_value = None
        with self.assertRaises(CredentialStoreError):
            self.store.retrieve(self.reference)
        self.backend.set_password.side_effect = RuntimeError("synthetic-secret")
        with self.assertRaises(CredentialStoreError) as error:
            self.store.store(self.reference, "synthetic-secret")
        self.assertNotIn("synthetic-secret", str(error.exception))
        self.assertIsNone(error.exception.__cause__)
        with self.assertRaises(InvalidCatalogChange):
            self.store.store(self.reference, "")

    def test_delete_removes_only_specified_reference(self):
        self.store.delete(self.reference)
        self.backend.delete_password.assert_called_once_with(
            "ResticDesktop.Catalog", str(self.reference)
        )

    def test_rejects_other_keyring_backend(self):
        with patch("keyring.get_keyring", return_value=object()):
            with self.assertRaises(CredentialStoreError):
                WindowsCredentialStore()


if __name__ == "__main__":
    unittest.main()
