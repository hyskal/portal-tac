from flask import Blueprint, render_template, abort, request, redirect, url_for, make_response
from flask_login import current_user
from sqlalchemy import extract
from app.extensions import db
from app.models import Turma, Post, Disciplina, Chamado
from app.utils import is_htmx, hx_toast, email_valido
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
    # Turmas arquivadas não aparecem na lista pública
    turmas = Turma.query.filter(Turma.arquivada == False).order_by(Turma.nome).all()
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

    abrir_chamado = request.args.get('chamado') == '1' and post.permite_chamado
    return render_template('main/post.html', post=post, turma_contexto=turma_contexto,
                           abrir_chamado=abrir_chamado)

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
    if filtro in ['atividade', 'material', 'aviso']:
        query = query.filter(Post.tipo == filtro)
    elif filtro == 'importante':
        query = query.filter(Post.is_pinned == True)

    disciplina_id = request.args.get('disciplina')
    if disciplina_id:
        query = query.filter(Post.disciplina_id == int(disciplina_id))

    # Filtro de Arquivo (Mês/Ano)
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    if mes and ano:
        query = query.filter(extract('month', Post.scheduled_at) == mes)
        query = query.filter(extract('year', Post.scheduled_at) == ano)

    posts = query.order_by(Post.is_pinned.desc(), Post.scheduled_at.desc()).all()

    # Meses/anos que possuem posts (menu de Arquivo)
    arquivo_datas = db.session.query(
        extract('month', Post.scheduled_at).label('mes'),
        extract('year', Post.scheduled_at).label('ano')
    ).filter(Post.turmas.contains(turma), Post.deleted_at == None,
             Post.is_draft == False, Post.scheduled_at <= agora)\
     .distinct().order_by(Post.scheduled_at.desc()).all()

    disciplinas_ativas = db.session.query(Disciplina)\
        .join(Post)\
        .filter(Post.turmas.contains(turma))\
        .filter(Post.scheduled_at <= agora)\
        .filter(Post.deleted_at == None)\
        .distinct()\
        .all()

    contexto = dict(turma=turma,
                    posts=posts,
                    disciplinas=disciplinas_ativas,
                    filtro_ativo=filtro,
                    disciplina_ativa=disciplina_id,
                    arquivo_datas=arquivo_datas,
                    mes_ativo=mes,
                    ano_ativo=ano)

    # Requisição HTMX (chips/bottom-nav) recebe só o fragmento do feed
    if is_htmx():
        return render_template('main/partials/feed_posts.html', **contexto)
    return render_template('main/turma.html', **contexto)

# --- CHAMADOS DE DÚVIDA ---

@main_bp.route('/post/<int:id>/chamado-form')
def chamado_form(id):
    post = Post.query.get_or_404(id)
    if not post.permite_chamado:
        abort(404)
    if is_htmx():
        return render_template('main/partials/chamado_form.html', post=post)
    # Acesso direto: página completa do post com o formulário aberto
    return redirect(url_for('main.ver_post', id=id, chamado=1) + '#chamado-area-%d' % id)

@main_bp.route('/post/<int:id>/chamado', methods=['POST'])
def criar_chamado(id):
    post = Post.query.get_or_404(id)
    if not post.permite_chamado:
        abort(404)

    nome = (request.form.get('nome') or '').strip()
    email = (request.form.get('email') or '').strip()
    telefone = (request.form.get('telefone') or '').strip()
    duvida = (request.form.get('duvida') or '').strip()
    telefone_digitos = re.sub(r'\D', '', telefone)

    errors = {}
    if not nome:
        errors['nome'] = 'Informe seu nome.'
    if not email:
        errors['email'] = 'Informe seu e-mail.'
    elif not email_valido(email):
        errors['email'] = 'E-mail inválido. Confira o endereço digitado.'
    if not telefone:
        errors['telefone'] = 'Informe seu telefone com DDD.'
    elif not (10 <= len(telefone_digitos) <= 13):
        errors['telefone'] = 'Telefone inválido. Use DDD + número.'
    if not duvida:
        errors['duvida'] = 'Escreva sua dúvida.'

    if errors:
        form_data = {'nome': nome, 'email': email, 'telefone': telefone, 'duvida': duvida}
        if is_htmx():
            return render_template('main/partials/chamado_form.html', post=post,
                                   errors=errors, form_data=form_data)
        turma_contexto = post.turmas[0] if post.turmas else None
        return render_template('main/post.html', post=post, turma_contexto=turma_contexto,
                               abrir_chamado=True, errors=errors, form_data=form_data)

    chamado = Chamado(post_id=post.id, nome=nome[:100], email=email[:150],
                      telefone=telefone[:20], duvida=duvida)
    db.session.add(chamado)
    db.session.commit()

    if is_htmx():
        resp = make_response(render_template('main/partials/chamado_sucesso.html', post=post))
        return hx_toast(resp, 'Dúvida enviada! O professor vai te responder por e-mail.', 'success')
    turma_contexto = post.turmas[0] if post.turmas else None
    return render_template('main/post.html', post=post, turma_contexto=turma_contexto,
                           chamado_enviado=True)

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

@main_bp.app_template_filter('fone_digits')
def fone_digits_filter(telefone):
    """Só os dígitos do telefone (para links wa.me)."""
    return re.sub(r'\D', '', telefone or '')

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
