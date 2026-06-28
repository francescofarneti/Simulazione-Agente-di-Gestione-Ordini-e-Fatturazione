#!/usr/bin/env python3
"""
Agente principale di gestione ordini e fatturazione simulata.
Esegue un ciclo completo di elaborazione e termina.
Invocabile direttamente (python agent.py) o da app.py.

Modalità duale automatica:
  - Se ANTHROPIC_API_KEY è impostata -> modalità AI (Claude Haiku via Anthropic SDK)
  - Altrimenti -> modalità rule-based (keyword matching + allegati strutturati)
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
REVIEW_QUEUE     = BASE_DIR / "review_queue"
LOGS             = BASE_DIR / "logs"
DB_PATH          = BASE_DIR / "data" / "db.json"
CATEGORIES_PATH  = BASE_DIR / "data" / "categories.json"
LIVE_STATE_PATH  = BASE_DIR / "data" / "live_state.json"

# ---- Modalità AI automatica ----
USE_AI = bool(os.getenv("ANTHROPIC_API_KEY"))
CONFIDENCE_THRESHOLD = 0.72
AI_MODEL = "claude-haiku-4-5-20251001"

if USE_AI:
    try:
        import anthropic as _anthropic
    except ImportError:
        USE_AI = False

_log_file = None


# ============================================================
# LOGGER
# ============================================================

def init_logger():
    global _log_file
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = open(LOGS / f"{ts}.log", "w", encoding="utf-8")
    mode_tag = "[AI]" if USE_AI else "[RULE-BASED]"
    log(f"=== Sessione avviata: {ts} {mode_tag} ===")


def log(msg: str):
    riga = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(riga)
    if _log_file and not _log_file.closed:
        _log_file.write(riga + "\n")
        _log_file.flush()


# ============================================================
# LIVE STATE
# ============================================================

def reset_live_state():
    _save_live({
        "cycle_active": True, "active_step": 0,
        "current_item": "", "step_results": {},
        "ai_mode": USE_AI,
    })


def _save_live(state: dict):
    try:
        with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def report_step(step_id: int, data: dict, item_label: str = ""):
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
# FUNZIONI INTELLIGENTI -DUAL MODE
# ============================================================

def _ai_client():
    return _anthropic.Anthropic()


def riconosci_tipo_mail(mail: dict) -> dict:
    """
    Classifica una mail in: 'ordine', 'info', 'altro'.
    Ritorna {"tipo": str, "confidence": float, "reasoning": str}.
    """
    if USE_AI:
        try:
            client = _ai_client()
            testo = f"Oggetto: {mail.get('subject', '')}\nCorpo: {mail.get('body', '')}"
            response = client.messages.create(
                model=AI_MODEL,
                max_tokens=256,
                tools=[{
                    "name": "classifica_mail",
                    "description": "Classifica il tipo di una mail aziendale ricevuta.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "tipo": {
                                "type": "string",
                                "enum": ["ordine", "info", "altro"],
                                "description": "Tipo: 'ordine' se richiesta d'acquisto, 'info' se informazione, 'altro' altrimenti."
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidenza della classificazione, da 0.0 a 1.0."
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Breve spiegazione del ragionamento in italiano (max 1 frase)."
                            }
                        },
                        "required": ["tipo", "confidence", "reasoning"]
                    }
                }],
                tool_choice={"type": "tool", "name": "classifica_mail"},
                messages=[{
                    "role": "user",
                    "content": (
                        "Classifica questa mail aziendale e indica confidenza e ragionamento:\n\n"
                        + testo
                    )
                }]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "classifica_mail":
                    return block.input
        except Exception as e:
            log(f"[WARN] AI classificazione fallita: {e} -fallback rule-based")

    # Rule-based fallback
    if mail.get("attachment", {}).get("tipo") == "ordine":
        tipo = "ordine"
    else:
        testo = (mail.get("subject", "") + " " + mail.get("body", "")).lower()
        parole_chiave = ["ordine", "richiesta", "acquisto", "commissione", "fornitura", "preventivo"]
        tipo = "ordine" if any(p in testo for p in parole_chiave) else "altro"
    return {"tipo": tipo, "confidence": 1.0, "reasoning": "Classificazione rule-based da keyword"}


def estrai_dati_ordine(mail: dict) -> dict:
    """
    Estrae i dati strutturati dell'ordine dalla mail.
    Ritorna il dict ordine + campi aggiuntivi: confidence, reasoning.
    """
    if USE_AI:
        try:
            client = _ai_client()
            response = client.messages.create(
                model=AI_MODEL,
                max_tokens=1024,
                tools=[{
                    "name": "estrai_ordine",
                    "description": "Estrae i dati strutturati di un ordine da una mail aziendale italiana.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "cliente": {
                                "type": "string",
                                "description": "Nome del cliente o azienda"
                            },
                            "email_cliente": {
                                "type": "string",
                                "description": "Email del cliente per la fattura"
                            },
                            "prodotti": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "nome":            {"type": "string"},
                                        "quantita":        {"type": "number"},
                                        "prezzo_unitario": {"type": "number"}
                                    },
                                    "required": ["nome", "quantita", "prezzo_unitario"]
                                },
                                "description": "Lista prodotti/servizi ordinati"
                            },
                            "totale": {
                                "type": "number",
                                "description": "Totale imponibile EUR (calcola se non esplicitato)"
                            },
                            "note": {
                                "type": "string",
                                "description": "Note aggiuntive (P.IVA, condizioni, tempi)"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidenza dell'estrazione da 0.0 a 1.0"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Breve spiegazione in italiano (max 1 frase)"
                            }
                        },
                        "required": ["cliente", "email_cliente", "prodotti", "totale",
                                     "note", "confidence", "reasoning"]
                    }
                }],
                tool_choice={"type": "tool", "name": "estrai_ordine"},
                messages=[{
                    "role": "user",
                    "content": (
                        "Estrai i dati dell'ordine da questa mail aziendale italiana. "
                        "Calcola il totale se non esplicito (somma quantita * prezzo_unitario).\n\n"
                        f"Mail:\n{json.dumps(mail, ensure_ascii=False, indent=2)}"
                    )
                }]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "estrai_ordine":
                    result = dict(block.input)
                    result["mail_id"] = mail.get("id", "")
                    return result
        except Exception as e:
            log(f"[WARN] AI estrazione fallita: {e} -fallback rule-based")

    # Rule-based fallback
    att = mail.get("attachment", {})
    note = att.get("note", "")
    if not att.get("prodotti"):
        note = "[Dati strutturati assenti -abilita AI per estrazione automatica da testo libero]"
    return {
        "cliente":       att.get("cliente") or mail.get("from_name", "Sconosciuto"),
        "email_cliente": att.get("email_cliente") or mail.get("from", ""),
        "prodotti":      att.get("prodotti", []),
        "totale":        float(att.get("totale", 0.0)),
        "note":          note,
        "mail_id":       mail.get("id", ""),
        "confidence":    1.0,
        "reasoning":     "Estrazione rule-based da allegato strutturato",
    }


def genera_testo_fattura(ordine: dict, id_fattura: str) -> dict:
    """
    Produce il testo della fattura.
    Ritorna {"testo": str, "confidence": float, "reasoning": str}.
    """
    if USE_AI:
        try:
            client = _ai_client()
            response = client.messages.create(
                model=AI_MODEL,
                max_tokens=1200,
                tools=[{
                    "name": "genera_fattura",
                    "description": "Genera il testo di una fattura professionale italiana.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "testo": {
                                "type": "string",
                                "description": "Testo completo della fattura formattato in ASCII"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidenza da 0.0 a 1.0"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Breve nota sulla generazione (max 1 frase)"
                            }
                        },
                        "required": ["testo", "confidence", "reasoning"]
                    }
                }],
                tool_choice={"type": "tool", "name": "genera_fattura"},
                messages=[{
                    "role": "user",
                    "content": (
                        f"Genera una fattura professionale italiana.\n"
                        f"ID Fattura: {id_fattura}\n"
                        f"Data: {datetime.now().strftime('%d/%m/%Y')}\n"
                        f"Dati ordine:\n{json.dumps(ordine, ensure_ascii=False, indent=2)}"
                    )
                }]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "genera_fattura":
                    return block.input
        except Exception as e:
            log(f"[WARN] AI generazione fattura fallita: {e} -fallback template")

    # Template fallback
    data = datetime.now().strftime("%d/%m/%Y")
    righe = ""
    for p in ordine.get("prodotti", []):
        sub = p["quantita"] * p["prezzo_unitario"]
        righe += f"  {p['nome'][:44]:<44} {p['quantita']:>3} x EUR{p['prezzo_unitario']:>8.2f} = EUR{sub:>9.2f}\n"
    imponibile   = ordine["totale"]
    iva          = imponibile * 0.22
    totale_ivato = imponibile + iva
    testo = (
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
    return {"testo": testo, "confidence": 1.0, "reasoning": "Generazione da template strutturato"}


def categorizza_pagamento(pagamento: dict) -> dict:
    """
    Assegna una categoria al pagamento.
    Ritorna {"categoria": str, "confidence": float, "reasoning": str}.
    """
    if USE_AI:
        try:
            client = _ai_client()
            response = client.messages.create(
                model=AI_MODEL,
                max_tokens=256,
                tools=[{
                    "name": "categorizza_pagamento",
                    "description": "Categorizza un pagamento aziendale ricevuto.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "categoria": {
                                "type": "string",
                                "enum": ["servizi", "prodotti", "ricorrente", "altro"],
                                "description": "Categoria del pagamento"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidenza da 0.0 a 1.0"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Breve spiegazione in italiano (max 1 frase)"
                            }
                        },
                        "required": ["categoria", "confidence", "reasoning"]
                    }
                }],
                tool_choice={"type": "tool", "name": "categorizza_pagamento"},
                messages=[{
                    "role": "user",
                    "content": (
                        "Categorizza questo pagamento aziendale italiano:\n\n"
                        + json.dumps(pagamento, ensure_ascii=False, indent=2)
                    )
                }]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "categorizza_pagamento":
                    return block.input
        except Exception as e:
            log(f"[WARN] AI categorizzazione fallita: {e} -fallback rule-based")

    # Rule-based fallback
    categorie = carica_categorie()
    testo = (pagamento.get("descrizione", "") + " " + pagamento.get("tipo", "")).lower()
    for cat, keywords in categorie.items():
        if keywords and any(kw in testo for kw in keywords):
            return {"categoria": cat, "confidence": 1.0, "reasoning": "Categorizzazione rule-based da keyword"}
    return {"categoria": "altro", "confidence": 1.0, "reasoning": "Nessuna keyword corrispondente trovata"}


# ============================================================
# REVIEW QUEUE
# ============================================================

def invia_review_queue(mail: dict, ai_result: dict, tipo_check: str = "classificazione") -> str:
    """Salva un item nella coda di revisione umana per bassa confidenza AI."""
    REVIEW_QUEUE.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    item_id = f"rq_{ts}_{mail.get('id', 'unknown')}"
    item = {
        "id":         item_id,
        "timestamp":  datetime.now().isoformat(),
        "tipo_check": tipo_check,
        "mail":       mail,
        "ai_result":  ai_result,
        "stato":      "in_attesa",
    }
    with open(REVIEW_QUEUE / f"{item_id}.json", "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
    log(
        f"[REVIEW] '{mail.get('subject', 'N/A')}' -> coda revisione umana "
        f"(confidence: {ai_result.get('confidence', 0):.0%}, "
        f"AI suggerisce: {ai_result.get('tipo', ai_result.get('categoria', '?'))})"
    )
    return item_id


# ============================================================
# STEP DEL FLUSSO PRINCIPALE
# ============================================================

def step1_leggi_inbox() -> list:
    mail_list = []
    for f in sorted(INBOX.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            mail_list.append((f, json.load(fp)))
    log(f"[STEP 1] Trovate {len(mail_list)} mail in inbox/")
    report_step(1, {
        "trovate":  len(mail_list),
        "ai_mode":  USE_AI,
        "mails": [
            {
                "id":           m.get("id", f.name),
                "from_name":    m.get("from_name", m.get("from", "?")),
                "from":         m.get("from", ""),
                "subject":      m.get("subject", "N/A"),
                "timestamp":    m.get("timestamp", ""),
                "n_prodotti":   len(m.get("attachment", {}).get("prodotti", [])),
                "totale":       m.get("attachment", {}).get("totale", 0),
                "ha_attachment": bool(m.get("attachment", {}).get("prodotti")),
            }
            for f, m in mail_list
        ]
    })
    return mail_list


def step2_riconosci_ordine(mail: dict) -> dict:
    """
    Step 2: Classifica la mail.
    Ritorna {"action": "process"|"skip"|"review"} con campi aggiuntivi.
    """
    # Se approvata manualmente dalla review queue, bypassa la classificazione
    if mail.get("_approved"):
        log(f"[STEP 2] '{mail.get('subject', 'N/A')}' -approvata da operatore umano")
        report_step(2, {
            "subject":        mail.get("subject", ""),
            "from_name":      mail.get("from_name", mail.get("from", "")),
            "from":           mail.get("from", ""),
            "body_preview":   mail.get("body", "")[:300],
            "tipo":           "ordine",
            "is_ordine":      True,
            "confidence":     1.0,
            "reasoning":      "Approvato manualmente da operatore umano",
            "ai_mode":        USE_AI,
            "needs_review":   False,
            "human_approved": True,
        }, item_label=f"Mail: {mail.get('from_name', mail.get('from', ''))}")
        return {"action": "process", "confidence": 1.0}

    result     = riconosci_tipo_mail(mail)
    tipo       = result.get("tipo", "altro")
    confidence = float(result.get("confidence", 1.0))
    reasoning  = result.get("reasoning", "")

    log(
        f"[STEP 2] '{mail.get('subject', 'N/A')}' -> {tipo} "
        f"({'AI' if USE_AI else 'rule-based'}, confidence: {confidence:.0%})"
    )

    needs_review = USE_AI and confidence < CONFIDENCE_THRESHOLD
    if needs_review:
        invia_review_queue(mail, result, "classificazione")

    report_step(2, {
        "subject":      mail.get("subject", ""),
        "from_name":    mail.get("from_name", mail.get("from", "")),
        "from":         mail.get("from", ""),
        "body_preview": mail.get("body", "")[:300],
        "tipo":         tipo,
        "is_ordine":    tipo == "ordine",
        "confidence":   confidence,
        "reasoning":    reasoning,
        "ai_mode":      USE_AI,
        "needs_review": needs_review,
    }, item_label=f"Mail: {mail.get('from_name', mail.get('from', ''))}")

    if needs_review:
        return {"action": "review", "confidence": confidence}
    if tipo == "ordine":
        return {"action": "process", "confidence": confidence}
    return {"action": "skip"}


def step3_estrai_dati(mail: dict) -> dict:
    dati       = estrai_dati_ordine(mail)
    confidence = float(dati.get("confidence", 1.0))
    reasoning  = dati.get("reasoning", "")
    log(
        f"[STEP 3] Estratto -Cliente: {dati['cliente']} | "
        f"Prodotti: {len(dati['prodotti'])} voci | "
        f"Totale: EUR {dati['totale']:.2f} "
        f"({'AI' if USE_AI else 'rule-based'}, confidence: {confidence:.0%})"
    )
    report_step(3, {
        "cliente":       dati["cliente"],
        "email_cliente": dati["email_cliente"],
        "prodotti":      dati["prodotti"],
        "totale":        dati["totale"],
        "note":          dati.get("note", ""),
        "confidence":    confidence,
        "reasoning":     reasoning,
        "ai_mode":       USE_AI,
    })
    return dati


def step4_invia_produzione(ordine: dict, id_ordine: str):
    clean = {k: v for k, v in ordine.items() if k not in ("confidence", "reasoning")}
    record = {"id_ordine": id_ordine, "timestamp": datetime.now().isoformat(),
              "stato": "in_lavorazione", **clean}
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
    result     = genera_testo_fattura(ordine, id_fattura)
    testo      = result.get("testo", "")
    confidence = float(result.get("confidence", 1.0))
    reasoning  = result.get("reasoning", "")

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
        "confidence":    confidence,
        "reasoning":     reasoning,
        "ai_mode":       USE_AI,
    })
    return fattura


def step6_invia_fattura(fattura: dict):
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
    result     = categorizza_pagamento(pagamento)
    categoria  = result.get("categoria", "altro")
    confidence = float(result.get("confidence", 1.0))
    reasoning  = result.get("reasoning", "")
    mittente   = pagamento.get("from_name") or pagamento.get("from", "N/A")
    log(
        f"[STEP 8] Pagamento '{pagamento.get('id', 'N/A')}' "
        f"da {mittente} (EUR {pagamento.get('importo', 0):.2f}) "
        f"-> {categoria} ({'AI' if USE_AI else 'rule-based'}, confidence: {confidence:.0%})"
    )
    report_step(8, {
        "id":          pagamento.get("id", ""),
        "from_name":   pagamento.get("from_name", pagamento.get("from", "")),
        "importo":     pagamento.get("importo", 0),
        "descrizione": pagamento.get("descrizione", ""),
        "tipo_orig":   pagamento.get("tipo", ""),
        "categoria":   categoria,
        "confidence":  confidence,
        "reasoning":   reasoning,
        "ai_mode":     USE_AI,
    }, item_label=f"Pagamento: {mittente}")
    return categoria


def step9_registra_nel_db(
    ordine: dict = None, fattura: dict = None,
    pagamento: dict = None, categoria: str = None, id_ordine: str = None,
):
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
        aggiornamenti.append({"tipo": "ordine", "id": id_ordine,
                               "cliente": ordine["cliente"], "totale": ordine["totale"]})
        log(f"[STEP 9] Ordine {id_ordine} registrato nel gestionale")

    if fattura:
        db["fatture"].append({
            "id_fattura": fattura["id_fattura"], "cliente": fattura["cliente"],
            "totale": fattura["totale"], "stato": fattura["stato"],
            "timestamp": datetime.now().isoformat(),
        })
        aggiornamenti.append({"tipo": "fattura", "id": fattura["id_fattura"],
                               "cliente": fattura["cliente"], "totale": fattura["totale"]})
        log(f"[STEP 9] Fattura {fattura['id_fattura']} registrata nel gestionale")

    if pagamento and categoria:
        db["pagamenti"].append({
            "id_pagamento":        pagamento.get("id", ""),
            "from":                pagamento.get("from", ""),
            "from_name":           pagamento.get("from_name", ""),
            "importo":             pagamento.get("importo", 0.0),
            "categoria":           categoria,
            "riferimento_fattura": pagamento.get("riferimento_fattura", ""),
            "timestamp":           datetime.now().isoformat(),
        })
        aggiornamenti.append({"tipo": "pagamento", "id": pagamento.get("id", ""),
                               "importo": pagamento.get("importo", 0), "categoria": categoria})
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
    dest = PROCESSED / src.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    log(f"[CLEANUP] {etichetta} '{src.name}' spostato in processed/")


def _salva_history(state: dict, stats: dict):
    """Appende il ciclo completato alla storia persistente (data/history.json)."""
    history_path = BASE_DIR / "data" / "history.json"
    history = []
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    entry = {
        "cycle_id":    f"cycle_{ts}",
        "timestamp":   datetime.now().isoformat(),
        "ai_mode":     USE_AI,
        "stats":       stats,
        "step_results": state.get("step_results", {}),
    }
    history.insert(0, entry)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history[:200], f, ensure_ascii=False, indent=2)


# ============================================================
# CICLO PRINCIPALE
# ============================================================

def esegui_ciclo():
    for d in [INBOX, PRODUCTION_QUEUE, INVOICES_DRAFTS, INVOICES_SENT,
              PAYMENTS, PROCESSED, REVIEW_QUEUE, LOGS, (BASE_DIR / "data")]:
        d.mkdir(parents=True, exist_ok=True)

    init_logger()
    reset_live_state()
    mode = f"AI ({AI_MODEL})" if USE_AI else "rule-based"
    log(f">>> INIZIO CICLO DI ELABORAZIONE <<< [{mode}]")

    _stats = {"ordini_processati": 0, "fatturato": 0.0,
              "pagamenti": 0, "in_revisione": 0, "errori": 0}

    # ---- Mail ----
    mail_list = step1_leggi_inbox()
    for mail_path, mail in mail_list:
        log(f"\n--- Elaborazione mail: {mail.get('subject', mail_path.name)} ---")
        try:
            step2 = step2_riconosci_ordine(mail)
            if step2["action"] == "review":
                log("Mail in coda di revisione umana -in attesa di approvazione operatore")
                _stats["in_revisione"] += 1
                sposta_processed(mail_path, "Mail (in revisione)")
                continue
            elif step2["action"] == "skip":
                log("Mail non e' un ordine -saltata")
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
            _stats["ordini_processati"] += 1
            _stats["fatturato"] += float(ordine.get("totale", 0))
        except Exception as e:
            log(f"[ERRORE] Mail '{mail_path.name}': {e}")
            _stats["errori"] += 1

    # ---- Pagamenti ----
    pay_list = step7_leggi_pagamenti()
    for pay_path, pagamento in pay_list:
        log(f"\n--- Elaborazione pagamento: {pagamento.get('id', pay_path.name)} ---")
        try:
            categoria = step8_categorizza(pagamento)
            step9_registra_nel_db(pagamento=pagamento, categoria=categoria)
            sposta_processed(pay_path, "Pagamento")
            _stats["pagamenti"] += 1
        except Exception as e:
            log(f"[ERRORE] Pagamento '{pay_path.name}': {e}")
            _stats["errori"] += 1

    try:
        if LIVE_STATE_PATH.exists():
            with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            state["cycle_active"] = False
            state["cycle_stats"]  = _stats
            _save_live(state)
            _salva_history(state, _stats)
    except Exception:
        pass

    log("\n>>> CICLO COMPLETATO <<<")
    if _log_file and not _log_file.closed:
        _log_file.close()


if __name__ == "__main__":
    esegui_ciclo()
