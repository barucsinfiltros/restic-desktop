"""Windows Credential Manager adapter for catalog repository secrets."""

import sys
from uuid import UUID

from .catalog_domain import InvalidCatalogChange, require_uuid


class CredentialStoreError(Exception):
    """The operating system credential store is unavailable or cannot be used."""


class WindowsCredentialStore:
    """Store opaque-reference secrets in the current Windows account's vault."""

    _service = "ResticDesktop.Catalog"

    def __init__(self):
        if sys.platform != "win32":
            raise CredentialStoreError("Windows Credential Manager is required.")
        try:
            import keyring
            from keyring.backends.Windows import WinVaultKeyring

            backend = keyring.get_keyring()
            if not isinstance(backend, WinVaultKeyring):
                raise CredentialStoreError("Windows Credential Manager is unavailable.")
        except CredentialStoreError:
            raise
        except Exception:
            raise CredentialStoreError("Windows Credential Manager is unavailable.") from None
        self._backend = backend

    def store(self, reference: UUID, secret: str) -> None:
        key = require_uuid(reference)
        if not isinstance(secret, str) or not secret:
            raise InvalidCatalogChange("A non-empty credential is required.")
        try:
            self._backend.set_password(self._service, key, secret)
        except Exception:
            raise CredentialStoreError("Credential storage failed.") from None

    def retrieve(self, reference: UUID) -> str:
        key = require_uuid(reference)
        try:
            secret = self._backend.get_password(self._service, key)
        except Exception:
            raise CredentialStoreError("Credential retrieval failed.") from None
        if not secret:
            raise CredentialStoreError("The credential is unavailable for this Windows account.")
        return secret

    def delete(self, reference: UUID) -> None:
        """Delete a specific credential reference from the current account."""
        key = require_uuid(reference)
        try:
            self._backend.delete_password(self._service, key)
        except Exception:
            raise CredentialStoreError("Credential deletion failed.") from None
