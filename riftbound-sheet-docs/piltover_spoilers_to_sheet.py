#!/usr/bin/env python3

import argparse
import itertools
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLIENT_PATH = ROOT / "google-oauth-client.json"
TOKEN_PATH = ROOT / "google-oauth-token.json"
SHEET_ID = "1sBn6N3f3I7AI3_98lK8-7pJOuyycji_kw4wi178mPcM"
CARD_DATA_SHEET = "Card Data"
DEFAULT_JPG_DIR = Path("/Users/josh/Dev/Riftbound-TTS/riftbound_jpg")
FALLBACK_CARD_IDS = {
    "UNL": {
        "Square Up": "UNL-017",
        "Katarina, Reckless": "UNL-023",
        "Allay, Eager Admirer": "UNL-041",
        "Downstage Dramatics": "UNL-061",
        "Targonian Visionary": "UNL-098",
        "Mageseeker Investigator": "UNL-163",
    }
}


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def api_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_request(url, token, method="GET", payload=None):
    body = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_google_client():
    payload = json.loads(CLIENT_PATH.read_text())
    return payload.get("web", payload.get("installed", {}))


def refresh_access_token(token_payload):
    client = load_google_client()
    body = urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": token_payload["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        client["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        refreshed = json.loads(resp.read().decode("utf-8"))
    token_payload["access_token"] = refreshed["access_token"]
    token_payload["expires_in"] = refreshed.get("expires_in", token_payload.get("expires_in"))
    token_payload["token_type"] = refreshed.get("token_type", token_payload.get("token_type"))
    TOKEN_PATH.write_text(json.dumps(token_payload, indent=2) + "\n")
    return token_payload["access_token"]


def fetch_piltover_html(set_code, page=1):
    params = {"sets": set_code}
    if page > 1:
        params["page"] = str(page)
    url = "https://piltoverarchive.com/cards?" + urllib.parse.urlencode(params)
    return http_get(url, headers={"User-Agent": "Mozilla/5.0"})


def decode_piltover_html(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    decoded = []
    for chunk in chunks:
        try:
            decoded.append(json.loads(f'"{chunk}"'))
        except json.JSONDecodeError:
            decoded.append(chunk.encode("utf-8").decode("unicode_escape"))
    return "\n".join(decoded)


def fetch_piltover_text(set_code):
    return decode_piltover_html(fetch_piltover_html(set_code))


def fetch_piltover_new_text():
    url = "https://piltoverarchive.com/cards?new=true"
    return decode_piltover_html(http_get(url, headers={"User-Agent": "Mozilla/5.0"}))


def fetch_riftstorm_html(path):
    url = urllib.parse.urljoin("https://riftstorm.gg/", path.lstrip("/"))
    return http_get(url, headers={"User-Agent": "Mozilla/5.0"})


def group_entries(decoded_text):
    entries = []
    current_key = None
    current_lines = []
    for line in decoded_text.splitlines():
        match = re.match(r"^([0-9a-z]+):(.*)$", line)
        if match:
            if current_key is not None:
                entries.append((current_key, "\n".join(current_lines)))
            current_key = match.group(1)
            current_lines = [match.group(2)]
        elif current_key is not None:
            current_lines.append(line)
    if current_key is not None:
        entries.append((current_key, "\n".join(current_lines)))
    return entries


def ordered_id_name_map(decoded_text):
    ids = re.findall(
        r'"children":"Card Number:"\}\],\["\$","span",null,\{"children":"([^"]+)"',
        decoded_text,
    )
    raw_names = [
        m.group(1)
        for m in re.finditer(
            r'https://piltoverarchive\.b-cdn\.net/(?:cards|temporary)/[^\\"]+","alt":"([^"]+)"',
            decoded_text,
        )
    ]
    compressed = []
    for name, group in itertools.groupby(raw_names):
        run = list(group)
        compressed.extend([name] * (len(run) // 2))
    return dict(zip(ids, compressed))


def ordered_id_image_map(decoded_text):
    ids = re.findall(
        r'"children":"Card Number:"\}\],\["\$","span",null,\{"children":"([^"]+)"',
        decoded_text,
    )
    raw_urls = [
        m.group(1)
        for m in re.finditer(
            r'(https://piltoverarchive\.b-cdn\.net/(?:cards|temporary)/[^\\"]+)","alt":"([^"]+)"',
            decoded_text,
        )
    ]
    compressed = []
    for url, group in itertools.groupby(raw_urls):
        run = list(group)
        compressed.extend([url] * (len(run) // 2))
    return dict(zip(ids, compressed))


def ref_keys(payload):
    return list(dict.fromkeys(re.findall(r'"\$L([0-9a-z]+)"', payload)))


def load_jsonish(payload):
    payload = payload.replace("childre\nn", "children")
    decoder = json.JSONDecoder()
    candidates = [
        payload,
        payload.replace("\n", ""),
        payload.replace("\n", "\\n"),
    ]
    last_error = None
    for candidate in candidates:
        try:
            obj, _ = decoder.raw_decode(candidate)
            return obj
        except json.JSONDecodeError as exc:
            last_error = exc
    raise last_error or ValueError("Unable to decode payload")


def extract_text(node):
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        if len(node) >= 4 and node[0] == "$" and isinstance(node[3], dict) and "alt" in node[3]:
            return node[3]["alt"]
        return "".join(extract_text(child) for child in node)
    if isinstance(node, dict):
        return extract_text(node.get("children", ""))
    if node in (None, False, True):
        return ""
    return str(node)


def clean_effect(text):
    text = normalize_card_text(text)
    text = text.replace("Description", "", 1).strip()
    text = re.sub(r"\$div|\$p|\$iitalic-\d+", "", text)
    text = re.sub(r"\n +", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()
    if text in {".", "-"}:
        return "-"
    return text


def extract_effect(entries, info_index):
    candidate_offsets = [-1, -2, -3, 1, 2, 3]
    for offset in candidate_offsets:
        j = info_index + offset
        if not (0 <= j < len(entries)):
            continue
        payload = entries[j][1]
        if "whitespace-pre-line" not in payload:
            continue
        try:
            return clean_effect(extract_text(load_jsonish(payload)))
        except Exception:
            continue
    return ""


def extract_nearby_payload(entries, info_index, required_fragments):
    candidate_offsets = [-1, -2, -3, 1, 2, 3, 4, 5]
    for offset in candidate_offsets:
        j = info_index + offset
        if not (0 <= j < len(entries)):
            continue
        payload = entries[j][1]
        if all(fragment in payload for fragment in required_fragments):
            return payload
    return ""


def extract_nearby_equip_might(entries, info_index):
    candidate_offsets = [-1, -2, -3, 1, 2, 3, 4, 5]
    for offset in candidate_offsets:
        j = info_index + offset
        if not (0 <= j < len(entries)):
            continue
        payload = entries[j][1]
        equip_might = parse_equip_might(payload)
        if equip_might:
            return equip_might
    return ""


def parse_stats(payload):
    matches = re.findall(
        r'"children":"(Energy|Power|Might)"\}\],\["\$","p",null,\{"className":"text-4xl font-bold","children":(-?\d+)\}\]',
        payload,
    )
    stats = {label: value for label, value in matches}
    return {
        "cost": stats.get("Energy", ""),
        "power": stats.get("Power", ""),
        "might": stats.get("Might", ""),
    }


def parse_flavor(payload):
    if not payload:
        return ""
    try:
        text = extract_text(load_jsonish(payload))
    except Exception:
        return ""
    text = text.replace("$div", "")
    text = text.replace("$p", "")
    text = text.replace("Flavor Text", "", 1).strip()
    return normalize_card_text(text)


def repair_mojibake(text):
    if not text:
        return text
    suspicious_markers = ("Ã", "Â", "â", "å", "é", "è", "æ", "ç", "ï", "ð", "ñ", "ò", "ó", "ô", "õ", "ö", "", "", "", "")
    if not any(marker in text for marker in suspicious_markers):
        return text.strip()
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text.strip()
    return repaired.strip()


def normalize_card_text(text):
    text = repair_mojibake(text or "")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("•", "*")
    text = text.replace("\u00a0", " ")
    text = text.replace("\t", " ")
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_artist(text):
    text = repair_mojibake(text or "")
    text = text.replace("$span", "")
    text = text.replace("$div", "")
    text = text.replace("$p", "")
    text = text.replace("／", "/")
    text = re.sub(r"\s*/\s*", " / ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" -")


def parse_equip_might(payload):
    if not payload:
        return ""
    match = re.search(
        r'"children":"Might".*?"children":\["\+",(-?\d+)',
        payload,
        flags=re.S,
    )
    return match.group(1) if match else ""


def parse_artist(payload):
    if not payload:
        return ""
    match = re.search(
        r'"children":"Artist:"\}\],\["\$","span",null,\{"children":"([^"]*)"\}\]',
        payload,
    )
    if match:
        return normalize_artist(match.group(1))
    try:
        text = extract_text(load_jsonish(payload))
    except Exception:
        return ""
    match = re.search(r"Artist:\s*(.*?)(?:\s*Set:|\s*Card Number:|$)", text, flags=re.S)
    return normalize_artist(match.group(1)) if match else ""


def parse_domains(payload):
    domains = re.findall(r'"children":\["\$L[0-9a-z]+","([^"]+)"\]', payload)
    domains = [domain for domain in domains if not domain.startswith("$L")]
    if not domains:
        domains = re.findall(
            r'https://cdn\.piltoverarchive\.com/colors/[^"]+","alt":"([^"]+)"',
            payload,
        )
    return "|".join(dict.fromkeys(domains))


def parse_domains_with_refs(payload, entry_map):
    labels = []
    for ref_key, label in re.findall(r'"children":\["\$L([0-9a-z]+)","([^"]+)"\]', payload):
        ref_payload = entry_map.get(ref_key, "")
        if "cdn.piltoverarchive.com/colors/" in ref_payload:
            labels.append(label)
    if labels:
        return "|".join(dict.fromkeys(labels))
    ref_domains = []
    for key in ref_keys(payload):
        ref_payload = entry_map.get(key, "")
        match = re.search(
            r'https://cdn\.piltoverarchive\.com/colors/[^"]+","alt":"([^"]+)"',
            ref_payload,
        )
        if match:
            ref_domains.append(match.group(1))
    if ref_domains:
        return "|".join(dict.fromkeys(ref_domains))
    return parse_domains(payload)


def parse_rarity(payload):
    match = re.search(
        r'https://cdn\.piltoverarchive\.com/rarities/[^"]+","alt":"([^"]+)"',
        payload,
    )
    if match:
        return match.group(1)
    text_badges = re.findall(r'"children":\["\$L[0-9a-z]+","([^"]+)"\]', payload)
    for badge in text_badges:
        if badge in {"Common", "Uncommon", "Rare", "Epic", "Showcase"}:
            return badge
    return "Unknown"


def parse_image_url(payload):
    match = re.search(
        r'(https://(?:piltoverarchive\.b-cdn\.net|cdn\.piltoverarchive\.com)/(?:cards|temporary)/[^\\"]+)',
        payload,
    )
    return match.group(1) if match else ""


def parse_image_source(image_url):
    path = urllib.parse.urlparse(image_url).path
    if "/cards/" in path:
        return "official"
    if "/temporary/" in path:
        return "temporary"
    return ""


def normalize_card_id(card_id):
    return re.sub(r"\*$", "s", card_id)


def normalize_riftstorm_card_id(public_code):
    return normalize_card_id(public_code.split("/", 1)[0].strip().upper())


def is_supported_card_id(set_code, card_id):
    patterns = {
        "UNL": (
            rf"{set_code}-\d{{3}}(?:a|s)?",
            rf"{set_code}-R\d{{2}}a",
            rf"{set_code}-T\d{{2}}",
        ),
        "RAD": (
            rf"{set_code}-\d{{3}}(?:a|s)?",
            rf"{set_code}-R\d{{2}}a",
            rf"{set_code}-T\d{{2}}",
        ),
        "VEN": (
            rf"{set_code}-\d{{3}}(?:a|s)?",
            rf"{set_code}-R\d{{2}}a",
            rf"{set_code}-T\d{{2}}",
        ),
    }
    return any(re.fullmatch(pattern, card_id) for pattern in patterns.get(set_code, ()))


def riftstorm_cards_payload(html):
    pattern = re.compile(
        r'\{\\\"id\\\":\\\"(?P<id>[^\\\"]+)\\\",'
        r'\\\"name\\\":\\\"(?P<name>(?:[^\\\"\\\\]|\\\\.)*)\\\",'
        r'\\\"publicCode\\\":\\\"(?P<public_code>(?:[^\\\"\\\\]|\\\\.)*)\\\",'
        r'\\\"collectorNumber\\\":(?P<collector_number>\d+),'
        r'\\\"imageUrl\\\":\\\"(?P<image_url>(?:[^\\\"\\\\]|\\\\.)*)\\\",'
        r'\\\"domain\\\":\\\"(?P<domain>(?:[^\\\"\\\\]|\\\\.)*)\\\",'
        r'\\\"alt\\\":\\\"(?P<alt>.*?)\\\",'
        r'\\\"isChampion\\\":(?P<is_champion>true|false),'
        r'\\\"printLabel\\\":(?P<print_label>null|\\\"(?:[^\\\"\\\\]|\\\\.)*\\\")',
        flags=re.S,
    )
    rows = []
    for match in pattern.finditer(html):
        row = match.groupdict()
        for key in ("id", "name", "public_code", "image_url", "domain", "alt"):
            row[key] = json.loads(f'"{row[key]}"')
        print_label = row["print_label"]
        row["print_label"] = (
            None if print_label == "null" else json.loads(f'"{print_label[2:-2]}"')
        )
        row["collector_number"] = int(row["collector_number"])
        row["is_champion"] = row["is_champion"] == "true"
        rows.append(row)
    return rows


def parse_riftstorm_tts_type(raw_type, is_champion):
    if is_champion:
        return "Champion"
    return {
        "Battlefield": "Battlefield",
        "Gear": "Gear",
        "Legend": "Legend",
        "Rune": "Rune",
        "Spell": "Spell",
        "Unit": "Unit",
        "Unit-Gear": "Unit",
    }.get(raw_type, "")


def extract_riftstorm_effect(alt_text, card_name):
    match = re.match(
        rf"^Riftbound ([A-Za-z-]+): {re.escape(card_name)}\. ?(.*)$",
        alt_text,
        flags=re.S,
    )
    if not match:
        return "", ""
    return match.group(1), clean_effect(match.group(2))


def extract_riftstorm_cards(set_code):
    if set_code != "VEN":
        return []
    rows = []
    for card in riftstorm_cards_payload(fetch_riftstorm_html("/vendetta")):
        card_id = normalize_riftstorm_card_id(card.get("public_code", ""))
        if not card_id or not is_supported_card_id(set_code, card_id):
            continue
        card_name = card["name"].strip()
        raw_type, effect = extract_riftstorm_effect(card["alt"], card_name)
        rows.append(
            {
                "card-id": card_id,
                "card_name": card_name,
                "effect": effect,
                "set": set_code_to_set_name(set_code),
                "image_url": card["image_url"].strip(),
                "tts-type": parse_riftstorm_tts_type(raw_type, card["is_champion"]),
                "rarity": "Unknown",
                "domain": card["domain"].strip(),
                "might": "",
                "cost": "",
                "power": "",
                "equip_might": "",
                "flavor": "",
                "artist": "",
                "image_source": "official",
            }
        )
    return rows


def merge_card_rows(primary, secondary):
    merged = dict(primary)
    for key, value in secondary.items():
        if key == "card-id":
            continue
        if value in ("", None):
            continue
        existing = merged.get(key)
        if existing in ("", None):
            merged[key] = value
            continue
        # Keep concrete upstream values when the fallback only has placeholders.
        if key == "rarity" and value == "Unknown" and existing != "Unknown":
            continue
        merged[key] = value
    return merged


def parse_tts_type(payload):
    badge_match = re.search(
        r'https://cdn\.piltoverarchive\.com/types/[^"]+","alt":"([^"]+)"',
        payload,
    )
    raw_type = badge_match.group(1) if badge_match else ""
    keyed_type_match = re.search(
        r'"children":\[\["\$","div","(Spell|Unit|Gear|Battlefield|Legend|Rune)"',
        payload,
    )
    keyed_type = keyed_type_match.group(1) if keyed_type_match else ""
    if "Champion Unit" in payload or "Champion Gear" in payload or "Champion Spell" in payload:
        return "Champion"
    if "Basic Rune" in payload:
        return "Rune"
    if raw_type in {"Legend", "Unit", "Spell", "Gear", "Rune", "Battlefield"}:
        return raw_type
    if keyed_type in {"Legend", "Unit", "Spell", "Gear", "Rune", "Battlefield"}:
        return keyed_type
    text_fallbacks = [
        ("Token Card", "Token"),
        ("Unit Gear", "Unit"),
        ("Token Unit", "Unit"),
        ("Token Rune", "Rune"),
        ("Signature Spell", "Spell"),
        ("Battlefield", "Battlefield"),
        ("Legend", "Legend"),
        ("Spell", "Spell"),
        ("Unit", "Unit"),
        ("Gear", "Gear"),
        ("Rune", "Rune"),
    ]
    for label, normalized in text_fallbacks:
        if f'],"{label}"]' in payload or f'"children":"{label}"' in payload:
            return normalized
    return raw_type


def parse_effect_payload(payload):
    if not payload:
        return ""
    try:
        return clean_effect(extract_text(load_jsonish(payload)))
    except Exception:
        return ""


def primary_payload_segment(payload, entry_map):
    if payload.startswith('["$","div",null,{"className":"space-y-6"'):
        start = payload.find('["$","$L76"')
        if start != -1:
            payload = payload[start:]
    keys = ref_keys(payload)
    info_idx = None
    for idx, key in enumerate(keys):
        ref_payload = entry_map.get(key, "")
        if '"children":"Card Information"' in ref_payload:
            info_idx = idx
            break
    if info_idx is None:
        return payload
    for key in keys[info_idx + 1:]:
        ref_payload = entry_map.get(key, "")
        if 'text-xl md:text-2xl pr-8' in ref_payload:
            marker = f'"$L{key}"'
            pos = payload.find(marker)
            if pos != -1:
                return payload[:pos]
    return payload


def enrich_row(entries, entry_map, payload, payload_index):
    refs = [entry_map[key] for key in ref_keys(payload) if key in entry_map]
    info_index = None
    badge_payload = primary_payload_segment(payload, entry_map)
    tts_type = parse_tts_type(badge_payload)
    stats_payload = next((p for p in refs if '"children":"Energy"' in p and '"children":"Might"' in p), "")
    effect_payload = next((p for p in refs if '"children":"Description"' in p), "")
    flavor_payload = next((p for p in refs if '"children":"Flavor Text"' in p), "")
    info_payload = next((p for p in refs if '"children":"Card Information"' in p), "")
    if info_payload:
        for idx, (_, entry_payload) in enumerate(entries):
            if entry_payload == info_payload:
                info_index = idx
                break
    stats = parse_stats(stats_payload) if stats_payload else {"cost": "", "power": "", "might": ""}
    might = stats["might"]
    if might == "0" and tts_type not in {"Unit", "Champion"}:
        might = ""
    power = stats["power"]
    if power == "0":
        power = ""
    equip_might = ""
    for ref_payload in refs:
        equip_might = parse_equip_might(ref_payload)
        if equip_might:
            break
    if not equip_might:
        equip_might = extract_nearby_equip_might(entries, info_index if info_index is not None else payload_index)
    effect = parse_effect_payload(effect_payload)
    if not effect:
        effect = extract_effect(entries, info_index if info_index is not None else payload_index)
    return {
        "effect": effect,
        "info_payload": info_payload,
        "rarity": parse_rarity(badge_payload),
        "tts_type": tts_type,
        "domain": parse_domains_with_refs(badge_payload, entry_map),
        "cost": stats["cost"],
        "power": power,
        "might": might,
        "equip_might": equip_might,
        "flavor": parse_flavor(flavor_payload),
        "artist": parse_artist(info_payload),
    }


def page_count(decoded_text):
    matches = re.findall(r'"currentPage":(\d+),"totalPages":(\d+)', decoded_text)
    if not matches:
        return 1
    return max(int(total) for _, total in matches)


def extract_cards_from_text(decoded_text, set_code):
    entries = group_entries(decoded_text)
    entry_map = {key: payload for key, payload in entries}
    set_name = set_code_to_set_name(set_code)
    fallback_ids = FALLBACK_CARD_IDS.get(set_code, {})
    card_payloads = [
        (idx, payload)
        for idx, (_, payload) in enumerate(entries)
        if 'text-xl md:text-2xl pr-8' in payload or 'pr-8 text-xl md:text-2xl' in payload
    ]

    rows = []
    for idx, payload in card_payloads:
        row = enrich_row(entries, entry_map, payload, idx)
        info_payload = row["info_payload"]
        name_match = re.search(
            r'"className":"(?:text-xl md:text-2xl pr-8|pr-8 text-xl md:text-2xl)","children":"([^"]+)"',
            payload,
        )
        card_name = name_match.group(1) if name_match else ""
        fallback_card_id = fallback_ids.get(card_name, "")
        if info_payload and f'"children":"{set_name}"' not in info_payload and not fallback_card_id:
            continue
        match = re.search(
            r'"children":"Card Number:"\}\],\["\$","span",null,\{"children":"([^"]+)"',
            info_payload or "",
        )
        if match:
            card_id = normalize_card_id(re.sub(r"\s+", "", match.group(1)))
        elif fallback_card_id:
            card_id = fallback_card_id
        else:
            continue
        if not is_supported_card_id(set_code, card_id):
            continue
        image_url = parse_image_url(primary_payload_segment(payload, entry_map))
        if not image_url and fallback_card_id:
            image_url = f"https://cdn.piltoverarchive.com/cards/{card_id}.webp"
        rows.append(
            {
                "card-id": card_id,
                "card_name": card_name,
                "effect": row["effect"],
                "set": set_name,
                "image_url": image_url,
                "tts-type": row["tts_type"],
                "rarity": row["rarity"],
                "domain": row["domain"],
                "might": row["might"],
                "cost": row["cost"],
                "power": row["power"],
                "equip_might": row["equip_might"],
                "flavor": row["flavor"],
                "artist": row["artist"],
                "image_source": parse_image_source(image_url),
            }
        )
    return rows


def extract_cards(set_code):
    first_decoded = decode_piltover_html(fetch_piltover_html(set_code, page=1))
    rows = extract_cards_from_text(first_decoded, set_code)
    total_pages = page_count(first_decoded)
    for page in range(2, total_pages + 1):
        decoded_text = decode_piltover_html(fetch_piltover_html(set_code, page=page))
        rows.extend(extract_cards_from_text(decoded_text, set_code))
    rows.extend(extract_cards_from_text(fetch_piltover_new_text(), set_code))
    rows.extend(extract_riftstorm_cards(set_code))
    deduped = {}
    for row in rows:
        existing = deduped.get(row["card-id"])
        deduped[row["card-id"]] = row if existing is None else merge_card_rows(existing, row)
    return [deduped[key] for key in sorted(deduped)]


def set_code_to_set_name(set_code):
    mapping = {
        "UNL": "Unleashed",
        "VEN": "Vendetta",
        "RAD": "Radiance",
    }
    return mapping.get(set_code, set_code)


def read_sheet_token():
    token_payload = json.loads(TOKEN_PATH.read_text())
    if token_payload.get("refresh_token"):
        return refresh_access_token(token_payload)
    return token_payload["access_token"]


def current_sheet_rows(token):
    range_name = urllib.parse.quote(f"'{CARD_DATA_SHEET}'!A:Y", safe="!'")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"
    data = api_json(url, token)
    values = data.get("values", [])
    row_map = {}
    for row_num, row in enumerate(values[1:], start=2):
        if len(row) >= 2 and row[1]:
            row_map[row[1]] = row_num
    return row_map


def current_sheet_values(token):
    range_name = urllib.parse.quote(f"'{CARD_DATA_SHEET}'!A:Y", safe="!'")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"
    data = api_json(url, token)
    return data.get("values", [])


def read_sheet_range(range_a1, token):
    range_name = urllib.parse.quote(range_a1, safe="!'")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"
    data = api_json(url, token)
    return data.get("values", [])


def write_sheet_range(range_a1, values, token, value_input_option="USER_ENTERED"):
    payload = {
        "valueInputOption": value_input_option,
        "data": [
            {
                "range": range_a1,
                "majorDimension": "ROWS",
                "values": values,
            }
        ],
    }
    batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
    return api_request(batch_url, token, method="POST", payload=payload)


def ensure_image_tracking_headers(token):
    values = current_sheet_values(token)
    headers = values[0] if values else []
    updates = []
    if len(headers) < 24 or headers[23] != "image-source":
        updates.append(
            {
                "range": f"'{CARD_DATA_SHEET}'!X1",
                "majorDimension": "ROWS",
                "values": [["image-source"]],
            }
        )
    if len(headers) < 25 or headers[24] != "image-url":
        updates.append(
            {
                "range": f"'{CARD_DATA_SHEET}'!Y1",
                "majorDimension": "ROWS",
                "values": [["image-url"]],
            }
        )
    if updates:
        batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
        api_request(
            batch_url,
            token,
            method="POST",
            payload={"valueInputOption": "RAW", "data": updates},
        )


def card_data_sheet_id(token):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}?fields=sheets.properties"
    data = api_json(url, token)
    for sheet in data.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == CARD_DATA_SHEET:
            return props["sheetId"]
    raise RuntimeError(f"Sheet not found: {CARD_DATA_SHEET}")


def normalize_existing_unl_block(set_code, token):
    set_name = set_code_to_set_name(set_code)
    values = current_sheet_values(token)
    updates = []
    touched_rows = []
    for row_num, row in enumerate(values[1:], start=2):
        card_id = row[1] if len(row) > 1 else ""
        trimmed = card_id.strip()
        if not trimmed.startswith(f"{set_code}-"):
            continue
        if card_id != trimmed:
            updates.append(
                {
                    "range": f"'{CARD_DATA_SHEET}'!B{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[trimmed]],
                }
            )
        current_set = row[20] if len(row) > 20 else ""
        if current_set != set_name:
            updates.append(
                {
                    "range": f"'{CARD_DATA_SHEET}'!U{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[set_name]],
                }
            )
        if card_id != trimmed or current_set != set_name:
            touched_rows.append(row_num)
    if updates:
        batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
        api_request(
            batch_url,
            token,
            method="POST",
            payload={"valueInputOption": "RAW", "data": updates},
        )
    return {"normalized_rows": touched_rows}


def sort_set_block(set_code, token):
    set_name = set_code_to_set_name(set_code)
    normalized = normalize_existing_unl_block(set_code, token)
    values = current_sheet_values(token)
    if not values:
        return {"sorted": False, "reason": "empty sheet"}

    matching_rows = []
    for row_num, row in enumerate(values[1:], start=2):
        card_id = row[1].strip() if len(row) > 1 else ""
        if (len(row) > 20 and row[20] == set_name) or card_id.startswith(f"{set_code}-"):
            matching_rows.append(row_num)
    if not matching_rows:
        return {"sorted": False, "reason": f"no rows found for {set_name}"}

    start_row = min(matching_rows)
    end_row = max(matching_rows)
    payload = {
        "requests": [
            {
                "sortRange": {
                    "range": {
                        "sheetId": card_data_sheet_id(token),
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 24,
                    },
                    "sortSpecs": [
                        {
                            "dimensionIndex": 20,
                            "sortOrder": "DESCENDING",
                        },
                        {
                            "dimensionIndex": 1,
                            "sortOrder": "ASCENDING",
                        }
                    ],
                }
            }
        ]
    }
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}:batchUpdate"
    api_request(url, token, method="POST", payload=payload)
    return {
        "sorted": True,
        "set": set_name,
        "start_row": start_row,
        "end_row": end_row,
        "sort_column": "U,B",
        "normalized_rows": normalized["normalized_rows"],
    }


def inspect_set_block(set_code, token):
    set_name = set_code_to_set_name(set_code)
    values = current_sheet_values(token)
    matching_rows = []
    for row_num, row in enumerate(values[1:], start=2):
        if len(row) > 20 and row[20] == set_name:
            matching_rows.append(row_num)
    if not matching_rows:
        return {"rows": [], "set": set_name}
    start_row = min(matching_rows)
    end_row = max(matching_rows)
    rows = []
    for row_num in range(start_row, end_row + 1):
        row = values[row_num - 1] if row_num - 1 < len(values) else []
        rows.append(
            {
                "row": row_num,
                "card_name": row[0] if len(row) > 0 else "",
                "card_id": row[1] if len(row) > 1 else "",
                "set": row[20] if len(row) > 20 else "",
            }
        )
    return {"set": set_name, "start_row": start_row, "end_row": end_row, "rows": rows}


def inspect_headers(token):
    values = current_sheet_values(token)
    headers = values[0] if values else []
    return [{"column": i + 1, "header": header} for i, header in enumerate(headers)]


def set_row_numbers(set_code, token):
    set_name = set_code_to_set_name(set_code)
    values = current_sheet_values(token)
    row_nums = []
    for row_num, row in enumerate(values[1:], start=2):
        card_id = row[1].strip() if len(row) > 1 else ""
        set_value = row[20] if len(row) > 20 else ""
        if card_id.startswith(f"{set_code}-") or set_value == set_name:
            row_nums.append(row_num)
    return row_nums


def clear_shifted_columns(set_code, token):
    row_nums = set_row_numbers(set_code, token)
    if not row_nums:
        return {"cleared": False, "reason": "no matching rows"}
    start_row = min(row_nums)
    end_row = max(row_nums)
    payload = {
        "valueInputOption": "RAW",
        "data": [
            {
                "range": f"'{CARD_DATA_SHEET}'!I{start_row}:I{end_row}",
                "majorDimension": "ROWS",
                "values": [[""] for _ in range(start_row, end_row + 1)],
            },
            {
                "range": f"'{CARD_DATA_SHEET}'!P{start_row}:P{end_row}",
                "majorDimension": "ROWS",
                "values": [[""] for _ in range(start_row, end_row + 1)],
            },
            {
                "range": f"'{CARD_DATA_SHEET}'!V{start_row}:V{end_row}",
                "majorDimension": "ROWS",
                "values": [[""] for _ in range(start_row, end_row + 1)],
            },
        ],
    }
    batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
    api_request(batch_url, token, method="POST", payload=payload)
    return {"cleared": True, "start_row": start_row, "end_row": end_row, "columns": ["I", "P", "V"]}


def set_spawn_defaults(set_code, token):
    defaults = {
        "UNL": {
            "UNL-040": "XP Tracker",
            "UNL-044": "Bird",
            "UNL-048": "Sprite",
            "UNL-069": "Sprite",
            "UNL-081": "Reflection",
            "UNL-082": "Sprite",
            "UNL-082a": "Sprite",
            "UNL-088": "Bird",
            "UNL-095": "XP Tracker",
            "UNL-112": "XP Tracker",
            "UNL-117": "XP Tracker",
            "UNL-127": "XP Tracker",
            "UNL-129": "XP Tracker",
            "UNL-136": "XP Tracker",
            "UNL-145": "Gold",
            "UNL-160": "Bird",
            "UNL-153": "Bird",
            "UNL-158": "XP Tracker",
            "UNL-185": "Gold",
            "UNL-189": "Sprite",
            "UNL-195": "Brush",
            "UNL-199": "Reflection",
            "UNL-200": "Reflection",
            "UNL-222": "Gold",
            "UNL-084": "Sprite",
            "UNL-230": "Sprite",
            "UNL-230s": "Sprite",
            "UNL-233": "Brush",
            "UNL-233s": "Brush",
        },
        "VEN": {
            "VEN-T01": "Empower",
        },
    }
    desired = defaults.get(set_code, {})

    values = current_sheet_values(token)
    updates = []
    updated = []
    for row_num, row in enumerate(values[1:], start=2):
        card_id = row[1].strip() if len(row) > 1 else ""
        current_spawn = row[15] if len(row) > 15 else ""
        effect = row[6] if len(row) > 6 else ""

        spawn = desired.get(card_id, "")
        if not spawn and set_code == "VEN" and "empower" in effect.lower() and not current_spawn:
            spawn = "Empower"
        if not spawn:
            continue
        if current_spawn == spawn:
            continue
        if current_spawn and current_spawn != spawn:
            continue
        updates.append(
            {
                "range": f"'{CARD_DATA_SHEET}'!P{row_num}",
                "majorDimension": "ROWS",
                "values": [[spawn]],
            }
        )
        updated.append({"row": row_num, "card_id": card_id, "spawn": spawn})
    if updates:
        batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
        api_request(
            batch_url,
            token,
            method="POST",
            payload={"valueInputOption": "RAW", "data": updates},
        )
    return {"updated": updated}


def delete_duplicate_set_rows(set_code, token):
    set_name = set_code_to_set_name(set_code)
    values = current_sheet_values(token)
    duplicates = []
    seen = {}
    for row_num, row in enumerate(values[1:], start=2):
        card_id = row[1].strip() if len(row) > 1 else ""
        set_value = row[20] if len(row) > 20 else ""
        if not card_id.startswith(f"{set_code}-") and set_value != set_name:
            continue
        if not card_id:
            continue
        if card_id in seen:
            duplicates.append(
                {
                    "row": row_num,
                    "card_id": card_id,
                    "card_name": row[0] if len(row) > 0 else "",
                }
            )
        else:
            seen[card_id] = row_num
    if duplicates:
        payload = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": card_data_sheet_id(token),
                            "dimension": "ROWS",
                            "startIndex": dup["row"] - 1,
                            "endIndex": dup["row"],
                        }
                    }
                }
                for dup in sorted(duplicates, key=lambda d: d["row"], reverse=True)
            ]
        }
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}:batchUpdate"
        api_request(url, token, method="POST", payload=payload)
    return {"deleted": duplicates}


