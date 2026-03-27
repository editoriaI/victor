# Victor Command Rebuild Reference

This file tracks the command set that is still parked while Victor comes back online in stages.

## Active Runtime

- Loaded cogs: `bot.cogs.staff_console`, `bot.cogs.monitor`, `bot.cogs.verify`, `bot.cogs.admin`, `bot.cogs.help`
- Active text commands: `!menu`, `!help`, `!verify`, `!manualverify`, `!status`, `!sync`
- Active slash commands: `/menu`, `/help`, `/verify`, `/manualverify`, `/status`, `/sync`
- Source of truth for staged runtime loading: `bot/main.py`

## Parked Cogs

- `bot/cogs/blackmarket.py`
- `bot/cogs/matchmaking.py`

## Parked Text Commands

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

## Parked Slash Commands

- `/marketlist [query]`
- `/marketadd item_name price`
- `/marketremove listing_id`
- `/request item_name max_price`
- `/cancelrequest request_id`
- `/accept match_id`
- `/decline match_id`
- `/restart`

## Rebuild Notes

- The parked command implementations are still present in the parked cog files above.
- `bot/cogs/verify.py` is live again, including `verify`, `manualverify`, and `status`.
- `bot/cogs/help.py` is live again, including a `menu` command that opens a button-driven command board inside Discord.
- `bot/cogs/staff_console.py` keeps operational crash-thread tooling, and verify review threads now reconnect to the live verify handlers.
