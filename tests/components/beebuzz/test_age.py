"""Tests for BeeBuzz's minimal age writer."""

from __future__ import annotations

import base64
from pathlib import Path
import shutil
import subprocess

import pytest

from custom_components.beebuzz._age import (
    AgeEncryptionError,
    encrypt_age_x25519,
    parse_x25519_recipient,
    _wrap_base64_body,
)
from custom_components.beebuzz._bech32 import encode

from .conftest import VALID_AGE_RECIPIENT

GO_AGE_AVAILABLE = shutil.which("age") is not None and shutil.which("age-keygen") is not None


class DeterministicRandom:
    """Deterministic byte source for structural encryption tests."""

    def __init__(self) -> None:
        self._counter = 0

    def __call__(self, length: int) -> bytes:
        start = self._counter
        self._counter += length
        return bytes((start + index) % 256 for index in range(length))


def test_parse_x25519_recipient_accepts_valid_age_recipient() -> None:
    """A native age X25519 recipient decodes to a 32-byte public key."""

    assert len(parse_x25519_recipient(VALID_AGE_RECIPIENT)) == 32


@pytest.mark.parametrize(
    "recipient",
    [
        "",
        "test1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqggc9ld",
        encode("age", b"\x00" * 31),
        encode("age", b"\x00" * 33),
        VALID_AGE_RECIPIENT.upper(),
        VALID_AGE_RECIPIENT[:-1] + "x",
    ],
)
def test_parse_x25519_recipient_rejects_unsupported_or_invalid_values(
    recipient: str,
) -> None:
    """Only lowercase native X25519 age recipients are accepted."""

    with pytest.raises(AgeEncryptionError):
        parse_x25519_recipient(recipient)


@pytest.mark.parametrize(
    "plaintext",
    [
        b"",
        b"x",
        b"a" * (64 * 1024 - 1),
        b"a" * (64 * 1024),
        b"a" * (64 * 1024 + 1),
    ],
)
def test_encrypt_age_x25519_emits_binary_age_file(plaintext: bytes) -> None:
    """Encryption should emit structurally valid age v1 data for edge sizes."""

    ciphertext = encrypt_age_x25519(
        plaintext,
        [VALID_AGE_RECIPIENT],
        random_bytes=DeterministicRandom(),
    )
    header, payload = ciphertext.split(b"\n--- ", 1)
    mac_line, encrypted_payload = payload.split(b"\n", 1)
    stanza_lines = header.splitlines()
    recipient_line = stanza_lines[1].split()
    stanza_body_line = stanza_lines[2]
    payload_nonce = encrypted_payload[:16]
    payload_body = encrypted_payload[16:]

    assert header.startswith(b"age-encryption.org/v1\n-> X25519 ")
    assert len(recipient_line) == 3
    assert b"=" not in recipient_line[2]
    assert len(recipient_line[2]) == 43
    assert b"=" not in stanza_body_line
    assert len(stanza_body_line) == 43
    assert b"=" not in mac_line
    assert len(mac_line) == 43
    assert len(base64.b64decode(mac_line + b"=")) == 32
    assert len(payload_nonce) == 16
    assert len(payload_body) >= 16


def test_encrypt_age_x25519_requires_recipients() -> None:
    """Encrypting without recipients is invalid."""

    with pytest.raises(AgeEncryptionError):
        encrypt_age_x25519(b"payload", [], random_bytes=DeterministicRandom())


def test_encrypt_age_x25519_rejects_low_order_recipient() -> None:
    """Low-order X25519 recipient public keys must not be accepted."""

    with pytest.raises(AgeEncryptionError):
        encrypt_age_x25519(
            b"x",
            [encode("age", b"\x00" * 32)],
            random_bytes=DeterministicRandom(),
        )


def test_encrypt_age_x25519_uses_distinct_ephemeral_shares_per_recipient() -> None:
    """Every recipient stanza must get a fresh ephemeral share."""

    ciphertext = encrypt_age_x25519(
        b"payload",
        [VALID_AGE_RECIPIENT, VALID_AGE_RECIPIENT],
        random_bytes=DeterministicRandom(),
    )
    shares = [
        line.split()[2]
        for line in ciphertext.splitlines()
        if line.startswith(b"-> X25519 ")
    ]

    assert len(shares) == 2
    assert shares[0] != shares[1]


def test_wrap_base64_body_adds_trailing_empty_line_at_exact_line_width() -> None:
    """A 48-byte body encodes to exactly one 64-character raw base64 line."""

    wrapped = _wrap_base64_body(bytes(range(48)))

    assert wrapped.count(b"\n") == 2
    assert wrapped.endswith(b"\n\n")
    assert b"=" not in wrapped


def _generate_identity(identity_path: Path) -> str:
    keygen = subprocess.run(
        ["age-keygen", "-o", str(identity_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in f"{keygen.stdout}\n{keygen.stderr}".splitlines():
        if line.startswith("Public key: "):
            return line.removeprefix("Public key: ").strip()
    raise AssertionError("age-keygen did not print a public key")


@pytest.mark.skipif(not GO_AGE_AVAILABLE, reason="Go age binaries not available")
@pytest.mark.parametrize(
    "plaintext",
    [
        b"",
        b'{"title":"Greeting","body":"Hello","topic":"general"}',
        b"a" * (64 * 1024 + 1),
    ],
)
def test_encrypt_age_x25519_interoperates_with_go_age(
    tmp_path,
    plaintext: bytes,
) -> None:
    """Ciphertexts produced by Python must decrypt with the Go reference binary."""

    identity_path = tmp_path / "identity.txt"
    recipient = _generate_identity(identity_path)
    ciphertext = encrypt_age_x25519(plaintext, [recipient])

    decrypted = subprocess.run(
        ["age", "--decrypt", "-i", str(identity_path)],
        check=True,
        input=ciphertext,
        capture_output=True,
    )

    assert decrypted.stdout == plaintext


@pytest.mark.skipif(not GO_AGE_AVAILABLE, reason="Go age binaries not available")
def test_encrypt_age_x25519_multi_recipient_interoperates_with_go_age(tmp_path) -> None:
    """A multi-recipient ciphertext should decrypt with each matching identity."""

    identities: list[str] = []
    recipients: list[str] = []
    for index in range(2):
        identity_path = tmp_path / f"identity-{index}.txt"
        identities.append(str(identity_path))
        recipients.append(_generate_identity(identity_path))
    plaintext = b"multi-recipient payload"
    ciphertext = encrypt_age_x25519(plaintext, recipients)

    for identity in identities:
        decrypted = subprocess.run(
            ["age", "--decrypt", "-i", identity],
            check=True,
            input=ciphertext,
            capture_output=True,
        )
        assert decrypted.stdout == plaintext


@pytest.mark.skipif(not GO_AGE_AVAILABLE, reason="Go age binaries not available")
def test_go_age_rejects_tampered_python_ciphertext(tmp_path) -> None:
    """Reference age must reject ciphertexts with modified authenticated data."""

    identity_path = tmp_path / "identity.txt"
    recipient = _generate_identity(identity_path)
    ciphertext = bytearray(encrypt_age_x25519(b"payload", [recipient]))
    ciphertext[-1] ^= 1

    decrypted = subprocess.run(
        ["age", "--decrypt", "-i", str(identity_path)],
        input=bytes(ciphertext),
        capture_output=True,
    )

    assert decrypted.returncode != 0
