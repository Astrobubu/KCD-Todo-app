from flask import Flask, jsonify, request, send_from_directory
import json, os, pathlib

app = Flask(__name__)
DATA   = pathlib.Path(__file__).with_name("quests.json")

def load():
    with DATA.open("r", encoding="utf‑8") as f:
        return json.load(f)

def save(obj):
    with DATA.open("w", encoding="utf‑8") as f:
        json.dump(obj, f, indent=2)

@app.post("/api/quests/blank")
def blank():
    """Create a blank quest, persist it, and return it to the client."""
    import time
    quests = load()                      # 1) read current file

    new_q = {
        "id": str(int(time.time() * 1000)),   # crude unique id
        "title": "New Quest",
        "category": "side",
        "objective": "",
        "description": "",
        "subtasks": [],
        "active": True,
        "prevCat": "side",
        "notes": "",         
    }

    quests.append(new_q)                # 2) add to list
    save(quests)                        # 3) write back to quests.json

    return jsonify(new_q), 201          # 4) send to front-end
@app.get("/api/quests")
def all_quests():
    return jsonify(load())
@app.post("/api/quests")
def add_quest():
    quests = load()
    new_q  = request.json           # comes with id, title, …
    if "id" not in new_q:           # just in case
        import time
        new_q["id"] = int(time.time()*1000).toString()
    quests.append(new_q)
    save(quests)
    return jsonify(new_q), 201
@app.delete("/api/quests/<quest_id>")
def delete_quest(quest_id):
    quests = load()
    before = len(quests)
    quests = [q for q in quests if str(q["id"]) != str(quest_id)]
    if len(quests) == before:
        return {"error": "not found"}, 404
    save(quests)
    return "", 204
@app.get("/api/quests/<quest_id>")
def get_one(quest_id):
    for q in load():
        if str(q["id"]) == str(quest_id):
            return jsonify(q)
    return {"error": "not found"}, 404

@app.put("/api/quests/<quest_id>")
def update_quest(quest_id):
    quests = load()
    for q in quests:
        if str(q["id"]) == str(quest_id):    # ← new
            q.update(request.json)
            save(quests)
            return "", 204
    return {"error": "not found"}, 404

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    app.run(debug=True)
