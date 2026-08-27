# githuber

Telegram bot that tracks your open GitHub PRs: CI results, reviews, comments,
and merge conflicts. One live message per PR.

Notifies on:

- CI going green (once per commit)
- New comments and review comments from others
- Review verdicts: approved / changes requested
- Merge conflicts with the base branch

## Commands

| Command | Description |
|---------|-------------|
| `/status` | List open PRs with CI and review state |
| `/mute org/repo` or `/mute org/repo#7` | Silence a repo or a single PR |
| `/unmute <target>` | Remove a mute |
| `/mutes` | List active mutes |
| `/help` | Show commands |

## Configuration

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Token used to search PRs and read checks |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Chat to notify (your user id for DMs) |
| `GITHUB_API_URL` | API base, default `https://api.github.com` |
| `POLL_INTERVAL` | Seconds between polls, default `60` |
| `STATE_FILE` | State path, default `/state/state.json` |
| `WEBHOOK_SECRET` | Optional GitHub webhook secret; enables instant refresh |
| `WEBHOOK_PORT` | Optional port for the webhook listener |

When `WEBHOOK_SECRET` and `WEBHOOK_PORT` are set, the bot also listens for GitHub webhooks
(`check_suite`, `pull_request`, reviews, comments) and refreshes immediately on delivery.

## Development

```sh
uv sync
uv run --group dev pytest tests
uv run --group dev ruff check .
```

## Running

```sh
docker compose up -d
```
