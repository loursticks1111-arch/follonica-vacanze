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
        '<table width="100%%" cellpadding="0" cellspacing="0" style="margin:4px 0;border-bottom:1px solid #E2E8EE">'
        '<tr>'
        '<td style="font-size:14px;color:#6B7280;padding:6px 12px 6px 0;width:110px;vertical-align:top">%s</td>'
        '<td style="font-size:14px;color:#2C2C2C;font-weight:600;padding:6px 0;vertical-align:top">%s</td>'
        '</tr></table>'
    ) % (label, value)


def build_apt_rows_proprietario(appartamenti):
    rows = []
    for a in appartamenti:
        apt_id = a.get('id', '').upper()
        nome   = a.get('nome', '')
        url    = a.get('url', '')
        rows.append(row(apt_id, '%s &nbsp;<a href="%s" style="font-size:12px;color:#1A6FA8">Vedi pagina &rarr;</a>' % (nome, url)))
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
            '<a href="%s" style="display:inline-block;background:#1A6FA8;'
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
    note_html   = ''
    if p.get('note'):
        note_html = """
        <div style="margin-top:20px">
          <p style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
                    color:#0D8C8C;margin:0 0 8px">Note aggiuntive</p>
          <div style="background:#EBF5F5;border-left:4px solid #0D8C8C;border-radius:6px;
                      padding:14px 16px;font-size:14px;color:#2C2C2C;
                      font-style:italic;line-height:1.65">%s</div>
        </div>""" % p['note']

    settimane  = notti // 7
    sett_label = 'settimana' if settimane == 1 else 'settimane'
    appartamenti = p.get('appartamenti', [])
    n_apt      = len(appartamenti)
    apt_label  = '%d appartamento richiesto' % n_apt if n_apt == 1 else '%d appartamenti richiesti' % n_apt
    apt_rows   = build_apt_rows_proprietario(appartamenti)

    return """<!DOCTYPE html>
<html lang="it" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Nuova richiesta preventivo</title>
  <style>
    body { margin:0; padding:0; background:#F4F7FA;
           font-family:Arial,Helvetica,sans-serif; -webkit-text-size-adjust:100%%; }
    table { border-collapse:collapse; }
    img { border:0; display:block; }
    a { color:#1A6FA8; }
    .wrap { width:100%%; max-width:600px; margin:0 auto; }
    @media screen and (max-width:620px) {
      .wrap        { width:100%% !important; }
      .pad         { padding:16px !important; }
      .pad-sm      { padding:12px !important; }
      .font-sm     { font-size:13px !important; }
      .btn-full    { width:100%% !important; text-align:center !important; }
    }
  </style>
</head>
<body style="margin:0;padding:0;background:#F4F7FA">

<!-- Wrapper -->
<table width="100%%" cellpadding="0" cellspacing="0" role="presentation">
<tr><td align="center" style="padding:24px 8px">

<table class="wrap" cellpadding="0" cellspacing="0" role="presentation"
       style="width:100%%;max-width:600px;background:#ffffff;
              border-radius:10px;overflow:hidden;
              box-shadow:0 2px 16px rgba(0,0,0,0.08)">

  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#125082,#1A6FA8);
               padding:22px 28px;text-align:left">
      <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:2px;
                text-transform:uppercase;color:rgba(255,255,255,0.75)">%(site)s</p>
      <h1 style="margin:6px 0 0;font-size:20px;font-weight:700;
                 color:#ffffff;line-height:1.3">
        &#127968; Nuova richiesta di preventivo
      </h1>
    </td>
  </tr>

  <!-- Corpo -->
  <tr>
    <td class="pad" style="padding:24px 28px">

      <!-- Appartamenti -->
      <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:1px;
                text-transform:uppercase;color:#1A6FA8">%(apt_label)s</p>
      <div style="background:#EBF4FB;border-left:4px solid #1A6FA8;
                  border-radius:6px;padding:14px 16px;margin-bottom:20px">
        %(apt_rows)s
      </div>

      <!-- Periodo -->
      <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:1px;
                text-transform:uppercase;color:#1A6FA8">Periodo e ospiti</p>
      <div style="background:#EBF4FB;border-left:4px solid #1A6FA8;
                  border-radius:6px;padding:14px 16px;margin-bottom:20px">
        %(row_arrivo)s
        %(row_partenza)s
        %(row_durata)s
        %(row_ospiti)s
        %(anim_row)s
      </div>

      <!-- Cliente -->
      <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:1px;
                text-transform:uppercase;color:#1A6FA8">Dati cliente</p>
      <div style="background:#EBF4FB;border-left:4px solid #1A6FA8;
                  border-radius:6px;padding:14px 16px;margin-bottom:20px">
        %(row_nome)s
        %(row_email)s
        %(row_tel)s
      </div>

      %(note_html)s

      <!-- CTA -->
      <table width="100%%" cellpadding="0" cellspacing="0" role="presentation"
             style="margin-top:22px">
      <tr><td align="center">
        <a class="btn-full" href="mailto:%(email)s?subject=Preventivo - %(site)s"
           style="display:inline-block;background:#1A6FA8;color:#ffffff !important;
                  text-decoration:none;padding:13px 32px;border-radius:7px;
                  font-size:14px;font-weight:700;letter-spacing:.3px;
                  font-family:Arial,Helvetica,sans-serif">
          Rispondi al cliente &rarr;
        </a>
      </td></tr></table>

    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#F4F7FA;padding:14px 28px;text-align:center;
               border-top:1px solid #D1D9E0">
      <p style="margin:0;font-size:11px;color:#6B7280">
        %(site)s &middot; Messaggio automatico
      </p>
    </td>
  </tr>

</table>
</td></tr></table>
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
        'row_email':   row('Email',    '<a href="mailto:%(e)s" style="color:#1A6FA8">%(e)s</a>' % {'e': p['email']}),
        'row_tel':     row('Telefono', p['telefono']),
        'note_html':   note_html,
        'email':       p['email'],
    }

def email_cliente(p, cfg):
    notti       = calc_notti(p['checkin'], p['checkout'])
    bambini_str = (' + %s bambini' % p['bambini']) if int(p.get('bambini', 0)) > 0 else ''
    anim_str    = build_animali_str(p.get('animali'))
    anim_row    = row('&#128062; Animali', anim_str) if anim_str else ''
    apt_rows    = build_apt_rows_cliente(p.get('appartamenti', []))
    apt_buttons = build_apt_cta_buttons(p.get('appartamenti', []))

    return """<!DOCTYPE html>
