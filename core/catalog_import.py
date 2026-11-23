"""Read-only analysis of legacy settings; reports contain no input values."""

import hashlib
import json
import re
from urllib.parse import unquote, urlsplit
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .catalog_domain import InvalidCatalogChange, LocationSpec, encode_location, encode_profile_options

CANONICAL_VERSION = 1

# Field names originate in ResticSettingsManager and the legacy job/repository forms.
PROFILE_OPTIONS = {
    "paths", "tags", "exclude_patterns", "exclude_caches", "pack_size",
    "one_file_system", "timeout", "exclude_if_present", "compression",
    "no_cache", "ignore_inode", "skip_if_unchanged",
}
PROFILE_FIELDS = PROFILE_OPTIONS | {"name", "repository", "repositories", "schedule", "created", "last_run"}
REPOSITORY_FIELDS = {
    "name", "type", "path", "password", "sftp_host", "sftp_port", "sftp_user",
    "sftp_remote_path", "sftp_absolute", "ssh_key", "https_url", "rest_auth",
    "rest_user", "rest_password", "network_server", "network_share", "network_subpath",
    "network_user", "network_password", "network_drive", "network_connect_only",
    "cloud_provider", "cloud_path", "rclone_remote", "rclone_config", "object_bucket",
    "object_key_id", "object_secret", "object_endpoint", "object_region", "color",
    "last_checked", "check_status", "check_error",
}
SENSITIVE_FIELDS = {
    "password", "rest_password", "network_password", "object_key_id", "object_secret",
    "rclone_config", "app_password_hash", "app_password_salt", "rclone_conf_encrypted",
    "ssh_key", "https_url", "rest_auth", "access_token", "refresh_token",
    "api_key", "private_key", "client_secret", "token", "secret", "credential",
}
# Values of all other root settings stay out of the plan as they are not catalog entities.
ROOT_FIELDS = {
    "repositories", "backup_jobs", "theme", "restic_path", "rclone_path",
    "last_repository", "auto_refresh_snapshots", "snapshot_refresh_interval",
    "auto_check_repository_status", "repository_status_check_interval_minutes",
    "log_level", "log_retention_days", "temp_restore_path", "app_password_hash",
    "app_password_salt", "health_backup_overdue_hours", "health_backup_overdue_value",
    "health_backup_overdue_unit", "health_check_interval_days", "health_check_interval_value",
    "health_check_interval_unit", "health_restore_test_interval_days",
    "health_restore_test_interval_value", "health_restore_test_interval_unit",
    "health_default_check_level", "health_restore_test_max_files", "rclone_conf_encrypted",
}


class InvalidLegacyConfiguration(ValueError):
    """Input cannot be safely parsed. Messages contain no source content."""


@dataclass(frozen=True)
class FieldReview:
    # A known field name is safe to identify. Unknown field names themselves are withheld.
    field: str
    category: str


@dataclass(frozen=True)
class RecordPlan:
    source_key: str
    fingerprint: str = field(repr=False)
    fields: tuple[FieldReview, ...]


@dataclass(frozen=True)
class Relationship:
    profile_key: str
    repository_key: str
    position: int


@dataclass(frozen=True)
class Conflict:
    source_key: str
    code: str


@dataclass(frozen=True)
class ImportPlan:
    canonical_version: int
    source_sha256: str = field(repr=False)
    canonical_sha256: str = field(repr=False)
    profiles: tuple[RecordPlan, ...]
    repositories: tuple[RecordPlan, ...]
    relationships: tuple[Relationship, ...]
    root_fields: tuple[FieldReview, ...]
    conflicts: tuple[Conflict, ...]


@dataclass(frozen=True)
class DisplayRecord:
    source_key: str
    fields: tuple[FieldReview, ...]


@dataclass(frozen=True)
class DisplayPlan:
    """Safe presentation representation without hashes or source values."""

    canonical_version: int
    profiles: tuple[DisplayRecord, ...]
    repositories: tuple[DisplayRecord, ...]
    relationships: tuple[Relationship, ...]
    root_fields: tuple[FieldReview, ...]
    conflicts: tuple[Conflict, ...]