def upsert_rows(rows, token):
    ensure_image_tracking_headers(token)
    existing_rows = current_sheet_rows(token)
    missing = [row for row in rows if row["card-id"] not in existing_rows]

    if missing:
        append_range = urllib.parse.quote(f"'{CARD_DATA_SHEET}'!A:A", safe="!'")
        append_url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/"
            f"{append_range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
        )
        append_payload = {"majorDimension": "ROWS", "values": [[row["card_name"]] for row in missing]}
        append_resp = api_request(append_url, token, method="POST", payload=append_payload)
        updated_range = append_resp["updates"]["updatedRange"]
        m = re.search(r"!A(\d+)(?::A(\d+))?$", updated_range)
        start_row = int(m.group(1))
        for offset, row in enumerate(missing):
            existing_rows[row["card-id"]] = start_row + offset

    data = []
    for row in rows:
        row_num = existing_rows[row["card-id"]]
        data.extend(
            [
                {
                    "range": f"'{CARD_DATA_SHEET}'!A{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["card_name"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!G{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["effect"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!H{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["tts-type"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!L{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["domain"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!M{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["might"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!N{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["cost"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!O{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["power"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!Q{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["equip_might"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!R{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["flavor"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!S{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["artist"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!T{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["rarity"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!U{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["set"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!X{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["image_source"]]],
                },
                {
                    "range": f"'{CARD_DATA_SHEET}'!Y{row_num}",
                    "majorDimension": "ROWS",
                    "values": [[row["image_url"]]],
                },
            ]
        )
    if missing:
        start_row = min(existing_rows[row["card-id"]] for row in missing)
        end_row = max(existing_rows[row["card-id"]] for row in missing)
        data.append(
            {
                "range": f"'{CARD_DATA_SHEET}'!B{start_row}:B{end_row}",
                "majorDimension": "ROWS",
                "values": [[row["card-id"]] for row in missing],
            }
        )
    updates = {"valueInputOption": "RAW", "data": data}
    batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate"
    api_request(batch_url, token, method="POST", payload=updates)
    return {
        "appended": len(missing),
        "updated": len(rows),
        "rows": rows,
        "appended_rows": missing,
    }


