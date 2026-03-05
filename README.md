# 🔴🔵 BFC Accrediti Disabili Bot

> Bot Telegram che monitora automaticamente il sito del **Bologna FC** e avvisa non appena aprono le richieste di accredito per persone con disabilità.

[![GitHub Actions](https://github.com/giga89/bfc-accrediti-bot/actions/workflows/scraper.yml/badge.svg)](https://github.com/giga89/bfc-accrediti-bot/actions/workflows/scraper.yml)

---

## 📲 Come ricevere le notifiche

Unisciti al canale Telegram ufficiale:

👉 **[Unisciti al canale](https://t.me/bfc_info_channel)**

Oppure aggiungi direttamente il bot:

🤖 **[@bfc_info_match_bot](https://t.me/bfc_info_match_bot)**

---

## ⚙️ Come funziona

```
Bologna FC Website ──► Scraper (Python) ──► Telegram Notification
                              │
                              ▼
                       GitHub Gist (stato)
```

1. **GitHub Actions** esegue lo scraper ogni 4 ore automaticamente
2. Lo script controlla la pagina [biglietti di Bologna FC](https://www.bolognafc.it/biglietti/) cercando link "info=ticket" per le prossime partite
3. Per ogni partita trovata, cerca la sezione **"Accrediti per persone con disabilità"**
4. Se trova informazioni nuove o aggiornate (hash MD5 diverso), invia una notifica su Telegram
5. Lo stato viene salvato su un **GitHub Gist** per evitare notifiche duplicate

---

## 📩 Esempio di notifica

```
🟢 Nuove info Accrediti Disabili!

⚽ Partita: Bologna - Roma
📅 Data Partita: Dom 9 Marzo - 20:45
🎫 Inizio Vendita Libera: Dalle ore 10 del 6/3...

♿ Info Accrediti Disabili:
🕒 Le richieste devono pervenire esclusivamente dalle ore 10 alle ore 17 del 5 marzo

🔗 Link Ufficiale
```

---

## 🛠️ Tech Stack

| Componente | Tecnologia |
|---|---|
| Scraping | Python + BeautifulSoup |
| Automazione | GitHub Actions (ogni 4h) |
| Stato/Dedup | GitHub Gist (JSON) |
| Notifiche | Telegram Bot API |
| Container | Docker |

---

## 🚀 Deploy in proprio

### Prerequisiti

- Account Telegram + Bot Token (via [@BotFather](https://t.me/BotFather))
- Account GitHub con Gist
- GitHub Personal Access Token con scope `gist`

### Secrets necessari (GitHub Actions)

| Secret | Descrizione |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot Telegram |
| `TELEGRAM_CHAT_ID` | ID del gruppo/canale Telegram |
| `GHA_GIST_TOKEN` | GitHub PAT con permesso `gist` |
| `GIST_ID` | ID del Gist per salvare lo stato |

### Esecuzione locale con Docker

```bash
docker build -t bfc-bot .
docker run -e TELEGRAM_BOT_TOKEN=xxx \
           -e TELEGRAM_CHAT_ID=xxx \
           -e GHA_GIST_TOKEN=xxx \
           -e GIST_ID=xxx \
           bfc-bot
```

### Esecuzione locale senza Docker

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
export GHA_GIST_TOKEN=xxx
export GIST_ID=xxx
python scraper.py
```

---

## 📁 Struttura del progetto

```
bfc-accrediti-bot/
├── scraper.py                    # Script principale
├── requirements.txt              # Dipendenze Python
├── Dockerfile                    # Container Docker
└── .github/
    └── workflows/
        └── scraper.yml           # GitHub Actions workflow
```

---

## 🔗 Link utili

- [Bologna FC - Biglietteria](https://www.bolognafc.it/biglietti/)
- [Repository GitHub](https://github.com/giga89/bfc-accrediti-bot)

---

*Made with ❤️ by [giga89](https://github.com/giga89)*
