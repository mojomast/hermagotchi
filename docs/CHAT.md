# Chat routes

The live API serves moderated lobby chat at:

```
GET  /v1/chat/channels/{channel_id}/messages
POST /v1/chat/channels/{channel_id}/messages
```

The Desktop client addresses these through the local bridge proxy
(`/chat/channels/{channel_id}/messages`) with the default channel `lobby`
(`/chat/channels/lobby/messages`). The bridge allowlist already accepts that
pattern.

Do not use `/v1/chat/messages` or `/chat/messages`: that shortcut path is not
mounted and returns `404`.

## Production mount

Chat routes are mounted with the other `/v1` routers. Production needs no
special disable flag for the routes themselves; a deployment that exposes the
router exposes chat automatically. The Desktop UI's policy flag
`chat_enabled` only controls whether the pane shows the live composer or the
chat-off stub.

If a future environment gate named `HERMAGOTCHI_CHAT_ENABLED` is introduced,
keep it enabled by default in production so the existing routes remain
reachable. Treat any explicit opt-out as a deployment-local override rather
than a required production setting.

## Contracts

- `GET` returns `{contracts_version, channel_id, messages, next_before}`.
- `POST` returns `{contracts_version, message}` with status `201`.
- Bodies are plain display text (maximum 400 characters); clients must render
  them as text and never as HTML.
- Sending requires a paired account session. Rate limits, blocks and moderation
  reports return structured error envelopes that the Desktop UI turns into
  display-only moderation notices.
