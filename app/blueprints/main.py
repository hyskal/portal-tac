from flask import Blueprint, render_template, abort, request
from flask_login import current_user
from app.extensions import db
from app.models import Turma, Post, Disciplina
from datetime import datetime, timedelta, timezone
import re

main_bp = Blueprint('main', __name__)

def get_now_br():
    # Retorna o horário de Brasília puro (naive) - UTC-3
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)

@main_bp.context_processor
def inject_now():
    return {'now': get_now_br()}

@main_bp.route('/')
def index():
    turmas = Turma.query.order_by(Turma.nome).all()
    return render_template('main/index.html', turmas=turmas)

@main_bp.route('/post/<int:id>')
def ver_post(id):
    post = Post.query.get_or_404(id)
    agora = get_now_br()
    
    if not current_user.is_authenticated:
        if post.is_draft or post.deleted_at or post.scheduled_at > agora:
            abort(404)
            
    context_slug = request.args.get('context')
    turma_contexto = None
    if context_slug:
        turma_contexto = Turma.query.filter_by(slug=context_slug).first()
    if not turma_contexto and post.turmas:
        turma_contexto = post.turmas[0]
    return render_template('main/post.html', post=post, turma_contexto=turma_contexto)

@main_bp.route('/<string:slug>')
def ver_turma(slug):
    turma = Turma.query.filter_by(slug=slug).first_or_404()
    agora = get_now_br()
    
    query = Post.query.filter(
        Post.turmas.contains(turma),
        Post.deleted_at == None,
        Post.is_draft == False,
        Post.scheduled_at <= agora
    )
    
    filtro = request.args.get('filtro')
    if filtro == 'atividade': query = query.filter(Post.tipo == 'atividade')
    elif filtro == 'material': query = query.filter(Post.tipo == 'material')
    elif filtro == 'aviso': query = query.filter(Post.tipo == 'aviso')
    elif filtro == 'importante': query = query.filter(Post.is_pinned == True)
    
    disciplina_id = request.args.get('disciplina')
    if disciplina_id: query = query.filter(Post.disciplina_id == int(disciplina_id))

    posts = query.order_by(Post.is_pinned.desc(), Post.scheduled_at.desc()).all()
    
    disciplinas_ativas = db.session.query(Disciplina)\
        .join(Post)\
        .filter(Post.turmas.contains(turma))\
        .filter(Post.scheduled_at <= agora)\
        .filter(Post.deleted_at == None)\
        .distinct()\
        .all()

    return render_template('main/turma.html', 
                           turma=turma, 
                           posts=posts, 
                           disciplinas=disciplinas_ativas,
                           filtro_ativo=filtro,
                           disciplina_ativa=disciplina_id)

# --- FILTROS JINJA2 ---

@main_bp.app_template_filter('youtube_embed')
def youtube_embed_filter(url):
    if not url: return None
    # Regex Atualizada para suportar /shorts/ e links mobile m.youtube
    regex = r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([\w\-]+)'
    match = re.search(regex, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"
    return url

@main_bp.app_template_filter('time_left')
def time_left_filter(dt):
    if not dt: return ""
    agora = get_now_br()
    if dt > agora:
        diff = dt - agora
        return f"em {int(diff.total_seconds() // 3600)}h"
    diff_p = agora - dt
    if diff_p.days == 0: return "Postado hoje"
    return f"Postado há {diff_p.days} dias"

@main_bp.app_template_filter('reading_time')
def reading_time_filter(html_content):
    if not html_content: return "1 min"
    text = re.sub('<[^<]+?>', '', html_content)
    words = len(text.split())
    minutes = round(words / 200)
    return f"{max(1, minutes)} min de leitura"

@main_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
