# cloudreve-cli

Full-coverage CLI for the [Cloudreve v4](https://cloudreve.org/) API.

## Installation

Requires Python 3.12+.

```bash
pip install cloudreve-cli
```

Or install from source with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/jore731/cloudreve-cli.git
cd cloudreve-cli
uv sync
```

## Quick Start

### Configure

Set your Cloudreve server URL and API token via environment variables:

```bash
export CLOUDREVE_SERVER="https://cloud.example.com"
export CLOUDREVE_TOKEN="your-api-token"
```

Or pass them as flags:

```bash
cloudreve --server https://cloud.example.com --token your-api-token site ping
```

### Test connectivity

```bash
cloudreve site ping
```

## Global Options

| Flag | Description |
|------|-------------|
| `--server URL` | Cloudreve server URL |
| `--token TOKEN` | API bearer token |
| `--profile NAME` | Config profile name (default: `default`) |
| `--output FORMAT` | Output format: `table` (default) or `json` |
| `--quiet` | Suppress non-essential output |
| `--verbose` | Log HTTP requests to stderr |
| `--retries N` | Retry count for 5xx errors (default: 0) |

## Authentication

### Generating an API Token

cloudreve-cli authenticates using a **Bearer token** obtained from the Cloudreve v4 sign-in API. To generate one, send a `POST` request to your Cloudreve server:

```bash
curl -X POST https://cloud.example.com/api/v4/session/token \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'
```

The response contains an `access_token` and a `refresh_token`:

```json
{
  "code": 0,
  "data": {
    "token": {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "eyJhbGciOi...",
      "access_expires": "2025-04-26T16:19:38+08:00",
      "refresh_expires": "2025-10-23T15:19:38+08:00"
    }
  }
}
```

Use the `access_token` value as your `CLOUDREVE_TOKEN`.

> **2FA enabled?** If your account has two-factor authentication, the sign-in response will return `"code": 203` with a session ID instead. Use it to complete the 2FA challenge:
>
> ```bash
> curl -X POST https://cloud.example.com/api/v4/session/2fa \
>   -H "Content-Type: application/json" \
>   -d '{"session_id": "<session-id>", "code": "123456"}'
> ```

### Configuration

Environment variables take absolute precedence — if any `CLOUDREVE_*` env var is set, the config file is completely ignored.

| Variable | Description |
|----------|-------------|
| `CLOUDREVE_SERVER` | Server URL |
| `CLOUDREVE_TOKEN` | Bearer token (the `access_token` from sign-in) |

When no env vars are set, configuration is read from `~/.config/cloudreve-cli/config.toml`.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest -v

# Lint
uv run ruff check .
uv run ruff format --check .
```

## License

[GPL-3.0](LICENSE)