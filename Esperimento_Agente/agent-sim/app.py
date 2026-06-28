#!/usr/bin/env python3
"""
Dashboard web per il sistema agente simulativo.
Avvia con: python app.py
Poi apri:  http://localhost:5000

Dipendenze: pip install flask anthropic
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

BASE_DIR          = Path(__file__).parent
AGENT_PATH        = BASE_DIR / "agent.py"
SEED_PATH         = BASE_DIR / "seed.py"
LOGS_DIR          = BASE_DIR / "logs"
REVIEW_QUEUE_DIR  = BASE_DIR / "review_queue"
INBOX_DIR         = BASE_DIR / "inbox"

# Crea directory necessarie al primo avvio
for _d in [REVIEW_QUEUE_DIR, INBOX_DIR, LOGS_DIR]:
    _d.mkdir(exist_ok=True)

app = Flask(__name__)

# ============================================================
# STATO GLOBALE
# ============================================================

_is_agent_running = False
_loop_active      = False
_stop_event       = threading.Event()
_next_run_at      = None
_agent_lock       = threading.Lock()


# ============================================================
# FUNZIONI INTERNE
# ============================================================

def _run_agent_blocking():
    global _is_agent_running
    with _agent_lock:
        _is_agent_running = True
    try:
        subprocess.run(
            [sys.executable, str(AGENT_PATH)],
            cwd=str(BASE_DIR),
        )
    finally:
        with _agent_lock:
            _is_agent_running = False


def _loop_worker():
    global _loop_active, _next_run_at
    _loop_active = True
    _stop_event.clear()
    try:
        while not _stop_event.is_set():
            _run_agent_blocking()
            if _stop_event.is_set():
                break
            _next_run_at = time.time() + 60
            _stop_event.wait(timeout=60)
    finally:
        _loop_active = False
        _next_run_at = None


def _latest_log() -> Path | None:
    logs = sorted(LOGS_DIR.glob("*.log"))
    return logs[-1] if logs else None


def _count_json(folder: Path) -> int:
    return len(list(folder.glob("*.json")))


# ============================================================
# ROUTES — core
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run-once", methods=["POST"])
def api_run_once():
    if _is_agent_running:
        return jsonify({"error": "Agente già in esecuzione"}), 409
    if _loop_active:
        return jsonify({"error": "Loop attivo — fermalo prima"}), 409
    threading.Thread(target=_run_agent_blocking, daemon=True).start()
    return jsonify({"status": "avviato"})


@app.route("/api/start-loop", methods=["POST"])
def api_start_loop():
    if _loop_active:
        return jsonify({"error": "Loop già attivo"}), 409
    if _is_agent_running:
        return jsonify({"error": "Agente già in esecuzione"}), 409
    threading.Thread(target=_loop_worker, daemon=True).start()
    return jsonify({"status": "loop_avviato"})


@app.route("/api/stop-loop", methods=["POST"])
def api_stop_loop():
    _stop_event.set()
    return jsonify({"status": "stop_richiesto"})


@app.route("/api/seed", methods=["POST"])
def api_seed():
    """Seed scenario standard (backward-compat con il frontend legacy)."""
    if _is_agent_running or _loop_active:
        return jsonify({"error": "Impossibile fare seed mentre l'agente è in esecuzione"}), 409
    result = subprocess.run(
        [sys.executable, str(SEED_PATH), "--scenario", "standard"],
        cwd=str(BASE_DIR), capture_output=True, text=True, encoding="utf-8",
    )
    return jsonify({"status": "ok", "output": result.stdout})


@app.route("/api/seed/<scenario>", methods=["POST"])
def api_seed_scenario(scenario):
    """Seed di uno scenario specifico: standard, retail, manifattura, studio."""
    if scenario not in ("standard", "retail", "manifattura", "studio"):
        return jsonify({"error": f"Scenario '{scenario}' non valido"}), 400
    if _is_agent_running or _loop_active:
        return jsonify({"error": "Impossibile fare seed mentre l'agente è in esecuzione"}), 409
    result = subprocess.run(
        [sys.executable, str(SEED_PATH), "--scenario", scenario],
        cwd=str(BASE_DIR), capture_output=True, text=True, encoding="utf-8",
    )
    return jsonify({"status": "ok", "scenario": scenario, "output": result.stdout})


@app.route("/api/status")
def api_status():
    db = {"clienti": {}, "ordini": [], "fatture": [], "pagamenti": []}
    db_path = BASE_DIR / "data" / "db.json"
    if db_path.exists():
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)

    countdown = None
    if _next_run_at:
        countdown = max(0, int(_next_run_at - time.time()))

    return jsonify({
        "agent_running": _is_agent_running,
        "loop_active":   _loop_active,
        "countdown":     countdown,
        "dirs": {
            "inbox":            _count_json(BASE_DIR / "inbox"),
            "production_queue": _count_json(BASE_DIR / "production_queue"),
            "invoices_drafts":  _count_json(BASE_DIR / "invoices" / "drafts"),
            "invoices_sent":    _count_json(BASE_DIR / "invoices" / "sent"),
            "payments":         _count_json(BASE_DIR / "payments"),
            "processed":        _count_json(BASE_DIR / "processed"),
        },
        "db": {
            "clienti":   len(db.get("clienti", {})),
            "ordini":    len(db.get("ordini", [])),
            "fatture":   len(db.get("fatture", [])),
            "pagamenti": len(db.get("pagamenti", [])),
        },
    })


@app.route("/api/live")
def api_live():
    live_path = BASE_DIR / "data" / "live_state.json"
    if not live_path.exists():
        return jsonify({"cycle_active": False, "active_step": 0,
                        "current_item": "", "step_results": {}, "ai_mode": False})
    with open(live_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/logs/stream")
def api_logs_stream():
    def generate():
        watched = None
        offset  = 0
        while True:
            latest = _latest_log()
            if latest and latest != watched:
                watched = latest
                offset  = 0
                yield f"data: {json.dumps({'type': 'new_log', 'file': latest.name})}\n\n"

            if watched and watched.exists():
                size = watched.stat().st_size
                if size > offset:
                    with open(watched, "r", encoding="utf-8") as f:
                        f.seek(offset)
                        chunk = f.read()
                    offset = size
                    for line in chunk.splitlines():
                        if line.strip():
                            yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
            time.sleep(0.2)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# ROUTES — "Prova tu" free-text input
# ============================================================

@app.route("/api/process-freetext", methods=["POST"])
def api_process_freetext():
    """
    Riceve testo libero dal frontend, lo inserisce come mail in inbox/
    e avvia l'agente. Il frontend vedrà la pipeline animarsi in tempo reale.
    """
    if _is_agent_running or _loop_active:
        return jsonify({"error": "Agente già in esecuzione — riprova tra qualche secondo"}), 409

    data  = request.get_json(force=True) or {}
    testo = data.get("testo", "").strip()
    if not testo:
        return jsonify({"error": "Testo vuoto"}), 400

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    mail_id = f"freetext_{ts}"
    mail    = {
        "id":        mail_id,
        "timestamp": datetime.now().isoformat(),
        "from":      "utente@demo.it",
        "from_name": "Utente Demo (Prova tu)",
        "subject":   "Richiesta ordine — testo libero",
        "body":      testo,
        "attachment": {}
    }
    inbox_file = INBOX_DIR / f"{mail_id}.json"
    with open(inbox_file, "w", encoding="utf-8") as f:
        json.dump(mail, f, ensure_ascii=False, indent=2)

    threading.Thread(target=_run_agent_blocking, daemon=True).start()
    return jsonify({"status": "avviato", "mail_id": mail_id})


# ============================================================
# ROUTES — review queue (human-in-the-loop)
# ============================================================

@app.route("/api/review")
def api_review():
    """Lista tutti gli item nella coda di revisione umana."""
    REVIEW_QUEUE_DIR.mkdir(exist_ok=True)
    items = []
    for f in sorted(REVIEW_QUEUE_DIR.glob("rq_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                items.append(json.load(fp))
        except Exception:
            pass
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/review/<item_id>/approve", methods=["POST"])
def api_review_approve(item_id):
    """
    Approva un item in coda di revisione: reinserisce la mail in inbox/
    con flag _approved=True e avvia l'agente.
    """
    rq_file = REVIEW_QUEUE_DIR / f"{item_id}.json"
    if not rq_file.exists():
        return jsonify({"error": "Item non trovato"}), 404

    if _is_agent_running or _loop_active:
        return jsonify({"error": "Agente già in esecuzione — riprova tra qualche secondo"}), 409

    with open(rq_file, "r", encoding="utf-8") as f:
        item = json.load(f)

    mail = item.get("mail", {})
    mail["_approved"]    = True
    mail["_approved_at"] = datetime.now().isoformat()
    new_id = f"approved_{item_id}"
    mail["id"] = new_id

    inbox_file = INBOX_DIR / f"{new_id}.json"
    with open(inbox_file, "w", encoding="utf-8") as f:
        json.dump(mail, f, ensure_ascii=False, indent=2)

    rq_file.unlink()

    threading.Thread(target=_run_agent_blocking, daemon=True).start()
    return jsonify({"status": "approvato", "mail_id": new_id})


@app.route("/api/review/<item_id>/reject", methods=["POST"])
def api_review_reject(item_id):
    """Rigetta un item dalla coda di revisione (lo elimina)."""
    rq_file = REVIEW_QUEUE_DIR / f"{item_id}.json"
    if not rq_file.exists():
        return jsonify({"error": "Item non trovato"}), 404
    rq_file.unlink()
    return jsonify({"status": "rifiutato"})


# ============================================================
# ROUTES — AI status e KPI
# ============================================================

@app.route("/api/ai-status")
def api_ai_status():
    """Ritorna se la modalità AI è attiva e i parametri correlati."""
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    ai_mode = api_key_set
    if ai_mode:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            ai_mode = False

    return jsonify({
        "ai_mode":     ai_mode,
        "api_key_set": api_key_set,
        "model":       "claude-haiku-4-5-20251001",
        "threshold":   0.72,
    })


@app.route("/api/kpis")
def api_kpis():
    """Ritorna i KPI di business calcolati dal gestionale."""
    db = {"clienti": {}, "ordini": [], "fatture": [], "pagamenti": []}
    db_path = BASE_DIR / "data" / "db.json"
    if db_path.exists():
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)

    fatturato = sum(ft.get("totale", 0) for ft in db.get("fatture", []))
    totale_pag = sum(p.get("importo", 0) for p in db.get("pagamenti", []))
    in_revisione = _count_json(REVIEW_QUEUE_DIR)

    return jsonify({
        "fatturato":       fatturato,
        "ordini":          len(db.get("ordini", [])),
        "clienti":         len(db.get("clienti", {})),
        "pagamenti":       totale_pag,
        "in_revisione":    in_revisione,
        "n_fatture":       len(db.get("fatture", [])),
    })


# ============================================================
# ROUTES — reset gestionale e storico cicli
# ============================================================

@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Svuota db, cartelle output e live_state. Conserva history.json."""
    if _is_agent_running or _loop_active:
        return jsonify({"error": "Impossibile resettare mentre l'agente e' in esecuzione"}), 409

    db_path = BASE_DIR / "data" / "db.json"
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump({"clienti": {}, "ordini": [], "fatture": [], "pagamenti": []},
                  f, ensure_ascii=False, indent=2)

    for folder in [
        BASE_DIR / "production_queue",
        BASE_DIR / "processed",
        BASE_DIR / "review_queue",
        BASE_DIR / "invoices" / "drafts",
        BASE_DIR / "invoices" / "sent",
        BASE_DIR / "inbox",
        BASE_DIR / "payments",
    ]:
        folder.mkdir(parents=True, exist_ok=True)
        for fj in folder.glob("*.json"):
            fj.unlink(missing_ok=True)

    live_path = BASE_DIR / "data" / "live_state.json"
    with open(live_path, "w", encoding="utf-8") as f:
        json.dump({"cycle_active": False, "active_step": 0,
                   "current_item": "", "step_results": {}, "ai_mode": False}, f)

    return jsonify({"status": "ok"})


@app.route("/api/history")
def api_history():
    """Ritorna la lista dei cicli completati (storico persistente)."""
    history_path = BASE_DIR / "data" / "history.json"
    if not history_path.exists():
        return jsonify({"cycles": [], "count": 0})
    with open(history_path, "r", encoding="utf-8") as f:
        cycles = json.load(f)
    return jsonify({"cycles": cycles, "count": len(cycles)})


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":
    print("=" * 52)
    print("  Agent Sim Dashboard")
    print("  Apri: http://localhost:5000")
    print("  Ctrl+C per fermare")
    print("=" * 52)
    app.run(debug=False, port=5000, threaded=True, use_reloader=False)
