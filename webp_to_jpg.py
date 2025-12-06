# webp_to_jpg.py
from PIL import Image
import os
from pathlib import Path

# Folder with your .webp files from the previous step
webp_folder = Path("sfd3_webp")
jpg_folder   = Path("sfd3_jpg")
jpg_folder.mkdir(exist_ok=True)

print(f"Converting {len(list(webp_folder.glob('*.webp')))} cards → {jpg_folder}\n")

for webp_path in webp_folder.glob("*.webp"):
    jpg_path = jpg_folder / (webp_path.stem + ".jpg")
    
    if jpg_path.exists():
        print(f"Skip (exists): {jpg_path.name}")
        continue
        
    try:
        img = Image.open(webp_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=95, optimize=True)
        print(f"Converted: {webp_path.name} → {jpg_path.name}")
    except Exception as e:
        print(f"Failed {webp_path.name}: {e}")

print("\nAll done! Ready for Imgur/Catbox upload.")