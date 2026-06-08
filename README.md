# BeeBuzz for Home Assistant

Custom Home Assistant integration that sends end-to-end encrypted [BeeBuzz](https://beebuzz.app) push notifications.

The integration encrypts every notification locally with [age](https://age-encryption.org) v1 (X25519) using each paired device's
public key before it is sent to the BeeBuzz API, so the BeeBuzz service can never read the title, body or attachments.

## Requirements

- Home Assistant **2024.6.0** or newer.
- A BeeBuzz account, an API token and at least one paired BeeBuzz device.

## Installation with HACS

1. Add this repository as a HACS custom repository of type **Integration**.
2. Install **BeeBuzz**.
3. Restart Home Assistant.
4. Add the integration from **Settings → Devices & services → Add integration → BeeBuzz**.

## Configuration

The UI setup accepts:

- **Domain** – default `beebuzz.app`. Self-hosted endpoints must be reachable over HTTPS.
- **API token** – generated from your BeeBuzz account.
- **Default topic** – default `#general`. Values like `#general` are accepted and sent as `general`.
- **Default priority** – `normal` or `high`.

When the form is submitted Home Assistant fetches the BeeBuzz device public
keys from `/v1/push/keys`. The keys are then refreshed periodically, on
demand via the **Refresh device keys** button, and after every successful
send (the API can return an updated key list).

If a send returns 401 Unauthorized, the integration triggers the standard
Home Assistant reauthentication flow.

## Sending notifications

### Standard notify entity

```yaml
action: notify.send_message
target:
  entity_id: notify.beebuzz
data:
  title: "Door"
  message: "The front door opened"
```

### BeeBuzz extended action

For BeeBuzz-specific options like `topic`, `priority`, or `attachment`, use
the dedicated action:

```yaml
action: beebuzz.send_message
data:
  title: "Door"
  body: "The front door opened"
  topic: "#general"
  priority: high
```

### Attachments

Attachments may be a string or an object. Supported sources:

- A local path on the Home Assistant host. Local paths must be allowed by
  Home Assistant's
  [`allowlist_external_dirs`](https://www.home-assistant.io/docs/configuration/basic/#allowlist_external_dirs).
- A `media-source://` URI that resolves to a local file.
- An `http://` or `https://` URL.

```yaml
action: beebuzz.send_message
data:
  title: "Camera"
  body: "Motion detected"
  attachment:
    url: "https://example.com/snapshot.jpg"
    filename: "snapshot.jpg"
    mime: "image/jpeg"
```

Attachments are limited to 1 MiB before encryption.

## Repairs and troubleshooting

The integration creates Home Assistant *Repairs* issues when:

- No BeeBuzz devices are paired – open the BeeBuzz mobile app and pair at
  least one device.
- Several consecutive device key refreshes fail – check the host, API token
  and that the BeeBuzz API is reachable.

The diagnostics download (Settings → Devices & services → BeeBuzz → ⋮ →
Download diagnostics) redacts the API token, the topic, and any self-hosted
host name, and only reports short fingerprints of paired device keys.

## Development

This repository uses `mise` to keep the Python toolchain and local commands
stable. From the repository root:

```sh
mise install
mise run test
```

Useful focused commands:

```sh
mise run test-age
mise run lint
```

`uv` installs the test tooling on demand from `requirements_test.txt`, so
local test runs do not depend on globally installed `pytest` or `ruff`.

The age interoperability tests in
[`tests/components/beebuzz/test_age.py`](tests/components/beebuzz/test_age.py)
shell out to the Go `age` and `age-keygen` binaries, which `mise` installs
from the aqua registry alongside Python. Both local `mise run test` and the
GitHub Actions workflow therefore exercise the interop tests by default;
they are only skipped when the binaries are unavailable on `PATH`.

## License

Released under the [MIT License](LICENSE).
