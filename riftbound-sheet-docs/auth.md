# Auth

Google Sheets access uses a local OAuth client JSON plus a saved user token.

Files:

- Client: [google-oauth-client.json](google-oauth-client.json)
- Token: [google-oauth-token.json](google-oauth-token.json)
- Helper: [google_auth.py](google_auth.py)

## Required OAuth Setup

Expected client type:

- Google OAuth web client

Expected redirect:

- `http://127.0.0.1:8080`

Expected scopes:

- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/spreadsheets`

## Normal Use

The importer refreshes access tokens automatically from the saved refresh token:

- `refresh_access_token(...)` in [piltover_spoilers_to_sheet.py](piltover_spoilers_to_sheet.py)
- `read_sheet_token()` wraps that for normal script runs

Usually nothing manual is needed until Google revokes the refresh token.

## Reauth

When refresh starts failing with:

```text
invalid_grant
Token has been expired or revoked.
```

Run:

```bash
python3 riftbound-sheet-docs/google_auth.py
```

That script:

1. starts a localhost listener on `127.0.0.1:8080`
2. prints a one-time Google consent URL
3. waits for the browser callback
4. exchanges the code
5. overwrites [google-oauth-token.json](google-oauth-token.json)

Browser success page:

```text
Auth received. You can close this tab.
```

## Manual Notes

- If `8080` is already in use, free it first.
- The consent URL is one-time because it includes `state` and PKCE fields.
- If the token file lacks a `refresh_token`, rerun auth with `prompt=consent`.
- If Google blocks access, confirm the account is still a test user in the Cloud project.

## Safety

These files grant access to the live spreadsheet.

Do not paste them into TTS docs.
