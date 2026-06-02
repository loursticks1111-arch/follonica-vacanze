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


def build_apt_rows_proprietario(appartamenti):
    rows = []
    for a in appartamenti:
        apt_id  = a.get('id', '').upper()
        nome    = a.get('nome', '')
        url     = a.get('url', '')
        row = (
            '<div class="row">'
            '<span>%s</span>'
            '<span style="text-align:right">%s<br>'
            '<a href="%s" style="font-size:12px;color:#B85224">Vedi pagina &rarr;</a>'
            '</span></div>'
        ) % (apt_id, nome, url)
        rows.append(row)
    return ''.join(rows)


def build_apt_rows_cliente(appartamenti):
    rows = []
    for a in appartamenti:
        nome = a.get('nome', '')
        row = (
            '<div class="row">'
            '<span class="lbl">&#127968; Appart.</span>'
            '<span class="val">%s</span>'
            '</div>'
        ) % nome
        rows.append(row)
    return ''.join(rows)


def build_apt_cta_buttons(appartamenti):
    buttons = []
    for a in appartamenti:
        nome = a.get('nome', '')
        url  = a.get('url', '')
        btn = (
            '<div class="cta">'
            '<a class="btn" href="%s">Vedi foto %s &rarr;</a>'
            '</div>'
        ) % (url, nome)
        buttons.append(btn)
    return ''.join(buttons)


def email_proprietario(p, cfg):
    notti       = calc_notti(p['checkin'], p['checkout'])
    ospiti      = int(p['adulti']) + int(p.get('bambini', 0))
    bambini_str = (' + %s bambini' % p['bambini']) if int(p.get('bambini', 0)) > 0 else ''
    anim_str    = build_animali_str(p.get('animali'))
    anim_row    = ''
    if anim_str:
        anim_row = '<div class="row"><span>Animali</span><span>%s</span></div>' % anim_str
    note_row = ''
    if p.get('note'):
        note_row = '<div class="row"><span>Note</span><span style="font-style:italic">%s</span></div>' % p['note']

    appartamenti = p.get('appartamenti', [])
    n_apt        = len(appartamenti)
    apt_label    = '%d appartamento richiesto' % n_apt if n_apt == 1 else '%d appartamenti richiesti' % n_apt
    apt_rows     = build_apt_rows_proprietario(appartamenti)
    settimane    = notti // 7
    sett_label   = 'settimana' if settimane == 1 else 'settimane'

    html = """<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8">
<style>
body{font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px}
.card{background:white;max-width:600px;margin:0 auto;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.hdr{background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;color:white}
.hdr h1{margin:0;font-size:22px}.hdr p{margin:6px 0 0;opacity:.8;font-size:14px}
.body{padding:28px 32px}
.section{margin-bottom:22px}
.section h2{color:#2C6B7A;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 10px}
.box{background:#F5EFE4;border-radius:10px;padding:16px;border-left:4px solid #B85224}
.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #E8DDD0;font-size:14px}
.row:last-child{border-bottom:none}
.row span:first-child{color:#7A6E63;min-width:90px}.row span:last-child{font-weight:600}
.btn{display:inline-block;background:#B85224;color:white;padding:13px 30px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px}
.footer{background:#F5EFE4;padding:14px 32px;font-size:12px;color:#7A6E63;text-align:center}
a{color:#B85224}
</style></head><body>
<div class="card">
<div class="hdr"><h1>&#127968; Nuova richiesta di preventivo</h1><p>%(site)s &mdash; ricevuta ora</p></div>
<div class="body">
<div class="section"><h2>%(apt_label)s</h2><div class="box">%(apt_rows)s</div></div>
<div class="section"><h2>Periodo e ospiti</h2><div class="box">
<div class="row"><span>Arrivo</span><span>%(checkin)s</span></div>
<div class="row"><span>Partenza</span><span>%(checkout)s</span></div>
<div class="row"><span>Durata</span><span>%(notti)d notti (%(settimane)d %(sett_label)s)</span></div>
<div class="row"><span>Ospiti</span><span>%(adulti)s adulti%(bambini_str)s (tot. %(ospiti)d)</span></div>
%(anim_row)s
</div></div>
<div class="section"><h2>Dati cliente</h2><div class="box">
<div class="row"><span>Nome</span><span>%(nome)s %(cognome)s</span></div>
<div class="row"><span>Email</span><span><a href="mailto:%(email)s">%(email)s</a></span></div>
<div class="row"><span>Telefono</span><span>%(telefono)s</span></div>
%(note_row)s
</div></div>
<p style="text-align:center;margin-top:8px">
<a class="btn" href="mailto:%(email)s?subject=Preventivo - %(site)s">Rispondi al cliente &rarr;</a>
</p>
</div>
<div class="footer">%(site)s &middot; Messaggio automatico</div>
</div></body></html>""" % {
        'site': cfg['site'], 'apt_label': apt_label, 'apt_rows': apt_rows,
        'checkin': format_date(p['checkin']), 'checkout': format_date(p['checkout']),
        'notti': notti, 'settimane': settimane, 'sett_label': sett_label,
        'adulti': p['adulti'], 'bambini_str': bambini_str, 'ospiti': ospiti,
        'anim_row': anim_row, 'note_row': note_row,
        'nome': p['nome'], 'cognome': p['cognome'],
        'email': p['email'], 'telefono': p['telefono'],
    }
    return html


