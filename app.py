#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Single-file Flask back-end for “Quest Board”.
– Stores quests **and** settings in quests.json
– Supports theme folders under static/themes/
– Proxies OpenAI calls so the key never leaves the server
"""
# ────────────────────────────────────────────────────────────────
#  Imports & basic setup
# ────────────────────────────────────────────────────────────────
from __future__ import annotations

import json, os, pathlib, tempfile, uuid
from flask import (
    Flask, Blueprint, jsonify, request, send_from_directory
)
from openai import OpenAI

BASE_DIR   = pathlib.Path(__file__).parent
DATA_FILE  = BASE_DIR / "quests.json"
THEMES_DIR = BASE_DIR / "static" / "themes"

app = Flask(__name__)
# ────────────────────────────────────────────────────────────────
#  Low-level file helpers
# ────────────────────────────────────────────────────────────────
def _read_raw() -> dict:
    """Return full JSON structure, upgrading legacy list-only files."""
    if not DATA_FILE.exists():
        return {"settings": {}, "quests": []}

    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # auto-upgrade legacy format
    if isinstance(data, list):
        data = {"settings": {}, "quests": data}

    data.setdefault("settings", {})
    data.setdefault("quests",   [])
    return data


def _write_raw(data: dict) -> None:
    """Atomic write to avoid corruption (works on POSIX & Windows)."""
    tmp_kwargs = dict(
        mode="w", delete=False, dir=DATA_FILE.parent, encoding="utf-8"
    )
    with tempfile.NamedTemporaryFile(**tmp_kwargs) as tmp:
        json.dump(data, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, DATA_FILE)


# thin convenience wrappers ----------------------------------------------------
def load_settings() -> dict:         return _read_raw()["settings"]
def save_settings(s: dict) -> None:
    d = _read_raw(); d["settings"] = s; _write_raw(d)

def load_quests() -> list:           return _read_raw()["quests"]
def save_quests(q: list) -> None:
    d = _read_raw(); d["quests"] = q; _write_raw(d)

# ────────────────────────────────────────────────────────────────
#  OpenAI helper (per-user key or env var)
# ────────────────────────────────────────────────────────────────
def get_openai() -> OpenAI:
    key = load_settings().get("openaiKey") or os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=key)

# ────────────────────────────────────────────────────────────────
#  AI proxy route (keeps key server-side)
# ────────────────────────────────────────────────────────────────
@app.post("/ai-rewrite")
def ai_rewrite():
    body   = request.get_json(force=True) or {}
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return {"error": "No prompt provided"}, 400

    try:
        chat = get_openai().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300, temperature=0.7,
        )
        return jsonify({"text": chat.choices[0].message.content.strip()})
    except Exception as exc:  # noqa: BLE001
        app.logger.exception(exc)
        return {"error": "AI request failed"}, 500

# ────────────────────────────────────────────────────────────────
#  Quests blueprint  (/api/quests)
# ────────────────────────────────────────────────────────────────
bp = Blueprint("quests", __name__, url_prefix="/api/quests")

def _new_id() -> str:  return uuid.uuid4().hex   # 32-char random hex


@bp.post("/blank")
def blank():
    qs = load_quests()
    new_q = {
        "id": _new_id(), "title": "New Quest", "category": "side",
        "objective": "", "description": "", "subtasks": [],
        "active": True, "prevCat": "side", "notes": ""
    }
    qs.append(new_q)
    save_quests(qs)
    return jsonify(new_q), 201


@bp.get("/")
def all_quests():
    return jsonify(load_quests())


@bp.post("/")
def add_quest():
    qs   = load_quests()
    new  = request.get_json(force=True) or {}
    new.setdefault("id", _new_id())
    qs.append(new)
    save_quests(qs)
    return jsonify(new), 201


@bp.get("/<quest_id>")
def get_one(quest_id: str):
    for q in load_quests():
        if q.get("id") == quest_id:
            return jsonify(q)
    return {"error": "not found"}, 404


@bp.put("/<quest_id>")
def update_quest(quest_id: str):
    qs      = load_quests()
    payload = request.get_json(force=True) or {}
    for q in qs:
        if q.get("id") == quest_id:
            q.update(payload)
            save_quests(qs)
            return "", 204
    return {"error": "not found"}, 404


@bp.delete("/<quest_id>")
def delete_quest(quest_id: str):
    qs = load_quests()
    new_qs = [q for q in qs if q.get("id") != quest_id]
    if len(new_qs) == len(qs):
        return {"error": "not found"}, 404
    save_quests(new_qs)
    return "", 204


app.register_blueprint(bp)        # ← **don’t forget this!**
# ────────────────────────────────────────────────────────────────
#  Settings & themes
# ────────────────────────────────────────────────────────────────
@app.get("/api/settings")
def api_get_settings():  return jsonify(load_settings())


@app.put("/api/settings")
def api_put_settings():
    s = load_settings()
    s.update(request.get_json(force=True) or {})
    save_settings(s)
    return "", 204


@app.get("/api/themes")
def api_list_themes():
    themes = [p.name for p in THEMES_DIR.iterdir() if p.is_dir()]
    return jsonify(themes)

# ────────────────────────────────────────────────────────────────
#  Static files  (index.html + assets)
# ────────────────────────────────────────────────────────────────
@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

# ────────────────────────────────────────────────────────────────
#  Entrypoint
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
