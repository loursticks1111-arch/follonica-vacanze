# api/check_availability.py
# Vercel Serverless Function — Python
#
# Legge la disponibilità dal foglio Google Sheets "Prenotazioni"
# tramite Google Sheets API v4.
#
# Un appartamento è OCCUPATO quando la cella corrispondente
# ha lo sfondo GIALLO (qualsiasi tonalità).
# Una cella vuota o bianca = LIBERO.
#
# Variabili d'ambiente necessarie su Vercel:
#   GOOGLE_API_KEY   → chiave API Google (vedi istruzioni)
#   SPREADSHEET_ID   → ID del foglio (opzionale, già preimpostato)

from http.server import BaseHTTPRequestHandler
import json, os, urllib.request, urllib.error
from datetime import date
from pathlib import Path

# ─── Configurazione ───────────────────────────────────────────

SPREADSHEET_ID = os.environ.get(
    'SPREADSHEET_ID',
    '1pYW-savF_OCNt-rzrD3jWQfre7BQvtgn3g5GsejQYrk'
)

# Nome del tab: viene costruito automaticamente con l'anno delle date richieste
# Es. date 2026 → legge "Prenotazioni_2026"
#     date 2027 → legge "Prenotazioni_2027" (basta creare il tab)
SHEET_NAME_PREFIX = 'Prenotazioni'

# Colonna → appartamento (indice 0-based nel foglio)
# Riga 1: [anno] | RIF001 | RIF003 | RIF005 | RIF002 | RIF004 | RIF006 | RIF007
APT_COLS = {
    'rif001': 1,
    'rif003': 2,
    'rif005': 3,
    'rif002': 4,
    'rif004': 5,
    'rif006': 6,
    'rif007': 7,
}

DATA_DIR = Path(__file__).parent.parent / 'data'


# ─── Dati appartamenti ────────────────────────────────────────

def load_proprieta() -> dict:
    with open(DATA_DIR / 'proprieta.json', encoding='utf-8') as f:
        return json.load(f)


# ─── Google Sheets API v4 ─────────────────────────────────────

def fetch_sheet_data(api_key: str, sheet_name: str) -> list:
    """
    Legge righe e colori di sfondo dal foglio tramite Sheets API v4.
    Restituisce la lista di rowData (una per riga del foglio).
    """
    # Richiediamo solo i campi necessari: valore cella + colore sfondo
    fields = (
        'sheets.data.rowData.values('
        'userEnteredValue,'
        'userEnteredFormat.backgroundColor'
        ')'
    )
    url = (
        f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}'
        f'?includeGridData=true'
        f'&ranges={urllib.request.quote(sheet_name)}'
        f'&fields={urllib.request.quote(fields)}'
        f'&key={api_key}'
    )
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'FollonicaVacanze/1.0'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    # Naviga nella struttura della risposta API
    try:
        return data['sheets'][0]['data'][0].get('rowData', [])
    except (KeyError, IndexError):
        print(f'[Sheets API] Struttura risposta inattesa: {list(data.keys())}')
        return []


# ─── Rilevamento colore giallo ────────────────────────────────

def is_yellow(color: dict) -> bool:
    """
    Restituisce True se il colore di sfondo è giallo (o simile).
    Google Sheets API omette i componenti RGB quando valgono 0.
    Es. giallo puro #FFFF00 → {red:1.0, green:1.0} senza blue.
    Quindi i default devono essere 0.0, non 1.0.
    """
    if not color:
        return False

    r = color.get('red',   0.0)   # 0.0 quando omesso dall'API
    g = color.get('green', 0.0)   # 0.0 quando omesso dall'API
    b = color.get('blue',  0.0)   # 0.0 quando omesso dall'API

    # Bianco esplicito {1,1,1} → non occupato
    if r >= 0.95 and g >= 0.95 and b >= 0.95:
        return False

    # Giallo: rosso alto, verde alto, blu basso
    # Copre: giallo puro (1,1,0), ambra (1,0.8,0), giallo chiaro (1,1,0.4)
    return r >= 0.75 and g >= 0.65 and b <= 0.45


# ─── Parsing date ─────────────────────────────────────────────

