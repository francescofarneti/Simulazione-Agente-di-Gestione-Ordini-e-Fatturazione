# Agent Sim — Agente AI per la Gestione Ordini e Fatturazione

> **Una dimostrazione pratica di come un sistema agentico AI può automatizzare il back-office di una PMI italiana — dalla ricezione dell'ordine all'emissione della fattura, in modo autonomo.**

---

## Il problema che risolve

Ogni giorno una PMI riceve ordini via email in formati diversi: testo libero, PDF, allegati strutturati. Un operatore deve leggere ogni mail, estrarre i dati, creare l'ordine, generare la fattura e registrare il tutto nel gestionale.

**Questo processo manuale è lento, soggetto a errori e non scala.**

Un agente AI lo automatizza completamente — e quando non è sicuro, chiede all'umano solo ciò che serve.

---

## ROI stimato per una PMI

| Attività manuale | Tempo/giorno | Con agente AI |
|---|---|---|
| Lettura e classificazione email ordini | 30 min | ~2 sec |
| Estrazione dati da testo libero | 20 min/ordine | automatica |
| Generazione fattura | 10 min/ordine | automatica |
| Registrazione nel gestionale | 5 min/ordine | automatica |
| Categorizzazione pagamenti | 15 min/giorno | automatica |

**Per 10 ordini/giorno → oltre 3 ore risparmiate ogni giorno lavorativo.**

---

## Cosa dimostra questo progetto

Questo sistema replica un flusso reale di back-office end-to-end:

```
Email in arrivo
  └─► [AI] Classificazione (ordine / info / altro)
        └─► [AI] Estrazione dati in linguaggio naturale
              └─► Creazione ordine in produzione
                    └─► [AI] Generazione fattura professionale
                          └─► "Invio" fattura al cliente
                                └─► [AI] Categorizzazione pagamento
                                      └─► Registrazione nel gestionale
```

**Il punto chiave:** funziona con qualsiasi testo libero in italiano, non solo con strutture dati predefinite.

---

## Human-in-the-loop

L'agente sa quando non è sicuro. Quando la confidenza AI è sotto il 72%, l'item non viene processato automaticamente ma va in **coda di revisione umana** — con l'AI che mostra il suo ragionamento e l'operatore che approva o rifiuta con un click.

Questo è il pattern corretto per sistemi AI in produzione: **automazione dove possibile, supervisione umana dove necessario.**

---

## Avvio rapido

```bash
# 1. Installa dipendenze
pip install -r requirements.txt

# 2. (Opzionale) Imposta API key per modalità AI
set ANTHROPIC_API_KEY=sk-ant-...   # Windows
export ANTHROPIC_API_KEY=sk-ant-... # macOS/Linux

# 3. Avvia la dashboard
cd Esperimento_Agente/agent-sim
python app.py
```

Apri **http://localhost:5000**

---

## Due modalità di funzionamento

| | Rule-based (default) | Modalità AI |
|---|---|---|
| Attivazione | Automatica senza API key | Con `ANTHROPIC_API_KEY` impostata |
| Classificazione mail | Keyword matching | Claude Haiku — comprensione semantica |
| Estrazione dati | Solo da allegati JSON strutturati | Da qualsiasi testo libero in italiano |
| Generazione fattura | Template fisso | Testo professionale generato da AI |
| Categorizzazione pagamenti | Keyword matching | Comprensione contestuale |
| Confidenza e ragionamento | Non disponibile | Visualizzato su ogni step |
| Human-in-the-loop | Non applicabile | Attivo sotto soglia 72% |

**La stessa infrastruttura, due livelli di intelligenza.** Perfetto per dimostrare il prima/dopo di un'implementazione AI.

---

## Dashboard — cosa si vede in tempo reale

### Pipeline a 9 step
Ogni step si illumina mentre viene eseguito. Cliccandoci si vedono i dati elaborati.

| Step | Descrizione | Con AI |
|---|---|---|
| 1 — Lettura inbox | Mail ricevute con tipo (testo libero vs strutturato) | Badge AI |
| 2 — Classificazione | Tipo mail + **barra di confidenza** + ragionamento AI | ✓ |
| 3 — Estrazione dati | Tabella prodotti + prezzi + totale | **Estratti da testo libero** |
| 4 — Inoltro produzione | ID ordine generato + file creato | |
| 5 — Genera fattura | Fattura completa renderizzata | **Testo generato da AI** |
| 6 — Invio fattura | Conferma invio | |
| 7 — Lettura pagamenti | Card pagamenti | |
| 8 — Categorizzazione | Categoria + **barra di confidenza** + ragionamento AI | ✓ |
| 9 — Aggiorna gestionale | Voci registrate + contatori DB | |

### KPI bar
- Fatturato totale (somma fatture emesse)
- Ordini processati
- Clienti acquisiti
- Pagamenti ricevuti
- Item in revisione umana

