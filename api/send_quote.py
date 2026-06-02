# api/send_quote.py

from http.server import BaseHTTPRequestHandler
import json, os
from datetime import date
import resend


def config():
    return {
        'owner_email':  os.environ.get('OWNER_EMAIL',  'info@follonicavacanze.com'),
        'from_address': os.environ.get('FROM_ADDRESS', 'onboarding@resend.dev'),
        'resend_key':   os.environ.get('RESEND_API_KEY', ''),
        'phone':        '338 2233166',
        'site':         'FollonicaVacanze.com',
        'site_url':     'https://www.follonicavacanze.com',
    }


MESI   = ['gennaio','febbraio','marzo','aprile','maggio','giugno',
          'luglio','agosto','settembre','ottobre','novembre','dicembre']
GIORNI = ['lunedi','martedi','mercoledi','giovedi','venerdi','sabato','domenica']


def format_date(s):
    d = date.fromisoformat(s)
    return "%s %d %s %d" % (GIORNI[d.weekday()], d.day, MESI[d.month - 1], d.year)


def calc_notti(checkin, checkout):
    return (date.fromisoformat(checkout) - date.fromisoformat(checkin)).days


def build_animali_str(animali):
    if not animali:
        return ''
    piccoli = int(animali.get('piccoli', 0))
    grandi  = int(animali.get('grandi',  0))
    tipo    = animali.get('tipo', '').strip()
    if piccoli + grandi == 0:
        return ''
    parts = []
    if piccoli:
        parts.append("%d piccola taglia" % piccoli)
    if grandi:
        parts.append("%d grande taglia" % grandi)
    s = ', '.join(parts)
    if tipo:
        s += ' (%s)' % tipo
    return s


# ── Riga etichetta/valore compatibile con tutti i client email ──
# Usa una mini-tabella invece di flexbox (non supportato da Gmail/Outlook)
def row(label, value):
    return (
        '<table width="100%%" cellpadding="0" cellspacing="0" style="margin:4px 0;border-bottom:1px solid #E8DDD0">'
        '<tr>'
        '<td style="font-size:14px;color:#7A6E63;padding:6px 12px 6px 0;width:110px;vertical-align:top">%s</td>'
        '<td style="font-size:14px;color:#1C1812;font-weight:600;padding:6px 0;vertical-align:top">%s</td>'
        '</tr></table>'
    ) % (label, value)


def build_apt_rows_proprietario(appartamenti):
    rows = []
    for a in appartamenti:
        apt_id = a.get('id', '').upper()
        nome   = a.get('nome', '')
        url    = a.get('url', '')
        rows.append(row(apt_id, '%s &nbsp;<a href="%s" style="font-size:12px;color:#B85224">Vedi pagina &rarr;</a>' % (nome, url)))
    return ''.join(rows)


def build_apt_rows_cliente(appartamenti):
    rows = []
    for a in appartamenti:
        rows.append(row('Appartamento', a.get('nome', '')))
    return ''.join(rows)


def build_apt_cta_buttons(appartamenti):
    buttons = []
    for a in appartamenti:
        nome = a.get('nome', '')
        url  = a.get('url', '')
        btn = (
            '<div style="text-align:center;margin:10px 0">'
            '<a href="%s" style="display:inline-block;background:#B85224;'
            'color:white !important;text-decoration:none;padding:13px 30px;'
            'border-radius:10px;font-weight:600;font-size:14px;font-family:Arial,sans-serif">'
            'Vedi foto %s &rarr;</a></div>'
        ) % (url, nome)
        buttons.append(btn)
    return ''.join(buttons)


