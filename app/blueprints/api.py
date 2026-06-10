from flask import Blueprint, jsonify
from app.models import Post

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/eventos-calendario')
def get_eventos():
    """
    Retorna JSON compatível com FullCalendar.
    Mostra apenas posts que têm prazo ou são atividades.
    """
    # Busca atividades futuras ou recentes que não estão na lixeira
    posts = Post.query.filter(
        Post.deleted_at == None,
        (Post.prazo != None) | (Post.tipo == 'atividade')
    ).all()
    
    eventos = []
    for post in posts:
        # Define a data do evento (Prazo ou Agendamento)
        start_date = post.prazo if post.prazo else post.scheduled_at
        
        eventos.append({
            'id': post.id,
            'title': f"{post.turma.nome}: {post.titulo}",
            'start': start_date.isoformat(),
            'color': post.turma.cor, # A cor vem da Turma
            'url': f'/admin/post/editar/{post.id}' # Clica para editar
        })
    
    return jsonify(eventos)