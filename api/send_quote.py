# api/send_quote.py
# Vercel Serverless Function — Python
# Usa l'SDK ufficiale Resend per evitare blocchi Cloudflare

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import date
import resend

# ─────────────────────────────────────────────
# CONFIGURAZIONE
# ─────────────────────────────────────────────

def config() -> dict:
    return {
        'owner_email':  os.environ.get('OWNER_EMAIL',  'info@follonicavacanze.com'),
        'from_address': os.environ.get('FROM_ADDRESS', 'onboarding@resend.dev'),
        'resend_key':   os.environ.get('RESEND_API_KEY', ''),
        'phone':        '338 2233166',
        'site':         'FollonicaVacanze.com',
        'site_url':     'https://www.follonicavacanze.com',
    }

# ─────────────────────────────────────────────
# UTILITÀ
# ─────────────────────────────────────────────

MESI = ['gennaio','febbraio','marzo','aprile','maggio','giugno',
        'luglio','agosto','settembre','ottobre','novembre','dicembre']

GIORNI = ['lunedì','martedì','mercoledì','giovedì','venerdì','sabato','domenica']

def format_date(date_str: str) -> str:
    d = date.fromisoformat(date_str)
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"

def calc_notti(checkin: str, checkout: str) -> int:
    return (date.fromisoformat(checkout) - date.fromisoformat(checkin)).days


# ─────────────────────────────────────────────
# TEMPLATE EMAIL — notifica al proprietario
# ─────────────────────────────────────────────

