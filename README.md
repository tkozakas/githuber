# githuber

Telegram/Slack bot for your open GitHub PRs. One live card per PR, updated in place and removed on merge or close.

Notifies on:

- CI going green
- New comments and reviews
- Approvals and change requests
- Merge conflicts

<details>
<summary><b>Why?</b></summary>

GitHub notifies about plenty of noise but stays silent on what I actually wait for: CI turning green, or a conflict after someone merges ahead of me. This bot tells me so I don't have to keep checking the tab.

</details>

<details>
<summary><b>Commands</b></summary>

Telegram: `/status`. Slack: `/githuber status`.

| Command | Description |
|---------|-------------|
| `status` | Open PRs with CI and review state |
| `mute org/repo` or `mute org/repo#7` | Silence a repo or PR |
| `unmute <target>` | Remove a mute |
| `mutes` | List mutes |
| `disable <type>` / `enable <type>` | Toggle `green`, `conflicts`, `comments`, `verdicts` |
| `settings` | Show toggles |
| `help` | Show commands |

</details>

<details>
<summary><b>Configuration</b></summary>

Configure at least one channel; defining its variables enables it.

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Reads PRs and checks |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Enable Telegram |
| `SLACK_BOT_TOKEN`, `SLACK_CHANNEL` | Enable Slack |
| `SLACK_SIGNING_SECRET` | Enables `/githuber` slash commands (needs `WEBHOOK_PORT`) |
| `WEBHOOK_SECRET`, `WEBHOOK_PORT` | Optional instant refresh via GitHub webhooks |
| `POLL_INTERVAL` | Polling interval in seconds when webhooks are off |

</details>

<details>
<summary><b>Run & develop</b></summary>

```sh
docker compose up -d
```

```sh
uv sync
uv run --group dev pytest tests
uv run --group dev ruff check .
```

</details>