### "Prova tu" — il momento wow
Scrivi qualsiasi email d'ordine in italiano in linguaggio naturale. L'AI estrae cliente, prodotti, quantità e prezzi, genera la fattura e registra tutto nel gestionale — mentre guardi la pipeline animarsi in tempo reale.

### Coda di revisione umana
Quando la confidenza AI è bassa, l'item appare nella coda con il ragionamento dell'AI. L'operatore approva (avvia elaborazione) o rifiuta con un click.

---

## Scenari di test inclusi

| Scenario | Tipo | Richiede AI |
|---|---|---|
| **Consulenza IT + Elettronica** | Mail con allegato strutturato | No |
| **Retail — Abbigliamento** | Email informale in testo libero | Sì |
| **Manifattura — Componentistica** | Ordine tecnico con codici articolo | Sì |
| **Studio Legale — Servizi** | Richiesta professionale con tariffe orarie | Sì |

Gli scenari AI mostrano chiaramente la differenza: in modalità rule-based i dati non vengono estratti; in modalità AI l'agente lavora come un operatore umano esperto.

---

## Architettura tecnica

```
agent-sim/
├── agent.py            # Agente principale — 9 step, dual-mode AI/rule-based
├── app.py              # Dashboard web Flask + 14 API endpoint
├── seed.py             # Generatore scenari di test (4 scenari)
├── watcher.py          # Loop autonomo ogni 60s
├── templates/
│   └── index.html      # Dashboard SPA (vanilla JS, GitHub dark theme)
├── inbox/              # Mail in arrivo (.json)
├── production_queue/   # Ordini inoltrati alla produzione
├── invoices/
│   ├── drafts/         # Bozze fatture
│   └── sent/           # Fatture inviate
├── payments/           # Pagamenti da categorizzare
├── review_queue/       # Item a bassa confidenza — in attesa di revisione umana
├── processed/          # File già elaborati
├── logs/               # Log di sessione con timestamp
└── data/
    ├── db.json          # Gestionale simulato
    ├── categories.json  # Categorie pagamento
    └── live_state.json  # Stato real-time per la dashboard (IPC)
```

### Pattern chiave implementati
- **Dual-mode automatico**: `USE_AI = bool(os.getenv("ANTHROPIC_API_KEY"))` — nessun cambio di codice richiesto
- **Structured tool use**: ogni funzione AI usa Anthropic tool_use per forzare output con `confidence` e `reasoning`
- **Human-in-the-loop**: review queue con soglia configurabile (default 72%)
- **Server-Sent Events**: streaming log in tempo reale senza WebSocket
- **IPC via JSON**: `live_state.json` come canale tra subprocess agent e dashboard Flask

---

## API endpoint

| Endpoint | Metodo | Descrizione |
|---|---|---|
| `/api/run-once` | POST | Esegue un singolo ciclo |
| `/api/start-loop` | POST | Avvia loop ogni 60s |
| `/api/stop-loop` | POST | Ferma il loop |
| `/api/seed/<scenario>` | POST | Genera dati test per scenario |
| `/api/process-freetext` | POST | Inserisce email in testo libero |
| `/api/review` | GET | Lista coda di revisione umana |
| `/api/review/<id>/approve` | POST | Approva item in revisione |
| `/api/review/<id>/reject` | POST | Rifiuta item in revisione |
| `/api/ai-status` | GET | Stato modalità AI + parametri |
| `/api/kpis` | GET | KPI di business (fatturato, ordini, clienti) |
| `/api/live` | GET | Stato real-time pipeline (polling) |
| `/api/logs/stream` | GET | SSE stream log in tempo reale |
| `/api/status` | GET | Stato sistema + conteggi cartelle |

---

## Requisiti

- Python 3.10+
- `flask>=3.0`
- `anthropic>=0.40.0` (opzionale — solo per modalità AI)

```bash
pip install -r requirements.txt
```

---

## Reset ambiente

```bash
# PowerShell
Remove-Item Esperimento_Agente\agent-sim\production_queue\*.json -EA SilentlyContinue
Remove-Item Esperimento_Agente\agent-sim\invoices\drafts\*.json  -EA SilentlyContinue
Remove-Item Esperimento_Agente\agent-sim\invoices\sent\*.json    -EA SilentlyContinue
Remove-Item Esperimento_Agente\agent-sim\processed\*.json        -EA SilentlyContinue
Remove-Item Esperimento_Agente\agent-sim\review_queue\*.json     -EA SilentlyContinue
Remove-Item Esperimento_Agente\agent-sim\logs\*.log              -EA SilentlyContinue
```

Poi ripristina il db:
```json
{ "clienti": {}, "ordini": [], "fatture": [], "pagamenti": [] }
```

---

*Progetto portfolio — dimostrazione di implementazione sistemi agentici AI per PMI italiane.*
