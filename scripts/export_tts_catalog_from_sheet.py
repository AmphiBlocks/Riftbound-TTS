#!/usr/bin/env python3

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "riftbound-sheet-docs"))

from piltover_spoilers_to_sheet import SHEET_ID, api_json, read_sheet_token  # noqa: E402


TAB_NAME = "TTS Lua Script (Automatically Generated)"
DEFAULT_LUA_OUTPUT = ROOT / "scripts" / "generated_riftbound_card_catalog.lua"
DEFAULT_JSON_OUTPUT = ROOT / "scripts" / "generated_riftbound_card_catalog.json"
DEFAULT_INDEX_OUTPUT = ROOT / "scripts" / "generated_riftbound_card_catalog_index.json"
DEFAULT_SHARD_DIR = ROOT / "scripts" / "generated_riftbound_card_catalog_shards"

CARD_ENTRY_RE = re.compile(
    r'^\["(?P<key>[^"]+)"\] = \{name="(?P<name>(?:\\.|[^"])*)", description="(?P<description>(?:\\.|[^"])*)"'
    r'(?:, image = "(?P<image>(?:\\.|[^"])*)")?, gmNotes = \[\[(?P<gm>.*)\]\]\},?$'
)
MAP_ENTRY_RE = re.compile(r'^\["(?P<key>[^"]+)"\] = "(?P<value>[^"]+)",?$')

SHARD_NAMES = ("fury", "mind", "body", "chaos", "calm", "order", "colorless", "multicolor")


def sanitize_lua_line(line):
    return (
        line.replace("•", "*")
        .replace("\u00a0", " ")
        .replace("\t", " ")
    )


def fetch_tab_lines(token):
    range_name = urllib.parse.quote(f"'{TAB_NAME}'!A:A", safe="!'")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"
    data = api_json(url, token)
    rows = data.get("values", [])
    lines = [sanitize_lua_line(row[0]) for row in rows if row and row[0].strip()]
    return lines


def lua_unescape(text):
    return json.loads(f'"{text}"')


def parse_lua_catalog(lines):
    card_data = {}
    tts_to_id_map = {}
    section = None

    for line in lines:
        if line == "local cardData = {":
            section = "cardData"
            continue
        if line == "local tts_to_id_map = {":
            section = "tts_to_id_map"
            continue
        if line == "}":
            section = None
            continue
        if section == "cardData":
            match = CARD_ENTRY_RE.match(line)
            if not match:
                continue
            image = match.group("image")
            entry = {
                "name": lua_unescape(match.group("name")),
                "description": lua_unescape(match.group("description")),
                "gmNotes": json.loads(match.group("gm")),
            }
            if image is not None:
                entry["image"] = lua_unescape(image)
            card_data[match.group("key")] = entry
            continue
        if section == "tts_to_id_map":
            match = MAP_ENTRY_RE.match(line)
            if not match:
                continue
            tts_to_id_map[match.group("key")] = match.group("value")

    if not card_data:
        raise RuntimeError("Failed to parse cardData from generated Lua tab")
    return {
        "cardData": card_data,
        "tts_to_id_map": tts_to_id_map,
    }


def classify_shard(entry):
    gm = entry.get("gmNotes") or {}
    color_identity = str(gm.get("color_identity") or "")
    colors = [part.strip().lower() for part in color_identity.split(",") if part.strip()]
    colors = [part for part in colors if part in {"fury", "mind", "body", "chaos", "calm", "order"}]

    if gm.get("type") == "battlefield" or gm.get("isSignature") is True or gm.get("isToken") is True:
        return "multicolor"
    if not colors:
        return "colorless"
    if len(colors) > 1:
        return "multicolor"
    return colors[0]


def fetch_catalog_lines():
    token = read_sheet_token()
    lines = fetch_tab_lines(token)
    if not lines:
        raise RuntimeError(f"No Lua lines found in sheet tab: {TAB_NAME}")
    return lines


def export_lua(output_path, lines):
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "format": "lua",
        "output": output_path,
        "line_count": len(lines),
        "first_line": lines[0],
        "last_line": lines[-1],
    }


def export_json(output_path, lines):
    payload = parse_lua_catalog(lines)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "format": "json",
        "output": output_path,
        "card_count": len(payload["cardData"]),
        "tts_map_count": len(payload["tts_to_id_map"]),
    }


def export_shards(index_output_path, shard_dir, lines):
    payload = parse_lua_catalog(lines)
    shard_dir.mkdir(parents=True, exist_ok=True)

    shards = {name: {} for name in SHARD_NAMES}
    slug_to_shard = {}
    name_index = []

    for slug, entry in payload["cardData"].items():
        shard = classify_shard(entry)
        shards[shard][slug] = entry
        slug_to_shard[slug] = shard
        name_index.append({"slug": slug, "name": entry.get("name", "")})

    for shard_name, cards in shards.items():
        shard_path = shard_dir / f"{shard_name}.json"
        shard_path.write_text(
            json.dumps({"cardData": cards}, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    index_output_path.write_text(
        json.dumps(
            {
                "slugToShard": slug_to_shard,
                "tts_to_id_map": payload["tts_to_id_map"],
                "nameIndex": name_index,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n",
        encoding="utf-8",
    )

    return {
        "format": "shards",
        "index_output": index_output_path,
        "shard_dir": shard_dir,
        "shard_counts": {name: len(cards) for name, cards in shards.items()},
    }


def main():
    parser = argparse.ArgumentParser(description="Export generated Riftbound card catalog from Sheets.")
    parser.add_argument(
        "--output",
        help="Output path. Defaults depend on format.",
    )
    parser.add_argument(
        "--format",
        choices=("lua", "json", "shards", "both"),
        default="lua",
        help="Output format.",
    )
    args = parser.parse_args()

    lines = fetch_catalog_lines()
    results = []

    if args.format == "lua":
        output = Path(args.output) if args.output else DEFAULT_LUA_OUTPUT
        results.append(export_lua(output, lines))
    elif args.format == "json":
        output = Path(args.output) if args.output else DEFAULT_JSON_OUTPUT
        results.append(export_json(output, lines))
    elif args.format == "shards":
        if args.output:
            raise SystemExit("--output is only valid with --format lua or --format json")
        results.append(export_shards(DEFAULT_INDEX_OUTPUT, DEFAULT_SHARD_DIR, lines))
    else:
        if args.output:
            raise SystemExit("--output is only valid with --format lua or --format json")
        results.append(export_lua(DEFAULT_LUA_OUTPUT, lines))
        results.append(export_json(DEFAULT_JSON_OUTPUT, lines))
        results.append(export_shards(DEFAULT_INDEX_OUTPUT, DEFAULT_SHARD_DIR, lines))

    for result in results:
        if result["format"] == "lua":
            print(f"Wrote {result['line_count']} lines to {result['output']}")
            print(f"First line: {result['first_line']}")
            print(f"Last line: {result['last_line']}")
        elif result["format"] == "json":
            print(
                f"Wrote {result['card_count']} cards and {result['tts_map_count']} tts-map entries "
                f"to {result['output']}"
            )
        else:
            shard_summary = ", ".join(f"{name}={count}" for name, count in sorted(result["shard_counts"].items()))
            print(f"Wrote shard index to {result['index_output']}")
            print(f"Wrote shard files to {result['shard_dir']}: {shard_summary}")


if __name__ == "__main__":
    main()
