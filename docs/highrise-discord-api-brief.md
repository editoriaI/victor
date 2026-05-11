# Highrise + Discord API Brief For Victor

Last reviewed: April 17, 2026

This note cross-references the current Highrise Bot API, Highrise Web API, and Discord app model so Victor's server-side verification and future bridge features stay grounded in the official docs.

## Current Platform Split

Victor touches two different Highrise surfaces:

- Highrise Bot API: real-time room actions and events over the bot connection / SDK.
- Highrise Web API: public read-only REST data for users, rooms, posts, items, grabs, and conversations.
- Discord API: slash commands, buttons, modals, permissions, OAuth scopes, and gateway intents used by the Discord bot.

The important distinction is that the Highrise Web API is public and read-only, while the Highrise Bot API is the interactive runtime surface for bots inside a room.

## Highrise Bot API Notes

Official docs confirm:

- Bots connect with a bot API token created in the Highrise dashboard.
- Bots need designer rights for the room they join.
- The API is event-driven over a websocket, and clients can limit traffic with an `events` query parameter.
- Documented event groups include `chat`, `emote`, `reaction`, `user_joined`, `user_left`, `user_moved`, `tip_reaction`, `voice`, and `channel`.

Useful bot-side request families called out in the docs:

- `GetRoomUsersRequest`: list users currently in the room with positions.
- `EmoteRequest`: trigger emotes, optionally targeting a user.
- `ModerateRoomRequest`: kick, ban, unban, or mute.
- `ChannelRequest`: hidden room message for bot/script coordination.
- `SendMessageRequest`: send conversation messages, including room invites.
- `GetMessagesRequest`: page through conversation history.
- `GetUserOutfitRequest` and `SetOutfitRequest`: read or change outfit data.
- `CheckVoiceChatRequest`: inspect current voice state.
- `TipUser...`: tipping is supported in the bot API family.

Runtime caution:

- The session metadata docs describe leaky-bucket limits and say a safe rule of thumb is roughly 1 request per second.
- If a bot exceeds the limit, requests may be processed more slowly instead of failing immediately.

## Highrise Web API Notes

Official docs confirm:

- Base URL: `https://webapi.highrise.game/`
- Authentication: currently not required for public data endpoints.
- Data is read-only; the docs explicitly say modification/updating is unsupported.
- Pagination uses cursor params `starts_after` and `ends_before`.
- Rate limiting is enforced with HTTP `429 Too Many Requests`.

Useful REST endpoints for Victor's verification and lookup work:

- `GET /users`
  - Supports `username`, `limit`, `sort_order`, `starts_after`, `ends_before`, and `include_avatar_svg`.
- `GET /users/{user_id}`
  - Returns a richer user payload including username, bio, outfit, social counts, and active room data when available.
- `GET /rooms` and `GET /rooms/{room_id}`
  - Useful if Victor later wants to validate room ownership or surface room info.
- `GET /posts`, `GET /items`, `GET /grabs`, and conversation resources
  - Useful for future market, trend, or profile enrichment work.

What this means for Victor:

- `bot/highrise_api.py` is correctly pointed at `https://webapi.highrise.game`.
- Treat `HIGHRISE_API_KEY` as optional only; it is not required by the current public docs.
- Username existence and profile lookup are a good fit for the Web API.
- Anything that requires "being in-room" should stay in the Bot API or a dedicated Highrise bot service, not in Victor's Discord-only process.

## Discord API Notes

Current Discord docs confirm:

- Application commands are the primary command model.
- Interactions cover slash commands, buttons, select menus, and modals.
- Interactions can be received via Gateway or via an HTTP interactions endpoint.
- The `applications.commands` OAuth scope is required for registering slash commands.
- Bot tokens are used for gateway connections and most bot REST calls.
- User Bearer tokens are only needed when acting on behalf of a user.
- Command visibility can be restricted with `default_member_permissions`.
- Per-command permission overwrites in a guild require a Bearer token with the `applications.commands.permissions.update` scope; bot tokens do not work for that endpoint.

What this means for Victor:

- Victor is aligned with Discord's current direction because it already uses slash commands, buttons, and modals for verification.
- Prefix commands still work, but slash-first UX is the safer long-term path.
- `message_content` and `members` intents remain important for Victor's current hybrid design.
- Role-gated staff commands should continue to be enforced in-code even if Discord command defaults are also set.

## Cross-Research: Best Fit By Job

Use Highrise Web API when Victor needs:

- exact username lookup
- profile/bio validation
- lightweight read-only enrichment
- pagination through public Highrise data

Use Highrise Bot API when the system needs:

- live room presence
- user coordinates / room roster
- in-room moderation
- emotes, tips, outfit changes, or hidden bot channels
- direct response to room events

Use Discord interactions when the server needs:

- staff approval UI
- verification intake modals
- audit-friendly staff actions
- permission-gated command lanes
- server-native onboarding flow

## Victor-Specific Recommendations

1. Keep verification centered on the Highrise Web API.
   Username lookup plus profile fetch is the cleanest supported path for Discord-side verification.

2. Do not design Victor as if it can control a Highrise room directly.
   If Victor ever needs live room state, pair it with a separate Highrise bot worker and communicate over a narrow internal API or queue.

3. Handle Highrise 429s explicitly in verification UX.
   The current client already surfaces rate-limit errors, which is worth keeping because the public docs confirm rate limiting.

4. Keep `HIGHRISE_API_KEY` optional in docs and config.
   Current official Web API docs say auth is not required.

5. Prefer slash commands and modals for staff workflows.
   That matches Discord's documented interaction model and reduces dependence on message content over time.

6. If command permissions need to be managed from outside Discord's UI later, plan for OAuth user authorization.
   Bot tokens cannot edit command permission overwrites on that endpoint.

## Suggested Future Integration Shape

If Victor grows beyond verification, the clean architecture is:

- `victor-bot`: Discord-facing command and review workflow.
- `highrise-bot`: room-connected worker using the Highrise Bot API / SDK.
- shared storage or a tiny internal service:
  - verification cache
  - room presence snapshots
  - marketplace sync jobs
  - moderation handoff events

That split keeps Discord concerns, Highrise room automation, and public REST lookups from bleeding into one process.

## Official Sources

- Highrise bot guide: <https://create.highrise.game/learn/bots/guides/creating-a-bot>
- Highrise bot endpoint docs:
  - <https://create.highrise.game/learn/bots/api/endpoints/getroomusersrequest>
  - <https://create.highrise.game/learn/bots/api/endpoints/emoterequest>
  - <https://create.highrise.game/learn/bots/api/endpoints/moderateroomrequest>
  - <https://create.highrise.game/learn/bots/api/endpoints/channelrequest>
  - <https://create.highrise.game/learn/bots/api/endpoints/getmessagesrequest>
  - <https://create.highrise.game/learn/bots/api/endpoints/checkvoicechatrequest>
  - <https://create.highrise.game/learn/bots-api/endpoints/sessionmetadata>
- Highrise Web API overview: <https://create.highrise.game/learn/web-api/general/overview>
- Highrise Web API users:
  - <https://create.highrise.game/learn/web-api/endpoints/invoke_get_users>
  - <https://create.highrise.game/learn/web-api/endpoints/invoke_get_user>
- Discord interactions and commands:
  - <https://docs.discord.com/developers/platform/interactions>
  - <https://docs.discord.com/developers/interactions/application-commands>
  - <https://docs.discord.com/developers/platform/oauth2-and-permissions>
