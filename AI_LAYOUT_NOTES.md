# AI Layout Notes - Riftbound LGS Table

Last updated: 2026-02-12

## Primary files in this directory
- Main save: `Riftbound-LGS-Table.json`

## Preferred AI workflow
- Use extraction/context pipeline before editing.
- Workspace: `S:\Dev\TTS\aipipeline\workspaces\riftbound`
- Extracted global script: `S:\Dev\TTS\aipipeline\workspaces\riftbound\scripts\global\LuaScript.lua`
- Script map/context: `S:\Dev\TTS\aipipeline\workspaces\riftbound\context\CONTEXT.md`
- Call graph: `S:\Dev\TTS\aipipeline\workspaces\riftbound\context\CALLS.json`
- Repack through pipeline instead of manual full JSON edits.

## Save structure summary
- TTS version observed: `v14.1.8`
- `ObjectStates` count: `77`
- Global Lua length: `145028`
- Global XmlUI length: `14861`
- Scripted objects (non-global): `31`

## Major script-bearing objects
- `c2d323` `PiecePack_Arms` `Riftbound_CardLibrary` (lua=248334, xml=0, depth=0)
- `02e062` `PiecePack_Arms` `Encoder` (lua=45689, xml=0, depth=0)
- `7deec9` `PiecePack_Moons` `Riftbound Card Menu` (lua=20894, xml=0, depth=0)
- `7dffc9` `PiecePack_Moons` `Riftbound Deck Codes` (lua=12590, xml=0, depth=0)
- `de4346` `PiecePack_Arms` `πGlimpse` (lua=9249, xml=0, depth=0)
- `7a0067` `PiecePack_Arms` `πNotepad` (lua=8644, xml=0, depth=0)
- `c369d7` `PiecePack_Arms` `πMenu` (lua=8506, xml=0, depth=0)
- `cd83de` `PiecePack_Crowns` `Auto Player Promoter` (lua=7132, xml=0, depth=0)
- `c2d324` `PiecePack_Arms` `Riftbound_CollationLibrary` (lua=5483, xml=0, depth=0)
- `f0607e` `Custom_Tile` `Blue Playmat Template` (lua=2508, xml=2633, depth=0)
- `53ddd0` `Custom_Tile` `Green Playmat Template` (lua=2602, xml=2535, depth=0)
- `35894d` `Custom_Tile` `Red Playmat Template` (lua=2532, xml=2535, depth=0)
- `a251c2` `Custom_Tile` `Purple Playmat Template` (lua=2508, xml=2535, depth=0)
- `3afac6` `CardCustom` `Quick Actions Panel` (lua=2362, xml=1606, depth=0)

## Containers worth checking
- `5ddb44` `Infinite_Bag` `Status Tokens` (contained=1)
- `7fd7f6` `Infinite_Bag` `D6` (contained=1)
- `9231d7` `Infinite_Bag` `Booster Packs` (contained=1)
- `421f2d` `Infinite_Bag` `Quick Actions Menus` (contained=1)

## Exploration order
1. Refresh extract/context in pipeline workspace.
2. Inspect global script entrypoints first.
3. Inspect major helper/library objects and menu modules.
4. Inspect relevant container prototypes for clone/spawn behavior.
5. Repack and test in TTS.

## Caveat
- GUIDs/object indexes may drift between save revisions; re-scan when save changes.
