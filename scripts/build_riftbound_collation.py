#!/usr/bin/env python3
"""
Generate Riftbound booster collation Lua blocks from Riftbound_CardLibrary metadata.

Default behavior:
- Reads the extracted CardLibrary Lua from the AI pipeline workspace.
- Emits SFD and OGN pools and pack collation config as Lua.

This is intended to avoid hand-maintaining large pool tables.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_CARDLIB = Path(
    r"S:\Dev\TTS\aipipeline\workspaces\riftbound\scripts\objects\0025_c2d323_riftbound-cardlibrary\LuaScript.lua"
)
DEFAULT_OUT = Path(
    r"S:\Dev\TTS\RiftBound\Riftbound-TTS\scripts\generated_riftbound_collation.lua"
)

ENTRY_RE = re.compile(
    r'^\["(?P<slug>[^"]+)"\]\s*=\s*\{.*?gmNotes\s*=\s*\[\[(?P<gm>\{.*\})\]\]\s*\},?\s*$'
)


def is_pack_slug(slug: str, set_prefix: str) -> bool:
    return re.match(rf"^{re.escape(set_prefix)}-\d{{3}}[as]?$", slug) is not None


def parse_entries(cardlibrary_path: Path) -> list[dict]:
    rows: list[dict] = []
    with cardlibrary_path.open("r", encoding="utf-8") as f:
        for line in f:
            m = ENTRY_RE.match(line.strip())
            if not m:
                continue
            slug = m.group("slug")
            try:
                gm = json.loads(m.group("gm"))
            except json.JSONDecodeError:
                continue
            if not isinstance(gm, dict):
                continue
            rows.append(
                {
                    "slug": slug,
                    "set": str(gm.get("set") or ""),
                    "rarity": int(gm.get("rarity") or 0),
                }
            )
    return rows


def bucket_rows(rows: list[dict], set_prefix: str, set_name: str) -> dict[str, list[str]]:
    pools = {
        "COMMON": [],
        "UNCOMMON": [],
        "RARE": [],
        "EPIC": [],
        "SHOWCASE": [],
    }
    seen = {k: set() for k in pools}

    for r in rows:
        slug = r["slug"]
        if not slug.startswith(f"{set_prefix}-"):
            continue
        if slug.endswith("-p"):
            continue
        if not is_pack_slug(slug, set_prefix):
            continue
        if r["set"] != set_name:
            continue

        rarity = r["rarity"]
        if rarity == 1:
            key = "COMMON"
        elif rarity == 2:
            key = "UNCOMMON"
        elif rarity == 3:
            key = "RARE"
        elif rarity == 4:
            key = "EPIC"
        elif rarity == 5:
            key = "SHOWCASE"
        else:
            continue

        if slug not in seen[key]:
            seen[key].add(slug)
            pools[key].append(slug)

    for key in pools:
        pools[key].sort()
    return pools


def lua_list(items: list[str]) -> str:
    return "{" + ",".join(f'"{x}"' for x in items) + "}"


def emit_set_block(setcode: str, pools: dict[str, list[str]]) -> str:
    lines: list[str] = []
    lines.append(f"{setcode}_Common_Pool = {lua_list(pools['COMMON'])}")
    lines.append(f"{setcode}_Uncommon_Pool = {lua_list(pools['UNCOMMON'])}")
    lines.append(f"{setcode}_Rare_Pool = {lua_list(pools['RARE'])}")
    lines.append(f"{setcode}_Epic_Pool = {lua_list(pools['EPIC'])}")
    lines.append(f"{setcode}_Showcase_Pool = {lua_list(pools['SHOWCASE'])}")
    lines.append(
        f'{setcode}_RarePlus_Roll = {{ {{ pool = "{setcode}_Rare_Pool", weight = 87.5 }}, {{ pool = "{setcode}_Epic_Pool", weight = 12.5 }} }}'
    )
    lines.append(
        f'{setcode}_Any_Roll = {{ {{ pool = "{setcode}_Common_Pool", weight = 75 }}, {{ pool = "{setcode}_Uncommon_Pool", weight = 22 }}, {{ pool = "{setcode}_Rare_Pool", weight = 2.5 }}, {{ pool = "{setcode}_Epic_Pool", weight = 0.4 }}, {{ pool = "{setcode}_Showcase_Pool", weight = 0.1 }} }}'
    )
    return "\n".join(lines)


def emit_pack_collations() -> str:
    return (
        "pack_collations = {\n"
        '  SFD = {\n'
        '    { type = "SFD_Common_Pool", count = 7 },\n'
        '    { type = "SFD_Uncommon_Pool", count = 3 },\n'
        '    { type = "SFD_RarePlus_Roll", count = 2 },\n'
        '    { type = "SFD_Any_Roll", count = 1 },\n'
        "  },\n"
        '  OGN = {\n'
        '    { type = "OGN_Common_Pool", count = 7 },\n'
        '    { type = "OGN_Uncommon_Pool", count = 3 },\n'
        '    { type = "OGN_RarePlus_Roll", count = 2 },\n'
        '    { type = "OGN_Any_Roll", count = 1 },\n'
        "  },\n"
        "}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Riftbound booster collation Lua blocks.")
    parser.add_argument("--cardlibrary", type=Path, default=DEFAULT_CARDLIB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stdout", action="store_true", help="Print Lua to stdout instead of writing file.")
    args = parser.parse_args()

    rows = parse_entries(args.cardlibrary)
    if not rows:
        raise SystemExit(f"No card entries parsed from {args.cardlibrary}")

    sfd = bucket_rows(rows, set_prefix="SFD", set_name="Spiritforged")
    ogn = bucket_rows(rows, set_prefix="OGN", set_name="Origins")

    lines: list[str] = []
    lines.append("-- Auto-generated by scripts/build_riftbound_collation.py")
    lines.append(f"-- Source: {args.cardlibrary}")
    lines.append("")
    lines.append(emit_set_block("SFD", sfd))
    lines.append("")
    lines.append(emit_set_block("OGN", ogn))
    lines.append("")
    lines.append(emit_pack_collations().rstrip())
    lines.append("")
    lines.append(
        f"-- Counts: SFD C/U/R/E/S = {len(sfd['COMMON'])}/{len(sfd['UNCOMMON'])}/{len(sfd['RARE'])}/{len(sfd['EPIC'])}/{len(sfd['SHOWCASE'])}"
    )
    lines.append(
        f"-- Counts: OGN C/U/R/E/S = {len(ogn['COMMON'])}/{len(ogn['UNCOMMON'])}/{len(ogn['RARE'])}/{len(ogn['EPIC'])}/{len(ogn['SHOWCASE'])}"
    )
    out_text = "\n".join(lines) + "\n"

    if args.stdout:
        print(out_text)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_text, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