def email_proprietario(p, cfg):
    notti       = calc_notti(p['checkin'], p['checkout'])
    ospiti      = int(p['adulti']) + int(p.get('bambini', 0))
    bambini_str = (' + %s bambini' % p['bambini']) if int(p.get('bambini', 0)) > 0 else ''
    anim_str    = build_animali_str(p.get('animali'))
    anim_row    = row('Animali', anim_str) if anim_str else ''
    note_row    = row('Note', '<span style="font-style:italic">%s</span>' % p['note']) if p.get('note') else ''
    settimane   = notti // 7
    sett_label  = 'settimana' if settimane == 1 else 'settimane'

    appartamenti = p.get('appartamenti', [])
    n_apt        = len(appartamenti)
    apt_label    = '%d appartamento richiesto' % n_apt if n_apt == 1 else '%d appartamenti richiesti' % n_apt
    apt_rows     = build_apt_rows_proprietario(appartamenti)

    html = """<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px">
<div style="background:white;max-width:600px;margin:0 auto;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

  <div style="background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;color:white">
    <h1 style="margin:0;font-size:22px">&#127968; Nuova richiesta di preventivo</h1>
    <p style="margin:6px 0 0;opacity:.8;font-size:14px">%(site)s &mdash; ricevuta ora</p>
  </div>

  <div style="padding:28px 32px">

    <h2 style="color:#2C6B7A;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 10px">%(apt_label)s</h2>
    <div style="background:#F5EFE4;border-radius:10px;padding:16px;border-left:4px solid #B85224;margin-bottom:22px">
      %(apt_rows)s
    </div>

    <h2 style="color:#2C6B7A;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 10px">Periodo e ospiti</h2>
    <div style="background:#F5EFE4;border-radius:10px;padding:16px;border-left:4px solid #B85224;margin-bottom:22px">
      %(row_arrivo)s
      %(row_partenza)s
      %(row_durata)s
      %(row_ospiti)s
      %(anim_row)s
    </div>

    <h2 style="color:#2C6B7A;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 10px">Dati cliente</h2>
    <div style="background:#F5EFE4;border-radius:10px;padding:16px;border-left:4px solid #B85224;margin-bottom:22px">
      %(row_nome)s
      %(row_email)s
      %(row_telefono)s
      %(note_row)s
    </div>

    <div style="text-align:center;margin-top:8px">
      <a href="mailto:%(email)s?subject=Preventivo - %(site)s"
         style="display:inline-block;background:#B85224;color:white !important;
                text-decoration:none;padding:13px 30px;border-radius:8px;
                font-weight:600;font-size:14px;font-family:Arial,sans-serif">
        Rispondi al cliente &rarr;
      </a>
    </div>

  </div>
  <div style="background:#F5EFE4;padding:14px 32px;font-size:12px;color:#7A6E63;text-align:center">
    %(site)s &middot; Messaggio automatico
  </div>
</div>
</body></html>""" % {
        'site':        cfg['site'],
        'apt_label':   apt_label,
        'apt_rows':    apt_rows,
        'row_arrivo':  row('Arrivo',   format_date(p['checkin'])),
        'row_partenza':row('Partenza', format_date(p['checkout'])),
        'row_durata':  row('Durata',   '%d notti (%d %s)' % (notti, settimane, sett_label)),
        'row_ospiti':  row('Ospiti',   '%s adulti%s (tot. %d)' % (p['adulti'], bambini_str, ospiti)),
        'anim_row':    anim_row,
        'row_nome':    row('Nome',     '%s %s' % (p['nome'], p['cognome'])),
        'row_email':   row('Email',    '<a href="mailto:%(e)s" style="color:#B85224">%(e)s</a>' % {'e': p['email']}),
        'row_telefono':row('Telefono', p['telefono']),
        'note_row':    note_row,
        'email':       p['email'],
    }
    return html


