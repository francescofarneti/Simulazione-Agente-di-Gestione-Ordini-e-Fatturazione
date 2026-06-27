#!/usr/bin/env python3
"""
Script di seed: popola inbox/ e payments/ con 3 scenari di test realistici.
Eseguire con: python seed.py
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
INBOX    = BASE_DIR / "inbox"
PAYMENTS = BASE_DIR / "payments"


def crea_mail_techstart() -> dict:
    """Scenario 1: TechStart Srl ordina servizi di consulenza IT."""
    return {
        "id":        "mail_001",
        "timestamp": datetime.now().isoformat(),
        "from":      "acquisti@techstart.it",
        "from_name": "TechStart Srl",
        "subject":   "Richiesta ordine servizi consulenza IT",
        "body": (
            "Buongiorno,\n"
            "siamo interessati ad acquistare i seguenti servizi di consulenza IT.\n"
            "Si prega di emettere fattura intestata a TechStart Srl, P.IVA 01234567890.\n"
            "Modalità di pagamento: bonifico bancario a 30 giorni.\n"
            "Cordiali saluti,\nUfficio Acquisti — TechStart Srl"
        ),
        "attachment": {
            "tipo":    "ordine",
            "cliente": "TechStart Srl",
            "prodotti": [
                {
                    "nome":              "Consulenza IT — Setup infrastruttura cloud",
                    "quantita":          3,
                    "prezzo_unitario":   500.00
                },
                {
                    "nome":              "Consulenza IT — Analisi dei requisiti",
                    "quantita":          1,
                    "prezzo_unitario":   350.00
                }
            ],
            "totale": 1850.00,
            "note":   "P.IVA 01234567890 — Consegna report entro 15gg"
        }
    }


def crea_mail_makerlab() -> dict:
    """Scenario 2: MakerLab SpA ordina componenti elettronici (prodotti fisici)."""
    return {
        "id":        "mail_002",
        "timestamp": datetime.now().isoformat(),
        "from":      "ordini@makerlab.it",
        "from_name": "MakerLab SpA",
        "subject":   "Ordine acquisto componenti elettronici",
        "body": (
            "Gentili Signori,\n"
            "in allegato trovate il nostro ordine per componenti elettronici.\n"
            "Siamo disponibili per qualsiasi chiarimento tecnico.\n"
            "Distinti saluti,\nMakerLab SpA — Ufficio Approvvigionamenti"
        ),
        "attachment": {
            "tipo":    "ordine",
            "cliente": "MakerLab SpA",
            "prodotti": [
                {
                    "nome":            "Arduino Mega 2560",
                    "quantita":        10,
                    "prezzo_unitario": 25.00
                },
                {
                    "nome":            "Raspberry Pi 4 Model B (4 GB)",
                    "quantita":        5,
                    "prezzo_unitario": 75.00
                },
                {
                    "nome":            "Kit sensori IoT assortiti",
                    "quantita":        2,
                    "prezzo_unitario": 89.50
                }
            ],
            "totale": 804.00,
            "note":   "P.IVA 09876543210 — Consegna presso sede legale, Milano"
        }
    }


def crea_pagamento_freelancexyz() -> dict:
    """
    Scenario 3: FreelanceXYZ ha già effettuato un pagamento.
    Il file va direttamente in payments/ (non in inbox/) — l'agente lo deve categorizzare.
    """
    return {
        "id":                  "pay_001",
        "timestamp":           datetime.now().isoformat(),
        "from":                "pagamenti@freelancexyz.it",
        "from_name":           "FreelanceXYZ",
        "importo":             800.00,
        "descrizione":         "Pagamento per servizi di consulenza grafica e sviluppo web — Giugno 2026",
        "tipo":                "consulenza",
        "riferimento_fattura": "INV-2026-PREV-042",
        "metodo_pagamento":    "bonifico"
    }


def main():
    print("[SEED] Generazione dati di test in corso...")

    # Scenario 1 — TechStart Srl → inbox/
    mail1 = crea_mail_techstart()
    dest1 = INBOX / f"{mail1['id']}.json"
    with open(dest1, "w", encoding="utf-8") as f:
        json.dump(mail1, f, ensure_ascii=False, indent=2)
    print(f"[SEED]  OK inbox/{dest1.name}  - TechStart Srl (consulenza IT, EUR 1850)")

    # Scenario 2 — MakerLab SpA → inbox/
    mail2 = crea_mail_makerlab()
    dest2 = INBOX / f"{mail2['id']}.json"
    with open(dest2, "w", encoding="utf-8") as f:
        json.dump(mail2, f, ensure_ascii=False, indent=2)
    print(f"[SEED]  OK inbox/{dest2.name}  - MakerLab SpA (componenti elettronici, EUR 804)")

    # Scenario 3 — FreelanceXYZ → payments/
    pay = crea_pagamento_freelancexyz()
    dest3 = PAYMENTS / f"{pay['id']}.json"
    with open(dest3, "w", encoding="utf-8") as f:
        json.dump(pay, f, ensure_ascii=False, indent=2)
    print(f"[SEED]  OK payments/{dest3.name} - FreelanceXYZ (pagamento da categorizzare, EUR 800)")

    print("\n[SEED] Pronto. Avvia il sistema con:")
    print("         python agent.py    # ciclo singolo (test manuale)")
    print("         python watcher.py  # loop autonomo ogni 60s")


if __name__ == "__main__":
    main()
