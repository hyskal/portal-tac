"""
Armazenamento plugável de anexos.

Provedores: 'local' (pasta static/uploads), 'sml' (SML Storage API —
Firebase Cloud Functions), 'supabase' (Supabase Storage via REST) e
'cloudinary' (serviço original, via variáveis de ambiente).

Se o provedor configurado for uma API e ela não responder, o arquivo é
salvo localmente (fallback automático) e o resultado vem com
``fallback: True`` para o admin ser avisado.
"""
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

import requests
from flask import current_app

from app.extensions import db
from app.models import Configuracao
from app.services.upload_service import upload_file_to_cloud

PROVIDERS = ('local', 'sml', 'supabase', 'cloudinary')

SML_BASE_URL_PADRAO = 'https://us-east1-sml-storage.cloudfunctions.net'

# Content-Type por extensão (a SML Storage API exige que o PUT use o
# mesmo Content-Type do signed URL, senão o Storage devolve 403)
CONTENT_TYPES = {
    'pdf':  'application/pdf',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'png':  'image/png',
    'gif':  'image/gif',
    'webp': 'image/webp',
    'doc':  'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls':  'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


# ---------- Configuração (banco com fallback para variáveis de ambiente) ----------

def get_config(chave, default=''):
    item = db.session.get(Configuracao, chave)
    if item is not None and (item.valor or '').strip():
        return item.valor.strip()
    return os.environ.get(chave.upper(), default)


def set_config(chave, valor):
    item = db.session.get(Configuracao, chave)
    if item is None:
        item = Configuracao(chave=chave)
        db.session.add(item)
    item.valor = (valor or '').strip()


def provider_ativo():
    p = get_config('storage_provider')
    if p in PROVIDERS:
        return p
    # Compatibilidade: quem já usava Cloudinary por env continua igual
    return 'cloudinary' if current_app.config.get('CLOUDINARY_CLOUD_NAME') else 'local'


# ---------- Utilidades ----------

def limpar_nome_arquivo(nome):
    base, _ = os.path.splitext(nome or 'arquivo')
    nfkd_form = unicodedata.normalize('NFKD', base)
    nome_ascii = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    nome_limpo = re.sub(r'[^a-zA-Z0-9]', '_', nome_ascii)
    return re.sub(r'_{2,}', '_', nome_limpo).strip('_') or 'arquivo'


def _extensao(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in (filename or '') else ''


# ---------- Upload (com fallback local) ----------

def upload_anexo(file_obj):
    """Envia o anexo pelo provedor ativo. Devolve dict com url/public_id/format/
    provider (e fallback=True quando a API falhou e o arquivo foi salvo local)."""
    if not file_obj or not file_obj.filename:
        return None

    base = limpar_nome_arquivo(file_obj.filename)
    ext = _extensao(file_obj.filename)
    provider = provider_ativo()
    resultado = None

    if provider != 'local':
        try:
            if provider == 'sml':
                resultado = _upload_sml(file_obj, base, ext)
            elif provider == 'supabase':
                resultado = _upload_supabase(file_obj, base, ext)
            elif provider == 'cloudinary':
                resultado = upload_file_to_cloud(
                    file_obj, custom_public_id=f"{base}_{datetime.now().strftime('%d%m%Y')}")
                if resultado:
                    resultado['provider'] = 'cloudinary'
        except Exception as e:
            print(f"⚠️ Provedor '{provider}' falhou: {e}", file=sys.stderr)
            resultado = None

    if resultado is None:
        resultado = _upload_local(file_obj, base, ext)
        if resultado and provider != 'local':
            resultado['fallback'] = True
    return resultado


def _upload_local(file_obj, base, ext):
    mes = datetime.now().strftime('%Y-%m')
    pasta = os.path.join(current_app.root_path, 'static', 'uploads', 'posts', mes)
    os.makedirs(pasta, exist_ok=True)
    nome = f"{int(time.time() * 1000)}_{base}{('.' + ext) if ext else ''}"
    file_obj.seek(0)
    file_obj.save(os.path.join(pasta, nome))
    return {
        'url': f"/static/uploads/posts/{mes}/{nome}",
        'public_id': f"posts/{mes}/{nome}",
        'format': ext,
        'provider': 'local',
    }


def _upload_sml(file_obj, base, ext):
    """Fluxo de 3 passos da SML Storage API: getUploadUrl → PUT → confirmUpload."""
    base_url = get_config('sml_base_url', SML_BASE_URL_PADRAO).rstrip('/')
    api_key = get_config('sml_api_key')
    projeto = get_config('sml_projeto', 'portal-tac')
    if not api_key:
        return None
    headers = {'Content-Type': 'application/json', 'x-api-key': api_key}
    filename = f"{base}{('.' + ext) if ext else ''}"

    # 1) Solicita o signed URL
    r = requests.post(f'{base_url}/getUploadUrl', headers=headers, timeout=20, json={
        'projeto': projeto, 'filename': filename,
        'tag1': 'portal-anexo', 'tag2': datetime.now().strftime('%Y-%m'), 'tag3': '',
    })
    data = r.json()
    if r.status_code != 200 or not data.get('success'):
        print(f"⚠️ SML getUploadUrl: {r.status_code} {data.get('error')}", file=sys.stderr)
        return None

    # 2) PUT direto ao Storage (Content-Type precisa coincidir com o signed URL)
    file_obj.seek(0)
    put = requests.put(data['uploadUrl'], data=file_obj.read(), timeout=120,
                       headers={'Content-Type': CONTENT_TYPES.get(ext, 'application/octet-stream')})
    if put.status_code not in (200, 201):
        print(f"⚠️ SML PUT: {put.status_code}", file=sys.stderr)
        return None

    # 3) Confirma o upload
    conf = requests.post(f'{base_url}/confirmUpload', headers=headers,
                         json={'docId': data['docId']}, timeout=30)
    cdata = conf.json()
    if conf.status_code != 200 or not cdata.get('success'):
        print(f"⚠️ SML confirmUpload: {conf.status_code} {cdata.get('error')}", file=sys.stderr)
        return None
    return {
        'url': cdata['url'],
        'public_id': cdata.get('path') or data.get('path'),
        'format': ext,
        'provider': 'sml',
    }


def _upload_supabase(file_obj, base, ext):
    url = get_config('supabase_url').rstrip('/')
    key = get_config('supabase_key')
    bucket = get_config('supabase_bucket', 'portal')
    if not (url and key):
        return None
    mes = datetime.now().strftime('%Y-%m')
    path = f"posts/{mes}/{int(time.time() * 1000)}_{base}{('.' + ext) if ext else ''}"
    file_obj.seek(0)
    r = requests.post(f'{url}/storage/v1/object/{bucket}/{path}', data=file_obj.read(), timeout=120,
                      headers={
                          'Authorization': f'Bearer {key}',
                          'apikey': key,
                          'Content-Type': CONTENT_TYPES.get(ext, 'application/octet-stream'),
                          'x-upsert': 'true',
                      })
    if r.status_code not in (200, 201):
        print(f"⚠️ Supabase upload: {r.status_code} {r.text[:200]}", file=sys.stderr)
        return None
    return {
        'url': f'{url}/storage/v1/object/public/{bucket}/{path}',
        'public_id': path,
        'format': ext,
        'provider': 'supabase',
    }


# ---------- Teste de conexão ----------

def testar_conexao(provider, valores=None):
    """Testa o provedor com os valores do formulário (sem precisar salvar antes).
    Devolve (ok: bool, mensagem: str)."""
    def val(chave, default=''):
        if valores is not None and (valores.get(chave) or '').strip():
            return valores.get(chave).strip()
        return get_config(chave, default)

    try:
        if provider == 'local':
            pasta = os.path.join(current_app.root_path, 'static', 'uploads', 'posts')
            os.makedirs(pasta, exist_ok=True)
            if os.access(pasta, os.W_OK):
                return True, 'Pasta local gravável (static/uploads/posts). Nenhuma API necessária.'
            return False, 'Sem permissão de escrita em static/uploads/posts.'

        if provider == 'sml':
            api_key = val('sml_api_key')
            if not api_key:
                return False, 'Informe a chave de API (header x-api-key).'
            base_url = val('sml_base_url', SML_BASE_URL_PADRAO).rstrip('/')
            projeto = val('sml_projeto', 'portal-tac')
            r = requests.post(f'{base_url}/listUploads', timeout=15,
                              headers={'Content-Type': 'application/json', 'x-api-key': api_key},
                              json={'projeto': projeto})
            if r.status_code == 200 and r.json().get('success'):
                return True, f"Conectado! {r.json().get('count', 0)} arquivo(s) no projeto \"{projeto}\"."
            if r.status_code == 401:
                return False, 'Chave de API inválida (401).'
            return False, f'A API respondeu com erro {r.status_code}.'

        if provider == 'supabase':
            url, key = val('supabase_url').rstrip('/'), val('supabase_key')
            bucket = val('supabase_bucket', 'portal')
            if not (url and key):
                return False, 'Informe a URL do projeto e a chave (service_role).'
            r = requests.get(f'{url}/storage/v1/bucket/{bucket}', timeout=15,
                             headers={'Authorization': f'Bearer {key}', 'apikey': key})
            if r.status_code == 200:
                publico = r.json().get('public')
                aviso = '' if publico else ' Atenção: o bucket não é público — as URLs dos anexos não abrirão para os alunos.'
                return True, f'Conectado! Bucket "{bucket}" encontrado.{aviso}'
            if r.status_code in (400, 404):
                return False, f'Bucket "{bucket}" não encontrado no projeto.'
            if r.status_code in (401, 403):
                return False, 'Chave inválida ou sem permissão (use a service_role key).'
            return False, f'O Supabase respondeu com erro {r.status_code}.'

        if provider == 'cloudinary':
            if current_app.config.get('CLOUDINARY_CLOUD_NAME'):
                return True, 'Credenciais CLOUDINARY_* presentes no ambiente. O teste completo acontece no primeiro upload.'
            return False, 'Variáveis CLOUDINARY_* não configuradas no ambiente do servidor.'

        return False, 'Provedor desconhecido.'
    except requests.RequestException as e:
        return False, f'Sem conexão com a API ({e.__class__.__name__}). Uploads cairão no salvamento local.'
