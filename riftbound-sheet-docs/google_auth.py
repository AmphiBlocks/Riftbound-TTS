#!/usr/bin/env python3

import base64
import hashlib
import json
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLIENT_PATH = ROOT / "google-oauth-client.json"
TOKEN_PATH = ROOT / "google-oauth-token.json"
REDIRECT_URI = "http://127.0.0.1:8080"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.deployments",
    "https://www.googleapis.com/auth/spreadsheets",
]


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_client():
    payload = json.loads(CLIENT_PATH.read_text())
    if "web" not in payload:
        raise SystemExit("Expected a web OAuth client JSON at google-oauth-client.json")
    return payload["web"]


def make_auth_url(client):
    verifier = b64url(secrets.token_bytes(48))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = b64url(secrets.token_bytes(24))
    params = {
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = client["auth_uri"] + "?" + urllib.parse.urlencode(params)
    return url, state, verifier


class CallbackHandler(BaseHTTPRequestHandler):
    server_version = "RiftboundOAuth/1.0"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        query_flat = {k: v[0] for k, v in query.items()}
        if parsed.path == "/" and ("code" in query_flat or "error" in query_flat):
            self.server.oauth_result = {
                "path": parsed.path,
                "query": query_flat,
            }
        body = "Auth received. You can close this tab.\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, fmt, *args):
        return


def start_server():
    server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
    server.timeout = 0.5
    server.oauth_result = None

    def run():
        while getattr(server, "_keep_running", True):
            server.handle_request()

    server._keep_running = True
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return server, thread


def exchange_code(client, code, verifier):
    payload = {
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        client["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def save_token(token):
    TOKEN_PATH.write_text(json.dumps(token, indent=2) + "\n")


def main():
    client = load_client()
    auth_url, expected_state, verifier = make_auth_url(client)

    print("Open this URL in your browser and sign in:")
    print(auth_url)
    print()
    print(f"Waiting for callback on {REDIRECT_URI} ...", flush=True)

    server, thread = start_server()
    deadline = time.time() + 600
    try:
        while time.time() < deadline:
            if server.oauth_result:
                result = server.oauth_result["query"]
                break
            time.sleep(0.2)
        else:
            raise SystemExit("Timed out waiting for OAuth callback.")
    finally:
        server._keep_running = False
        try:
            urllib.request.urlopen(f"{REDIRECT_URI}/shutdown", timeout=1)
        except Exception:
            pass
        thread.join(timeout=2)

    if "error" in result:
        raise SystemExit(f"OAuth error: {result['error']}")
    if result.get("state") != expected_state:
        raise SystemExit("State mismatch in OAuth callback.")
    if "code" not in result:
        raise SystemExit("No authorization code returned.")

    token = exchange_code(client, result["code"], verifier)
    save_token(token)
    print(f"Saved token to {TOKEN_PATH}")
    print("Scopes granted:")
    print(token.get("scope", ""))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
