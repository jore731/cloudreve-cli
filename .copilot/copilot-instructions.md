# Copilot Instructions — cloudreve-cli

## Project Overview

Full-coverage Python CLI for the [Cloudreve v4 API](https://cloudrevev4.apifox.cn/llms.txt) (~70+ endpoints). The CLI command is `cloudreve`, the package is `cloudreve-cli`.

- **PRD**: GitHub issue #1
- **Implementation issues**: #3–#18 (vertical slices, each with acceptance criteria)
- **License**: GPL v3

## Stack & Tooling

- **Runtime**: Python ≥3.12 (provided by uv, no separate python in devbox)
- **Package manager**: [uv](https://docs.astral.sh/uv/) via devbox
- **Dev environment**: [devbox](https://www.jetify.com/devbox/) — packages: `uv@latest`, `pre-commit@latest`
- **Build backend**: hatchling
- **Dependencies**: click, httpx, pydantic, rich, tomli-w
- **Dev deps**: ruff, pytest, pytest-httpx
- **Pre-commit hooks**: ruff (lint + fix), ruff-format, ggshield (secret scanning)

## Critical: Always Use `devbox run`

All commands MUST be run through devbox:

```sh
devbox run "uv sync"
devbox run "uv run pytest"
devbox run "uv run ruff check src/ tests/"
devbox run "git commit -m 'message'"
```

**Why**: The ggshield pre-commit hook crashes outside devbox due to a Python 3.13 compatibility issue in its marshmallow dependency. Running inside devbox provides the correct Python environment.

Use the pattern `devbox run "cd target_directory && command"` if you need to change directory.

## Architecture

### Module Layout

```
src/cloudreve_cli/
├── cli.py            # Root Click group, global options, GlobalState, main()
├── client.py         # CloudreveClient (httpx wrapper, envelope parsing, retries)
├── config.py         # Three-tier auth resolution
├── exceptions.py     # CloudreveError hierarchy with exit codes
├── exit_codes.py     # Exit code constants
├── commands/         # Click command groups (one file per group)
│   └── site.py       # `site ping` — reference implementation
└── utils/
    └── output.py     # render_json, render_table, render_kv, echo
```

### Adding a New Command Group

1. Create `src/cloudreve_cli/commands/<group>.py`
2. Import `cli` and `pass_state` from `cloudreve_cli.cli`
3. Define a `@cli.group()` and subcommands
4. Register it via bottom import in `cli.py`: `from cloudreve_cli.commands import <group> as _<group>`

See `commands/site.py` for the reference pattern.

### Auth Resolution (strict precedence)

1. **CLI flags** (`--server`, `--token`) — highest priority
2. **Env vars** (`CLOUDREVE_SERVER`, `CLOUDREVE_TOKEN`) — if ANY env var is set, config file is completely ignored
3. **TOML profiles** (`~/.config/cloudreve-cli/config.toml`) — named profiles with `default_profile`

### API Response Envelope

All Cloudreve v4 API responses follow this envelope:

```json
{"code": 0, "data": {...}, "msg": "", "error": null, "correlation_id": null}
```

- `code: 0` = success → extract and return `data`
- Non-zero `code` = error → raise `APIError` with message from `msg` or `error`

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Auth error (401/403) |
| 3 | Not found (404) |
| 4 | Conflict (409) |

### Error Handling

Two layers:
1. **`CloudreveGroup.invoke()`**: Catches `CloudreveError`, prints to stderr, raises `SystemExit(exit_code)`
2. **`main()`**: Entry point catches `CloudreveError`, `click.Exit`, `click.Abort`

### Output Conventions

- **JSON output** (`--output json`): Raw API response to **stdout** via `render_json()`
- **Table output** (`--output table`): Rich tables to **stderr** via `render_table()` / `render_kv()`
- **Rich console** (`err_console`): Always writes to stderr to keep stdout clean for piping
- **`echo()`**: Respects `--quiet` flag
- **Progress bars**: Rich progress to stderr, suppressed by `--quiet` and `--output json`

### HTTP Client (`CloudreveClient`)

- Wraps httpx with Bearer auth header
- Retries with exponential backoff (`min(2^attempt, 30)s`) on 5xx and connection errors
- Never retries 4xx
- Maps HTTP status to exceptions: 401/403→`AuthError`, 404→`NotFoundError`, 409→`ConflictError`
- `--verbose` logs HTTP method, URL, status, and timing to stderr

## Design Decisions

- **Paths are always absolute** — no cwd state, no relative paths
- **Cloudreve URI scheme**: `cloudreve://my/`, `cloudreve://trash/`, `cloudreve://shared_with_me/`
- **`--proxied` is always available** as a flag on upload commands
- **Upload strategy pattern**: `LocalUploader` / `S3Uploader` selected at runtime
- **Downloads**: Single file only via `files download`; archive workflow for directories
- **Pagination**: Auto-paginate by default; `--page`/`--per-page` for specific slices
- **2FA**: Interactive prompt in TTY + `--2fa-code` flag for scripting
- **Retries**: `--retries N` (default 0 = fail fast)

## Testing

```sh
devbox run "uv run pytest"
devbox run "uv run pytest -v"             # verbose
devbox run "uv run pytest tests/test_site_ping.py"  # specific file
```

- Tests use `pytest-httpx` to mock HTTP responses
- `CliRunner` from Click for CLI integration tests
- **Do NOT use `CliRunner(mix_stderr=False)`** — removed in Click 8.2+

## Linting & Formatting

```sh
devbox run "uv run ruff check src/ tests/"       # lint
devbox run "uv run ruff check src/ tests/ --fix"  # lint + autofix
devbox run "uv run ruff format src/ tests/"       # format
```

Ruff config: line-length 99, target py312, rules: E, F, I, UP, B, SIM, RUF.

## Git Workflow

- Pre-commit hooks run automatically on `git commit` (inside devbox)
- Always commit via `devbox run "git commit -m '...'"` 
- Close issues with `Closes #N` in commit messages
- GitHub account: `jore731` (switch with `gh auth switch --user jore731`)