def email_cliente(p, cfg):
    notti       = calc_notti(p['checkin'], p['checkout'])
    bambini_str = (' + %s bambini' % p['bambini']) if int(p.get('bambini', 0)) > 0 else ''
    anim_str    = build_animali_str(p.get('animali'))
    anim_row    = ''
    if anim_str:
        anim_row = '<div class="row"><span class="lbl">&#128062; Animali</span><span class="val">%s</span></div>' % anim_str

    apt_rows    = build_apt_rows_cliente(p.get('appartamenti', []))
    apt_buttons = build_apt_cta_buttons(p.get('appartamenti', []))

    html = """<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8">
<style>
body{font-family:Arial,sans-serif;background:#F5EFE4;margin:0;padding:20px}
.card{background:white;max-width:600px;margin:0 auto;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.hdr{background:linear-gradient(135deg,#8B3A10,#B85224);padding:28px 32px;color:white;text-align:center}
.hdr .icon{font-size:48px;margin-bottom:10px}
.hdr h1{margin:0;font-size:22px}.hdr p{margin:8px 0 0;opacity:.85;font-size:15px}
.body{padding:28px 32px}
.summary{background:linear-gradient(135deg,#F5EFE4,#EDE2D4);border-radius:12px;padding:20px;border-left:4px solid #B85224;margin-bottom:22px}
.row{display:flex;gap:10px;padding:6px 0;font-size:14px}
.lbl{color:#7A6E63;min-width:90px}.val{font-weight:600;color:#1C1812}
.cta{text-align:center;margin:12px 0}
.btn{display:inline-block;background:#B85224;color:white;padding:13px 30px;border-radius:10px;text-decoration:none;font-weight:600;font-size:14px}
.contact{background:#F0F7F9;border-radius:10px;padding:16px 20px;border-left:4px solid #2C6B7A}
.footer{background:#F5EFE4;padding:14px 32px;font-size:12px;color:#7A6E63;text-align:center;border-top:1px solid #E8DDD0}
a{color:#B85224}
</style></head><body>
<div class="card">
<div class="hdr"><div class="icon">&#9989;</div><h1>Richiesta ricevuta!</h1>
<p>Grazie %(nome)s, ti risponderemo entro poche ore</p></div>
<div class="body">
<p style="font-size:15px;color:#1C1812;line-height:1.7">
Abbiamo ricevuto la tua richiesta di preventivo.
Ti contatteremo presto all'indirizzo <strong>%(email)s</strong>.
</p>
<div class="summary">
<div style="font-weight:700;font-size:15px;color:#B85224;margin-bottom:12px">&#128203; Riepilogo</div>
%(apt_rows)s
<div class="row"><span class="lbl">&#128197; Arrivo</span><span class="val">%(checkin)s</span></div>
<div class="row"><span class="lbl">&#128197; Partenza</span><span class="val">%(checkout)s</span></div>
<div class="row"><span class="lbl">&#127769; Durata</span><span class="val">%(notti)d notti</span></div>
<div class="row"><span class="lbl">&#128101; Ospiti</span><span class="val">%(adulti)s adulti%(bambini_str)s</span></div>
%(anim_row)s
</div>
%(apt_buttons)s
<div class="contact">
<strong style="color:#2C6B7A">&#128222; Risposta urgente?</strong><br>
<span style="font-size:14px">Chiamaci al <a href="tel:+39%(phone_raw)s" style="color:#2C6B7A">%(phone)s</a></span>
</div>
</div>
<div class="footer">%(site)s &middot; <a href="%(site_url)s">%(site_url)s</a></div>
</div></body></html>""" % {
        'nome': p['nome'], 'email': p['email'],
        'apt_rows': apt_rows, 'apt_buttons': apt_buttons,
        'checkin': format_date(p['checkin']), 'checkout': format_date(p['checkout']),
        'notti': notti, 'adulti': p['adulti'], 'bambini_str': bambini_str,
        'anim_row': anim_row,
        'phone': cfg['phone'], 'phone_raw': cfg['phone'].replace(' ', ''),
        'site': cfg['site'], 'site_url': cfg['site_url'],
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
            'nome':        body['nome'],
            'cognome':     body['cognome'],
            'email':       body['email'],
            'telefono':    body['telefono'],
            'note':        body.get('note', ''),
            'appartamenti': body['appartamenti'],
            'checkin':     body['checkin'],
            'checkout':    body['checkout'],
            'adulti':      body['adulti'],
            'bambini':     body.get('bambini', 0),
            'animali':     body.get('animali', {}),
        }

        ok, err = send_emails(p, cfg)
        if ok:
            return self._json(200, {'success': True})
        else:
            return self._json(500, {'error': 'Errore invio: ' + err})

    def log_message(self, format, *args):
        pass
