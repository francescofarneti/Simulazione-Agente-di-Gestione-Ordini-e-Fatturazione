# Agent Sim — Simulazione Agente di Gestione Ordini e Fatturazione

Un sistema agentico simulativo che replica il flusso di back-office di una piccola azienda: ricezione ordini via email, generazione fatture, registrazione pagamenti. Tutto gira su file locali, senza database reali né connessioni esterne.

---

## Cosa fa

L'agente legge file JSON da cartelle locali che simulano caselle email e conti pagamenti, poi esegue autonomamente 9 step in sequenza:

```
inbox/          →  riconosce se è un ordine
                →  estrae cliente, prodotti, importi
                →  crea l'ordine in production_queue/
                →  genera la fattura in invoices/drafts/
                →  "invia" la fattura (sposta in invoices/sent/)
                →  aggiorna il gestionale db.json

payments/       →  categorizza il pagamento (servizi / prodotti / ricorrente)
                →  registra tutto in db.json
```

Ogni mail elaborata viene spostata in `processed/`. Ogni azione viene loggata in `logs/` con timestamp.

---

## Architettura

```
agent-sim/
├── agent.py            # Agente principale — esegue un ciclo completo
├── watcher.py          # Loop autonomo — rilancia agent.py ogni 60 secondi
├── seed.py             # Genera dati di test realistici
├── app.py              # Dashboard web (Flask)
├── templates/
│   └── index.html      # UI della dashboard
├── inbox/              # Mail in arrivo (.json)
├── production_queue/   # Ordini inoltrati alla produzione
├── invoices/
│   ├── drafts/         # Fatture generate ma non ancora inviate
│   └── sent/           # Fatture inviate
├── payments/           # Pagamenti ricevuti da categorizzare
├── processed/          # File già elaborati (mail + pagamenti)
├── logs/               # Log di ogni sessione (un file per esecuzione)
└── data/
    ├── db.json          # Gestionale simulato (clienti, ordini, fatture, pagamenti)
    ├── categories.json  # Categorie di pagamento con keyword per il matching
    └── live_state.json  # Stato in tempo reale per la dashboard
```

---

## Requisiti

### Python
- Python **3.10 o superiore** (testato su 3.14)
- Verifica con: `python --version`

### Dipendenze

La simulazione usa solo librerie standard Python, tranne una:

```
flask >= 3.0
```

Installazione:
```bash
python -m pip install flask
```

> Tutte le altre librerie (`json`, `pathlib`, `subprocess`, `threading`, `shutil`, `re`) sono incluse in Python.

### Sistema operativo
Compatibile con **Windows**, macOS e Linux. I percorsi sono gestiti con `pathlib` e funzionano su tutti i sistemi.

---

## Installazione

1. Clona o scarica il progetto
2. Entra nella cartella:
   ```bash
   cd agent-sim
   ```
3. Installa Flask:
   ```bash
   python -m pip install flask
   ```

Nessun altro setup richiesto.

---

## Come avviare

### Opzione A — Dashboard web (consigliata)

Avvia il server:
```bash
python app.py
```

Apri il browser su: **http://localhost:5000**

Dalla dashboard puoi:
- Cliccare **"Reset / Genera dati test"** per popolare inbox e payments con 3 scenari
- Cliccare **"Ciclo singolo"** per eseguire l'agente una volta
- Cliccare **"Avvia loop (60s)"** per il loop autonomo
- Fermare il server con `Ctrl+C` nel terminale

### Opzione B — Terminale puro

```bash
python seed.py      # Popola inbox/ con i 3 scenari di test
python agent.py     # Esegue un ciclo singolo
python watcher.py   # Avvia il loop autonomo (Ctrl+C per fermare)
```

---

## La dashboard in dettaglio

La UI mostra in tempo reale cosa sta facendo l'agente ad ogni step:

| Step | Pannello dettaglio |
|---|---|
| 1 — Lettura inbox | Le mail in arrivo con mittente, oggetto, prodotti e importo |
| 2 — Classificazione | Corpo della mail + badge **ORDINE** / **NON ORDINE** |
| 3 — Estrazione dati | Tabella prodotti con quantità, prezzi, subtotali, totale |
| 4 — Inoltro produzione | ID ordine generato e file creato in `production_queue/` |
| 5 — Genera fattura | La fattura completa renderizzata su sfondo carta |
| 6 — Invio fattura | Conferma con destinatario, ID fattura e timestamp |
| 7 — Lettura pagamenti | Card dei pagamenti con importo e descrizione |
| 8 — Categorizzazione | Pagamento + badge colorato della categoria assegnata |
| 9 — Aggiorna gestionale | Voci registrate + contatori aggiornati del db |