def email_cliente(p, cfg):
    notti       = calc_notti(p['checkin'], p['checkout'])
    bambini_str = (' + %s bambini' % p['bambini']) if int(p.get('bambini', 0)) > 0 else ''
    anim_str    = build_animali_str(p.get('animali'))
    anim_row    = row('&#128062; Animali', anim_str) if anim_str else ''
    apt_rows    = build_apt_rows_cliente(p.get('appartamenti', []))
    apt_buttons = build_apt_cta_buttons(p.get('appartamenti', []))

    html = """<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px">
<div style="background:white;max-width:600px;margin:0 auto;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

  <div style="background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;color:white;text-align:center">
    <div style="font-size:48px;margin-bottom:10px">&#9989;</div>
    <h1 style="margin:0;font-size:22px">Richiesta ricevuta!</h1>
    <p style="margin:8px 0 0;opacity:.85;font-size:15px">Grazie %(nome)s, ti risponderemo entro poche ore</p>
  </div>

  <div style="padding:28px 32px">
    <p style="font-size:15px;color:#1C1812;line-height:1.7">
      Abbiamo ricevuto la tua richiesta di preventivo.
      Ti contatteremo presto all'indirizzo <strong>%(email)s</strong>.
    </p>

    <div style="background:linear-gradient(135deg,#F5EFE4,#EDE2D4);border-radius:12px;padding:20px;border-left:4px solid #B85224;margin-bottom:22px">
      <div style="font-weight:700;font-size:15px;color:#B85224;margin-bottom:12px">&#128203; Riepilogo</div>
      %(apt_rows)s
      %(row_arrivo)s
      %(row_partenza)s
      %(row_durata)s
      %(row_ospiti)s
      %(anim_row)s
    </div>

    %(apt_buttons)s

    <div style="background:#F0F7F9;border-radius:10px;padding:16px 20px;border-left:4px solid #2C6B7A">
      <strong style="color:#2C6B7A">&#128222; Risposta urgente?</strong><br>
      <span style="font-size:14px">Chiamaci al
        <a href="tel:+39%(phone_raw)s" style="color:#2C6B7A">%(phone)s</a>
      </span>
    </div>
  </div>

  <div style="background:#F5EFE4;padding:14px 32px;font-size:12px;color:#7A6E63;text-align:center;border-top:1px solid #E8DDD0">
    %(site)s &middot; <a href="%(site_url)s" style="color:#B85224">%(site_url)s</a>
  </div>
</div>
</body></html>""" % {
        'nome':        p['nome'],
        'email':       p['email'],
        'apt_rows':    apt_rows,
        'apt_buttons': apt_buttons,
        'row_arrivo':  row('&#128197; Arrivo',   format_date(p['checkin'])),
        'row_partenza':row('&#128197; Partenza', format_date(p['checkout'])),
        'row_durata':  row('&#127769; Durata',   '%d notti' % notti),
        'row_ospiti':  row('&#128101; Ospiti',   '%s adulti%s' % (p['adulti'], bambini_str)),
        'anim_row':    anim_row,
        'phone':       cfg['phone'],
        'phone_raw':   cfg['phone'].replace(' ', ''),
        'site':        cfg['site'],
        'site_url':    cfg['site_url'],
    }
    return html


def send_emails(p, cfg):
    try:
        resend.api_key = cfg['resend_key']
        apt_nomi = ', '.join([a.get('nome', a.get('id', '')) for a in p.get('appartamenti', [])])
        resend.Emails.send({
            "from": cfg['from_address'], "to": [cfg['owner_email']],
            "subject": "Nuova richiesta preventivo - %s" % apt_nomi,
            "html": email_proprietario(p, cfg),
        })
        resend.Emails.send({
            "from": cfg['from_address'], "to": [p['email']],
            "subject": "Richiesta ricevuta - %s" % cfg['site'],
            "html": email_cliente(p, cfg),
        })
        return True, "ok"
    except Exception as e:
        return False, str(e)


class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, status, data):
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

        required = ['nome', 'cognome', 'email', 'telefono',
                    'appartamenti', 'checkin', 'checkout', 'adulti']
        missing = [f for f in required if not body.get(f)]
        if missing:
            return self._json(400, {'error': 'Campi mancanti: ' + ', '.join(missing)})

        if not body.get('appartamenti') or len(body['appartamenti']) == 0:
            return self._json(400, {'error': 'Seleziona almeno un appartamento'})

        cfg = config()
        if not cfg['resend_key']:
            return self._json(500, {'error': 'RESEND_API_KEY non configurata'})

        p = {
            'nome':         body['nome'],
            'cognome':      body['cognome'],
            'email':        body['email'],
            'telefono':     body['telefono'],
            'note':         body.get('note', ''),
            'appartamenti': body['appartamenti'],
            'checkin':      body['checkin'],
            'checkout':     body['checkout'],
            'adulti':       body['adulti'],
            'bambini':      body.get('bambini', 0),
            'animali':      body.get('animali', {}),
        }

        ok, err = send_emails(p, cfg)
        if ok:
            return self._json(200, {'success': True})
        else:
            return self._json(500, {'error': 'Errore invio: ' + err})

    def log_message(self, format, *args):
        pass
