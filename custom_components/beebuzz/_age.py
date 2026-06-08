"""Minimal age v1 encryption writer for X25519 recipients."""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence
import hmac
import os

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ._bech32 import Bech32Error, decode

VERSION_LINE = b"age-encryption.org/v1\n"
X25519_INFO = b"age-encryption.org/v1/X25519"
HEADER_INFO = b"header"
PAYLOAD_INFO = b"payload"
ZERO_NONCE = b"\x00" * 12
CHUNK_SIZE = 64 * 1024

RandomBytes = Callable[[int], bytes]


class AgeEncryptionError(ValueError):
    """Raised when age encryption input or processing fails."""


def parse_x25519_recipient(recipient: str) -> bytes:
    """Parse a native age X25519 recipient and return the raw public key."""

    try:
        hrp, data = decode(recipient)
    except Bech32Error as err:
        raise AgeEncryptionError("invalid Bech32 recipient") from err
    if hrp != "age":
        raise AgeEncryptionError(f"unsupported age recipient HRP: {hrp}")
    if len(data) != 32:
        raise AgeEncryptionError(f"invalid age recipient length: {len(data)}")
    return data


def encrypt_age_x25519(
    plaintext: bytes,
    recipients: Sequence[str],
    *,
    random_bytes: RandomBytes = os.urandom,
) -> bytes:
    """Encrypt bytes as an age v1 file for native X25519 recipients."""

    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")

    recipient_keys = [parse_x25519_recipient(recipient) for recipient in recipients]
    if not recipient_keys:
        raise AgeEncryptionError("at least one recipient is required")

    file_key = _read_random(random_bytes, 16)
    header = bytearray(VERSION_LINE)
    for recipient_key in recipient_keys:
        header.extend(_x25519_stanza(file_key, recipient_key, random_bytes))
    header.extend(_header_mac_line(file_key, bytes(header)))
    return bytes(header) + _encrypt_payload(file_key, plaintext, random_bytes)


def _x25519_stanza(
    file_key: bytes,
    recipient_key: bytes,
    random_bytes: RandomBytes,
) -> bytes:
    ephemeral_key = _private_key_from_random(random_bytes)
    ephemeral_share = ephemeral_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    try:
        public_key = x25519.X25519PublicKey.from_public_bytes(recipient_key)
        shared_secret = ephemeral_key.exchange(public_key)
    except (TypeError, ValueError, UnsupportedAlgorithm) as err:
        raise AgeEncryptionError("invalid X25519 recipient public key") from err
    if hmac.compare_digest(shared_secret, b"\x00" * 32):
        raise AgeEncryptionError("invalid all-zero X25519 shared secret")

    wrap_key = _hkdf(
        ikm=shared_secret,
        salt=ephemeral_share + recipient_key,
        info=X25519_INFO,
    )
    body = ChaCha20Poly1305(wrap_key).encrypt(ZERO_NONCE, file_key, None)
    stanza = bytearray(b"-> X25519 ")
    stanza.extend(_raw_base64(ephemeral_share).encode())
    stanza.extend(b"\n")
    stanza.extend(_wrap_base64_body(body))
    return bytes(stanza)


def _header_mac_line(file_key: bytes, header_without_mac: bytes) -> bytes:
    mac_key = _hkdf(ikm=file_key, salt=b"", info=HEADER_INFO)
    mac_input = header_without_mac + b"---"
    digest = hmac.digest(mac_key, mac_input, "sha256")
    return b"--- " + _raw_base64(digest).encode() + b"\n"


def _encrypt_payload(
    file_key: bytes,
    plaintext: bytes,
    random_bytes: RandomBytes,
) -> bytes:
    nonce = _read_random(random_bytes, 16)
    payload_key = _hkdf(ikm=file_key, salt=nonce, info=PAYLOAD_INFO)
    aead = ChaCha20Poly1305(payload_key)

    encrypted = bytearray(nonce)
    if not plaintext:
        encrypted.extend(aead.encrypt(_stream_nonce(0, final=True), b"", None))
        return bytes(encrypted)

    counter = 0
    for offset in range(0, len(plaintext), CHUNK_SIZE):
        chunk = plaintext[offset : offset + CHUNK_SIZE]
        final = offset + CHUNK_SIZE >= len(plaintext)
        encrypted.extend(aead.encrypt(_stream_nonce(counter, final=final), chunk, None))
        counter += 1
    return bytes(encrypted)


def _stream_nonce(counter: int, *, final: bool) -> bytes:
    if counter < 0 or counter >= 1 << 88:
        raise AgeEncryptionError("chunk counter out of range")
    return counter.to_bytes(11, "big") + (b"\x01" if final else b"\x00")


def _private_key_from_random(random_bytes: RandomBytes) -> x25519.X25519PrivateKey:
    try:
        return x25519.X25519PrivateKey.from_private_bytes(_read_random(random_bytes, 32))
    except (TypeError, ValueError, UnsupportedAlgorithm) as err:
        raise AgeEncryptionError("invalid X25519 ephemeral secret") from err


def _read_random(random_bytes: RandomBytes, length: int) -> bytes:
    data = random_bytes(length)
    if not isinstance(data, bytes) or len(data) != length:
        raise AgeEncryptionError(f"random source returned invalid {length}-byte value")
    return data


def _hkdf(*, ikm: bytes, salt: bytes, info: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    ).derive(ikm)


def _raw_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii").rstrip("=")


def _wrap_base64_body(data: bytes) -> bytes:
    encoded = _raw_base64(data)
    lines = [encoded[index : index + 64] for index in range(0, len(encoded), 64)]
    if not lines or len(lines[-1]) == 64:
        lines.append("")
    return "".join(f"{line}\n" for line in lines).encode()
