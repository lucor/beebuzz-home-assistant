"""Tests for the BeeBuzz client helpers."""

from __future__ import annotations

from pathlib import Path
import pytest

from custom_components.beebuzz.client import (
    BeeBuzzValidationError,
    _read_limited_file,
    _resolve_file_path,
    build_api_url,
    encrypt_payload,
    normalize_topic,
    validate_device_keys,
)
from custom_components.beebuzz.const import MAX_ATTACHMENT_BYTES

from .conftest import VALID_AGE_RECIPIENT


def test_build_api_url_adds_https_and_trims_trailing_slash() -> None:
    """Hosts without a scheme should be normalized to HTTPS with the api. prefix."""

    assert build_api_url("beebuzz.app/") == "https://api.beebuzz.app"


def test_build_api_url_rejects_non_https_urls() -> None:
    """Only HTTPS BeeBuzz API endpoints should be accepted."""

    with pytest.raises(BeeBuzzValidationError, match="HTTPS endpoint"):
        build_api_url("http://beebuzz.app")


@pytest.mark.parametrize(
    ("raw_topic", "expected_topic"),
    [
        ("#general", "general"),
        ("  #alerts  ", "alerts"),
        ("custom", "custom"),
        ("", "general"),
        (None, "general"),
    ],
)
def test_normalize_topic(raw_topic: str | None, expected_topic: str) -> None:
    """Topics should be normalized the same way as the CLI."""

    assert normalize_topic(raw_topic) == expected_topic


def test_validate_device_keys_strips_recipients(monkeypatch: pytest.MonkeyPatch) -> None:
    """Device keys should be normalized before they are persisted."""

    monkeypatch.setattr(
        "custom_components.beebuzz.client._parse_recipient",
        lambda recipient: recipient,
    )

    normalized = validate_device_keys(
        [
            {
                "device_id": "device-1",
                "age_recipient": "  age1testrecipient  ",
            }
        ]
    )

    assert normalized == [
        {
            "device_id": "device-1",
            "age_recipient": "age1testrecipient",
        }
    ]


def test_validate_device_keys_rejects_non_dict_entries() -> None:
    """Malformed device key entries should be rejected."""

    with pytest.raises(BeeBuzzValidationError, match="device key entry"):
        validate_device_keys(["not-a-dict"])


def test_validate_device_keys_rejects_missing_recipient() -> None:
    """A device key without an age recipient is invalid."""

    with pytest.raises(BeeBuzzValidationError, match="missing age_recipient"):
        validate_device_keys([{}])


def test_validate_device_keys_rejects_invalid_recipient() -> None:
    """Invalid age recipients returned by the backend should fail validation."""

    with pytest.raises(BeeBuzzValidationError, match="Invalid BeeBuzz age recipient"):
        validate_device_keys([{"age_recipient": "age1invalid"}])


def test_encrypt_payload_rejects_empty_recipient_list() -> None:
    """Encryption requires at least one device recipient."""

    with pytest.raises(BeeBuzzValidationError, match="No BeeBuzz device public keys"):
        encrypt_payload(b"payload", [])


def test_encrypt_payload_accepts_valid_recipient() -> None:
    """The client helper should encrypt with the internal age writer."""

    ciphertext = encrypt_payload(b"payload", [VALID_AGE_RECIPIENT])

    assert ciphertext.startswith(b"age-encryption.org/v1\n")


def test_resolve_file_path_raises_on_missing_file() -> None:
    """A non-existent attachment path should raise a validation error."""

    with pytest.raises(BeeBuzzValidationError, match="Attachment not found"):
        _resolve_file_path(Path("/nonexistent/path/to/file.png"))


def test_resolve_file_path_raises_on_permission_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A permission error during resolution should be wrapped."""

    def raise_permission(path, strict=True):
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "resolve", raise_permission)

    with pytest.raises(BeeBuzzValidationError, match="Permission denied"):
        _resolve_file_path(Path("/restricted/file.png"))


def test_resolve_file_path_raises_when_path_is_directory(tmp_path: Path) -> None:
    """Directories must not be accepted as attachment paths."""

    with pytest.raises(BeeBuzzValidationError, match="not a file"):
        _resolve_file_path(tmp_path)


def test_read_limited_file_raises_on_oversized_file(tmp_path: Path) -> None:
    """Attachments larger than the limit should be rejected."""

    oversized = tmp_path / "big.bin"
    oversized.write_bytes(b"x" * (MAX_ATTACHMENT_BYTES + 1))

    with pytest.raises(BeeBuzzValidationError, match="exceeds"):
        _read_limited_file(oversized)


def test_read_limited_file_raises_on_unreadable_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OS errors during file read should be wrapped as validation errors."""

    dummy = tmp_path / "dummy.bin"
    dummy.write_text("x")

    def raise_os_error(*_args, **_kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(Path, "open", raise_os_error)

    with pytest.raises(BeeBuzzValidationError, match="Cannot read attachment"):
        _read_limited_file(dummy)


