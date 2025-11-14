# scrape_riftbound_to_lua.py -- FIXED VERSION
# Run: python scrape_riftbound_to_lua.py > cardData.lua

import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os

BASE_URL = "https://www.lolcards.fr"  # Added www!
CARDS_URL = f"{BASE_URL}/cards"
HEADERS = {'User-Agent': 'Riftbound-TTS-Mod-Scraper/1.0'}

def get_card_links():
    print("Fetching card list...", end="", flush=True)
    resp = requests.get(CARDS_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # FIXED REGEX: Match href="/cards/en-ogs-001-annie-fiery"
    links = soup.find_all('a', href=re.compile(r'^/cards/[^"]+'))
    full_urls = [BASE_URL + a['href'] for a in links]
    
    # Extract IDs from page text: OGS-001, OGN-017-1, etc.
    id_pattern = r'([OGS|OGN|OGP]+\-\d+(?:[a-z])?-\d+)'
    ids = re.findall(id_pattern, resp.text, re.IGNORECASE)
    ids = list(set(ids))  # Unique
    ids.sort()  # Alphabetical
    
    print(f" {len(ids)} cards found.")
    return ids, full_urls[:20]  # Return IDs + sample URLs for debug

def scrape_card(card_id):
    # Build URL from ID pattern: en-ogs-001-annie-fiery (slug unknown → use ID page if exists, fallback)
    set_code = card_id.split('-')[0].lower()
    num_id = card_id.split('-')[1]
    card_path = f"/cards/en-{set_code}-{num_id}-"  # Partial for search
    url = f"{BASE_URL}/card/{card_id}"  # Direct /card/OGS-001-1 ?
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            # Fallback: search page or construct from list
            url = f"{BASE_URL}{card_path}"  # Partial match
            resp = requests.get(url, headers=HEADERS, timeout=10)
        
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')

        # Name (from h? or text near ID)
        name_match = soup.find(['h1', 'h2', 'h3'], string=re.compile(card_id, re.I))
        name = name_match.get_text(strip=True) if name_match else card_id

        # Image (largest card img)
        img_tag = soup.find('img', src=re.compile(r'card\.png|card\.jpg'))
        image_url = BASE_URL + img_tag['src'] if img_tag and img_tag['src'].startswith('/') else (img_tag['src'] if img_tag else "")

        # Description (card-text div)
        desc_div = soup.find('div', class_='card-text') or soup.find('div', {'class': re.compile('text|desc')})
        description = desc_div.get_text(separator='\n', strip=True) if desc_div else ""

        # Stats table/rows
        stats = {}
        for row in soup.find_all(['div', 'span'], class_=re.compile('stat|cost|might|type|color')):
            text = row.get_text()
            if ':' in text:
                key, val = text.split(':', 1)
                stats[key.strip().lower()] = val.strip()

        card_type = stats.get('type', 'unknown').lower()
        color = stats.get('color', '').lower()
        set_code = card_id.split('-')[0].upper()

        # gmNotes JSON (Riftbound-tuned)
        gm_notes = {
            "type": card_type,
            "color_identity": color.replace(' ', ','),
            "power_cost": re.search(r'power[:\s]*(\d+)', ' '.join(stats.values())) or "0",
            "energy_cost": re.search(r'energy[:\s]*(\d+)', ' '.join(stats.values())) or "0",
            "might": stats.get('might', '0'),
            "rarity": 3,  # TODO: parse
            "isSignature": 'champion' in card_type or 'signature' in card_type,
            "isToken": False,
            "isCosmetic": False,
            "tags": color,
            "set": set_code
        }

        # Escape Lua
        desc_escaped = description.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
        gm_json = json.dumps(gm_notes).replace('true', 'true').replace('false', 'false')

        lua_entry = f'    ["{card_id.upper()}"] = {{\n'
        lua_entry += f'        name = "{name}",\n'
        lua_entry += f'        description = "{desc_escaped}",\n'
        lua_entry += f'        image = "",  -- TODO: Steam UGC\n'
        lua_entry += f'        gmNotes = [[{gm_json}]]\n'
        lua_entry += f'    }},\n'

        return {
            'id': card_id.upper(),
            'lua': lua_entry,
            'image_url': image_url,
            'url': url
        }
    except Exception as e:
        print(f"Error on {card_id}: {e}")
        return None

def main():
    print("=== FIXED Riftbound TTS cardData Scraper ===\n")
    card_ids, sample_urls = get_card_links()
    print("Sample URLs:", sample_urls[:5])

    print("\nScraping card details...\n")
    lua_lines = ['cardData = {\n']

    for i, card_id in enumerate(card_ids[:50]):  # Limit 50 for test
        print(f"  [{i+1}/50] {card_id}", end="")
        card = scrape_card(card_id)
        if card:
            lua_lines.append(card['lua'])
            print(" OK")
        else:
            print(" FAILED")
        time.sleep(0.5)

    lua_lines.append('}\n')
    with open('cardData.lua', 'w', encoding='utf-8') as f:
        f.write(''.join(lua_lines))

    print("\n cardData.lua generated (50 cards)!")
    print("\nRun full: Comment out [:50] in for loop")
    print("1. Upload images -> Steam UGC")
    print("2. Paste into mod")

if __name__ == '__main__':
    main()