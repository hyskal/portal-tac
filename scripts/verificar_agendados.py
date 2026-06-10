import sqlite3
import os
from datetime import datetime, timedelta, timezone

def get_now_br():
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)

# Localiza o banco
db_files = [f for f in os.listdir('.') if f.endswith('.db')]
if not db_files:
    # Tenta procurar em subpastas caso esteja em instance/
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.db'):
                db_files.append(os.path.join(root, f))

if not db_files:
    print("Erro: Banco de dados nao encontrado.")
    exit()

db_path = db_files[0]
print(f"Verificando banco: {db_path}")
print(f"Hora atual (Brasília): {get_now_br().strftime('%d/%m/%Y %H:%M:%S')}")
print("-" * 50)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Busca os posts não deletados
cursor.execute("SELECT id, titulo, scheduled_at FROM post WHERE deleted_at IS NULL ORDER BY scheduled_at DESC LIMIT 5")
posts = cursor.fetchall()

if not posts:
    print("Nenhum post encontrado.")
else:
    for p in posts:
        p_id, titulo, p_date_str = p
        # Converte a string do banco para objeto datetime para comparar
        try:
            # Tenta formatos comuns de banco (ISO)
            p_date = datetime.fromisoformat(p_date_str.split('.')[0].replace(' ', 'T'))
        except:
            print(f"Erro ao converter data: {p_date_str}")
            continue

        agora = get_now_br()
        status = "AGENDADO (Invisível)" if p_date > agora else "PUBLICADO (Visível)"
        diff = p_date - agora
        
        print(f"Post: {titulo}")
        print(f"Data no Banco: {p_date.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Status Atual: {status}")
        if p_date > agora:
            horas = int(diff.total_seconds() // 3600)
            minutos = int((diff.total_seconds() % 3600) // 60)
            print(f"Aparece em: {horas}h e {minutos}min")
        print("-" * 30)

conn.close()
