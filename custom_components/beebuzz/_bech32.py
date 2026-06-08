"""Minimal Bech32 support vendored from age.

Ported from FiloSottile/age internal/bech32/bech32.go.
Upstream source: https://github.com/FiloSottile/age/tree/main/internal/bech32
This implementation follows age compatibility needs and is not a strict
BIP-0173 general-purpose Bech32 implementation.
License notice from upstream:

Copyright (c) 2017 Takatoshi Nakagawa
Copyright (c) 2019 The age Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from __future__ import annotations

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


class Bech32Error(ValueError):
    """Raised when Bech32 data is invalid."""


def _polymod(values: bytes) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5
        chk ^= value
        for index in range(5):
            if (top >> index) & 1:
                chk ^= GENERATOR[index]
    return chk


def _hrp_expand(hrp: str) -> bytes:
    lowered = hrp.lower().encode()
    return bytes(char >> 5 for char in lowered) + b"\x00" + bytes(
        char & 31 for char in lowered
    )


def _verify_checksum(hrp: str, data: bytes) -> bool:
    return _polymod(_hrp_expand(hrp) + data) == 1


def _create_checksum(hrp: str, data: bytes) -> bytes:
    values = _hrp_expand(hrp) + data + b"\x00\x00\x00\x00\x00\x00"
    mod = _polymod(values) ^ 1
    return bytes((mod >> (5 * (5 - index))) & 31 for index in range(6))


def convert_bits(data: bytes, frombits: int, tobits: int, *, pad: bool) -> bytes:
    """Convert a byte string between power-of-two bit group sizes."""

    ret = bytearray()
    acc = 0
    bits = 0
    maxv = (1 << tobits) - 1
    for index, value in enumerate(data):
        if value >> frombits:
            raise Bech32Error(
                f"invalid data range: data[{index}]={value} (frombits={frombits})"
            )
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits > 0:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits:
        raise Bech32Error("illegal zero padding")
    elif ((acc << (tobits - bits)) & maxv) != 0:
        raise Bech32Error("non-zero padding")
    return bytes(ret)


def encode(hrp: str, data: bytes) -> str:
    """Encode HRP and bytes as Bech32."""

    values = convert_bits(data, 8, 5, pad=True)
    if not hrp:
        raise Bech32Error(f"invalid HRP: {hrp!r}")
    for index, char in enumerate(hrp):
        codepoint = ord(char)
        if codepoint < 33 or codepoint > 126:
            raise Bech32Error(f"invalid HRP character: hrp[{index}]={codepoint}")
    if hrp.upper() != hrp and hrp.lower() != hrp:
        raise Bech32Error(f"mixed case HRP: {hrp!r}")
    lower = hrp.lower() == hrp
    hrp = hrp.lower()
    encoded = hrp + "1" + "".join(CHARSET[value] for value in values)
    encoded += "".join(CHARSET[value] for value in _create_checksum(hrp, values))
    return encoded if lower else encoded.upper()


def decode(value: str) -> tuple[str, bytes]:
    """Decode a Bech32 string into HRP and bytes."""

    if value.lower() != value and value.upper() != value:
        raise Bech32Error("mixed case")
    pos = value.rfind("1")
    if pos < 1 or pos + 7 > len(value):
        raise Bech32Error(
            f"separator '1' at invalid position: pos={pos}, len={len(value)}"
        )
    hrp = value[:pos]
    for index, char in enumerate(hrp):
        codepoint = ord(char)
        if codepoint < 33 or codepoint > 126:
            raise Bech32Error(
                f"invalid character human-readable part: s[{index}]={codepoint}"
            )
    lowered = value.lower()
    data = bytearray()
    for index, char in enumerate(lowered[pos + 1 :]):
        decoded = CHARSET.find(char)
        if decoded == -1:
            raise Bech32Error(f"invalid character data part: s[{index}]={char}")
        data.append(decoded)
    if not _verify_checksum(hrp, bytes(data)):
        raise Bech32Error("invalid checksum")
    return hrp, convert_bits(bytes(data[:-6]), 5, 8, pad=False)
