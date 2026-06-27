#!/usr/bin/env python3
"""
Agente principale di gestione ordini e fatturazione simulata.
Esegue un ciclo completo di elaborazione e termina.
Invocabile direttamente (python agent.py) o da watcher.py / app.py.
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR         = Path(__file__).parent
INBOX            = BASE_DIR / "inbox"
PRODUCTION_QUEUE = BASE_DIR / "production_queue"
INVOICES_DRAFTS  = BASE_DIR / "invoices" / "drafts"
INVOICES_SENT    = BASE_DIR / "invoices" / "sent"
PAYMENTS         = BASE_DIR / "payments"
PROCESSED        = BASE_DIR / "processed"
LOGS             = BASE_DIR / "logs"
DB_PATH          = BASE_DIR / "data" / "db.json"
CATEGORIES_PATH  = BASE_DIR / "data" / "categories.json"
LIVE_STATE_PATH  = BASE_DIR / "data" / "live_state.json"

_log_file = None


# ============================================================
# LOGGER
# ============================================================

def init_logger():
    """Apre il file di log per questa sessione con nome timestamp."""
    global _log_file
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = open(LOGS / f"{ts}.log", "w", encoding="utf-8")
    log(f"=== Sessione avviata: {ts} ===")


def log(msg: str):
    """Scrive su console e su file di log con timestamp."""
    riga = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(riga)
    if _log_file and not _log_file.closed:
        _log_file.write(riga + "\n")
        _log_file.flush()


# ============================================================
# LIVE STATE — dati per la dashboard in tempo reale
# ============================================================

def reset_live_state():
    """Resetta lo stato live all'inizio di ogni ciclo."""
    _save_live({"cycle_active": True, "active_step": 0,
                "current_item": "", "step_results": {}})


def _save_live(state: dict):
    """Scrive live_state.json. Silenziosa in caso di errore."""
    try:
        with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def report_step(step_id: int, data: dict, item_label: str = ""):
    """Aggiorna live_state.json con i dati del passo appena eseguito."""
    try:
        state = {}
        if LIVE_STATE_PATH.exists():
            with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        state["active_step"] = step_id
        if item_label:
            state["current_item"] = item_label
        state.setdefault("step_results", {})[str(step_id)] = data
        _save_live(state)
    except Exception:
        pass


# ============================================================
# ACCESSO AL DB
# ============================================================

