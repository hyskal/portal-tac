from app.models import Post, Turma
from datetime import datetime

def filtrar_posts(args):
    """
    Filtra posts para o Admin e Dashboard.
    Suporta relacionamento Many-to-Many.
    """
    query = Post.query

    # Filtro por Turma (Agora verifica se a turma está na lista do post)
    turma_id = args.get('turma_id')
    if turma_id:
        query = query.filter(Post.turmas.any(id=turma_id))
    
    # Filtro por Tipo
    if args.get('tipo'):
        query = query.filter(Post.tipo == args.get('tipo'))

    # Filtro por Status
    status = args.get('status')
    if status == 'rascunho':
        query = query.filter(Post.is_draft == True, Post.deleted_at == None)
    elif status == 'agendado':
        query = query.filter(Post.scheduled_at > datetime.now(), Post.deleted_at == None)
    elif status == 'lixeira':
        query = query.filter(Post.deleted_at != None)
    else:
        # Padrão: Ativos e não deletados
        query = query.filter(Post.deleted_at == None)
    
    return query.order_by(Post.is_pinned.desc(), Post.scheduled_at.desc())