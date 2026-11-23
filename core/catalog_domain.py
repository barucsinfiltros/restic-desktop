"""Qt-free types and validation for the staged profiles and repositories catalog."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit
from uuid import UUID


class CatalogError(Exception):
    """A catalog operation could not be completed."""


class InvalidCatalogChange(CatalogError):
    """Input, state or impact approval does not allow the requested change."""


class StaleCatalogRevision(CatalogError):
    """The catalog changed since the caller reviewed it."""


class CatalogStorageError(CatalogError):
    """The catalog could not be opened or the transaction could not be committed."""


class ProfileState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RepositoryState(str, Enum):
    PENDING_INIT = "pending_init"
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True)
class Profile:
    profile_id: UUID
    display_name: str
    state: ProfileState
    revision: int
    options: dict


@dataclass(frozen=True)
class Repository:
    repository_id: UUID
    display_name: str
    state: RepositoryState
    exclusive_profile_id: UUID | None
    revision: int


@dataclass(frozen=True)
class LocationSpec:
    """A locator with non-secret metadata and an optional opaque credential reference.

    The service stores the verified ID supplied by the caller; it does not contact the backend.
    """

    backend: str
    locator: str
    backend_config: dict = field(default_factory=dict)
    credential_ref: UUID | None = None
    verified_restic_id: str | None = None


@dataclass(frozen=True)
class RepositoryLocation:
    repository_id: UUID
    spec: LocationSpec
    location_fingerprint: str


@dataclass(frozen=True)
class ProfileRepository:
    profile_id: UUID
    repository_id: UUID
    position: int


@dataclass(frozen=True)
class RepositoryDraft:
    display_name: str
    location: LocationSpec | None = None
    state: RepositoryState = RepositoryState.REGISTERED


@dataclass(frozen=True)
class CatalogSnapshot:
    installation_id: UUID
    revision: int
    profiles: tuple[Profile, ...]
    repositories: tuple[Repository, ...]
    locations: tuple[RepositoryLocation, ...]
    associations: tuple[ProfileRepository, ...]


def require_uuid(value: UUID) -> str:
    if not isinstance(value, UUID) or value.int == 0:
        raise InvalidCatalogChange("A non-nil UUID is required.")
    return str(value)


def require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise InvalidCatalogChange(f"{label} must be non-empty text.")
    return value


def _string_list(value):
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) and "\x00" not in item
        for item in value
    )


def _boolean(value):
    return type(value) is bool


def _positive_integer(value):
    return type(value) is int and value > 0


def _text(value):
    return isinstance(value, str) and "\x00" not in value


_PROFILE_OPTIONS = {
    "paths": _string_list,
    "tags": _string_list,
    "exclude_patterns": _string_list,
    "exclude_caches": _boolean,
    "pack_size": _positive_integer,
    "one_file_system": _boolean,
    "timeout": lambda value: type(value) is int and value >= 0,
    "exclude_if_present": _text,
    "compression": lambda value: value in ("auto", "off", "max"),
    "no_cache": _boolean,
    "ignore_inode": _boolean,
    "skip_if_unchanged": _boolean,
}

_BACKEND_OPTIONS = {
    "local": {},
    "unc": {},
    "rest": {},
    "sftp": {},
    "rclone": {},
    "s3": {"region": _text},
    "b2": {},
    "azure": {"account_name": _text},
    "wasabi": {"region": _text},
    "gs": {"project_id": _text},
    "swift": {},
}


def _encode_options(values: dict, validators: dict, label: str) -> str:
    if not isinstance(values, dict):
        raise InvalidCatalogChange(f"{label} must be a JSON object.")
    for key, value in values.items():
        if key not in validators or not validators[key](value):
            raise InvalidCatalogChange(f"{label} contains an unsupported field or value.")
    return json.dumps(values, allow_nan=False, sort_keys=True)


def encode_profile_options(options: dict) -> str:
    return _encode_options(options, _PROFILE_OPTIONS, "Profile options")


def _validate_url(locator: str, schemes: tuple[str, ...], *, allow_user=False):
    try:
        url = urlsplit(locator)
        port = url.port
        valid = (
            url.scheme in schemes
            and url.hostname
            and not any(character.isspace() for character in url.netloc)
            and port != 0
            and (url.username is None or (allow_user and re.fullmatch(r"[A-Za-z0-9_.-]+", url.username)))
            and url.password is None
        )
    except ValueError:
        valid = False
    if not valid:
        raise InvalidCatalogChange("Invalid or credential-bearing repository URL.")
    return url


def encode_location(spec: LocationSpec) -> tuple:
    if not isinstance(spec, LocationSpec) or not isinstance(spec.backend, str):
        raise InvalidCatalogChange("A location with a supported backend is required.")
    backend = spec.backend
    if backend not in _BACKEND_OPTIONS:
        raise InvalidCatalogChange("Unsupported repository backend.")

    locator = require_text(spec.locator, "Repository locator")
    if backend == "local":
        windows = PureWindowsPath(locator)
        if windows.drive.startswith("\\\\") or not (
            windows.is_absolute() or PurePosixPath(locator).is_absolute()
        ):
            raise InvalidCatalogChange("A local locator must be absolute and non-UNC.")
    elif backend == "unc":
        windows = PureWindowsPath(locator)
        if not windows.is_absolute() or not windows.drive.startswith("\\\\") or (
            windows.drive.startswith(("\\\\?\\", "\\\\.\\"))
        ):
            raise InvalidCatalogChange("A UNC locator must name a server and share.")
    else:
        if (
            locator != locator.strip()
            or any(ord(character) < 32 for character in locator)
            or any(delimiter in locator for delimiter in ("?", "#", "\\"))
        ):
            raise InvalidCatalogChange("Invalid remote locator.")
        if backend == "rest":
            _validate_url(locator.removeprefix("rest:"), ("https", "http"))
        elif backend == "sftp":
            if locator.startswith("sftp://"):
                url = _validate_url(locator, ("sftp",), allow_user=True)
                if not url.path:
                    raise InvalidCatalogChange("SFTP requires a repository path.")
            elif not re.fullmatch(r"sftp:(?:[A-Za-z0-9_.-]+@)?(?:[A-Za-z0-9_.-]+|\[[0-9a-fA-F:]+\]):.+", locator):
                raise InvalidCatalogChange("Invalid or credential-bearing SFTP locator.")
        elif backend in ("s3", "wasabi"):
            target = locator.removeprefix("s3:").removeprefix("wasabi:")
            if "://" not in target:
                target = "https://" + target
            url = _validate_url(target, ("https", "http"))
            if not url.path.lstrip("/"):
                raise InvalidCatalogChange("Object storage requires a bucket.")
        else:
            # Restic accepts a container by itself, or a container with a prefix.
            # For rclone, the colon is required even when the remote path is empty.
            name, separator, _ = locator.removeprefix(f"{backend}:").partition(":")
            if (backend == "rclone" and not separator) or not re.fullmatch(r"[A-Za-z0-9_. -]+", name):
                raise InvalidCatalogChange("Invalid remote or container name.")

    config = _encode_options(spec.backend_config, _BACKEND_OPTIONS[backend], "Backend config")
    credential_ref = require_uuid(spec.credential_ref) if spec.credential_ref is not None else None
    if spec.verified_restic_id is not None and (
        not isinstance(spec.verified_restic_id, str)
        or not re.fullmatch(r"[0-9a-f]{64}", spec.verified_restic_id)
    ):
        raise InvalidCatalogChange("A verified Restic ID must be a full lowercase hexadecimal ID.")

    # Exact spelling is intentionally conservative. This fingerprint only finds candidates.
    identity = json.dumps([1, backend, locator], ensure_ascii=True).encode("ascii")
    fingerprint = hashlib.sha256(identity).hexdigest()
    return backend, locator, fingerprint, spec.verified_restic_id, config, credential_ref
