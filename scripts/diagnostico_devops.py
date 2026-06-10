import os
import sys
from datetime import datetime
import pytz

# Tenta carregar o App para ver a config real
try:
    from app import create_app
    from app.extensions import db
    from app.models import Post, Turma
    app = create_app()
    app.app_context().push()
    
    print("--- [1] AMBIENTE ---")
    print(f"Diretório Atual: {os.getcwd()}")
    print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    
    print("\n--- [2] HORÁRIOS ---")
    tz_br = pytz.timezone('America/Sao_Paulo')
    agora_utc = datetime.now()
    agora_br = datetime.now(tz_br)
    print(f"Relógio do Servidor (UTC): {agora_utc}")
    print(f"Relógio de Brasília:        {agora_br}")
    
    print("\n--- [3] DADOS NO BANCO (POSTS AGENDADOS) ---")
    # Busca posts que não foram deletados
    posts = Post.query.filter(Post.deleted_at == None).order_by(Post.scheduled_at.desc()).limit(5).all()
    
    if not posts:
        print("Nenhum post encontrado no banco.")
    else:
        for p in posts:
            status = "FUTURO (Não deve aparecer)" if p.scheduled_at > agora_br.replace(tzinfo=None) else "PASSADO (Deve aparecer)"
            print(f"ID: {p.id} | Título: {p.titulo[:30]}...")
            print(f"   - Agendado para: {p.scheduled_at}")
            print(f"   - Status Lógico: {status}")
            print(f"   - Rascunho? {p.is_draft}")
            print(f"   - Turmas: {[t.nome for t in p.turmas]}")

except Exception as e:
    print(f"ERRO NO DIAGNÓSTICO: {str(e)}")
    import traceback
    traceback.print_exc()
