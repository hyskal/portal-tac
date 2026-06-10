import json
import re

from flask import request

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def is_htmx():
    """True quando a requisição veio do HTMX (e não é restauração de histórico,
    que precisa da página completa)."""
    return (request.headers.get('HX-Request') == 'true'
            and request.headers.get('HX-History-Restore-Request') != 'true')


def hx_toast(response, message, type='success'):
    """Anexa um evento showToast via header HX-Trigger (consumido no base.html)."""
    triggers = {'showToast': {'message': message, 'type': type}}
    existing = response.headers.get('HX-Trigger')
    if existing:
        try:
            data = json.loads(existing)
            data.update(triggers)
            triggers = data
        except ValueError:
            pass
    response.headers['HX-Trigger'] = json.dumps(triggers)
    return response


def hx_event(response, name, payload=None):
    """Anexa um evento custom via HX-Trigger (ex.: atualizar badge de chamados)."""
    triggers = {name: payload if payload is not None else {}}
    existing = response.headers.get('HX-Trigger')
    if existing:
        try:
            data = json.loads(existing)
            data.update(triggers)
            triggers = data
        except ValueError:
            pass
    response.headers['HX-Trigger'] = json.dumps(triggers)
    return response


def email_valido(email):
    return bool(email and EMAIL_RE.match(email))
