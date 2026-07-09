# Sheets Bridge

Primary sheet bridge is direct Google Sheets API access.

Do not start with the Apps Script web app. Treat that as fallback only.

## Files

- OAuth client: [google-oauth-client.json](google-oauth-client.json)
- OAuth token: [google-oauth-token.json](google-oauth-token.json)
- Reauth helper: [google_auth.py](google_auth.py)
- Main sheet helper / importer: [piltover_spoilers_to_sheet.py](piltover_spoilers_to_sheet.py)

## Spreadsheet

- Title: `Riftbound Card Data for LGS Table TTS Mod`
- Spreadsheet id: `1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM`
- Main tab: `Card Data`
- Collation tab: `Collation Library`

Live tabs seen on 2026-03-31:

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

## Default Workflow

1. Refresh access token from `google-oauth-token.json`.
2. Read/write with Sheets API.
3. Use `Card Data` as the source of truth for card rows.
4. Use local docs here for schema and auth.

## Current `Card Data` Header

Live row 1 as of 2026-03-31:

```text
A card_name
B card-id
C tts-slug-same
D tts-slug-initial
E legacy coverage?
F dot-gg-slug
G effect
H tts-type
I super-type
J type
K tags
L domain
M might
N cost
O power
P spawn
Q equip_might
R flavor
S artist
T rarity
U set
V seq
W signature_key
```

Important: older notes that place `effect` at `H` or `set` at `V` are stale.

## Main Read/Write Columns

Usually authored:

- `A` `card_name`
- `B` `card-id`
- `G` `effect`
- `H` `tts-type`
- `L` `domain`
- `M` `might`
- `N` `cost`
- `O` `power`
- `P` `spawn`
- `Q` `equip_might`
- `R` `flavor`
- `S` `artist`
- `T` `rarity`
- `U` `set`

Usually formula / generated:

- `C` `tts-slug-same`
- `D` `tts-slug-initial`
- `F` `dot-gg-slug`
- `I` `super-type`
- `W` `signature_key`

Do not assume formula status from old docs. Recheck row 1 if a write matters.

## Live API Pattern

Read values:

```bash
curl -s \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID/values/Card%20Data!A:W"
```

Batch write values:

```bash
curl -s \
  -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID/values:batchUpdate" \
  -d '{
    "valueInputOption": "RAW",
    "data": [
      {"range": "Card Data!G968", "values": [["example effect"]]}
    ]
  }'
```

Sheet metadata:

```bash
curl -s \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://sheets.googleapis.com/v4/spreadsheets/$SHEET_ID?fields=properties.title,sheets.properties"
```

## Script Notes

`piltover_spoilers_to_sheet.py` already knows:

- sheet id
- OAuth file locations
- current `Card Data` write map
- `UNL` sort behavior
- duplicate cleanup helpers
- `spawn` helper patches

Useful commands:

```bash
python3 riftbound-sheet-docs/piltover_spoilers_to_sheet.py --set UNL --json
python3 riftbound-sheet-docs/piltover_spoilers_to_sheet.py --set UNL --append-sheet
python3 riftbound-sheet-docs/piltover_spoilers_to_sheet.py --set UNL --sort-sheet-block
python3 riftbound-sheet-docs/piltover_spoilers_to_sheet.py --set UNL --set-spawn-defaults
python3 scripts/export_tts_catalog_from_sheet.py
```

Generated Lua export:

- Source tab: `TTS Lua Script (Automatically Generated)`
- Expected shape: one Lua line per row in column `A`
- Output file: `scripts/generated_riftbound_card_catalog.lua`

## Known Failure Mode

Most common bridge failure is:

```text
invalid_grant
Token has been expired or revoked.
```

If that happens, reauthorize. See [auth.md](auth.md).

## Scope

This bridge doc is sheet-only.

It intentionally does not document:

- TTS Lua layout
- JPG directory behavior beyond what the importer needs
- collation library internals
