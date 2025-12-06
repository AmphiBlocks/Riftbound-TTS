# riftmana_official_export_to_lua.py
import json
import requests

url = "https://riftmana.com/wp-content/uploads/Card-Data/riftmana-tts-export.json"
data = requests.get(url).json()

print(f"Loaded {len(data)} cards from official Riftmana export\n")

lua = "local cardData = {\n"

for card in data:
    cid = card["id"]                     # e.g. "OGS-023-1"
    name = card["name"]
    desc = card["effect"].replace('"', '\\"').replace('\n', ' ')
    image = card["image"]                 # already full URL

    # Build gmNotes exactly like you need
    gm = {
        "color_identity": ", ".join(card["colors"]).lower() if card["colors"] else "",
        "type": card["type"].lower(),
        "rarity": card["rarity"],
        "isSignature": card["type"] == "Champion",
        "signature_key": card["champion"].lower() if card["type"] == "Champion" else "",
        "isToken": card.get("token", False),
        "isCosmetic": False,
        "keyword": card.get("keywords", ""),
        "set": card["set"].replace(" ", "")
    }

    lua += f'    ["{cid}"] = {{\n'
    lua += f'        name = "{name}",\n'
    lua += f'        description = "{desc}",\n'
    lua += f'        image = "{image}",\n'
    lua += f'        gmNotes = [[{json.dumps(gm, indent=4)}]]\n'
    lua += f'    }},\n'

lua += "}\nreturn cardData"

with open("riftbound_card_library.lua", "w", encoding="utf-8") as f:
    f.write(lua)

print("Done! → riftbound_card_library.lua (perfect, up-to-date, no scraping needed)")