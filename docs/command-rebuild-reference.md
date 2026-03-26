# Victor Command Rebuild Reference

This file tracks the command set that has been parked while Victor runs in sync-only mode.

## Active Runtime

- Loaded cogs: `bot.cogs.staff_console`, `bot.cogs.monitor`, `bot.cogs.admin`
- Active text command: `!sync`
- Active slash command: `/sync`
- Source of truth for sync-only mode: `bot/main.py`

## Parked Cogs

- `bot/cogs/verify.py`
- `bot/cogs/blackmarket.py`
- `bot/cogs/matchmaking.py`
- `bot/cogs/help.py`

## Parked Text Commands

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
- `!restart`
- `!help`
- `!help verify`
- `!help blackmarket`
- `!help matchmaking`
- `!help admin`

## Parked Slash Commands

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
- `/restart`
- `/help [feature]`

## Rebuild Notes

- The command implementations are still present in the parked cog files above.
- `bot/cogs/admin.py` is the only command cog still loaded, and it now exposes sync only.
- `bot/cogs/staff_console.py` keeps operational crash-thread tooling, but its auto-fix path is limited to sync-safe guidance.
