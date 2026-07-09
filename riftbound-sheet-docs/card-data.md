# `Card Data`

Live schema notes for the main sheet tab.

Verified against the live sheet on 2026-03-31 through direct Google Sheets API access.

## Current Shape

- tab title: `Card Data`
- row count including header: `1012`
- frozen row count: `1`
- active columns used by the bridge: `A:W`

## Live Header

```text
card_name
card-id
tts-slug-same
tts-slug-initial
legacy coverage?
dot-gg-slug
effect
tts-type
super-type
type
tags
domain
might
cost
power
spawn
equip_might
flavor
artist
rarity
set
seq
signature_key
```

## Meaning

- `card_name`: display name
- `card-id`: canonical print id, eg `UNL-219`
- `tts-slug-same`: current TTS slug
- `tts-slug-initial`: initial TTS slug
- `legacy coverage?`: legacy support/status column
- `dot-gg-slug`: DotGG slug
- `effect`: rules text
- `tts-type`: TTS-facing type, eg `Unit`, `Spell`, `Battlefield`, `Rune`, `Legend`
- `super-type`: derived type layer, usually formula/generated
- `type`: raw gameplay type
- `tags`: tribes / regions / other tags
- `domain`: rune/domain identity
- `might`: stat, blank when not relevant
- `cost`: play cost
- `power`: extra stat field where relevant
- `spawn`: token/helper spawn string for TTS scripting
- `equip_might`: equipment bonus might
- `flavor`: flavor text
- `artist`: artist credit
- `rarity`: rarity text
- `set`: set name, eg `Unleashed`
- `seq`: sequence index within same card family
- `signature_key`: derived signature grouping key

## Current Set Values Seen

- `Origins`
- `Spiritforged`
- `Unleashed`
- `Arcane Box Set`
- `Proving Grounds`
- `Riftbound Promotional Cards`
- `Custom`

## Notes For Agents

- Row identity is effectively `card-id`
- One row per print / variant / token / rune
- Empty numeric-ish fields are empty strings, not `null`
- `spawn` is single-value; if a card wants two helper objects, a manual preference may be required

## Safe Write Targets

The importer currently writes:

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

Treat these as bridge-owned unless the sheet design changes.

## Caution

Older notes that mention:

- `effect` in column `H`
- `set` in column `V`
- `seq` near the front

are stale.
