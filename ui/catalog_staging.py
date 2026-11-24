"""Isolated staged catalog editor. It never launches Restic."""

from pathlib import PureWindowsPath
from uuid import UUID, uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from core.catalog_credentials import CredentialStoreError, WindowsCredentialStore
from core.catalog_domain import CatalogError, LocationSpec, ProfileState, RepositoryState


class _RepositorySettings:
    """Adapter for the existing backup-job form."""

    def __init__(self, repositories):
        self.repositories = repositories

    def get(self, name):
        return self.repositories if name == "repositories" else None


class CatalogStagingDialog(QDialog):
    def __init__(self, catalog, profile_dialog_type, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.profile_dialog_type = profile_dialog_type
        self.setWindowTitle("Catálogo en preparación")
        self.resize(750, 520)
        layout = QVBoxLayout(self)
        notice = QLabel("Preparación local. Los respaldos y la activación aún están bloqueados.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        layout.addWidget(QLabel("Perfiles"))
        self.profiles = QListWidget()
        layout.addWidget(self.profiles)
        buttons = QHBoxLayout()
        for label, action in (("Crear perfil", self.create_profile),
                              ("Editar perfil", self.edit_profile),
                              ("Archivar perfil", self.archive_profile)):
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Repositorios"))
        self.repositories = QListWidget()
        layout.addWidget(self.repositories)
        buttons = QHBoxLayout()
        for label, action in (("Registrar carpeta", self.create_repository),
                              ("Renombrar", self.rename_repository),
                              ("Desregistrar", self.unregister_repository)):
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.current = self.catalog.snapshot()
        self.profiles.clear()
        self.repositories.clear()
        for profile in self.current.profiles:
            item = QListWidgetItem(f"{profile.display_name} — {profile.state.value}")
            item.setData(Qt.ItemDataRole.UserRole, str(profile.profile_id))
            self.profiles.addItem(item)
        for repository in self.current.repositories:
            item = QListWidgetItem(f"{repository.display_name} — {repository.state.value}")
            item.setData(Qt.ItemDataRole.UserRole, str(repository.repository_id))
            self.repositories.addItem(item)

    def _selected_id(self, widget):
        item = widget.currentItem()
        return UUID(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _report(self, message):
        QMessageBox.warning(self, "Catálogo en preparación", message)

    def create_profile(self):
        self._edit_profile(None)

    def edit_profile(self):
        identifier = self._selected_id(self.profiles)
        if identifier is None:
            self._report("Selecciona un perfil.")
            return
        self._edit_profile(identifier)

    def _edit_profile(self, identifier):
        snapshot = self.catalog.snapshot()
        profile = next((item for item in snapshot.profiles if item.profile_id == identifier), None)
        if profile and profile.state == ProfileState.ARCHIVED:
            self._report("El perfil está archivado.")
            return
        available = [item for item in snapshot.repositories
                     if item.state != RepositoryState.UNREGISTERED]
        labels = {f"{item.display_name} [{item.repository_id}]": item.repository_id
                  for item in available}
        existing = None
        if profile:
            existing = {"name": profile.display_name, **profile.options}
            linked = {link.repository_id for link in snapshot.associations if link.profile_id == identifier}
            # Include desregistered links so saving does not silently discard them.
            for repository in snapshot.repositories:
                if repository.repository_id in linked and repository.state == RepositoryState.UNREGISTERED:
                    labels[f"{repository.display_name} [{repository.repository_id}]"] = repository.repository_id
            existing["repositories"] = [label for label, repo_id in labels.items() if repo_id in linked]
        dialog = self.profile_dialog_type(
            self, _RepositorySettings([{"name": label} for label in labels]), existing
        )
        dialog.schedule_enabled_check.setChecked(False)
        dialog.schedule_enabled_check.setEnabled(False)
        original_form = dialog.get_job_data() if profile else None
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_job_data()
        selected = [labels[label] for label in data["repositories"]]
        if profile:
            selected_set = set(selected)
            previous = [link.repository_id for link in snapshot.associations
                        if link.profile_id == identifier and link.repository_id in selected_set]
            selected = previous + [repo for repo in selected if repo not in previous]
        fields = ("paths", "tags", "exclude_patterns", "exclude_caches", "pack_size",
                  "one_file_system", "timeout", "exclude_if_present", "compression",
                  "no_cache", "ignore_inode", "skip_if_unchanged")
        if profile:
            options = dict(profile.options)
            for name in fields:
                if name in data and data[name] != original_form.get(name):
                    options[name] = data[name]
        else:
            options = {name: data[name] for name in fields if name in data}
        try:
            if identifier is None:
                self.catalog.create_profile(data["name"], options=options,
                                            repository_ids=selected,
                                            expected_revision=snapshot.revision)
            else:
                self.catalog.update_profile(identifier, data["name"], options,
                                            repository_ids=selected,
                                            expected_revision=snapshot.revision)
            self.refresh()
        except (CatalogError, ValueError, TypeError):
            self._report("No se pudo guardar el perfil. Comprueba que tenga una sola carpeta, "
                         "que las asociaciones sean compatibles y que el catálogo no haya cambiado.")

    def archive_profile(self):
        identifier = self._selected_id(self.profiles)
        if identifier is None:
            self._report("Selecciona un perfil.")
            return
        if QMessageBox.question(self, "Archivar perfil",
                                "Se retirarán las asociaciones y opciones del perfil. ¿Continuar?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.catalog.archive_profile(identifier, expected_revision=self.current.revision)
            self.refresh()
        except CatalogError:
            self._report("No se pudo archivar. Resuelve los repositorios exclusivos y vuelve a intentarlo.")

    def create_repository(self):
        snapshot = self.catalog.snapshot()
        name, accepted = QInputDialog.getText(self, "Registrar repositorio", "Nombre")
        if not accepted or not name.strip():
            return
        path = QFileDialog.getExistingDirectory(self, "Seleccionar ubicación del repositorio")
        if not path:
            return
        secret, accepted = QInputDialog.getText(
            self, "Credencial", "Contraseña del repositorio (opcional)",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return
        reference = uuid4() if secret else None
        vault = None
        try:
            if reference is not None:
                vault = WindowsCredentialStore()
                vault.store(reference, secret)
            backend = "unc" if PureWindowsPath(path).drive.startswith("\\\\") else "local"
            self.catalog.create_repository(
                name, location=LocationSpec(backend, path, credential_ref=reference),
                expected_revision=snapshot.revision,
            )
        except (CatalogError, CredentialStoreError, OSError, ValueError):
            if vault is not None:
                try:
                    vault.delete(reference)
                except CredentialStoreError:
                    self._report("No se pudo retirar la credencial recién creada del almacén de Windows.")
            self._report("No se pudo registrar el repositorio.")
            return
        finally:
            secret = None
        self.refresh()

    def rename_repository(self):
        identifier = self._selected_id(self.repositories)
        if identifier is None:
            self._report("Selecciona un repositorio.")
            return
        name, accepted = QInputDialog.getText(self, "Renombrar repositorio", "Nombre nuevo")
        if not accepted:
            return
        try:
            self.catalog.rename_repository(identifier, name, expected_revision=self.current.revision)
            self.refresh()
        except CatalogError:
            self._report("No se pudo renombrar el repositorio.")

    def unregister_repository(self):
        identifier = self._selected_id(self.repositories)
        if identifier is None:
            self._report("Selecciona un repositorio.")
            return
        if QMessageBox.question(self, "Desregistrar", "Se conservarán los datos físicos. ¿Continuar?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.catalog.unregister_repository(identifier, expected_revision=self.current.revision)
            self.refresh()
        except CatalogError:
            self._report("No se pudo desregistrar el repositorio.")