def display_plan(plan: ImportPlan) -> DisplayPlan:
    """Use this projection for presentation, logging or serialization."""
    return DisplayPlan(
        plan.canonical_version,
        tuple(DisplayRecord(record.source_key, record.fields) for record in plan.profiles),
        tuple(DisplayRecord(record.source_key, record.fields) for record in plan.repositories),
        plan.relationships, plan.root_fields, plan.conflicts,
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidLegacyConfiguration("Duplicate JSON object key.")
        result[key] = value
    return result


def _nonfinite(_value):
    raise InvalidLegacyConfiguration("Non-finite JSON number.")


def _canonical(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise InvalidLegacyConfiguration("Non-finite JSON number.")
        if value.is_zero():
            return "0"
        sign, digits, exponent = value.as_tuple()
        digits = list(digits)
        while digits[-1] == 0:
            digits.pop()
            exponent += 1
        coefficient = "".join(str(digit) for digit in digits)
        return ("-" if sign else "") + coefficient + "e" + str(exponent)
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise InvalidLegacyConfiguration("Invalid Unicode scalar value.")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            _canonical(key) + ":" + _canonical(value[key]) for key in sorted(value)
        ) + "}"
    raise InvalidLegacyConfiguration("Unsupported JSON value.")


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _catalog_option(value):
    # JSON integers are parsed as Decimal to avoid precision loss in canonicalization.
    if isinstance(value, Decimal) and value.adjusted() <= 100 and value == value.to_integral_value():
        return int(value)
    if isinstance(value, list):
        return [_catalog_option(item) for item in value]
    return value


def _sensitive_key(key):
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in {re.sub(r"[^a-z0-9]", "", name) for name in SENSITIVE_FIELDS}


def _nested_reviews(value, *, schedule=False):
    """Report nested types without disclosing keys outside the known schedule schema."""
    reviews = []
    schedule_fields = {
        "enabled", "frequency", "time", "days", "day_of_month",
        "run_if_missed", "pause_after_completion", "last_run",
    }
    if isinstance(value, dict):
        for child, child_value in value.items():
            if _sensitive_key(child):
                reviews.append(FieldReview("<nested_sensitive>", "sensitive"))
            elif schedule and child in schedule_fields:
                category = "not_representable"
                if child == "days" and (
                    not isinstance(child_value, list)
                    or any(not isinstance(day, str) for day in child_value)
                ):
                    category = "review"
                reviews.append(FieldReview("schedule." + child, category))
            else:
                reviews.append(FieldReview("<nested_unknown>", "unknown"))
            reviews.extend(_nested_reviews(child_value))
    elif isinstance(value, list):
        for item in value:
            reviews.extend(_nested_reviews(item))
    return reviews


def _locator_has_authentication(value):
    if not isinstance(value, str):
        return False
    # URL query/fragment and userinfo can carry credentials. Treat encoded
    # delimiters conservatively as well, without returning the original value.
    candidate = unquote(value)
    if "?" in candidate or "#" in candidate:
        return True
    if "://" in candidate:
        scheme = candidate.split("://", 1)[0].rsplit(":", 1)[-1]
        url_text = scheme + "://" + candidate.split("://", 1)[1]
        try:
            url = urlsplit(url_text)
            return bool(url.username or url.password or url.query or url.fragment)
        except ValueError:
            return True
    if re.match(r"^sftp:[^/:@]+@", candidate, re.IGNORECASE):
        return True
    return bool(re.search(r"(?:^|[:/])[^/:@]+:[^/@]+@", candidate))


def _record(record, key, known, profile):
    fields = []
    for field, value in record.items():
        if _sensitive_key(field):
            fields.append(FieldReview(field if field in known else "<sensitive>", "sensitive"))
        elif field not in known:
            fields.append(FieldReview("<unknown>", "unknown"))
        elif profile and field in PROFILE_OPTIONS:
            try:
                encode_profile_options({field: _catalog_option(value)})
            except (InvalidCatalogChange, TypeError, ValueError, OverflowError):
                fields.append(FieldReview(field, "incompatible"))
            else:
                fields.append(FieldReview(field, "known"))
        elif field == "schedule":
            fields.append(FieldReview(field, "not_representable"))
            if not isinstance(value, dict):
                fields.append(FieldReview("schedule", "incompatible"))
        elif not profile and field == "path" and _locator_has_authentication(value):
            fields.append(FieldReview(field, "sensitive"))
        elif field in {"created", "last_run"}:
            fields.append(FieldReview(field, "not_representable"))
        elif not profile and field not in {"name", "type", "path"}:
            # Metadata and backend-specific values require an explicit mapping.
            fields.append(FieldReview(field, "review"))
        elif isinstance(value, (dict, list)) and field != "repositories":
            fields.append(FieldReview(field, "review"))
        else:
            fields.append(FieldReview(field, "known"))
        fields.extend(_nested_reviews(value, schedule=field == "schedule"))
    return RecordPlan(key, _digest(record), tuple(fields))


def _collections(root, name):
    if name not in root:
        return []
    value = root[name]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise InvalidLegacyConfiguration("Legacy collections must contain objects.")
    return value


def _valid_name(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _backend(repo):
    kind = repo.get("type", "local")
    if not isinstance(kind, str):
        return None
    if kind == "network":
        return "unc"
    if kind in ("https", "rest"):
        return "rest"
    if kind == "cloud":
        provider = repo.get("cloud_provider")
        if provider in ("s3", "b2", "azure", "wasabi"):
            return provider
        return "rclone" if isinstance(provider, str) and provider else None
    return kind


def analyze_bytes(data: bytes) -> ImportPlan:
    """Return internal analysis containing sensitive hashes.

    Never serialize or display this object. Use display_plan() for presentation.
    Store hashes only in protected memory or storage authorized by a later phase.
    """
    if not isinstance(data, bytes):
        raise TypeError("Input must be bytes.")
    try:
        root = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_nonfinite,
        )
        canonical_hash = _digest(root)
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidOperation, RecursionError, ValueError) as exc:
        if isinstance(exc, InvalidLegacyConfiguration):
            raise
        raise InvalidLegacyConfiguration("Invalid UTF-8 or JSON configuration.") from None
    if not isinstance(root, dict):
        raise InvalidLegacyConfiguration("Configuration root must be an object.")

    profiles = _collections(root, "backup_jobs")
    repositories = _collections(root, "repositories")
    profile_plans = tuple(_record(item, f"backup_jobs[{index}]", PROFILE_FIELDS, True)
                          for index, item in enumerate(profiles))
    repository_plans = tuple(_record(item, f"repositories[{index}]", REPOSITORY_FIELDS, False)
                             for index, item in enumerate(repositories))
    root_fields_list = []
    for name, value in root.items():
        if name in ("repositories", "backup_jobs"):
            continue
        if _sensitive_key(name):
            root_fields_list.append(FieldReview(name if name in ROOT_FIELDS else "<sensitive>", "sensitive"))
        elif name not in ROOT_FIELDS:
            root_fields_list.append(FieldReview("<unknown>", "unknown"))
        elif isinstance(value, (dict, list)):
            root_fields_list.append(FieldReview(name, "review"))
        else:
            root_fields_list.append(FieldReview(name, "known"))
        root_fields_list.extend(_nested_reviews(value))
    root_fields = tuple(root_fields_list)
    conflicts = [
        Conflict(name, "missing_collection")
        for name in ("repositories", "backup_jobs") if name not in root
    ]
    links = []
    names = [repo.get("name") for repo in repositories]
    profile_names = [profile.get("name") for profile in profiles]
    counts = Counter(name for name in names if _valid_name(name))
    profile_counts = Counter(name for name in profile_names if _valid_name(name))

    for index, repo in enumerate(repositories):
        key = f"repositories[{index}]"
        name = repo.get("name")
        if not _valid_name(name):
            conflicts.append(Conflict(key, "invalid_name"))
        elif counts[name] > 1:
            conflicts.append(Conflict(key, "duplicate_name"))
        try:
            encode_location(LocationSpec(_backend(repo), repo.get("path")))
        except (InvalidCatalogChange, TypeError, ValueError):
            conflicts.append(Conflict(key, "location_requires_review"))

    for index, profile in enumerate(profiles):
        key = f"backup_jobs[{index}]"
        name = profile.get("name")
        if not _valid_name(name):
            conflicts.append(Conflict(key, "invalid_name"))
        elif profile_counts[name] > 1:
            conflicts.append(Conflict(key, "duplicate_name"))
        many = profile.get("repositories")
        one = profile.get("repository")
        if many is not None and (not isinstance(many, list) or any(not _valid_name(x) for x in many)):
            conflicts.append(Conflict(key, "invalid_repositories"))
            continue
        if one is not None and not _valid_name(one):
            conflicts.append(Conflict(key, "invalid_repository"))
            continue
        if many and one and many != [one]:
            conflicts.append(Conflict(key, "conflicting_repository_fields"))
            continue
        selected = many or ([one] if one else [])
        if not selected:
            conflicts.append(Conflict(key, "missing_repository"))
        if len(selected) != len(set(selected)):
            conflicts.append(Conflict(key, "duplicate_repository_reference"))
            continue
        for position, reference in enumerate(selected):
            if counts[reference] != 1:
                conflicts.append(Conflict(key, "missing_or_ambiguous_repository"))
                continue
            links.append(Relationship(key, f"repositories[{names.index(reference)}]", position))

    for record in (*profile_plans, *repository_plans):
        if any(field.category != "known" for field in record.fields):
            conflicts.append(Conflict(record.source_key, "field_review_required"))
    if any(field.category in ("unknown", "sensitive", "review") for field in root_fields):
        conflicts.append(Conflict("root", "field_review_required"))
    return ImportPlan(
        CANONICAL_VERSION, hashlib.sha256(data).hexdigest(), canonical_hash,
        profile_plans, repository_plans, tuple(links), root_fields, tuple(conflicts),
    )


def analyze_file(path) -> ImportPlan:
    """Read the requested file only; no source or catalog files are written."""
    return analyze_bytes(Path(path).read_bytes())
