"""BeeBuzz HTTP and encryption client."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Iterable
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from aiohttp import ClientError, ClientResponse, ClientTimeout, ContentTypeError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._age import AgeEncryptionError, encrypt_age_x25519, parse_x25519_recipient
from .const import DEFAULT_HOST, MAX_ATTACHMENT_BYTES

KEYS_PATH = "/v1/push/keys"
PUSH_PATH = "/v1/push/"
DEFAULT_TIMEOUT = ClientTimeout(total=15)
ATTACHMENT_TIMEOUT = ClientTimeout(total=15)


class BeeBuzzError(Exception):
    """Base BeeBuzz integration error."""


class BeeBuzzAuthError(BeeBuzzError):
    """BeeBuzz authentication failed."""


class BeeBuzzConnectionError(BeeBuzzError):
    """BeeBuzz connection failed."""


class BeeBuzzValidationError(BeeBuzzError):
    """BeeBuzz payload validation failed."""


def build_api_url(host: str | None = None, legacy_url: str | None = None) -> str:
    """Build the BeeBuzz API URL from a configured host."""

    value = (host or legacy_url or DEFAULT_HOST).strip().rstrip("/")
    if not value:
        value = DEFAULT_HOST
    if "://" not in value:
        if not value.startswith("api."):
            value = f"api.{value}"
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise BeeBuzzValidationError("BeeBuzz requires an HTTPS endpoint")
    if not parsed.netloc:
        raise BeeBuzzValidationError("BeeBuzz host is invalid")
    return value.rstrip("/")


def normalize_topic(topic: str | None) -> str:
    """Normalize a BeeBuzz topic for the push endpoint."""

    topic = (topic or "").strip()
    if topic.startswith("#"):
        topic = topic[1:]
    return topic or "general"


def build_plain_payload(
    *,
    title: str,
    body: str,
    topic: str,
    attachment: dict[str, Any] | None,
) -> bytes:
    """Build the plaintext JSON payload encrypted for BeeBuzz devices."""

    payload: dict[str, Any] = {
        "title": title,
        "body": body,
        "topic": topic,
    }
    if attachment:
        payload["attachment"] = attachment
    return json.dumps(payload, separators=(",", ":")).encode()


def encrypt_payload(plaintext: bytes, recipients: Iterable[str]) -> bytes:
    """Encrypt a BeeBuzz payload with age X25519 recipients."""

    normalized_recipients = [
        recipient.strip() for recipient in recipients if recipient.strip()
    ]
    if not normalized_recipients:
        raise BeeBuzzValidationError("No BeeBuzz device public keys are configured")
    try:
        return encrypt_age_x25519(plaintext, normalized_recipients)
    except AgeEncryptionError as err:
        raise BeeBuzzValidationError(str(err)) from err


class BeeBuzzClient:
    """Async BeeBuzz API client."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the client."""

        self._hass = hass
        self._session = async_get_clientsession(hass)

    async def async_fetch_keys(self, api_url: str, api_token: str) -> list[dict[str, Any]]:
        """Fetch paired device age public keys."""

        response = await self._request("GET", f"{api_url}{KEYS_PATH}", api_token)
        payload = await _read_json(response)
        if not isinstance(payload, dict):
            raise BeeBuzzValidationError("Invalid BeeBuzz keys response")
        keys = payload.get("data") or []
        if not isinstance(keys, list):
            raise BeeBuzzValidationError("Invalid BeeBuzz keys response")
        return validate_device_keys(keys)

    async def async_push(
        self,
        *,
        api_url: str,
        api_token: str,
        topic: str,
        priority: str,
        title: str,
        body: str,
        device_keys: list[dict[str, Any]],
        attachment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Encrypt and send a notification."""

        normalized_topic = normalize_topic(topic)
        recipients = [key.get("age_recipient", "") for key in device_keys]
        plaintext = build_plain_payload(
            title=title,
            body=body,
            topic=normalized_topic,
            attachment=attachment,
        )
        ciphertext = await self._hass.async_add_executor_job(encrypt_payload, plaintext, recipients)
        url = f"{api_url}{PUSH_PATH}{quote(normalized_topic, safe='')}"
        response = await self._request(
            "POST",
            url,
            api_token,
            data=ciphertext,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Priority": priority,
            },
        )
        payload = await _read_json(response)
        if not isinstance(payload, dict):
            raise BeeBuzzValidationError("Invalid BeeBuzz push response")
        if "device_keys" in payload:
            payload["device_keys"] = validate_device_keys(payload.get("device_keys") or [])
        return payload

    async def async_attachment_from_value(self, value: Any) -> dict[str, str] | None:
        """Resolve an attachment mapping value to the encrypted BeeBuzz attachment shape."""

        if value in (None, ""):
            return None

        if isinstance(value, dict):
            source = value.get("url") or value.get("path") or value.get("file")
            filename = value.get("filename")
            mime = value.get("mime")
            if not source:
                raise BeeBuzzValidationError(
                    "Attachment object must include one of: url, path, file"
                )
        else:
            source = str(value)
            filename = None
            mime = None

        if not source:
            return None

        if source.startswith("media-source://"):
            return await self._async_media_source_attachment(source, filename, mime)

        if source.startswith(("http://", "https://")):
            return await self._async_remote_attachment(source, filename, mime)

        return await self._async_local_attachment(source, filename, mime)

    async def _async_media_source_attachment(
        self,
        media_source_id: str,
        filename: str | None,
        mime: str | None,
    ) -> dict[str, str]:
        """Resolve a Home Assistant media source attachment."""

        from homeassistant.components import media_source

        if not media_source.is_media_source_id(media_source_id):
            raise BeeBuzzValidationError("Invalid media source URI")

        resolved = await media_source.async_resolve_media(self._hass, media_source_id, None)
        if resolved.path is None:
            raise BeeBuzzValidationError(
                "BeeBuzz only supports media-source attachments that resolve to local files"
            )

        data = await self._hass.async_add_executor_job(_read_limited_file, resolved.path)
        return _encoded_attachment(
            data=data,
            filename=filename or resolved.path.name,
            mime=mime or resolved.mime_type,
        )

    async def _request(
        self,
        method: str,
        url: str,
        api_token: str,
        **kwargs: Any,
    ) -> ClientResponse:
        """Run an authenticated request and normalize errors."""

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {api_token}"
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        try:
            response = await self._session.request(
                method, url, headers=headers, **kwargs
            )
        except (ClientError, asyncio.TimeoutError) as err:
            raise BeeBuzzConnectionError(str(err) or err.__class__.__name__) from err

        if response.status == 401:
            body = await _safe_text(response)
            raise BeeBuzzAuthError(body or "Unauthorized")
        if response.status >= 400:
            body = await _safe_text(response)
            raise BeeBuzzError(
                f"{method} {url} failed with HTTP {response.status}: {body}"
            )
        return response

    async def _async_remote_attachment(
        self,
        url: str,
        filename: str | None,
        mime: str | None,
    ) -> dict[str, str]:
        """Fetch and encode a remote attachment."""

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise BeeBuzzValidationError("Attachment URL must use http or https")

        try:
            async with self._session.get(
                url,
                timeout=ATTACHMENT_TIMEOUT,
            ) as response:
                if response.status >= 400:
                    body = await _safe_text(response)
                    raise BeeBuzzError(
                        f"Attachment download failed with HTTP {response.status}: {body}"
                    )
                data = await response.content.read(MAX_ATTACHMENT_BYTES + 1)
                if len(data) > MAX_ATTACHMENT_BYTES:
                    raise BeeBuzzValidationError(
                        f"Attachment exceeds {MAX_ATTACHMENT_BYTES} bytes"
                    )
                inferred_filename = Path(parsed.path).name or "attachment"
                return _encoded_attachment(
                    data=data,
                    filename=filename or inferred_filename,
                    mime=mime or response.headers.get("Content-Type"),
                )
        except (ClientError, asyncio.TimeoutError) as err:
            raise BeeBuzzConnectionError(
                f"Attachment download failed: {err or err.__class__.__name__}"
            ) from err

    async def _async_local_attachment(
        self,
        path: str,
        filename: str | None,
        mime: str | None,
    ) -> dict[str, str]:
        """Read and encode a local attachment."""

        file_path = await self._hass.async_add_executor_job(_resolve_file_path, Path(path).expanduser())
        if hasattr(self._hass.config, "is_allowed_path") and not self._hass.config.is_allowed_path(
            str(file_path)
        ):
            raise BeeBuzzValidationError(f"Attachment path is not allowed by Home Assistant: {file_path}")

        data = await self._hass.async_add_executor_job(_read_limited_file, file_path)
        return _encoded_attachment(
            data=data,
            filename=filename or file_path.name,
            mime=mime or mimetypes.guess_type(file_path.name)[0],
        )


def _read_limited_file(path: Path) -> bytes:
    """Read a local file with the BeeBuzz attachment limit."""

    try:
        with path.open("rb") as file:
            data = file.read(MAX_ATTACHMENT_BYTES + 1)
    except OSError as err:
        raise BeeBuzzValidationError(f"Cannot read attachment: {err}") from err
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise BeeBuzzValidationError(f"Attachment exceeds {MAX_ATTACHMENT_BYTES} bytes")
    return data


def _resolve_file_path(path: Path) -> Path:
    """Resolve a local attachment path and require a regular file."""

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise BeeBuzzValidationError(f"Attachment not found: {path}") from None
    except PermissionError:
        raise BeeBuzzValidationError(f"Permission denied for attachment: {path}") from None
    except OSError as err:
        raise BeeBuzzValidationError(f"Cannot resolve attachment path: {err}") from err

    if not resolved.is_file():
        raise BeeBuzzValidationError(f"Attachment path is not a file: {resolved}")
    return resolved


def _encoded_attachment(*, data: bytes, filename: str, mime: str | None) -> dict[str, str]:
    """Encode bytes for the BeeBuzz encrypted attachment payload."""

    return {
        "data": base64.b64encode(data).decode(),
        "mime": (mime or "application/octet-stream").split(";")[0],
        "filename": filename or "attachment",
    }


def validate_device_keys(keys: list[Any]) -> list[dict[str, Any]]:
    """Validate and normalize a BeeBuzz device key list."""

    normalized: list[dict[str, Any]] = []
    for item in keys:
        if not isinstance(item, dict):
            raise BeeBuzzValidationError("Invalid BeeBuzz device key entry")
        recipient = str(item.get("age_recipient", "")).strip()
        if not recipient:
            raise BeeBuzzValidationError("BeeBuzz device key is missing age_recipient")
        _parse_recipient(recipient)
        normalized_item = dict(item)
        normalized_item["age_recipient"] = recipient
        normalized.append(normalized_item)
    return normalized


def fingerprint_age_recipient(recipient: str) -> str:
    """Return a short stable fingerprint for an age recipient."""

    digest = hashlib.sha256(recipient.strip().encode()).hexdigest()
    return ":".join(digest[index : index + 2] for index in range(0, 16, 2))


def _parse_recipient(recipient: str) -> Any:
    """Parse an age recipient and normalize parsing errors."""

    try:
        return parse_x25519_recipient(recipient)
    except AgeEncryptionError as err:
        raise BeeBuzzValidationError(f"Invalid BeeBuzz age recipient: {recipient}") from err


async def _read_json(response: ClientResponse) -> Any:
    """Read a JSON response and normalize decoding errors."""

    try:
        return await response.json(content_type=None)
    except (ContentTypeError, ValueError, json.JSONDecodeError) as err:
        raise BeeBuzzValidationError(
            f"Invalid BeeBuzz response (not JSON): {err}"
        ) from err


async def _safe_text(response: ClientResponse) -> str:
    """Read a response body as text, swallowing decoding errors."""

    try:
        return await response.text()
    except (UnicodeDecodeError, ClientError, asyncio.TimeoutError):
        return ""
