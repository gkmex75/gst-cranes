#!/usr/bin/env python3
"""
LinkedIn Share API OAuth helper — refreshes LINKEDIN_ACCESS_TOKEN (personal post).

This is the "Share on LinkedIn" token (w_member_social scope) used by
yayin-motoru.py to post to the user's personal LinkedIn feed.
Separate from LINKEDIN_ADVERTISING_TOKEN (rw_ads scope, different app product).

Prereqs:
  - LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET already in .env
  - App "GST Cranes Marketing" (244010273) has "Share on LinkedIn" product enabled
  - Redirect URL http://localhost:8765/callback already authorized

Run:
    cd ~/gst-cranes && source .venv/bin/activate
    python scripts/get_linkedin_share_token.py

Flow: browser consent → /callback → exchange → write .env.
"""

import http.server
import secrets
import socketserver
import sys
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values, set_key

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
REDIRECT_URI = "http://localhost:8765/callback"
PORT = 8765
SCOPES = ["w_member_social", "openid", "profile"]

env = dotenv_values(ENV_PATH)
CLIENT_ID = env.get("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = env.get("LINKEDIN_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET in .env.")

state = secrets.token_urlsafe(24)
auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": " ".join(SCOPES),
    "state": state,
})

received = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404); self.end_headers(); return
        params = dict(urllib.parse.parse_qsl(parsed.query))
        received.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>LinkedIn callback received.</h2><p>Return to terminal.</p>")

    def log_message(self, *args, **kwargs):
        pass


print(f"\nOpening browser for LinkedIn consent…\n  {auth_url}\n")
webbrowser.open(auth_url)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), CallbackHandler) as httpd:
    print(f"Listening on http://localhost:{PORT}/callback — complete consent in browser.")
    while "code" not in received and "error" not in received:
        httpd.handle_request()

if "error" in received:
    sys.exit(f"OAuth error: {received.get('error')} — {received.get('error_description')}")
if received.get("state") != state:
    sys.exit("State mismatch — possible CSRF, aborting.")

print("Authorization code received. Exchanging for access token…")
token_resp = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type": "authorization_code",
        "code": received["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)
token_resp.raise_for_status()
tok = token_resp.json()

access_token = tok["access_token"]
expires_in = tok.get("expires_in", 5184000)
expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

print(f"  access_token: …{access_token[-8:]}  (expires {expires_at.isoformat()})")

# Fetch member ID via OpenID userinfo endpoint
uinfo = requests.get(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": f"Bearer {access_token}"},
    timeout=30,
)
if uinfo.ok:
    j = uinfo.json()
    member_id = j.get("sub", "")
    name = j.get("name", "")
    print(f"  member: {name}  sub={member_id}")
    set_key(str(ENV_PATH), "LINKEDIN_ACCESS_TOKEN", access_token)
    set_key(str(ENV_PATH), "LINKEDIN_ACCESS_TOKEN_EXPIRES_AT", expires_at.isoformat())
    if member_id:
        set_key(str(ENV_PATH), "LINKEDIN_ORG_ID", member_id)
    print(f"\nWrote LINKEDIN_ACCESS_TOKEN + LINKEDIN_ORG_ID to {ENV_PATH}")
else:
    print(f"  ✗ userinfo → HTTP {uinfo.status_code}: {uinfo.text[:200]}")
    set_key(str(ENV_PATH), "LINKEDIN_ACCESS_TOKEN", access_token)
    set_key(str(ENV_PATH), "LINKEDIN_ACCESS_TOKEN_EXPIRES_AT", expires_at.isoformat())
    print(f"\nWrote LINKEDIN_ACCESS_TOKEN to {ENV_PATH} (member ID lookup failed, kept old LINKEDIN_ORG_ID)")

print("\nDone. yayin-motoru.py LinkedIn artık çalışmalı.")
