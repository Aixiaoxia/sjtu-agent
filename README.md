# SJTU Agent

SJTU Agent is a deployable Shanghai Jiao Tong University campus assistant with a terminal chat agent, Telegram bot, reminder daemon, and MCP server.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
sjtu-agent setup
```

The recommended first-run path is the built-in conversational setup assistant. It now starts by saving the LLM API settings that drive the agent, then checks Python dependencies, verifies or installs Playwright Chromium, offers to save campus credentials, tries to auto-create a Canvas token when possible, imports teaching-platform cookies from Chrome, runs a configuration doctor, can install macOS launchd services in one pass, and finally offers to launch the main agent chat immediately.

During `sjtu-agent setup`, you can answer in plain language and use commands such as `status`, `help`, `skip`, `quit`, `open canvas`, and `auto canvas`.

## Runtime Data

Installed commands read and write runtime files from the user data directory instead of the repository root.

- macOS: `~/Library/Application Support/sjtu-agent`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/sjtu-agent`
- Windows: `%APPDATA%/sjtu-agent`

On first import, the package migrates existing local files from the repository root when they exist:

- `.env`
- `config.json`
- `agent_config.json`
- `reminders.json`
- `remind_state.json`
- `mysjtu_catalog.json`
- `.schedule_cache.json`

## Commands

```bash
sjtu-agent                # start chat mode
sjtu-agent setup          # conversational first-run setup assistant
sjtu-agent doctor         # print current setup and runtime paths
sjtu-agent setup-config   # read browser cookies and build config.json
sjtu-agent login --aihaoke
sjtu-agent ddl --canvas-only
sjtu-agent daily-report --test
sjtu-agent telegram-bot --test
sjtu-agent remind-check --list
sjtu-agent mcp --http --port 8765
sjtu-agent install-daemons
```

You can also run the package directly:

```bash
python -m sjtu_agent
```

Useful setup assistant variants:

```bash
sjtu-agent setup
sjtu-agent setup --yes --skip-cookie-import --skip-launchd
sjtu-agent setup --yes --write-daemons-only --output-dir /tmp/sjtu-agent-launchd
```

## macOS Launchd

On macOS, you can install the built-in user daemons with one command:

```bash
sjtu-agent install-daemons
```

By default this writes LaunchAgent plist files into `~/Library/LaunchAgents` and loads them into the current user session.

- `daily-report`: runs every day at `22:00`
- `remind-check`: runs every `60` seconds
- `telegram-bot`: starts at login and is kept alive by launchd

Useful variants:

```bash
sjtu-agent install-daemons --write-only
sjtu-agent install-daemons --services daily-report remind-check
sjtu-agent install-daemons --daily-report-time 21:30 --remind-interval 120
```

All generated agents use the selected Python interpreter, run from the runtime data directory, and write logs under `~/Library/Application Support/sjtu-agent/logs`.

## Configuration

The main runtime files are:

- `config.json`: platform tokens, cookies, Telegram settings
- `.env`: jAccount and MOOC credentials
- `agent_config.json`: LLM provider and model settings

For Canvas, `sjtu-agent setup` will try to auto-create and save the token when Playwright plus jAccount credentials are already available. If that best-effort path fails, it falls back to opening `https://oc.sjtu.edu.cn/profile/settings` and asking you to confirm the token once.

## Release Notes

This repository now exposes a package shell and stable entrypoint, but the core platform adapters still live in the existing top-level modules. That keeps behavior stable while making the project installable and distributable.