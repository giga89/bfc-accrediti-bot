import os
import re
import json
import requests
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup

# Config
BASE_URL = "https://www.bolognafc.it/biglietti/"
MATCH_BASE_URL = "https://www.bolognafc.it/match/"

# Secrets from Environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GHA_GIST_TOKEN = os.environ.get("GHA_GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID")

GIST_FILENAME = "history.json"

# Italian month names -> number
MONTHS_IT = {
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
    'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
    'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
}

def parse_italian_datetime(text):
    """
    Try to extract a datetime from an Italian text string like:
      "dalle ore 10 alle ore 17 del 5 marzo"
      "dal 6/3 dalle ore 14"
    Returns a datetime object or None.
    """
    if not text:
        return None
    t = text.lower()
    year = datetime.now().year

    day, month = None, None

    # Pattern: "del 5/3" or "dal 5/3"
    m = re.search(r'(?:del|dal)\s+(\d{1,2})\s*/\s*(\d{1,2})', t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))

    # Pattern: "del 5 marzo" or "dal 5 marzo"
    if day is None:
        months_pattern = '|'.join(MONTHS_IT.keys())
        m = re.search(rf'(?:del|dal)\s+(\d{{1,2}})\s+({months_pattern})', t)
        if m:
            day = int(m.group(1))
            month = MONTHS_IT[m.group(2)]

    # Fallback: just "5 marzo"
    if day is None:
        months_pattern = '|'.join(MONTHS_IT.keys())
        m = re.search(rf'(\d{{1,2}})\s+({months_pattern})', t)
        if m:
            day = int(m.group(1))
            month = MONTHS_IT[m.group(2)]

    if day is None or month is None:
        return None

    # Extract hour: "dalle ore 10" or "ore 10"
    time_match = re.search(r'(?:dalle?\s+)?(?:ore\s+)(\d{1,2})(?::(\d{2}))?', t)
    hour = int(time_match.group(1)) if time_match else 10
    minute = int(time_match.group(2)) if (time_match and time_match.group(2)) else 0

    try:
        dt = datetime(year, month, day, hour, minute)
        # If the date has already passed this year, try next year
        if dt < datetime.now() - timedelta(days=1):
            dt = datetime(year + 1, month, day, hour, minute)
        return dt
    except ValueError:
        return None


def make_gcal_url(title, start_dt, duration_minutes=60, description=""):
    """
    Generate a Google Calendar 'add event' URL.
    The event will have a popup reminder 30 minutes before start.
    """
    fmt = "%Y%m%dT%H%M%S"
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"
        f"&details={quote(description)}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def build_calendar_links(match_data, match_url):
    """
    Build Google Calendar links for:
      1. Disability accreditation window (30 min reminder before opening)
      2. General ticket sale (30 min reminder before opening)
    Returns a dict with 'disability_cal' and 'sale_cal' keys (may be None).
    """
    links = {"disability_cal": None, "sale_cal": None}
    teams = match_data.get("teams", "Bologna")

    # --- Disability accreditation ---
    dis_info = match_data.get("disability_info", "")
    dis_dt = parse_italian_datetime(dis_info)
    if dis_dt:
        reminder_dt = dis_dt - timedelta(minutes=30)
        title = f"♿ Accrediti Disabili – {teams}"
        desc = (
            f"Apertura accrediti disabili ore {dis_dt.strftime('%H:%M')}\n"
            f"Info: {match_url}"
        )
        links["disability_cal"] = make_gcal_url(title, reminder_dt, duration_minutes=30, description=desc)
        print(f"Calendar disability event: {dis_dt}")

    # --- General ticket sale ---
    sale_text = match_data.get("sale_date", "")
    sale_dt = parse_italian_datetime(sale_text)
    if sale_dt:
        reminder_dt = sale_dt - timedelta(minutes=30)
        title = f"🎫 Vendita Biglietti – {teams}"
        desc = (
            f"Apertura vendita biglietti ore {sale_dt.strftime('%H:%M')}\n"
            f"Info: {match_url}"
        )
        links["sale_cal"] = make_gcal_url(title, reminder_dt, duration_minutes=30, description=desc)
        print(f"Calendar sale event: {sale_dt}")

    return links


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping notification.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Notification sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def get_gist_content():
    if not GHA_GIST_TOKEN or not GIST_ID:
        return {}
    
    headers = {
        "Authorization": f"token {GHA_GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/gists/{GIST_ID}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            gist_data = response.json()
            if GIST_FILENAME in gist_data.get("files", {}):
                content = gist_data["files"][GIST_FILENAME]["content"]
                return json.loads(content)
    except Exception as e:
        print(f"Error reading gist: {e}")
    
    return {}

def update_gist_content(new_data):
    if not GHA_GIST_TOKEN or not GIST_ID:
        print("Gist credentials missing. Cannot update state.")
        return

    headers = {
        "Authorization": f"token {GHA_GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/gists/{GIST_ID}"
    
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": json.dumps(new_data, indent=2)
            }
        }
    }
    
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        print("Gist updated successfully.")
    except Exception as e:
        print(f"Failed to update gist: {e}")

