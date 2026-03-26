# Victor - The Undead Intern Discord Bot

Victor is a narrative-embedded Discord bot with a goth-cute undead intern persona. The repo still contains the broader command system, but the live runtime is intentionally parked in sync-only mode while the rest of the command set gets rebuilt.

## Quick Start

1. Create a virtual environment and install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Copy the config example and edit it:

```powershell
Copy-Item config\config.example.json config\config.json
```

3. Set your Discord token:

```powershell
$env:DISCORD_TOKEN = "your_token_here"
```

Or create a `.env` file:

```powershell
@'
DISCORD_TOKEN=your_token_here
'@ | Set-Content -Path .\.env
```

4. Run Victor:

```powershell
python -m bot.main
```

Or launch a child-mode session directly:

```powershell
.\start-child.ps1
```

## Commands

- `!sync`

## Slash Commands

- `/sync`

## Notes

- Enable Message Content Intent and Server Members Intent in the Discord Developer Portal.
- The bot stores data in `db/victor.db`.
- Errors are returned as URGENT embeds.
- By default, Victor watches `bot/`, `config/`, `.env`, `requirements.txt`, and `db/schema.sql` and restarts when those files change.
- `!sync` and `/sync` are the only active commands right now.
- The parked command inventory lives in `docs/command-rebuild-reference.md`.
- The underlying cogs for verification, marketplace, matchmaking, and help are still in the repo as rebuild reference, but they are not loaded by `bot/main.py`.
- Child process logs stay quiet in the console and write detailed command activity to `logs/victor-child.log`.
- If `log_channel_id` is set, Victor posts a color-coded mobile-friendly console feed to that Discord channel.

## Styling

Victor uses grayscale, CLI-styled embeds with dry, precise tone. Adjust colors and phrasing in `bot/embeds.py`.