def download_images(rows, jpg_dir, force_card_ids=None):
    jpg_dir = Path(jpg_dir)
    jpg_dir.mkdir(parents=True, exist_ok=True)
    force_card_ids = set(force_card_ids or [])
    source_meta_path = jpg_dir / ".piltover_image_sources.json"
    if source_meta_path.exists():
        try:
            source_meta = json.loads(source_meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            source_meta = {}
    else:
        source_meta = {}
    downloaded = []
    skipped = []
    for row in rows:
        card_id = row["card-id"]
        image_url = row.get("image_url", "")
        image_source = row.get("image_source", "")
        if not image_url:
            skipped.append({"card-id": card_id, "reason": "missing image_url"})
            continue
        out_path = jpg_dir / f"{card_id}.jpg"
        existing_meta = source_meta.get(card_id, {})
        force = card_id in force_card_ids
        if out_path.exists() and not force:
            if not existing_meta:
                if image_source == "official":
                    pass
                else:
                    source_meta[card_id] = {"image_url": image_url, "image_source": image_source}
                    skipped.append({"card-id": card_id, "reason": "exists-seeded", "source": image_url})
                    continue
            elif existing_meta.get("image_url") == image_url:
                skipped.append({"card-id": card_id, "reason": "exists", "source": image_url})
                continue
        suffix = Path(urllib.parse.urlparse(image_url).path).suffix or ".img"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"}),
                timeout=60,
            ) as resp:
                tmp_path.write_bytes(resp.read())
            subprocess.run(
                ["/usr/bin/sips", "-s", "format", "jpeg", str(tmp_path), "--out", str(out_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            source_meta[card_id] = {"image_url": image_url, "image_source": image_source}
            downloaded.append({"card-id": card_id, "path": str(out_path), "source": image_url})
        except Exception as exc:
            skipped.append({"card-id": card_id, "reason": str(exc), "source": image_url})
            if out_path.exists():
                out_path.unlink()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    source_meta_path.write_text(json.dumps(source_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"downloaded": downloaded, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="UNL")
    parser.add_argument("--append-sheet", action="store_true")
    parser.add_argument("--sort-sheet-block", action="store_true")
    parser.add_argument("--inspect-set-block", action="store_true")
    parser.add_argument("--inspect-headers", action="store_true")
    parser.add_argument("--dedupe-set", action="store_true")
    parser.add_argument("--clear-shifted-columns", action="store_true")
    parser.add_argument("--set-spawn-defaults", action="store_true")
    parser.add_argument("--download-jpg-dir", default="")
    parser.add_argument("--download-card-id", action="append", default=[])
    parser.add_argument("--read-range", default="")
    parser.add_argument("--write-range", default="")
    parser.add_argument("--write-value", default="")
    parser.add_argument("--write-value-file", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.read_range:
        token = read_sheet_token()
        result = read_sheet_range(args.read_range, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.write_range:
        token = read_sheet_token()
        value = args.write_value
        if args.write_value_file:
            value = Path(args.write_value_file).read_text(encoding="utf-8")
        result = write_sheet_range(args.write_range, [[value]], token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    rows = extract_cards(args.set)
    if args.download_jpg_dir:
        if args.download_card_id:
            wanted = set(args.download_card_id)
            rows = [row for row in rows if row["card-id"] in wanted]
        result = download_images(rows, args.download_jpg_dir, force_card_ids=args.download_card_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.append_sheet:
        token = read_sheet_token()
        result = upsert_rows(rows, token)
        if args.sort_sheet_block:
            result["sort"] = sort_set_block(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.sort_sheet_block:
        token = read_sheet_token()
        result = sort_set_block(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.inspect_set_block:
        token = read_sheet_token()
        result = inspect_set_block(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.inspect_headers:
        token = read_sheet_token()
        result = inspect_headers(token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.dedupe_set:
        token = read_sheet_token()
        result = delete_duplicate_set_rows(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.clear_shifted_columns:
        token = read_sheet_token()
        result = clear_shifted_columns(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.set_spawn_defaults:
        token = read_sheet_token()
        result = set_spawn_defaults(args.set, token)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    for row in rows:
        print(f"{row['card-id']}\t{row['card_name']}\t{row['effect']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(body, file=sys.stderr)
        raise
