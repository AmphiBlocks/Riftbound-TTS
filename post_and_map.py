
# cloudinary_upload_and_map.py
import cloudinary
import cloudinary.uploader
from pathlib import Path
import json
import time   # ← this was missing!

# ←←← PUT YOUR CLOUDINARY CREDENTIALS HERE ←←←
cloudinary.config(
    cloud_name = "daot4ukov",          # ← your cloud name
    api_key    = "762282351849164",       # ← paste here
    api_secret = "EBWS3B_TVY1opqJblavbg2-0PZk",    # ← paste here
    secure     = True
)

jpg_folder = Path("sfd3_jpg")       # ← folder with your JPGs
mapping_file = Path("cloudinary_mapping.json")
lua_snippet  = Path("cloudinary_lua_images.lua")

mapping = {}

print("Starting Cloudinary upload...\n")

for jpg_path in sorted(jpg_folder.glob("*.jpg")):
    slug = jpg_path.stem                     # e.g. "OGN-001" or "SFD-161"
    print(f"Uploading {slug}...", end="")

    try:
        result = cloudinary.uploader.upload(
            str(jpg_path),
            folder="riftbound/cards",        # nice folder structure
            public_id=slug,                  # keeps your exact card ID in URL!
            overwrite=True,
            resource_type="image"
        )
        url = result["secure_url"]           # https URL (works everywhere)
        mapping[slug] = url
        print(f" → {url}")
    except Exception as e:
        print(f" → FAILED ({e})")
    
    time.sleep(0.4)   # stay well under Cloudinary's generous free limits

# Save JSON mapping (perfect for Lua JSON.decode)
with open(mapping_file, "w", encoding="utf-8") as f:
    json.dump(mapping, f, indent=2)

# Save ready-to-paste Lua lines
lua_lines = []
for slug, url in sorted(mapping.items()):
    lua_lines.append(f'{slug},{url}')

with open(lua_snippet, "w", encoding="utf-8") as f:
    f.write("-- Cloudinary image URLs – paste into your cardData table\n\n")
    f.write("cardImages = {\n")
    f.write("\n".join(lua_lines))
    f.write("\n}\n")

print("\n" + "="*60)
print(f"Done! {len(mapping)} cards uploaded.")
print(f"→ Mapping saved to: {mapping_file}")
print(f"→ Lua snippet saved to: {lua_snippet}")
print("="*60)