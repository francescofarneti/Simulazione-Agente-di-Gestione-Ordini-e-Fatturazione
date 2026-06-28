#!/usr/bin/env python3
"""
Script di seed: popola inbox/ e payments/ con scenari di test realistici.

Uso:
  python seed.py                      # Scenario standard (consulenza IT + elettronica)
  python seed.py --scenario standard  # Idem
  python seed.py --scenario retail    # Mail informale: abbigliamento (richiede AI)
  python seed.py --scenario manifattura  # Componentistica industriale (richiede AI)
  python seed.py --scenario studio    # Studio legale / servizi professionali (richiede AI)
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
INBOX    = BASE_DIR / "inbox"
PAYMENTS = BASE_DIR / "payments"


# ============================================================
# SCENARI STANDARD — attachment strutturato (funziona anche rule-based)
# ============================================================

def crea_mail_techstart() -> dict:
    """Scenario standard 1: TechStart Srl ordina servizi di consulenza IT."""
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
                {"nome": "Consulenza IT — Setup infrastruttura cloud", "quantita": 3, "prezzo_unitario": 500.00},
                {"nome": "Consulenza IT — Analisi dei requisiti",      "quantita": 1, "prezzo_unitario": 350.00},
            ],
            "totale": 1850.00,
            "note":   "P.IVA 01234567890 — Consegna report entro 15gg"
        }
    }


def crea_mail_makerlab() -> dict:
    """Scenario standard 2: MakerLab SpA ordina componenti elettronici."""
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
                {"nome": "Arduino Mega 2560",              "quantita": 10, "prezzo_unitario": 25.00},
                {"nome": "Raspberry Pi 4 Model B (4 GB)", "quantita": 5,  "prezzo_unitario": 75.00},
                {"nome": "Kit sensori IoT assortiti",      "quantita": 2,  "prezzo_unitario": 89.50},
            ],
            "totale": 804.00,
            "note":   "P.IVA 09876543210 — Consegna presso sede legale, Milano"
        }
    }


def crea_pagamento_freelancexyz() -> dict:
    """Scenario standard 3: FreelanceXYZ pagamento da categorizzare."""
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


# ============================================================
# SCENARI AI — attachment vuoto, estrazione solo da testo libero
# ============================================================

def crea_mail_retail() -> dict:
    """
    Scenario retail: email informale da boutique.
    attachment: {} — l'agente DEVE estrarre tutto dal corpo in linguaggio naturale.
    In modalità rule-based → nessun dato estratto.
    In modalità AI       → cliente, prodotti, prezzi estratti automaticamente.
    """
    return {
        "id":        "mail_retail_001",
        "timestamp": datetime.now().isoformat(),
        "from":      "marta.russo@boutiqueverde.it",
        "from_name": "Marta Russo — Boutique Verde",
        "subject":   "Ordine abbigliamento urgente",
        "body": (
            "Salve,\n"
            "vi scrivo per un ordine urgente che mi serve entro fine settimana.\n"
            "Ho bisogno di 3 paia di jeans slim fit taglia 32 a 59,90 euro l'uno "
            "e 2 felpe con cappuccio taglia M a 45 euro ciascuna.\n"
            "Sono Marta Russo, titolare di Boutique Verde a Rimini.\n"
            "Vi chiedo di fatturare a: Boutique Verde di Marta Russo, "
            "boutiqueverde@rim.it, P.IVA 07654321098.\n"
            "Consegna entro 3 giorni lavorativi se possibile. Grazie mille!\n"
            "Cordiali saluti,\nMarta Russo"
        ),
        "attachment": {}
    }


def crea_mail_manifattura() -> dict:
    """
    Scenario manifattura: ordine componenti industriali con codici articolo.
    attachment: {} — estrazione da testo tecnico con codici e prezzi unitari.
    """
    return {
        "id":        "mail_manifattura_001",
        "timestamp": datetime.now().isoformat(),
        "from":      "ordini@metalmeccanicaxxx.it",
        "from_name": "Metalmeccanica Rossi Srl",
        "subject":   "Richiesta componenti reparto produzione",
        "body": (
            "Spett.le ditta,\n"
            "in riferimento al ns. fabbisogno di componentistica per il reparto produzione,\n"
            "siamo a richiedere i seguenti articoli:\n\n"
            "  - 50 pz viti M8x30 inox DIN 933 (art. VT-M8-030)  € 0,45 cad.\n"
            "  - 100 pz dadi M8 zincati DIN 934 (art. ND-M8-Z)   € 0,22 cad.\n"
            "  - 20 pz rondelle M8 large DIN 125 (art. RD-M8-L)  € 0,18 cad.\n\n"
            "Totale stimato € 48,10 (IVA esclusa).\n"
            "Intestare la fattura a: Metalmeccanica Rossi Srl, Via Industria 14, Brescia.\n"
            "Riferimento acquisti: ufficioacquisti@metalmeccanicaxxx.it — P.IVA 03456789012.\n"
            "In attesa di conferma disponibilità e tempi di consegna.\n"
            "Distinti saluti,\nUfficio Acquisti — Metalmeccanica Rossi Srl"
        ),
        "attachment": {}
    }


def crea_mail_studio() -> dict:
    """
    Scenario studio legale: richiesta servizi professionali con tariffe orarie.
    attachment: {} — estrazione di ore × tariffa dal testo in linguaggio formale.
    """
    return {
        "id":        "mail_studio_001",
        "timestamp": datetime.now().isoformat(),
        "from":      "s.bianchi@studiolegalebianchi.it",
        "from_name": "Studio Legale Bianchi",
        "subject":   "Richiesta servizi professionali",
        "body": (
            "Buongiorno,\n"
            "siamo lo Studio Legale Bianchi di Torino e necessitiamo dei seguenti servizi:\n\n"
            "  1) Revisione contratto di locazione commerciale — 2 ore a € 120/h\n"
            "  2) Consulenza apertura partita IVA forfettaria — 1,5 ore a € 150/h\n"
            "  3) Preparazione dichiarazione IVA trimestrale — 3 ore a € 90/h\n\n"
            "Totale preventivato: € 735,00 (IVA esclusa).\n"
            "Riferimento: avv. Stefano Bianchi.\n"
            "Email di fatturazione: s.bianchi@studiolegalebianchi.it\n"
            "P.IVA: 02345678901\n"
            "Rimaniamo in attesa di conferma e disponibilità.\n"
            "Cordiali saluti,\nStudio Legale Bianchi"
        ),
        "attachment": {}
    }


# ============================================================
# MAIN
# ============================================================

def _scrivi(cartella: Path, nome: str, dati: dict, etichetta: str):
    dest = cartella / nome
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    print(f"[SEED]  OK {cartella.name}/{dest.name}  - {etichetta}")


def main():
    parser = argparse.ArgumentParser(description="Genera dati di test per agent-sim.")
    parser.add_argument(
        "--scenario",
        choices=["standard", "retail", "manifattura", "studio"],
        default="standard",
        help="Scenario da generare (default: standard)"
    )
    args = parser.parse_args()

    print(f"[SEED] Generazione scenario '{args.scenario}' in corso...")

    if args.scenario == "standard":
        m1 = crea_mail_techstart()
        _scrivi(INBOX, f"{m1['id']}.json", m1, "TechStart Srl (consulenza IT, EUR 1850)")
        m2 = crea_mail_makerlab()
        _scrivi(INBOX, f"{m2['id']}.json", m2, "MakerLab SpA (componenti elettronici, EUR 804)")
        pay = crea_pagamento_freelancexyz()
        _scrivi(PAYMENTS, f"{pay['id']}.json", pay, "FreelanceXYZ (pagamento consulenza, EUR 800)")

    elif args.scenario == "retail":
        m = crea_mail_retail()
        _scrivi(INBOX, f"{m['id']}.json", m, "Boutique Verde - ordine abbigliamento [richiede AI]")

    elif args.scenario == "manifattura":
        m = crea_mail_manifattura()
        _scrivi(INBOX, f"{m['id']}.json", m, "Metalmeccanica Rossi - componenti industriali [richiede AI]")

    elif args.scenario == "studio":
        m = crea_mail_studio()
        _scrivi(INBOX, f"{m['id']}.json", m, "Studio Legale Bianchi - servizi professionali [richiede AI]")

    print(f"\n[SEED] Pronto. Avvia il sistema con:")
    print("         python app.py    # Dashboard web  ->  http://localhost:5000")
    print("         python agent.py  # Ciclo singolo da terminale")


if __name__ == "__main__":
    main()
