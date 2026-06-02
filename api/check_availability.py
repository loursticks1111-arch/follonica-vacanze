# api/check_availability.py
# Vercel Serverless Function — Python
#
# Riceve:  POST { "checkin": "2026-07-19", "checkout": "2026-07-26", "ospiti": 4 }
# Legge i feed iCal di Kross Booking per tutti gli appartamenti
# Risponde: { "disponibili": [ { "id": "rif001", ... }, ... ] }

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# ─────────────────────────────────────────────
# PERCORSI FILE DATI
# ─────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / 'data'

def load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, encoding='utf-8') as f:
        return json.load(f)


# ─────────────────────────────────────────────
# PARSER iCal — gestisce i formati Kross / Airbnb / Booking.com
# ─────────────────────────────────────────────

def parse_ical_date(value: str) -> date:
    """
    Converte una stringa iCal in un oggetto date.
    Gestisce i formati: YYYYMMDD  oppure  YYYYMMDDTHHMMSSZ
    """
    clean = value.replace('T', '').replace('Z', '').strip()[:8]
    return date(int(clean[0:4]), int(clean[4:6]), int(clean[6:8]))


def parse_ical(text: str) -> list[tuple[date, date]]:
    """
    Parsa il testo di un file .ics e restituisce una lista di tuple (start, end).
    Gestisce il line-folding standard iCal (righe di continuazione con spazio/tab iniziale).
    """
    # Normalizza i line ending e gestisci il folding
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    for line in normalized.split('\n'):
        if line.startswith((' ', '\t')) and lines:
            lines[-1] += line[1:]   # riga di continuazione: aggiungi alla precedente
        else:
            lines.append(line.strip())

    events = []
    in_event = False
    evt_start = evt_end = None

    for line in lines:
        upper = line.upper()

        if upper == 'BEGIN:VEVENT':
            in_event = True
            evt_start = evt_end = None

        elif upper == 'END:VEVENT':
            if in_event and evt_start and evt_end:
                events.append((evt_start, evt_end))
            in_event = False

        elif in_event:
            # DTSTART può avere parametri: DTSTART;VALUE=DATE:20260719
            if upper.startswith('DTSTART'):
                try:
                    evt_start = parse_ical_date(line.split(':', 1)[-1])
                except (ValueError, IndexError):
                    pass

            elif upper.startswith('DTEND'):
                try:
                    evt_end = parse_ical_date(line.split(':', 1)[-1])
                except (ValueError, IndexError):
                    pass

    return events


def fetch_ical(url: str) -> list[tuple[date, date]]:
    """
    Scarica un feed iCal e ne restituisce gli eventi.
    In caso di errore restituisce lista vuota (non blocca il controllo).
    """
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'FollonicaVacanze/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
        return parse_ical(text)
    except Exception as e:
        print(f"[iCal] Impossibile scaricare {url}: {e}")
        return []


def dates_overlap(start1: date, end1: date, start2: date, end2: date) -> bool:
    """Verifica se due intervalli di date si sovrappongono."""
    return start1 < end2 and end1 > start2


def is_disponibile(apt_id: str, req_start: date, req_end: date,
                   ical_feeds: dict) -> bool:
    """
    Controlla la disponibilità di un appartamento leggendo tutti i feed iCal.
    Se non ci sono feed configurati, considera l'appartamento disponibile.
    """
    feeds = ical_feeds.get(apt_id, {})
    urls  = [v for v in feeds.values() if v and 'XXXXX' not in v]

    if not urls:
        print(f"[Avviso] Nessun feed iCal configurato per {apt_id}")
        return True  # nessun dato = considera libero (aggiorna ical-feeds.json)

    for url in urls:
        events = fetch_ical(url)
        if any(dates_overlap(s, e, req_start, req_end) for s, e in events):
            return False  # trovata una sovrapposizione → occupato

    return True


# ─────────────────────────────────────────────
# HANDLER VERCEL
# ─────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        # Leggi il body
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return self._json_response(400, {'error': 'Body JSON non valido'})

        checkin_str  = body.get('checkin')
        checkout_str = body.get('checkout')
        ospiti       = body.get('ospiti')

        # Validazione parametri
        if not all([checkin_str, checkout_str, ospiti]):
            return self._json_response(400, {
                'error': 'Parametri obbligatori: checkin, checkout, ospiti'
            })

        try:
            req_start = date.fromisoformat(checkin_str)
            req_end   = date.fromisoformat(checkout_str)
        except ValueError:
            return self._json_response(400, {
                'error': 'Formato date non valido. Usa YYYY-MM-DD (es. 2026-07-19)'
            })

        if req_start >= req_end:
            return self._json_response(400, {
                'error': 'La data di partenza deve essere successiva a quella di arrivo'
            })

        # Carica i dati
        try:
            proprieta  = load_json('proprieta.json')
            ical_feeds = load_json('ical-feeds.json')
        except FileNotFoundError as e:
            return self._json_response(500, {'error': f'File dati mancante: {e}'})

        # Controlla disponibilità per ogni appartamento
        disponibili = []
        for apt_id, casa in proprieta.items():
            if casa.get('capacita', 0) < ospiti:
                continue  # capienza insufficiente
            if is_disponibile(apt_id, req_start, req_end, ical_feeds):
                disponibili.append({'id': apt_id, **casa})

        return self._json_response(200, {'disponibili': disponibili})

    def log_message(self, format, *args):
        pass  # silenzia i log HTTP di default
