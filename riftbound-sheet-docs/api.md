# Spreadsheet Access

Prefer direct Google Sheets API access.

Start with [sheets-bridge.md](sheets-bridge.md).

Keep this file only for the secondary Apps Script path and raw API examples.

Sheet:

```text
https://docs.google.com/spreadsheets/d/1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM/edit
```

Spreadsheet id:

```text
1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM
```

## Current Working Path

As of 2026-03-31:

- Direct Sheets API access is the real bridge.
- The Apps Script web app is still secondary.
- OAuth files live in this directory.

Use:

- OAuth client: [google-oauth-client.json](google-oauth-client.json)
- OAuth token: [google-oauth-token.json](google-oauth-token.json)
- Local auth helper: [google_auth.py](google_auth.py)

## Sheets API Reads

Metadata:

```bash
ACCESS_TOKEN='...'
SHEET_ID='1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM'
curl -s \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID?fields=properties.title,sheets.properties"
```

Values:

```bash
curl -s \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID/values/'Card%20Data'!A:AG"
```

Header metadata with formulas:

```bash
curl -s \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID?includeGridData=true&ranges='Card%20Data'!1:1&fields=sheets(data(rowData(values(userEnteredValue,effectiveValue,formattedValue))))"
```

## Live Sheet Summary

Verified tabs on 2026-03-31:

- `Card Data`
- `CardsSupportedByWillow`
- `Missing Image Finder`
- `Uploaded Images`
- `Lookup Charts`
- `TTS Lua Script (Automatically Generated)`
- `DotGG`
- `Collation Library`
- `RiftCodex`
- `Riftmana Pre-SFD Release`
- `Replay Schema`

`Card Data` current grid shape:

- 1012 rows including header
- 32 grid columns
- bridge currently uses `A:W`

## Apps Script Web App

Base URL:

```text
https://script.google.com/macros/s/AKfycbzDX1SnhIL16PK8XzgLzG5LFfDABsSb9n-HpeBQUanzdi30vMXFDPCy3yDlwEkcRRe7/exec
```

Status:

- Raw unauthenticated requests still redirect to Google sign-in.
- Keep this as a secondary path unless the deployment is changed.

## Routes

`GET ?route=tabs`

- Returns sheet/tab names.

Example:

```bash
curl -s "$BASE?route=tabs"
```

`GET ?route=schema&tab=TAB_NAME`

- Returns header metadata for one tab.
- Each column object has:
  - `name`
  - `type`: `authored` or `calculated`
  - `formula`: formula string or `null`

Example:

```bash
curl -s "$BASE?route=schema&tab=card%20data"
```

`GET ?route=query&tab=TAB_NAME`

- Returns row objects.
- Requires an `id` column in the tab.
- Optional filters:
  - `ids`: comma-separated row ids
  - `columns`: comma-separated column names

Examples:

```bash
curl -s "$BASE?route=query&tab=card%20data"
curl -s "$BASE?route=query&tab=card%20data&ids=UNL-001,UNL-002"
curl -s "$BASE?route=query&tab=card%20data&columns=id,name,set_name"
curl -s "$BASE?route=query&tab=card%20data&ids=UNL-001&columns=id,name,effect"
```

`POST ?route=patch`

- Applies per-row updates by `id`.
- Only authored columns are writable.
- Calculated columns reject writes.

Body shape:

```json
{
  "tab": "card data",
  "changes": [
    {
      "id": "UNL-001",
      "values": {
        "name": "Example Name"
      }
    }
  ]
}
```

Example:

```bash
curl -s \
  -X POST \
  -H 'Content-Type: application/json' \
  "$BASE?route=patch" \
  -d '{"tab":"card data","changes":[{"id":"UNL-001","values":{"name":"Example Name"}}]}'
```

## Behavior Notes

- `id` is the sheet row key.
- `query` returns full objects unless `columns` is supplied.
- `patch` writes cells one by one with `setValue`.
- Formula protection is based on the header row cell formula, not the target row cell formula.

## Quick Check

Use this for the live sheet:

```bash
ACCESS_TOKEN='...'
SHEET_ID='1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM'
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID?fields=properties.title,sheets.properties"
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID/values/'Card%20Data'!A1:Z5"
```

Use this only if the Apps Script web app becomes directly callable:

```bash
BASE='https://script.google.com/macros/s/AKfycbzDX1SnhIL16PK8XzgLzG5LFfDABsSb9n-HpeBQUanzdi30vMXFDPCy3yDlwEkcRRe7/exec'
curl -s "$BASE?route=tabs"
curl -s "$BASE?route=schema&tab=card%20data"
curl -s "$BASE?route=query&tab=card%20data&columns=id,name,set_name"
```