def get_upcoming_matches():
    print(f"Fetching {BASE_URL}")
    response = requests.get(BASE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    match_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/match/' in href and 'info=ticket' in href:
            if href not in match_links:
                match_links.append(href)
                
    return match_links

def check_match_page(url):
    print(f"Checking match info at {url}")
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    target_text = "Accrediti per persone con disabilità"
    sections = soup.find_all(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'div', 'p'] and target_text.lower() in tag.get_text().lower())
    
    match_data = {
        "disability_info": None,
        "match_date": "Data non trovata",
        "teams": "Bologna vs Avversario",
        "sale_date": "Non specificata"
    }

    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text()
        teams_match = re.search(r'(.*?)\s*–', title_text)
        if teams_match:
            match_data["teams"] = teams_match.group(1).strip()
            
    date_patterns = [r'(Dom|Lun|Mar|Mer|Gio|Ven|Sab)\s+\d+\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s*-\s*\d+:\d+',
                     r'\d{1,2}\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+\d{4}']
    
    for string in soup.stripped_strings:
        for pattern in date_patterns:
            if re.search(pattern, string, re.IGNORECASE):
                match_data["match_date"] = string
                break
        if match_data["match_date"] != "Data non trovata":
            break

    raw_text = soup.get_text(separator=' ', strip=True)

    sale_match = re.search(r'(?i)(dalle\s+(?:ore\s+)?\d+.*?vendita\s+.*?(?:aperta\s+a\s+tutti|libera))', raw_text)
    if sale_match:
        s = sale_match.group(1)
        short_s = re.search(r'(?i)(dalle.*?del\s*\d{1,2}(?:/\d{1,2}|\s+[a-z]+))', s)
        if short_s:
            match_data["sale_date"] = short_s.group(1).strip().capitalize()
        else:
            match_data["sale_date"] = s[:80].capitalize() + "..."
    else:
        sale_match_alt = re.search(r'(?i)(dal\s+\d{1,2}(?:/\d{1,2}|\s+[a-z]+).*?vendita)', raw_text)
        if sale_match_alt:
            match_data["sale_date"] = sale_match_alt.group(1).strip().capitalize()
    
    disability_match = re.search(r'(?i)(le richieste devono pervenire.*?)(?:\.\s|Si ricorda|$)', raw_text)
    if disability_match:
        dis_info = disability_match.group(1).strip()
        if len(dis_info) > 130:
            dis_info = dis_info.split('.')[0]
        match_data["disability_info"] = dis_info.capitalize()

    return match_data if match_data["disability_info"] else None

def main():
    history = get_gist_content()
    matches = get_upcoming_matches()
    
    print(f"Found {len(matches)} match info links.")
    
    new_notifications = 0
    
    for match_url in matches:
        match_data = check_match_page(match_url)
        if match_data:
            info = match_data["disability_info"]
            content_hash = hashlib.md5(info.encode('utf-8')).hexdigest()
            # Use the URL path without query string as stable unique key
            match_id = match_url.split('?')[0].strip('/')
            if not match_id:
                match_id = match_url
            print(f"Match key: '{match_id}' | Hash: {content_hash}")
            
            if match_id not in history or history[match_id] != content_hash:
                print(f"New or updated info found for {match_id}!")
                
                match_name_display = match_data["teams"]

                # Build calendar links
                cal = build_calendar_links(match_data, match_url)
                cal_section = ""
                if cal["disability_cal"] or cal["sale_cal"]:
                    cal_section = "\n\n📅 <b>Aggiungi al calendario</b> (promemoria 30 min prima):"
                    if cal["disability_cal"]:
                        cal_section += f'\n♿ <a href="{cal["disability_cal"]}">📆 Accrediti Disabili</a>'
                    if cal["sale_cal"]:
                        cal_section += f'\n🎫 <a href="{cal["sale_cal"]}">📆 Vendita Biglietti</a>'

                msg = f"""🟢 <b>Nuove info Accrediti Disabili!</b>

⚽ <b>Partita:</b> {match_name_display}
📅 <b>Data Partita:</b> {match_data['match_date']}
🎫 <b>Inizio Vendita Libera:</b> {match_data['sale_date']}

♿ <b>Info Accrediti Disabili:</b>
🕒 Le richieste devono pervenire esclusivamente {info}{cal_section}

🔗 <a href='{match_url}'>Link Ufficiale</a>"""
                
                send_telegram_message(msg)
                history[match_id] = content_hash
                new_notifications += 1
            else:
                print(f"No new changes for {match_id}.")
        else:
            print(f"Could not extract disability accreditation info for {match_url}.")
            
    if new_notifications > 0:
        update_gist_content(history)
    else:
        print("No updates needed.")

if __name__ == "__main__":
    main()
