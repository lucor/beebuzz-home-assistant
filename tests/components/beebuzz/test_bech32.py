"""Tests for the vendored age Bech32 implementation."""

from __future__ import annotations

import pytest

from custom_components.beebuzz._bech32 import Bech32Error, decode, encode

UPSTREAM_LONG_BECH32_VECTOR = "long1" + ("0pu8s7rc" * 204) + "0pu8s7qfcsvr0"


@pytest.mark.parametrize(
    ("hrp", "data"),
    [
        ("age", bytes.fromhex("00" * 32)),
        ("AGE", bytes.fromhex("11" * 32)),
        ("test", b"hello"),
    ],
)
def test_bech32_round_trip(hrp: str, data: bytes) -> None:
    """Vendored Bech32 should round-trip canonical values."""

    encoded = encode(hrp, data)

    assert decode(encoded) == (hrp, data)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("A12UEL5L", True),
        ("a12uel5l", True),
        (
            "an83characterlonghumanreadablepartthatcontainsthenumber1andthe"
            "excludedcharactersbio1tt5tgs",
            True,
        ),
        ("abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw", True),
        (
            "11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
            "qqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j",
            True,
        ),
        ("split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w", True),
        ("split1checkupstagehandshakeupstreamerranterredcaperred2y9e2w", False),
        ("s lit1checkupstagehandshakeupstreamerranterredcaperredp8hs2p", False),
        ("split1cheo2y9e2w", False),
        ("split1a2y9w", False),
        ("1checkupstagehandshakeupstreamerranterredcaperred2y9e3w", False),
        (
            "spl" + chr(127) + "t1checkupstagehandshakeupstreamerranterredcaperred2y9e3w",
            False,
        ),
        (UPSTREAM_LONG_BECH32_VECTOR, True),
        (
            "an84characterslonghumanreadablepartthatcontainsthenumber1andthe"
            "excludedcharactersbio1569pvx",
            True,
        ),
        ("pzry9x0s0muk", False),
        ("1pzry9x0s0muk", False),
        ("x1b4n0q5v", False),
        ("li1dgmt3", False),
        ("de1lg7wt\xff", False),
        ("A1G7SGD8", False),
        ("10a06t8", False),
        ("1qzzfhee", False),
    ],
)
def test_bech32_matches_upstream_age_vectors(value: str, valid: bool) -> None:
    """Mirror FiloSottile/age internal/bech32 TestBech32 vectors."""

    if not valid:
        with pytest.raises(Bech32Error):
            decode(value)
        return

    hrp, data = decode(value)
    assert encode(hrp, data) == value

    pos = value.rfind("1")
    flipped = value[: pos + 1] + chr(ord(value[pos + 1]) ^ 1) + value[pos + 2 :]
    with pytest.raises(Bech32Error):
        decode(flipped)


@pytest.mark.parametrize(
    "value",
    [
        "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8P",
        "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8x",
        "age1invalid!",
        "age",
    ],
)
def test_bech32_rejects_invalid_values(value: str) -> None:
    """Malformed Bech32 input must fail closed."""

    with pytest.raises(Bech32Error):
        decode(value)