def carica_db() -> dict:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def salva_db(db: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def carica_categorie() -> dict:
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def genera_id_ordine() -> str:
    db = carica_db()
    return f"ORD-{datetime.now().year}-{len(db['ordini']) + 1:04d}"


def genera_id_fattura() -> str:
    db = carica_db()
    return f"INV-{datetime.now().year}-{len(db['fatture']) + 1:04d}"


# ============================================================
# FUNZIONI INTELLIGENTI — DUAL MODE: API / rule-based
# ============================================================

def riconosci_tipo_mail(mail: dict) -> str:
    """Classifica una mail in: 'ordine', 'info', 'altro'. Usata allo Step 2."""
    # --- MODALITA' API (decommentare quando si ha ANTHROPIC_API_KEY) ---
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # testo_mail = f"Oggetto: {mail.get('subject', '')}\nCorpo: {mail.get('body', '')}"
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=10,
    #     messages=[{"role": "user", "content":
    #         "Classifica questa mail aziendale. Rispondi SOLO con: ordine, info, altro.\n\n"
    #         + testo_mail}]
    # )
    # return response.content[0].text.strip().lower()
    # --- FINE MODALITA' API ---

    if mail.get("attachment", {}).get("tipo") == "ordine":
        return "ordine"
    testo = (mail.get("subject", "") + " " + mail.get("body", "")).lower()
    parole_chiave = ["ordine", "richiesta", "acquisto", "commissione", "fornitura", "preventivo"]
    return "ordine" if any(p in testo for p in parole_chiave) else "altro"


def estrai_dati_ordine(mail: dict) -> dict:
    """Estrae i dati strutturati dell'ordine dalla mail. Usata allo Step 3."""
    # --- MODALITA' API (decommentare quando si ha ANTHROPIC_API_KEY) ---
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # schema = json.dumps({"cliente":"...","email_cliente":"...","prodotti":[{"nome":"...","quantita":1,"prezzo_unitario":0.0}],"totale":0.0,"note":"..."})
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=600,
    #     messages=[{"role": "user", "content":
    #         f"Estrai i dati dell'ordine. Rispondi SOLO JSON con schema:\n{schema}\n\nMail:\n{json.dumps(mail, ensure_ascii=False)}"}]
    # )
    # return json.loads(response.content[0].text)
    # --- FINE MODALITA' API ---

    att = mail.get("attachment", {})
    return {
        "cliente":       att.get("cliente") or mail.get("from_name", "Sconosciuto"),
        "email_cliente": mail.get("from", ""),
        "prodotti":      att.get("prodotti", []),
        "totale":        float(att.get("totale", 0.0)),
        "note":          att.get("note", ""),
        "mail_id":       mail.get("id", ""),
    }


def genera_testo_fattura(ordine: dict, id_fattura: str) -> str:
    """Produce il testo human-readable della fattura. Usata allo Step 5."""
    # --- MODALITA' API (decommentare quando si ha ANTHROPIC_API_KEY) ---
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=800,
    #     messages=[{"role": "user", "content":
    #         f"Genera fattura professionale italiana.\nID: {id_fattura}\nData: {datetime.now().strftime('%d/%m/%Y')}\n"
    #         f"Ordine:\n{json.dumps(ordine, ensure_ascii=False, indent=2)}"}]
    # )
    # return response.content[0].text
    # --- FINE MODALITA' API ---

    data = datetime.now().strftime("%d/%m/%Y")
    righe = ""
    for p in ordine.get("prodotti", []):
        sub = p["quantita"] * p["prezzo_unitario"]
        righe += f"  {p['nome'][:44]:<44} {p['quantita']:>3} x EUR{p['prezzo_unitario']:>8.2f} = EUR{sub:>9.2f}\n"
    imponibile   = ordine["totale"]
    iva          = imponibile * 0.22
    totale_ivato = imponibile + iva
    return (
        f"{'='*62}\n  FATTURA N. {id_fattura}\n{'='*62}\n"
        f"  Data emissione  : {data}\n"
        f"  Cliente         : {ordine['cliente']}\n"
        f"  Email           : {ordine['email_cliente']}\n"
        f"{'='*62}\n  VOCI\n{'-'*62}\n{righe}{'-'*62}\n"
        f"  Totale imponibile         : EUR{imponibile:>9.2f}\n"
        f"  IVA 22%                   : EUR{iva:>9.2f}\n"
        f"  TOTALE DA PAGARE          : EUR{totale_ivato:>9.2f}\n"
        f"{'='*62}\n  Note: {ordine.get('note', '-')}\n"
        f"  Pagamento entro 30 giorni dalla data di emissione.\n{'='*62}\n"
    )


def categorizza_pagamento(pagamento: dict) -> str:
    """Assegna una categoria al pagamento. Usata allo Step 8."""
    # --- MODALITA' API (decommentare quando si ha ANTHROPIC_API_KEY) ---
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=20,
    #     messages=[{"role": "user", "content":
    #         "Categorizza il pagamento. Rispondi SOLO con: servizi, prodotti, ricorrente, altro.\n\n"
    #         f"Pagamento:\n{json.dumps(pagamento, ensure_ascii=False)}"}]
    # )
    # return response.content[0].text.strip().lower()
    # --- FINE MODALITA' API ---

    categorie = carica_categorie()
    testo = (pagamento.get("descrizione", "") + " " + pagamento.get("tipo", "")).lower()
    for cat, keywords in categorie.items():
        if keywords and any(kw in testo for kw in keywords):
            return cat
    return "altro"


# ============================================================
# STEP DEL FLUSSO PRINCIPALE
# ============================================================

def step1_leggi_inbox() -> list:
    """Step 1: Legge tutte le mail .json in inbox/."""
    mail_list = []
    for f in sorted(INBOX.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            mail_list.append((f, json.load(fp)))
    log(f"[STEP 1] Trovate {len(mail_list)} mail in inbox/")

    report_step(1, {
        "trovate": len(mail_list),
        "mails": [
            {
                "id":        m.get("id", f.name),
                "from_name": m.get("from_name", m.get("from", "?")),
                "from":      m.get("from", ""),
                "subject":   m.get("subject", "N/A"),
                "timestamp": m.get("timestamp", ""),
                "n_prodotti": len(m.get("attachment", {}).get("prodotti", [])),
                "totale":    m.get("attachment", {}).get("totale", 0),
            }
            for f, m in mail_list
        ]
    })
    return mail_list


def step2_riconosci_ordine(mail: dict) -> bool:
    """Step 2: Verifica se la mail e' una richiesta d'ordine."""
    tipo = riconosci_tipo_mail(mail)
    log(f"[STEP 2] '{mail.get('subject', 'N/A')}' classificata come: {tipo}")

    report_step(2, {
        "subject":      mail.get("subject", ""),
        "from_name":    mail.get("from_name", mail.get("from", "")),
        "from":         mail.get("from", ""),
        "body_preview": mail.get("body", "")[:300],
        "tipo":         tipo,
        "is_ordine":    tipo == "ordine",
    }, item_label=f"Mail: {mail.get('from_name', mail.get('from', ''))}")

    return tipo == "ordine"


def step3_estrai_dati(mail: dict) -> dict:
    """Step 3: Estrae i dati strutturati dell'ordine dalla mail."""
    dati = estrai_dati_ordine(mail)
    log(
        f"[STEP 3] Estratto — Cliente: {dati['cliente']} | "
        f"Prodotti: {len(dati['prodotti'])} voci | "
        f"Totale: EUR {dati['totale']:.2f}"
    )
    report_step(3, {
        "cliente":       dati["cliente"],
        "email_cliente": dati["email_cliente"],
        "prodotti":      dati["prodotti"],
        "totale":        dati["totale"],
        "note":          dati.get("note", ""),
    })
    return dati


def step4_invia_produzione(ordine: dict, id_ordine: str):
    """Step 4: Scrive il file ordine in production_queue/."""
    record = {"id_ordine": id_ordine, "timestamp": datetime.now().isoformat(),
              "stato": "in_lavorazione", **ordine}
    dest = PRODUCTION_QUEUE / f"{id_ordine}.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    log(f"[STEP 4] Ordine {id_ordine} inoltrato alla produzione -> {dest.name}")

    report_step(4, {
        "id_ordine": id_ordine,
        "cliente":   ordine["cliente"],
        "prodotti":  ordine["prodotti"],
        "totale":    ordine["totale"],
        "file":      dest.name,
        "stato":     "in_lavorazione",
    })


def step5_genera_fattura(ordine: dict, id_fattura: str) -> dict:
    """Step 5: Genera la bozza fattura e la salva in invoices/drafts/."""
    testo = genera_testo_fattura(ordine, id_fattura)
    fattura = {
        "id_fattura":          id_fattura,
        "timestamp_creazione": datetime.now().isoformat(),
        "cliente":             ordine["cliente"],
        "email_cliente":       ordine["email_cliente"],
        "totale":              ordine["totale"],
        "prodotti":            ordine["prodotti"],
        "stato":               "bozza",
        "testo_fattura":       testo,
    }
    dest = INVOICES_DRAFTS / f"{id_fattura}.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(fattura, f, ensure_ascii=False, indent=2)
    log(f"[STEP 5] Bozza fattura {id_fattura} creata -> {dest.name}")

    report_step(5, {
        "id_fattura":    id_fattura,
        "cliente":       fattura["cliente"],
        "email_cliente": fattura["email_cliente"],
        "totale":        fattura["totale"],
        "prodotti":      fattura["prodotti"],
        "testo_fattura": testo,
    })
    return fattura


def step6_invia_fattura(fattura: dict):
    """Step 6: 'Invia' la fattura spostandola da drafts/ a sent/."""
    id_fattura = fattura["id_fattura"]
    src  = INVOICES_DRAFTS / f"{id_fattura}.json"
    dest = INVOICES_SENT   / f"{id_fattura}.json"
    fattura["stato"]           = "inviata"
    fattura["timestamp_invio"] = datetime.now().isoformat()
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(fattura, f, ensure_ascii=False, indent=2)
    src.unlink()
    log(f"[STEP 6] Fattura {id_fattura} 'inviata' a {fattura['cliente']} ({fattura['email_cliente']})")

    report_step(6, {
        "id_fattura":      id_fattura,
        "cliente":         fattura["cliente"],
        "email_cliente":   fattura["email_cliente"],
        "totale":          fattura["totale"],
        "timestamp_invio": fattura["timestamp_invio"],
    })


def step7_leggi_pagamenti() -> list:
    """Step 7: Legge tutti i pagamenti .json in payments/."""
    pay_list = []
    for f in sorted(PAYMENTS.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            pay_list.append((f, json.load(fp)))
    log(f"[STEP 7] Trovati {len(pay_list)} pagamenti in payments/")

    report_step(7, {
        "trovati": len(pay_list),
        "pagamenti": [
            {
                "id":          p.get("id", f.name),
                "from_name":   p.get("from_name", p.get("from", "?")),
                "importo":     p.get("importo", 0),
                "descrizione": p.get("descrizione", ""),
                "metodo":      p.get("metodo_pagamento", "N/A"),
            }
            for f, p in pay_list
        ]
    })
    return pay_list


def step8_categorizza(pagamento: dict) -> str:
    """Step 8: Categorizza il pagamento ricevuto."""
    categoria = categorizza_pagamento(pagamento)
    mittente  = pagamento.get("from_name") or pagamento.get("from", "N/A")
    log(
        f"[STEP 8] Pagamento '{pagamento.get('id', 'N/A')}' "
        f"da {mittente} (EUR {pagamento.get('importo', 0):.2f}) "
        f"-> categoria: {categoria}"
    )
    report_step(8, {
        "id":          pagamento.get("id", ""),
        "from_name":   pagamento.get("from_name", pagamento.get("from", "")),
        "importo":     pagamento.get("importo", 0),
        "descrizione": pagamento.get("descrizione", ""),
        "tipo_orig":   pagamento.get("tipo", ""),
        "categoria":   categoria,
    }, item_label=f"Pagamento: {mittente}")
    return categoria


def step9_registra_nel_db(
    ordine: dict = None, fattura: dict = None,
    pagamento: dict = None, categoria: str = None, id_ordine: str = None,
):
    """Step 9: Aggiorna il gestionale db.json."""
    db = carica_db()
    aggiornamenti = []

    if ordine and id_ordine:
        email = ordine.get("email_cliente", "")
        if email and email not in db["clienti"]:
            db["clienti"][email] = {
                "nome": ordine["cliente"], "email": email,
                "primo_ordine": datetime.now().isoformat(),
            }
        db["ordini"].append({
            "id_ordine": id_ordine, "cliente": ordine["cliente"],
            "email_cliente": email, "totale": ordine["totale"],
            "timestamp": datetime.now().isoformat(), "stato": "processato",
        })
        aggiornamenti.append({"tipo": "ordine", "id": id_ordine, "cliente": ordine["cliente"], "totale": ordine["totale"]})
        log(f"[STEP 9] Ordine {id_ordine} registrato nel gestionale")

    if fattura:
        db["fatture"].append({
            "id_fattura": fattura["id_fattura"], "cliente": fattura["cliente"],
            "totale": fattura["totale"], "stato": fattura["stato"],
            "timestamp": datetime.now().isoformat(),
        })
        aggiornamenti.append({"tipo": "fattura", "id": fattura["id_fattura"], "cliente": fattura["cliente"], "totale": fattura["totale"]})
        log(f"[STEP 9] Fattura {fattura['id_fattura']} registrata nel gestionale")

    if pagamento and categoria:
        db["pagamenti"].append({
            "id_pagamento": pagamento.get("id", ""),
            "from": pagamento.get("from", ""),
            "from_name": pagamento.get("from_name", ""),
            "importo": pagamento.get("importo", 0.0),
            "categoria": categoria,
            "riferimento_fattura": pagamento.get("riferimento_fattura", ""),
            "timestamp": datetime.now().isoformat(),
        })
        aggiornamenti.append({"tipo": "pagamento", "id": pagamento.get("id", ""), "importo": pagamento.get("importo", 0), "categoria": categoria})
        log(f"[STEP 9] Pagamento {pagamento.get('id', '')} registrato con categoria '{categoria}'")

    salva_db(db)
    report_step(9, {
        "aggiornamenti": aggiornamenti,
        "db_totali": {
            "clienti":   len(db.get("clienti", {})),
            "ordini":    len(db.get("ordini", [])),
            "fatture":   len(db.get("fatture", [])),
            "pagamenti": len(db.get("pagamenti", [])),
        }
    })


# ============================================================
# UTILITY
# ============================================================

def sposta_processed(src: Path, etichetta: str = "File"):
    """Sposta un file elaborato in processed/."""
    dest = PROCESSED / src.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    log(f"[CLEANUP] {etichetta} '{src.name}' spostato in processed/")


# ============================================================
# CICLO PRINCIPALE
# ============================================================

def esegui_ciclo():
    """Esegue un ciclo completo: mail in inbox/ + pagamenti in payments/."""
    init_logger()
    reset_live_state()
    log(">>> INIZIO CICLO DI ELABORAZIONE <<<")

    # ---- Mail ----
    mail_list = step1_leggi_inbox()
    for mail_path, mail in mail_list:
        log(f"\n--- Elaborazione mail: {mail.get('subject', mail_path.name)} ---")
        try:
            if not step2_riconosci_ordine(mail):
                log("Mail non e' un ordine — saltata")
                sposta_processed(mail_path, "Mail (non-ordine)")
                continue
            ordine     = step3_estrai_dati(mail)
            id_ordine  = genera_id_ordine()
            id_fattura = genera_id_fattura()
            step4_invia_produzione(ordine, id_ordine)
            fattura = step5_genera_fattura(ordine, id_fattura)
            step6_invia_fattura(fattura)
            step9_registra_nel_db(ordine=ordine, fattura=fattura, id_ordine=id_ordine)
            sposta_processed(mail_path, "Mail")
        except Exception as e:
            log(f"[ERRORE] Mail '{mail_path.name}': {e}")

    # ---- Pagamenti ----
    pay_list = step7_leggi_pagamenti()
    for pay_path, pagamento in pay_list:
        log(f"\n--- Elaborazione pagamento: {pagamento.get('id', pay_path.name)} ---")
        try:
            categoria = step8_categorizza(pagamento)
            step9_registra_nel_db(pagamento=pagamento, categoria=categoria)
            sposta_processed(pay_path, "Pagamento")
        except Exception as e:
            log(f"[ERRORE] Pagamento '{pay_path.name}': {e}")

    # Segna il ciclo come completato nel live state
    try:
        if LIVE_STATE_PATH.exists():
            with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            state["cycle_active"] = False
            _save_live(state)
    except Exception:
        pass

    log("\n>>> CICLO COMPLETATO <<<")
    if _log_file and not _log_file.closed:
        _log_file.close()


if __name__ == "__main__":
    esegui_ciclo()
