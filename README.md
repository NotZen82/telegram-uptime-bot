# Telegram Uptime Bot

A Telegram-native uptime monitor for small web studios, freelancers, and self-hosted projects.

Add websites directly from Telegram and get alerts when a site goes down, comes back online, or when its SSL certificate is close to expiration. The bot is designed for people who want simple monitoring in a chat instead of a heavy dashboard.

Try the bot: https://t.me/my_uptime_notzen_bot

## Why This Exists

Most uptime tools are built around dashboards, email alerts, Slack, or complex incident workflows. This bot focuses on a smaller workflow:

- add a client site from Telegram;
- get DOWN and RECOVERY alerts in Telegram;
- check SSL expiration;
- keep a lightweight incident history;
- manage everything from buttons and commands.

It is especially useful if you maintain websites for clients and want alerts in the same place where you already communicate.

## Features

- HTTP/HTTPS uptime checks
- Telegram DOWN and RECOVERY alerts
- SSL expiration warnings
- Domain expiration warnings
- Incident history
- Per-site settings:
  - failure threshold
  - custom check interval
  - SSL monitoring toggle
  - domain monitoring toggle
  - display name
- Manual check command
- Feedback forwarding to a private group
- RU/EN language switch
- Self-hosted deployment with PostgreSQL
- Retro MIDI mode, because monitoring can have a little personality

## Quick Start

Open the bot:

```text
https://t.me/my_uptime_notzen_bot
```

Start the bot:

```text
/start
```

Add a site:

```text
/add example.com
```

Check all sites:

```text
/check
```

Show monitoring summary:

```text
/status
```

Open a site card:

```text
/site 1
```

Change language:

```text
/lang
```

## Telegram Commands

```text
/start      Open the main menu
/add        Add a site, for example /add example.com
/remove     Remove a site by number or URL
/list       Show monitored sites
/site       Show a site card
/status     Show monitoring summary
/check      Run a manual check
/incidents  Show recent incidents
/feedback   Send feedback to the admin group
/myid       Show the current chat_id
/lang       Switch interface language
/retro      Open retro mode
```

## Self-Hosting

The bot is a Python worker that uses Telegram polling and PostgreSQL. It does not require a public IP address or open inbound ports.

### Requirements

- Python 3.11+
- PostgreSQL
- Telegram bot token from BotFather

Install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Create environment variables:

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://uptime_bot:password@127.0.0.1:5432/uptime_bot
FEEDBACK_CHAT_ID=-1001234567890
FAILURE_THRESHOLD=3
```

Run locally:

```bash
python bot.py
```

## Proxmox / Linux Service Example

This project works well in a small Proxmox LXC container.

Example `systemd` unit:

```ini
[Unit]
Description=Telegram Uptime Monitor Bot
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/telegram-uptime-bot
EnvironmentFile=/opt/telegram-uptime-bot/.env
ExecStart=/opt/telegram-uptime-bot/.venv/bin/python /opt/telegram-uptime-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable telegram-uptime-bot
systemctl start telegram-uptime-bot
systemctl status telegram-uptime-bot
```

View logs:

```bash
journalctl -u telegram-uptime-bot -n 50 --no-pager
```

## Database

The bot creates and updates the required PostgreSQL tables automatically on startup:

- `sites`
- `incidents`
- `chat_settings`

## Russian

Bot поддерживает русский и английский интерфейс. Чтобы переключить язык, используйте команду:

```text
/lang
```

Идея продукта: простой Telegram-мониторинг сайтов для фрилансеров, веб-студий и владельцев небольших проектов.

## Roadmap

- Client/project grouping
- Maintenance windows
- Acknowledge and mute buttons on alerts
- Daily and weekly Telegram reports
- Public mini status pages
- White-label mode for web studios

## License

No license has been selected yet.
