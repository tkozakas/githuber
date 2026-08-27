# githuber

Telegram bot (@githuber_bot) that sends a message when CI goes green on your open GitHub PRs.

Polls the GitHub API for open PRs authored by the token owner, checks check-runs and commit
statuses on each head SHA, and notifies once per PR-commit. Pushing new commits re-arms the
notification.

## Configuration

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Token used to search PRs and read checks |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Chat to notify (your user id for DMs) |
| `GITHUB_API_URL` | API base, default `https://api.github.com` |
| `POLL_INTERVAL` | Seconds between polls, default `60` |
| `STATE_FILE` | Notified-state path, default `/state/state.json` |

## Development

```sh
uv sync
uv run --group dev pytest tests
uv run --group dev ruff check .
```

## Running

Pushes to `main` publish `ghcr.io/tkozakas/githuber:main` (amd64 + arm64).

```sh
docker compose up -d
```
