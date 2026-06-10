import os
import sys
from datetime import datetime
import pytz

# Adiciona o diretório pai ao path para que o import 'app' funcione
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), '..')))

try:
    from app import create_app
    from app.extensions import db
    from app.models import Post
    
    app = create_app()
    with app.app_context():
        tz_br = pytz.timezone('America/Sao_Paulo')
        agora_br = datetime.now(tz_br).replace(tzinfo=None)
        
        print(f"\n--- DIAGNÓSTICO ---")
        print(f"Hora Atual Brasília: {agora_br}")
        
        # Pega os 3 posts mais recentes
        posts = Post.query.filter(Post.deleted_at == None).order_by(Post.scheduled_at.desc()).limit(3).all()
        
        for p in posts:
            visivel = "SIM" if p.scheduled_at <= agora_br and not p.is_draft else "NÃO"
            print(f"\nPost: {p.titulo}")
            print(f"Agendado para: {p.scheduled_at}")
            print(f"Deveria estar visível? {visivel}")
            print(f"Motivo: {'Data futura' if p.scheduled_at > agora_br else 'OK'}")

except Exception as e:
    print(f"Erro: {e}")
