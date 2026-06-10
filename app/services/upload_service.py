import cloudinary
import cloudinary.utils
import requests
import sys
import os
import time
from datetime import datetime

def upload_file_to_cloud(file_obj, custom_public_id=None):
    """
    Envia arquivo via Requests (Proxy Manual).
    Aceita 'custom_public_id' para definir o nome exato do arquivo.
    Organiza em pastas por Ano/Mês.
    """
    if not file_obj:
        return None
        
    try:
        # 1. Configurações e Proxy
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
        api_key = os.environ.get('CLOUDINARY_API_KEY')
        api_secret = os.environ.get('CLOUDINARY_API_SECRET')
        
        proxies = {
            "http": "http://proxy.server:3128",
            "https": "http://proxy.server:3128",
        }

        # 2. Organização Inteligente de Pastas (Ex: portal/2025/12)
        now = datetime.now()
        folder_path = f"portal_academico/{now.year}/{now.strftime('%m')}"

        # 3. Prepara Parâmetros
        timestamp = int(time.time())
        params_to_sign = {
            "folder": folder_path,
            "timestamp": timestamp,
            "overwrite": "true", # Permite substituir se tiver nome igual
            "unique_filename": "false" # IMPORTANTE: Para respeitar nosso nome
        }

        # Se tiver nome personalizado, adiciona ao payload
        if custom_public_id:
            params_to_sign["public_id"] = custom_public_id

        # 4. Gera Assinatura
        signature = cloudinary.utils.api_sign_request(params_to_sign, api_secret)

        # 5. Monta Payload
        payload = {
            "api_key": api_key,
            "signature": signature,
            **params_to_sign
        }

        file_obj.seek(0)
        files = {"file": file_obj}

        print(f"📤 Upload: {custom_public_id or 'Auto'} em {folder_path}...", file=sys.stderr)

        # 6. Envio
        url = f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload"
        
        response = requests.post(
            url,
            data=payload,
            files=files,
            proxies=proxies,
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            url_segura = data.get('secure_url')
            print(f"✅ Sucesso: {url_segura}", file=sys.stderr)
            
            return {
                'url': url_segura,
                'public_id': data.get('public_id'),
                'format': data.get('format')
            }
        else:
            print(f"❌ Erro Cloudinary ({response.status_code}): {response.text}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"❌ Erro Crítico Upload: {str(e)}", file=sys.stderr)
        return None