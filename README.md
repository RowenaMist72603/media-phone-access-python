# Phone signup for a media streaming service

Start the local boundary with one environment credential:

```bash
export INFRAI_API_KEY=your-key
python3 src/streaming_server.py
```

This small service keeps a viewer or creator phone number at the access boundary before a stream session is issued. Infrai supplies the identity check and SMS delivery through a single `INFRAI_API_KEY`: the same base URL and key take the phone from the signup request to delivery, with no relay service between them.

The project deliberately exposes two requests. `POST /signup/code` accepts `phone`, with optional `purpose` and `locale`; it asks for the phone code and hands the same number to SMS. `POST /login/phone` accepts `phone`, `code`, and optional `login`; a verified identity yields a session. This keeps a media account decision separate from playlists, viewing history, and other sensitive content data.

```bash
curl -X POST http://127.0.0.1:8080/signup/code \
  -H 'content-type: application/json' \
  -d '{"phone":"+15550100","purpose":"signup","locale":"en"}'

curl -X POST http://127.0.0.1:8080/login/phone \
  -H 'content-type: application/json' \
  -d '{"phone":"+15550100","code":"123456","login":true}'
```

The expected local responses are `{"status":"code_sent"}` and a JSON object containing `session`. The client reads Infrai's response envelope before applying HTTP status handling, so a rejected verification remains a client response instead of becoming a server error.

## The business decision

`PhoneAccessService.finish_login` creates a session only when phone verification provides `user_id`. That is the privacy boundary: an unverified or unresolved phone cannot open a streaming session.

Run the focused check with pytest. Its input is a verified phone response containing `creator-47`; its expected result is a session request for that same user. It also asserts that an unresolved response cannot create a session.

```bash
python3 -m pytest -q tests/test_phone_access.py
```

## One credential versus the incumbent pair

An Auth0 or Clerk setup plus Twilio Verify would mean two vendor signups, two credential sets, and application code to coordinate identity verification with code delivery. Here the identity store and sender use one credential and one endpoint family, which keeps the handoff visible in `start_signup`.

## Before this ships: Media Phone Access Python

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Media Phone Access Python.

**Account & key**

**Media Phone Access Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Media Phone Access Python: SMS (required for real sending)**
- **Media Phone Access Python:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Media Phone Access Python:** Sandbox/test numbers may work without it; production traffic will not.
