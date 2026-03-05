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
    
    extracted_info = None
    
    import re
    
    for section in sections:
        parent = section.parent
        full_text = parent.get_text(separator='\n', strip=True)
        
        if "esclusivamente" in full_text.lower() or "disabilità" in full_text.lower():
            # Try to find the date/time phrase using regex for a more concise message
            # e.g., "Le richieste devono pervenire ESCLUSIVAMENTE DALLE ORE 10 ALLE ORE 17 del 5 marzo"
            match = re.search(r'(?i)esclusivamente\s+(.*?)(?:\n|\.)', full_text)
            
            if match:
                date_info = match.group(1).strip()
                extracted_info = f"🕒 <b>{date_info.capitalize()}</b>"
                break
                
            # Fallback if regex doesn't match perfectly, grab the relevant line
            lines = full_text.split('\n')
            rel_lines = [l for l in lines if "esclusivamente" in l.lower() or "richieste" in l.lower()]
            if rel_lines:
                extracted_info = "\n".join(rel_lines)
                # Keep it short
                if len(extracted_info) > 150:
                    extracted_info = extracted_info[:147] + "..."
                break
    
    return extracted_info

def main():
    history = get_gist_content()
    matches = get_upcoming_matches()
    
    print(f"Found {len(matches)} match info links.")
    
    new_notifications = 0
    
    for match_url in matches:
        info = check_match_page(match_url)
        if info:
            # Create a simple hash of the info to detect changes
            content_hash = hashlib.md5(info.encode('utf-8')).hexdigest()
            match_id = match_url.rstrip('/').split('/')[-1].replace('?info=ticket','')
            
            if match_id not in history or history[match_id] != content_hash:
                print(f"New or updated info found for {match_id}!")
                
                # Format message
                match_name_display = match_id.replace('-', ' ').title()
                msg = f"🟢 <b>Nuove info Accrediti Disabili!</b>\n\n⚽ <b>Partita:</b> {match_name_display}\n🔗 <a href='{match_url}'>Link Ufficiale</a>\n\n<b>Dettagli:</b>\n{info}"
                
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
