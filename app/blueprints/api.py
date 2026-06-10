from flask import Blueprint, jsonify, request, render_template, make_response
from app.extensions import db
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
        # Post pode pertencer a várias turmas (M2M); usa a primeira como referência
        turma = post.turmas[0] if post.turmas else None

        eventos.append({
            'id': post.id,
            'title': f"{turma.nome + ': ' if turma else ''}{post.titulo}",
            'start': start_date.isoformat(),
            'color': turma.cor if turma else '#4F46E5',
            'url': f'/admin/post/editar/{post.id}' # Clica para editar
        })

    return jsonify(eventos)

@api_bp.route('/post/<int:id>/like', methods=['POST'])
def like_post(id):
    """
    Curtir/descurtir um post sem login. Um cookie liked_{id} impede o
    duplo like; clicar de novo desfaz a curtida. Retorna o fragmento HTML
    do botão para o swap outerHTML do HTMX.
    """
    post = Post.query.get_or_404(id)
    cookie_key = f'liked_{id}'
    ja_curtiu = request.cookies.get(cookie_key) == '1'

    if ja_curtiu:
        post.likes = max(0, (post.likes or 0) - 1)
        liked = False
    else:
        post.likes = (post.likes or 0) + 1
        liked = True
    db.session.commit()

    resp = make_response(render_template('main/partials/like_button.html',
                                         post=post, liked=liked, animar=liked))
    if liked:
        resp.set_cookie(cookie_key, '1', max_age=60 * 60 * 24 * 365, samesite='Lax')
    else:
        resp.delete_cookie(cookie_key)
    return resp
