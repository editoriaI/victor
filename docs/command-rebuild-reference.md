# Victor Command Rebuild Reference

This file tracks the command set that is still parked while Victor comes back online in stages.

## Active Runtime

- Loaded cogs: `bot.cogs.staff_console`, `bot.cogs.monitor`, `bot.cogs.verify`, `bot.cogs.admin`, `bot.cogs.blackmarket`, `bot.cogs.help`
- Active text commands: `!menu`, `!help`, `!verify`, `!manualverify`, `!status`, `!sync`, `!purge`, `!blackmarket list`, `!blackmarket add`, `!blackmarket remove`
- Active slash commands: `/menu`, `/help`, `/verify`, `/manualverify`, `/status`, `/sync`, `/autosync`, `/autoverifymode`, `/purge`, `/marketlist`, `/marketadd`, `/marketremove`
- Source of truth for staged runtime loading: `bot/main.py`

## Parked Cogs

- `bot/cogs/matchmaking.py`

## Parked Text Commands

- `!request "item name" 25000`
- `!cancel <request_id>`
- `!accept <match_id>`
- `!decline <match_id>`
- `!blacklist add @user reason`
- `!blacklist remove @user`
- `!blacklist list`
- `!restart`

## Parked Slash Commands

- `/request item_name max_price`
- `/cancelrequest request_id`
- `/accept match_id`
- `/decline match_id`
- `/restart`

## Rebuild Notes

- The parked command implementations are still present in the parked cog files above.
- `bot/cogs/verify.py` is live again, including `verify`, `manualverify`, and `status`.
- `bot/cogs/blackmarket.py` is live again, including listing browse/create/remove lanes.
- `bot/cogs/help.py` is live again, including a `menu` command that opens a button-driven command board inside Discord.
- Added `!autoverify @member username` so staff can instantly approve a username without navigating the modal flow (still limited to verifier/admin/owner).
- `bot/cogs/staff_console.py` keeps operational crash-thread tooling, and verify review threads now reconnect to the live verify handlers.

## Announcements

- `!verify` now opens the intake prompt and quietly deletes the member message after submission so the channel stays tidy; staff decisions self-destruct once they finish.
- Verified members who carry the admin, owner, or founder cloth now get a quick installation recognition badge in their success note so the whole desk knows it was a VIP file.
