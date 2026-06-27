#!/usr/bin/env python3
"""
Dashboard web per il sistema agente simulativo.
Avvia con: python app.py
Poi apri:  http://localhost:5000

Dipendenza: pip install flask
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template

BASE_DIR   = Path(__file__).parent
AGENT_PATH = BASE_DIR / "agent.py"
SEED_PATH  = BASE_DIR / "seed.py"
LOGS_DIR   = BASE_DIR / "logs"

app = Flask(__name__)

# ============================================================
# STATO GLOBALE DEL SISTEMA
# ============================================================

_is_agent_running = False   # True mentre subprocess agent.py e' attivo
_loop_active      = False   # True mentre il loop automatico gira
_stop_event       = threading.Event()
_next_run_at      = None    # timestamp UNIX della prossima esecuzione nel loop
_agent_lock       = threading.Lock()


# ============================================================
# FUNZIONI INTERNE
# ============================================================

def _run_agent_blocking():
    """Esegue agent.py come sottoprocesso bloccante. Thread-safe tramite lock."""
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
    """Thread del loop autonomo: esegue l'agente ogni 60s fino a stop."""
    global _loop_active, _next_run_at
    _loop_active = True
    _stop_event.clear()
    try:
        while not _stop_event.is_set():
            _run_agent_blocking()
            if _stop_event.is_set():
                break
            _next_run_at = time.time() + 60
            # Attende 60s ma si sveglia subito se stop_event viene settato
            _stop_event.wait(timeout=60)
    finally:
        _loop_active  = False
        _next_run_at  = None


def _latest_log() -> Path | None:
    """Ritorna il percorso del file di log piu' recente."""
    logs = sorted(LOGS_DIR.glob("*.log"))
    return logs[-1] if logs else None


def _count_json(folder: Path) -> int:
    """Conta i file .json in una cartella."""
    return len(list(folder.glob("*.json")))


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run-once", methods=["POST"])
def api_run_once():
    """Avvia un singolo ciclo dell'agente in un thread separato."""
    if _is_agent_running:
        return jsonify({"error": "Agente gia' in esecuzione"}), 409
    if _loop_active:
        return jsonify({"error": "Loop attivo — fermalo prima di avviare un ciclo singolo"}), 409
    threading.Thread(target=_run_agent_blocking, daemon=True).start()
    return jsonify({"status": "avviato"})


@app.route("/api/start-loop", methods=["POST"])
def api_start_loop():
    """Avvia il loop automatico ogni 60 secondi."""
    if _loop_active:
        return jsonify({"error": "Loop gia' attivo"}), 409
    if _is_agent_running:
        return jsonify({"error": "Agente gia' in esecuzione"}), 409
    threading.Thread(target=_loop_worker, daemon=True).start()
    return jsonify({"status": "loop_avviato"})


@app.route("/api/stop-loop", methods=["POST"])
def api_stop_loop():
    """Invia il segnale di stop al loop (termina dopo il ciclo corrente)."""
    _stop_event.set()
    return jsonify({"status": "stop_richiesto"})


@app.route("/api/seed", methods=["POST"])
def api_seed():
    """Esegue seed.py per rigenerare i dati di test."""
    if _is_agent_running or _loop_active:
        return jsonify({"error": "Impossibile fare seed mentre l'agente e' in esecuzione"}), 409
    result = subprocess.run(
        [sys.executable, str(SEED_PATH)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return jsonify({"status": "ok", "output": result.stdout})


@app.route("/api/status")
def api_status():
    """Ritorna lo stato completo del sistema: flag, conteggi cartelle, snapshot db."""
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
    """Ritorna lo stato live: step attivo e dati raccolti da ogni step."""
    live_path = BASE_DIR / "data" / "live_state.json"
    if not live_path.exists():
        return jsonify({"cycle_active": False, "active_step": 0,
                        "current_item": "", "step_results": {}})
    with open(live_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/logs/stream")
def api_logs_stream():
    """
    Server-Sent Events: trasmette nuove righe di log in tempo reale.
    Il client JS si connette una volta e riceve ogni riga appena scritta.
    """
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
# AVVIO
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Agent Sim Dashboard")
    print("  Apri: http://localhost:5000")
    print("  Ctrl+C per fermare")
    print("=" * 50)
    # use_reloader=False evita che il reloader uccida i thread in background
    app.run(debug=False, port=5000, threaded=True, use_reloader=False)
