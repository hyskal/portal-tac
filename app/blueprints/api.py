from flask import Blueprint, jsonify, request, render_template, make_response
from flask_login import login_required
from app.extensions import db
from app.models import Post, Anotacao

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/eventos-calendario')
@login_required
def get_eventos():
    """
    Retorna JSON compatível com FullCalendar (usado no painel admin).
    Posts com prazo ou atividades + anotações do professor.
    """
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
            'id': f'post-{post.id}',
            'title': f"{turma.nome + ': ' if turma else ''}{post.titulo}",
            'start': start_date.isoformat(),
            'color': turma.cor if turma else '#4F46E5',
            'url': f'/admin/post/editar/{post.id}',  # Clica para editar
            'extendedProps': {'tipo': 'post'},
        })

    # Anotações/avisos do professor (clicáveis e editáveis no calendário)
    for a in Anotacao.query.all():
        start = f"{a.data.isoformat()}T{a.hora.strftime('%H:%M')}" if a.hora else a.data.isoformat()
        nomes_turmas = [t.nome for t in a.turmas]
        eventos.append({
            'id': f'anotacao-{a.id}',
            'title': f"📝 {a.titulo}" + (f" [{', '.join(nomes_turmas)}]" if nomes_turmas else ''),
            'start': start,
            'color': a.cor or '#4F46E5',
            'extendedProps': {
                'tipo': 'anotacao',
                'anotacao_id': a.id,
                'titulo': a.titulo,
                'descricao': a.descricao or '',
                'data': a.data.isoformat(),
                'hora': a.hora.strftime('%H:%M') if a.hora else '',
                'cor': a.cor or '#4F46E5',
                'turma_ids': [t.id for t in a.turmas],
            },
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