def email_proprietario(p: dict, cfg: dict) -> str:
    notti  = calc_notti(p['checkin'], p['checkout'])
    ospiti = int(p['adulti']) + int(p.get('bambini', 0))
    bambini_str = f" + {p['bambini']} bambini" if int(p.get('bambini', 0)) > 0 else ""
    note_row = f"""
        <div class="row"><span>Note</span>
        <span style="font-style:italic">{p.get('note','')}</span></div>""" if p.get('note') else ''

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px}}
  .card{{background:white;max-width:600px;margin:0 auto;border-radius:16px;
         overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  .hdr{{background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;color:white}}
  .hdr h1{{margin:0;font-size:22px}} .hdr p{{margin:6px 0 0;opacity:.8;font-size:14px}}
  .body{{padding:28px 32px}}
  .section{{margin-bottom:22px}}
  .section h2{{color:#2C6B7A;font-size:13px;letter-spacing:1px;
               text-transform:uppercase;margin:0 0 10px}}
  .box{{background:#F5EFE4;border-radius:10px;padding:16px;border-left:4px solid #B85224}}
  .row{{display:flex;justify-content:space-between;padding:5px 0;
        border-bottom:1px solid #E8DDD0;font-size:14px}}
  .row:last-child{{border-bottom:none}}
  .row span:first-child{{color:#7A6E63}} .row span:last-child{{font-weight:600}}
  .badge{{background:#B85224;color:white;padding:3px 12px;
          border-radius:20px;font-size:12px;font-weight:600}}
  .btn{{display:inline-block;background:#B85224;color:white;padding:13px 30px;
        border-radius:8px;text-decoration:none;font-weight:600;font-size:14px}}
  .footer{{background:#F5EFE4;padding:14px 32px;font-size:12px;
           color:#7A6E63;text-align:center}}
  a{{color:#B85224}}
</style></head><body>
<div class="card">
  <div class="hdr">
    <h1>🏡 Nuova richiesta di preventivo</h1>
    <p>{cfg['site']} — ricevuta ora</p>
  </div>
  <div class="body">
    <div class="section">
      <h2>Appartamento richiesto</h2>
      <div class="box">
        <div class="row"><span>Codice</span>
          <span><span class="badge">{p['appartamento'].get('id','').upper()}</span></span></div>
        <div class="row"><span>Nome</span>
          <span>{p['appartamento'].get('nome','')}</span></div>
        <div class="row"><span>Link</span>
          <span><a href="{p['appartamento'].get('url','')}">Vedi pagina →</a></span></div>
      </div>
    </div>
    <div class="section">
      <h2>Periodo richiesto</h2>
      <div class="box">
        <div class="row"><span>Arrivo</span><span>{format_date(p['checkin'])}</span></div>
        <div class="row"><span>Partenza</span><span>{format_date(p['checkout'])}</span></div>
        <div class="row"><span>Durata</span>
          <span>{notti} notti ({notti//7} {'settimana' if notti//7==1 else 'settimane'})</span></div>
        <div class="row"><span>Ospiti</span>
          <span>{p['adulti']} adulti{bambini_str} (tot. {ospiti})</span></div>
      </div>
    </div>
    <div class="section">
      <h2>Dati cliente</h2>
      <div class="box">
        <div class="row"><span>Nome</span>
          <span>{p['nome']} {p['cognome']}</span></div>
        <div class="row"><span>Email</span>
          <span><a href="mailto:{p['email']}">{p['email']}</a></span></div>
        <div class="row"><span>Telefono</span>
          <span><a href="tel:{p['telefono']}">{p['telefono']}</a></span></div>
        {note_row}
      </div>
    </div>
    <p style="text-align:center;margin-top:8px">
      <a class="btn"
         href="mailto:{p['email']}?subject=Preventivo {p['appartamento'].get('id','').upper()} — {cfg['site']}">
        Rispondi al cliente →
      </a>
    </p>
  </div>
  <div class="footer">{cfg['site']} · Messaggio automatico dal form sul sito</div>
</div></body></html>"""


# ─────────────────────────────────────────────
# TEMPLATE EMAIL — conferma al cliente
# ─────────────────────────────────────────────

def email_cliente(p: dict, cfg: dict) -> str:
    notti = calc_notti(p['checkin'], p['checkout'])
    bambini_str = f" + {p['bambini']} bambini" if int(p.get('bambini', 0)) > 0 else ""

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px}}
  .card{{background:white;max-width:600px;margin:0 auto;border-radius:16px;
         overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  .hdr{{background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;
        color:white;text-align:center}}
  .hdr .icon{{font-size:48px;margin-bottom:10px}}
  .hdr h1{{margin:0;font-size:22px}} .hdr p{{margin:8px 0 0;opacity:.85;font-size:15px}}
  .body{{padding:28px 32px}}
  .summary{{background:linear-gradient(135deg,#F5EFE4,#EDE2D4);border-radius:12px;
            padding:20px;border-left:4px solid #B85224;margin-bottom:22px}}
  .row{{display:flex;gap:10px;padding:6px 0;font-size:14px}}
  .lbl{{color:#7A6E63;min-width:90px}} .val{{font-weight:600;color:#1C1812}}
  .cta{{text-align:center;margin:22px 0}}
  .btn{{display:inline-block;background:#B85224;color:white;padding:13px 30px;
        border-radius:10px;text-decoration:none;font-weight:600;font-size:14px}}
  .contact{{background:#F0F7F9;border-radius:10px;padding:16px 20px;
            border-left:4px solid #2C6B7A}}
  .footer{{background:#F5EFE4;padding:14px 32px;font-size:12px;
           color:#7A6E63;text-align:center;border-top:1px solid #E8DDD0}}
  a{{color:#B85224}}
</style></head><body>
<div class="card">
  <div class="hdr">
    <div class="icon">✅</div>
    <h1>Richiesta ricevuta!</h1>
    <p>Grazie {p['nome']}, ti risponderemo entro poche ore</p>
  </div>
  <div class="body">
    <p style="font-size:15px;color:#1C1812;line-height:1.7">
      Abbiamo ricevuto la tua richiesta di preventivo per
      <strong>{p['appartamento'].get('nome','')}</strong>.
      Ti contatteremo presto all'indirizzo <strong>{p['email']}</strong>.
    </p>
    <div class="summary">
      <div style="font-weight:700;font-size:15px;color:#B85224;margin-bottom:12px">
        📋 Riepilogo della tua richiesta
      </div>
      <div class="row"><span class="lbl">🏡 Appart.</span>
        <span class="val">{p['appartamento'].get('nome','')}</span></div>
      <div class="row"><span class="lbl">📅 Arrivo</span>
        <span class="val">{format_date(p['checkin'])}</span></div>
      <div class="row"><span class="lbl">📅 Partenza</span>
        <span class="val">{format_date(p['checkout'])}</span></div>
      <div class="row"><span class="lbl">🌙 Durata</span>
        <span class="val">{notti} notti</span></div>
      <div class="row"><span class="lbl">👥 Ospiti</span>
        <span class="val">{p['adulti']} adulti{bambini_str}</span></div>
    </div>
    <div class="cta">
      <a class="btn" href="{p['appartamento'].get('url','')}">
        Vedi le foto dell'appartamento →
      </a>
    </div>
    <div class="contact">
      <strong style="color:#2C6B7A">📞 Hai bisogno di una risposta urgente?</strong><br>
      <span style="font-size:14px;color:#3D3730">
        Chiamaci al <a href="tel:+39{cfg['phone'].replace(' ','')}"
        style="color:#2C6B7A">{cfg['phone']}</a>
      </span>
    </div>
  </div>
  <div class="footer">
    {cfg['site']} · Appartamenti sul mare a Follonica, Maremma Toscana<br>
    <a href="{cfg['site_url']}">{cfg['site_url']}</a>
  </div>
</div></body></html>"""


# ─────────────────────────────────────────────
# INVIO EMAIL via SDK Resend ufficiale
# ─────────────────────────────────────────────

def send_emails(p: dict, cfg: dict) -> tuple[bool, str]:
    """Invia le due email usando l'SDK ufficiale Resend."""
    try:
        resend.api_key = cfg['resend_key']

        # Email al proprietario
        resend.Emails.send({
            "from":    cfg['from_address'],
            "to":      [cfg['owner_email']],
            "subject": f"🏡 Nuova richiesta preventivo — {p['appartamento'].get('nome','')}",
            "html":    email_proprietario(p, cfg),
        })

        # Email di conferma al cliente
        resend.Emails.send({
            "from":    cfg['from_address'],
            "to":      [p['email']],
            "subject": f"✅ Richiesta ricevuta — {cfg['site']}",
            "html":    email_cliente(p, cfg),
        })

        return True, "ok"

    except Exception as e:
        return False, str(e)


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
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return self._json_response(400, {'error': 'Body JSON non valido'})

        required = ['nome', 'cognome', 'email', 'telefono',
                    'appartamento', 'checkin', 'checkout', 'adulti']
        missing  = [f for f in required if not body.get(f)]
        if missing:
            return self._json_response(400, {
                'error': f"Campi obbligatori mancanti: {', '.join(missing)}"
            })

        if '@' not in body['email'] or '.' not in body['email'].split('@')[-1]:
            return self._json_response(400, {'error': 'Email non valida'})

        cfg = config()
        if not cfg['resend_key']:
            return self._json_response(500, {'error': 'RESEND_API_KEY non configurata'})

        p = {**body, 'bambini': body.get('bambini', 0), 'note': body.get('note', '')}

        ok, err = send_emails(p, cfg)

        if ok:
            return self._json_response(200, {'success': True})
        else:
            return self._json_response(500, {'error': 'Errore durante l\'invio. Contattaci al 338 2233166.'})

    def log_message(self, format, *args):
        pass