def parse_week_dates(date_str: str, year: int):
    """
    Converte '23/05-30/05' in (date(2026,5,23), date(2026,5,30)).
    Gestisce il passaggio di mese (es. 26/09-03/10).
    Restituisce (None, None) se il formato non è valido.
    """
    try:
        parts = date_str.strip().split('-')
        if len(parts) != 2:
            return None, None
        start_s = parts[0].strip()   # '23/05'
        end_s   = parts[1].strip()   # '30/05'
        s_day, s_mon = int(start_s[:2]), int(start_s[3:5])
        e_day, e_mon = int(end_s[:2]),   int(end_s[3:5])
        return date(year, s_mon, s_day), date(year, e_mon, e_day)
    except Exception:
        return None, None


def dates_overlap(s1: date, e1: date, s2: date, e2: date) -> bool:
    return s1 < e2 and e1 > s2


# ─── Lettura disponibilità ────────────────────────────────────

def get_occupied(year: int, api_key: str, sheet_name: str) -> dict:
    """
    Legge il foglio e restituisce le settimane occupate per ogni appartamento,
    rilevando le celle con sfondo giallo.
    """
    row_data = fetch_sheet_data(api_key, sheet_name)
    occupied = {apt: [] for apt in APT_COLS}

    # Riga 0 = intestazione (anno, RIF001, ...) → saltiamo
    for row in row_data[1:]:
        values = row.get('values', [])
        if not values:
            continue

        # Colonna A: stringa con l'intervallo di date ('23/05-30/05')
        first_cell = values[0]
        date_val = (
            first_cell.get('userEnteredValue', {}).get('stringValue', '') or
            first_cell.get('userEnteredValue', {}).get('numberValue', '')
        )
        if not date_val or not isinstance(date_val, str):
            continue

        start, end = parse_week_dates(date_val, year)
        if not start or not end:
            continue

        # Controlla il colore di sfondo per ogni appartamento
        for apt_id, col_idx in APT_COLS.items():
            if col_idx >= len(values):
                continue
            cell   = values[col_idx]
            bg     = cell.get('userEnteredFormat', {}).get('backgroundColor', {})
            if is_yellow(bg):
                occupied[apt_id].append((start, end))
                print(f'[Occupato] {apt_id} settimana {date_val}')

    return occupied


# ─── Handler Vercel ───────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))
        except Exception:
            return self._json(400, {'error': 'Body JSON non valido'})

        checkin_str  = body.get('checkin')
        checkout_str = body.get('checkout')
        ospiti       = body.get('ospiti')

        if not all([checkin_str, checkout_str, ospiti]):
            return self._json(400, {'error': 'Parametri obbligatori: checkin, checkout, ospiti'})

        try:
            req_start = date.fromisoformat(checkin_str)
            req_end   = date.fromisoformat(checkout_str)
        except ValueError:
            return self._json(400, {'error': 'Formato date non valido (YYYY-MM-DD)'})

        if req_start >= req_end:
            return self._json(400, {'error': 'checkout deve essere dopo checkin'})

        # Nome del tab dinamico: "Prenotazioni_2026", "Prenotazioni_2027", ecc.
        sheet_name = f'{SHEET_NAME_PREFIX}_{req_start.year}'

        # Chiave API Google
        api_key = os.environ.get('GOOGLE_API_KEY', '')
        if not api_key:
            return self._json(500, {'error': 'GOOGLE_API_KEY non configurata'})

        # Carica dati appartamenti
        try:
            proprieta = load_proprieta()
        except Exception as e:
            return self._json(500, {'error': f'Errore caricamento dati: {e}'})

        # Leggi settimane occupate dal foglio
        try:
            occupied = get_occupied(req_start.year, api_key, sheet_name)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            print(f'[Sheets API] HTTP {e.code}: {err}')
            return self._json(502, {'error': f'Errore lettura foglio: HTTP {e.code}'})
        except Exception as e:
            print(f'[Sheets API] Errore: {e}')
            return self._json(502, {'error': f'Errore lettura foglio: {e}'})

        # Filtra appartamenti disponibili
        disponibili = []
        for apt_id, casa in proprieta.items():
            if casa.get('capacita', 0) < ospiti:
                continue
            apt_occupied = occupied.get(apt_id, [])
            is_free = not any(
                dates_overlap(s, e, req_start, req_end)
                for s, e in apt_occupied
            )
            if is_free:
                disponibili.append({'id': apt_id, **casa})

        return self._json(200, {'disponibili': disponibili})

    def log_message(self, format, *args):
        pass
