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

Environment variables take absolute precedence — if any `CLOUDREVE_*` env var is set, the config file is completely ignored.

| Variable | Description |
|----------|-------------|
| `CLOUDREVE_SERVER` | Server URL |
| `CLOUDREVE_TOKEN` | Bearer token |

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