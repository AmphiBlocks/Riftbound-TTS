#!/usr/bin/env python3

import argparse
import sys
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "riftbound-sheet-docs"))

from piltover_spoilers_to_sheet import SHEET_ID, api_json, read_sheet_token  # noqa: E402


TAB_NAME = "TTS Lua Script (Automatically Generated)"
DEFAULT_OUTPUT = ROOT / "scripts" / "generated_riftbound_card_catalog.lua"


def fetch_tab_lines(token):
    range_name = urllib.parse.quote(f"'{TAB_NAME}'!A:A", safe="!'")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"
    data = api_json(url, token)
    rows = data.get("values", [])
    lines = [row[0] for row in rows if row and row[0].strip()]
    return lines


def export_catalog(output_path):
    token = read_sheet_token()
    lines = fetch_tab_lines(token)
    if not lines:
        raise RuntimeError(f"No Lua lines found in sheet tab: {TAB_NAME}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "output": output_path,
        "line_count": len(lines),
        "first_line": lines[0],
        "last_line": lines[-1],
    }


def main():
    parser = argparse.ArgumentParser(description="Export generated Riftbound card catalog Lua from Sheets.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    result = export_catalog(Path(args.output))
    print(f"Wrote {result['line_count']} lines to {result['output']}")
    print(f"First line: {result['first_line']}")
    print(f"Last line: {result['last_line']}")


if __name__ == "__main__":
    main()
