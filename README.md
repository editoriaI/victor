# Victor - The Undead Intern Discord Bot

Victor is a narrative-embedded Discord bot with a goth-cute undead intern persona. This repo contains the bot, SQLite schema, and Discord command system for verification, marketplace flows, and admin controls.

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

- `!verify @user highrise_username`
- `!manualverify @user [highrise_username]`
- `!status`
- `!status @user`
- `!blackmarket list [query]`
- `!blackmarket add "item name" 25000`
- `!blackmarket remove <listing_id>`
- `!request "item name" 25000`
- `!cancel <request_id>`
- `!accept <match_id>`
- `!decline <match_id>`
- `!blacklist add @user reason`
- `!blacklist remove @user`
- `!blacklist list`
- `!sync`
- `!restart`
- `!help`
- `!help verify`
- `!help blackmarket`
- `!help matchmaking`
- `!help admin`

## Slash Commands

- `/help [feature]`
- `/verify member highrise_username`
- `/manualverify member [highrise_username]`
- `/status [member]`
- `/marketlist [query]`
- `/marketadd item_name price`
- `/marketremove listing_id`
- `/request item_name max_price`
- `/cancelrequest request_id`
- `/accept match_id`
- `/decline match_id`
- `/sync`
- `/restart`

## Notes

- Enable Message Content Intent and Server Members Intent in the Discord Developer Portal.
- The bot stores data in `db/victor.db`.
- Errors are returned as URGENT embeds.
- By default, Victor watches `bot/`, `config/`, `.env`, `requirements.txt`, and `db/schema.sql` and restarts when those files change.
- `!sync` and `/sync` resync slash commands manually. `!restart` and `/restart` request a clean restart.
- `!verify` and `/verify` now check the Highrise Web API for the username, issue a 4-character code, and attach a `Confirm Bio Updated` button that triggers the bio re-check.
- After two failed bio checks, staff can use `!manualverify` or `/manualverify`.
- Successful verification updates the member nickname to the Highrise username and grants the roles listed in `roles.verified_unlock`.
- Configure the Highrise endpoint with `highrise_api_base_url` and optional `highrise_api_key` if your deployment needs one.
- The `HBIC` owner role bypasses all role checks and blacklist restrictions.
- Child process logs stay quiet in the console and write detailed command activity to `logs/victor-child.log`.
- `!help` and `/help` include a dropdown selection interface for topic-based help.
- If `log_channel_id` is set, Victor posts a color-coded mobile-friendly console feed to that Discord channel.

## Styling

Victor uses grayscale, CLI-styled embeds with dry, precise tone. Adjust colors and phrasing in `bot/embeds.py`.
