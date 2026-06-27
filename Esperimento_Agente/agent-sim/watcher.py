#!/usr/bin/env python3
"""
Watcher: lancia agent.py in loop autonomo ogni 60 secondi.
Avvia con: python watcher.py
Interrompi con: Ctrl+C
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AGENT_PATH         = Path(__file__).parent / "agent.py"
INTERVALLO_SECONDI = 60


def intestazione():
    """Stampa il banner di avvio."""
    print("=" * 55)
    print("  WATCHER — Sistema Agente Ordini e Fatturazione")
    print("=" * 55)
    print(f"  Agente  : {AGENT_PATH}")
    print(f"  Intervallo: ogni {INTERVALLO_SECONDI}s | Ctrl+C per fermare")
    print("=" * 55)
    print()


def esegui_agente(iterazione: int) -> int:
    """
    Invoca agent.py come sottoprocesso e ritorna il returncode.
    L'output dell'agente viene stampato direttamente su console.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[WATCHER] [{ts}] -- Iterazione #{iterazione} --")
    print(f"[WATCHER] Avvio {AGENT_PATH.name}...\n")

    result = subprocess.run(
        [sys.executable, str(AGENT_PATH)],
        # stdout e stderr non catturati: l'agente stampa direttamente
    )

    if result.returncode != 0:
        print(f"\n[WATCHER] ATTENZIONE: agente terminato con errore (returncode={result.returncode})")
    else:
        print(f"\n[WATCHER] Agente completato con successo.")

    return result.returncode


def main():
    """Loop principale del watcher."""
    intestazione()
    iterazione = 0

    while True:
        iterazione += 1
        esegui_agente(iterazione)

        prossima = datetime.now().strftime("%H:%M:%S")
        print(f"[WATCHER] Prossima esecuzione tra {INTERVALLO_SECONDI}s "
              f"(ora corrente: {prossima})")
        time.sleep(INTERVALLO_SECONDI)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WATCHER] Interruzione ricevuta. Watcher fermato.")
        sys.exit(0)
