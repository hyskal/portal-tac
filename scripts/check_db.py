import sqlite3
import sys
from datetime import datetime
import pytz

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tz = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(tz).replace(tzinfo=None)

print(f"--- DIAGNÓSTICO DIRETO NO SQLITE ---")
print(f"Banco: {db_path}")
print(f"Hora Brasília: {agora}")

# Ajuste os nomes das colunas se necessário, mas o padrão do seu model é este:
try:
    cursor.execute("SELECT id, titulo, scheduled_at, is_draft FROM post WHERE deleted_at IS NULL ORDER BY scheduled_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for r in rows:
        status = "FUTURO" if r[2] > agora.isoformat() else "PASSADO"
        print(f"\nID: {r[0]} | Titulo: {r[1]}")
        print(f"Agendado para: {r[2]} | Status: {status} | Rascunho: {r[3]}")
except Exception as e:
    print(f"Erro ao ler tabela: {e}")

conn.close()
