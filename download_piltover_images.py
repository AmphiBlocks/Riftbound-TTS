# download_piltover_images.py
import requests
import time
import os
from pathlib import Path

# ------------------------------------------------------------------
# PASTE YOUR LIST OF CARD IDs HERE (one per line, no quotes/comma)
# ------------------------------------------------------------------
card_ids = """
SFD-141a
SFD-143a
SFD-148a
SFD-149a
""".strip().splitlines()

# ------------------------------------------------------------------
# Optional: or load from a text file (uncomment if you prefer)
# with open("card_ids.txt", "r") as f:
#     card_ids = [line.strip() for line in f if line.strip()]
# ------------------------------------------------------------------

# Create output folder
output_dir = Path("sfd3_webp")
output_dir.mkdir(exist_ok=True)

print(f"Downloading {len(card_ids)} cards → {output_dir.resolve()}")

for card_id in card_ids:
    card_id = card_id.strip()
    if not card_id:
        continue

    # Build filename (e.g. OGN-001.webp or OGS-023-1.webp)
    filename = f"{card_id}.webp"
    filepath = output_dir / filename

    # Skip if already downloaded already
    if filepath.exists():
        print(f"Skip (exists): {filename}")
        continue

    url = f"https://cdn.piltoverarchive.com/cards/{card_id}.webp"

    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"Downloaded: {filename}")
        else:
            print(f"Not found (404): {card_id}")
    except Exception as e:
        print(f"Error ({card_id}): {e}")

    time.sleep(0.5)  # Be nice to the CDN

print("\nAll done!")