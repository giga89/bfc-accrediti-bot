import os
import json
import requests
import hashlib
from bs4 import BeautifulSoup

# Config
BASE_URL = "https://www.bolognafc.it/biglietti/"
MATCH_BASE_URL = "https://www.bolognafc.it/match/"

# Secrets from Environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GHA_GIST_TOKEN = os.environ.get("GHA_GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID")  # Optional: we can create it if not provided, but usually better to provide

GIST_FILENAME = "history.json"

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping notification.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
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
    # Find links that go to match details with '?info=ticket'
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
    
    # Look for the section title. In Markdown we found "Accrediti per persone con disabilità"
    # In HTML it might be an h2, h3, or text within a div. Let's look for the text.
    
    target_text = "Accrediti per persone con disabilità"
    
    # Find headers or divs containing this text
    sections = soup.find_all(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'div', 'p'] and target_text.lower() in tag.get_text().lower())
    
    import re
    
    match_data = {
        "disability_info": None,
        "match_date": "Data non trovata",
        "teams": "Bologna vs Avversario",
        "sale_date": "Non specificata"
    }

    # Extract teams and date from the header/title
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

    # Extract raw text for robust regex finding
    raw_text = soup.get_text(separator=' ', strip=True)

    # Find General Sale start date
    # Usually format is "Dalle ore X del Y la vendita è aperta a tutti" or similar
    sale_match = re.search(r'(?i)(dalle\s+(?:ore\s+)?\d+.*?vendita\s+.*?(?:aperta\s+a\s+tutti|libera))', raw_text)
    if sale_match:
        # Clean it up to be concise
        s = sale_match.group(1)
        # Try to just get the date part
        short_s = re.search(r'(?i)(dalle.*?del\s*\d{1,2}(?:/\d{1,2}|\s+[a-z]+))', s)
        if short_s:
            match_data["sale_date"] = short_s.group(1).strip().capitalize()
        else:
            match_data["sale_date"] = s[:80].capitalize() + "..."
    else:
        # Fallback sale regex
        sale_match_alt = re.search(r'(?i)(dal\s+\d{1,2}(?:/\d{1,2}|\s+[a-z]+).*?vendita)', raw_text)
        if sale_match_alt:
            match_data["sale_date"] = sale_match_alt.group(1).strip().capitalize()
    
    # Find Disability Info
    # Look for the exact phrasing "Le richieste devono pervenire ESCLUSIVAMENTE DALLE ORE 10 ALLE ORE 17 del 5 marzo"
    disability_match = re.search(r'(?i)(le richieste devono pervenire.*?)(?:\.\s|Si ricorda|$)', raw_text)
    if disability_match:
        dis_info = disability_match.group(1).strip()
        # Clean up any trailing text that might be too long
        if len(dis_info) > 130:
            # Cut off at the first period if it went too far
            dis_info = dis_info.split('.')[0]
        
        # Format explicitly
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
            # Create a simple hash of the info to detect changes
            content_hash = hashlib.md5(info.encode('utf-8')).hexdigest()
            match_id = match_url.rstrip('/').split('/')[-1].replace('?info=ticket','')
            
            if match_id not in history or history[match_id] != content_hash:
                print(f"New or updated info found for {match_id}!")
                
                # Format message
                match_name_display = match_data["teams"]
                msg = f"""🟢 <b>Nuove info Accrediti Disabili!</b>

⚽ <b>Partita:</b> {match_name_display}
📅 <b>Data Partita:</b> {match_data['match_date']}
🎫 <b>Inizio Vendita Libera:</b> {match_data['sale_date']}

♿ <b>Info Accrediti Disabili:</b>
🕒 Le richieste devono pervenire esclusivamente {info}

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
