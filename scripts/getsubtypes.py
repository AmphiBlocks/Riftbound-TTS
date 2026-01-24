import requests
import csv

BASE_URL = "https://api.riftcodex.com"
PAGE_SIZE = 100  # Efficient and safe
OUTPUT_FILE = "riftbound_types_subtypes_tags.tsv"  # Tab-separated
ARRAY_SEPARATOR = " || "  # For multi-value fields

def fetch_all_cards_data():
    all_data = []
    page = 1
    
    params = {"size": PAGE_SIZE, "page": page}
    response = requests.get(f"{BASE_URL}/cards", params=params)
    response.raise_for_status()
    data = response.json()
    
    total_pages = data.get("pages", 1)
    
    # Process first page
    for item in data.get("items", []):
        classification = item.get("classification", {})
        card_data = {
            "name": item.get("name", ""),
            "type": classification.get("type", ""),
            "supertype": classification.get("supertype", ""),
            "domain": ARRAY_SEPARATOR.join(classification.get("domain", [])),
            "tags": ARRAY_SEPARATOR.join(item.get("tags", []))
        }
        all_data.append(card_data)
    
    # Paginate remaining pages
    for page in range(2, total_pages + 1):
        params["page"] = page
        response = requests.get(f"{BASE_URL}/cards", params=params)
        response.raise_for_status()
        data = response.json()
        
        for item in data.get("items", []):
            classification = item.get("classification", {})
            card_data = {
                "name": item.get("name", ""),
                "type": classification.get("type", ""),
                "supertype": classification.get("supertype", ""),
                "domain": ARRAY_SEPARATOR.join(classification.get("domain", [])),
                "tags": ARRAY_SEPARATOR.join(item.get("tags", []))
            }
            all_data.append(card_data)
        print(f"Fetched page {page}/{total_pages}")
    
    return all_data

def write_to_tsv(data):
    if not data:
        print("No data to write.")
        return
    
    fieldnames = ["name", "type", "supertype", "domain", "tags"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, dialect='excel-tab')  # Tab delimiter
        writer.writeheader()
        writer.writerows(data)
    print(f"Data written to {OUTPUT_FILE} ({len(data)} cards)")
    print("Open in Excel/Google Sheets – it will automatically use tabs as columns.")

if __name__ == "__main__":
    print("Fetching all Riftbound cards with types, supertypes, domains, and tags...")
    card_data = fetch_all_cards_data()
    write_to_tsv(card_data)