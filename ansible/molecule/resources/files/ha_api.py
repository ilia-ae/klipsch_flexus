#!/usr/bin/env python3
"""Home Assistant REST/WebSocket client for the Molecule verify steps (test-only).

Runs INSIDE the throwaway Home Assistant container with the image's own Python (aiohttp is part
of Home Assistant), against http://127.0.0.1:8123. Every command prints one JSON document.

  onboard                    create the test owner through the onboarding API (once), exchange the
                             auth code for a token and store a long-lived access token in
                             TOKEN_FILE. {"changed": bool}. A second call only checks the token.
  rest METHOD PATH [JSON]    one REST call with the stored token -> {"status", "json" | "text"}
  ws TYPE [JSON]             one WebSocket command -> {"success", "result", "error"}
  fetch PATH                 GET PATH (with the token) -> {"status", "sha256", "size", "content_type"}

The owner and token exist only in the test container; the password is random and never stored.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

import aiohttp

BASE = os.environ.get("HA_URL", "http://127.0.0.1:8123")
CLIENT_ID = f"{BASE}/"
TOKEN_FILE = Path(os.environ.get("HA_TOKEN_FILE", "/config/.molecule/ha_token"))


def _token() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"no token in {TOKEN_FILE}: run 'onboard' first")


async def _ws_call(session: aiohttp.ClientSession, token: str, msg: dict) -> dict:
    async with session.ws_connect(f"{BASE}/api/websocket", max_msg_size=0) as ws:
        hello = await ws.receive_json()
        if hello.get("type") != "auth_required":
            raise RuntimeError(f"unexpected websocket greeting: {hello}")
        await ws.send_json({"type": "auth", "access_token": token})
        auth = await ws.receive_json()
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"websocket auth failed: {auth}")
        await ws.send_json({"id": 1, **msg})
        while True:
            reply = await ws.receive_json()
            if reply.get("id") == 1 and reply.get("type") == "result":
                return {"success": reply.get("success"), "result": reply.get("result"), "error": reply.get("error")}


async def onboard(session: aiohttp.ClientSession) -> dict:
    if TOKEN_FILE.exists():
        async with session.get(f"{BASE}/api/", headers={"Authorization": f"Bearer {_token()}"}) as resp:
            if resp.status == 200:
                return {"changed": False}
            raise RuntimeError(f"stored token rejected (HTTP {resp.status}); onboarding cannot be repeated")
    user = {
        "client_id": CLIENT_ID,
        "name": "Molecule Test Owner",
        "username": "molecule",
        "password": secrets.token_urlsafe(24),
        "language": "en",
    }
    async with session.post(f"{BASE}/api/onboarding/users", json=user) as resp:
        if resp.status != 200:
            raise RuntimeError(f"onboarding/users: HTTP {resp.status}: {await resp.text()}")
        auth_code = (await resp.json())["auth_code"]
    form = {"grant_type": "authorization_code", "code": auth_code, "client_id": CLIENT_ID}
    async with session.post(f"{BASE}/auth/token", data=form) as resp:
        if resp.status != 200:
            raise RuntimeError(f"auth/token: HTTP {resp.status}: {await resp.text()}")
        access = (await resp.json())["access_token"]
    reply = await _ws_call(
        session, access, {"type": "auth/long_lived_access_token", "client_name": "molecule-verify", "lifespan": 365}
    )
    if not reply["success"]:
        raise RuntimeError(f"long-lived token: {reply['error']}")
    TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_FILE.write_text(reply["result"], encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    return {"changed": True}


async def rest(session: aiohttp.ClientSession, method: str, path: str, body: str | None) -> dict:
    kwargs = {"json": json.loads(body)} if body else {}
    headers = {"Authorization": f"Bearer {_token()}"}
    async with session.request(method.upper(), f"{BASE}{path}", headers=headers, **kwargs) as resp:
        text = await resp.text()
        try:
            return {"status": resp.status, "json": json.loads(text)}
        except ValueError:
            return {"status": resp.status, "text": text}


async def fetch(session: aiohttp.ClientSession, path: str) -> dict:
    headers = {"Authorization": f"Bearer {_token()}"}
    async with session.get(f"{BASE}{path}", headers=headers) as resp:
        data = await resp.read()
        return {
            "status": resp.status,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "content_type": resp.headers.get("Content-Type"),
        }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("onboard")
    p_rest = sub.add_parser("rest")
    p_rest.add_argument("method")
    p_rest.add_argument("path")
    p_rest.add_argument("body", nargs="?")
    p_ws = sub.add_parser("ws")
    p_ws.add_argument("type")
    p_ws.add_argument("payload", nargs="?")
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("path")
    args = parser.parse_args()

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if args.cmd == "onboard":
            out = await onboard(session)
        elif args.cmd == "rest":
            out = await rest(session, args.method, args.path, args.body)
        elif args.cmd == "ws":
            payload = json.loads(args.payload) if args.payload else {}
            out = await _ws_call(session, _token(), {"type": args.type, **payload})
        else:
            out = await fetch(session, args.path)
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