<html lang="it" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Richiesta ricevuta</title>
  <style>
    body { margin:0; padding:0; background:#F4F7FA;
           font-family:Arial,Helvetica,sans-serif; -webkit-text-size-adjust:100%%; }
    table { border-collapse:collapse; }
    img   { border:0; display:block; }
    a     { color:#1A6FA8; }
    .wrap { width:100%%; max-width:600px; margin:0 auto; }
    @media screen and (max-width:620px) {
      .wrap     { width:100%% !important; }
      .pad      { padding:16px !important; }
      .btn-full { width:100%% !important; text-align:center !important;
                  display:block !important; }
    }
  </style>
</head>
<body style="margin:0;padding:0;background:#F4F7FA">

<table width="100%%" cellpadding="0" cellspacing="0" role="presentation">
<tr><td align="center" style="padding:24px 8px">

<table class="wrap" cellpadding="0" cellspacing="0" role="presentation"
       style="width:100%%;max-width:600px;background:#ffffff;
              border-radius:10px;overflow:hidden;
              box-shadow:0 2px 16px rgba(0,0,0,0.08)">

  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#125082,#1A6FA8);
               padding:26px 28px;text-align:center">
      <div style="font-size:42px;line-height:1;margin-bottom:10px">&#9989;</div>
      <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff">
        Richiesta ricevuta!
      </h1>
      <p style="margin:6px 0 0;font-size:14px;color:rgba(255,255,255,0.82)">
        Grazie %(nome)s, ti risponderemo entro poche ore
      </p>
    </td>
  </tr>

  <!-- Intro -->
  <tr>
    <td class="pad" style="padding:22px 28px 0">
      <p style="margin:0;font-size:15px;color:#2C2C2C;line-height:1.65">
        Abbiamo ricevuto la tua richiesta di preventivo.<br>
        Ti contatteremo presto all'indirizzo
        <strong>%(email)s</strong>.
      </p>
    </td>
  </tr>

  <!-- Riepilogo -->
  <tr>
    <td class="pad" style="padding:18px 28px">
      <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:1px;
                text-transform:uppercase;color:#1A6FA8">&#128203; Riepilogo</p>
      <div style="background:linear-gradient(135deg,#EBF4FB,#E0EEF8);
                  border-left:4px solid #1A6FA8;border-radius:6px;padding:14px 16px">
        %(apt_rows)s
        %(row_arrivo)s
        %(row_partenza)s
        %(row_durata)s
        %(row_ospiti)s
        %(anim_row)s
      </div>
    </td>
  </tr>

  <!-- Bottoni appartamenti -->
  <tr>
    <td class="pad" style="padding:0 28px 18px">
      %(apt_buttons)s
    </td>
  </tr>

  <!-- Contatti urgenza -->
  <tr>
    <td class="pad" style="padding:0 28px 22px">
      <div style="background:#EBF5F5;border-left:4px solid #0D8C8C;
                  border-radius:6px;padding:14px 16px">
        <p style="margin:0 0 4px;font-weight:700;font-size:14px;color:#0D8C8C">
          &#128222; Hai bisogno di una risposta urgente?
        </p>
        <p style="margin:0;font-size:14px;color:#2C2C2C">
          Chiamaci al
          <a href="tel:+39%(phone_raw)s" style="color:#0D8C8C;font-weight:700">
            %(phone)s
          </a>
        </p>
      </div>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#F4F7FA;padding:14px 28px;text-align:center;
               border-top:1px solid #D1D9E0">
      <p style="margin:0 0 4px;font-size:11px;color:#6B7280">%(site)s</p>
      <a href="%(site_url)s" style="font-size:11px;color:#1A6FA8">%(site_url)s</a>
    </td>
  </tr>

</table>
</td></tr></table>
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