Il pannello segue automaticamente lo step attivo. Cliccando su un qualsiasi step nella pipeline si può rivedere i dati che ha elaborato.

---

## Scenari di test inclusi

`seed.py` genera 3 scenari realistici:

| Scenario | Tipo | File creato |
|---|---|---|
| **TechStart Srl** — 2 servizi di consulenza IT per EUR 1.850 | Mail → ordine | `inbox/mail_001.json` |
| **MakerLab SpA** — 3 tipi di componenti elettronici per EUR 804 | Mail → ordine | `inbox/mail_002.json` |
| **FreelanceXYZ** — Pagamento EUR 800 per consulenza web | Pagamento diretto | `payments/pay_001.json` |

Puoi eseguire `seed.py` più volte: sovrascrive i file esistenti e ripristina l'ambiente iniziale.

---

## Aggiungere scenari personalizzati

### Nuova mail-ordine

Crea un file `.json` in `inbox/` con questa struttura:

```json
{
  "id": "mail_004",
  "timestamp": "2026-06-27T10:00:00",
  "from": "cliente@esempio.it",
  "from_name": "Nome Azienda Srl",
  "subject": "Richiesta ordine",
  "body": "Buongiorno, vorrei ordinare i seguenti prodotti...",
  "attachment": {
    "tipo": "ordine",
    "cliente": "Nome Azienda Srl",
    "prodotti": [
      { "nome": "Descrizione prodotto", "quantita": 2, "prezzo_unitario": 300.00 }
    ],
    "totale": 600.00,
    "note": "Eventuali note"
  }
}
```

### Nuovo pagamento

Crea un file `.json` in `payments/`:

```json
{
  "id": "pay_002",
  "timestamp": "2026-06-27T11:00:00",
  "from": "azienda@email.it",
  "from_name": "Nome Azienda",
  "importo": 500.00,
  "descrizione": "Pagamento canone mensile abbonamento",
  "tipo": "abbonamento",
  "riferimento_fattura": "INV-2026-0003",
  "metodo_pagamento": "bonifico"
}
```

La categorizzazione è automatica per keyword. Le categorie e le parole chiave sono configurabili in `data/categories.json`.

---

## Modalità API (opzionale)

Tutta la logica intelligente dell'agente è scritta in **doppia versione**:

- **Versione rule-based** (attiva di default): usa keyword matching, struttura JSON, template testuali. Non richiede connessioni esterne.
- **Versione API** (commentata): chiama `claude-sonnet-4-6` via Anthropic SDK per ogni decisione intelligente — classificazione mail, estrazione dati in linguaggio naturale, generazione fattura in prosa, categorizzazione semantica.

Per attivare la modalità API:

1. Ottieni una API key su [console.anthropic.com](https://console.anthropic.com)
2. Installa l'SDK:
   ```bash
   python -m pip install anthropic
   ```
3. Imposta la variabile d'ambiente:
   ```bash
   # Windows
   set ANTHROPIC_API_KEY=sk-ant-...

   # macOS / Linux
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
4. In `agent.py`, per ciascuna delle 4 funzioni intelligenti, commenta il blocco rule-based e decommenta il blocco API:
   - `riconosci_tipo_mail()`
   - `estrai_dati_ordine()`
   - `genera_testo_fattura()`
   - `categorizza_pagamento()`

Ogni blocco API è delimitato da:
```python
# --- MODALITA' API (decommentare quando si ha ANTHROPIC_API_KEY) ---
# ...codice...
# --- FINE MODALITA' API ---
```

---

## Reset completo dell'ambiente

Per ripartire da zero (db vuoto, cartelle pulite):

```bash
# Svuota le cartelle di output
# Windows PowerShell:
Remove-Item agent-sim\production_queue\*.json -ErrorAction SilentlyContinue
Remove-Item agent-sim\invoices\drafts\*.json  -ErrorAction SilentlyContinue
Remove-Item agent-sim\invoices\sent\*.json    -ErrorAction SilentlyContinue
Remove-Item agent-sim\processed\*.json        -ErrorAction SilentlyContinue
Remove-Item agent-sim\logs\*.log              -ErrorAction SilentlyContinue
```

Poi ripristina il db vuoto creando `data/db.json` con:
```json
{ "clienti": {}, "ordini": [], "fatture": [], "pagamenti": [] }
```

Infine rigenera i dati di test:
```bash
python seed.py
```
