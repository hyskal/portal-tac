from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, make_response
from flask_login import login_required
from datetime import datetime
import os
import unicodedata
import re
from app.extensions import db
from app.models import Turma, Post, Link, Disciplina, Chamado
from app.services.upload_service import upload_file_to_cloud
from app.services.query_service import filtrar_posts
from app.utils import is_htmx, hx_toast, hx_event

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def limpar_nome_arquivo(nome):
    base, _ = os.path.splitext(nome)
    nfkd_form = unicodedata.normalize('NFKD', base)
    nome_ascii = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    nome_limpo = re.sub(r'[^a-zA-Z0-9]', '_', nome_ascii)
    return re.sub(r'_{2,}', '_', nome_limpo)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
def arquivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def contar_chamados_pendentes():
    return Chamado.query.filter_by(resolvido=False).count()

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    query = filtrar_posts(request.args)
    page = request.args.get('page', 1, type=int)
    posts = query.paginate(page=page, per_page=10)

    # Paginação/filtros via HTMX recebem só o fragmento da tabela
    if is_htmx():
        return render_template('admin/partials/posts_table.html', posts=posts)

    turmas = Turma.query.order_by(Turma.arquivada, Turma.nome).all()
    links = Link.query.all()
    disciplinas = Disciplina.query.order_by(Disciplina.nome).all()
    chamados = Chamado.query.order_by(Chamado.resolvido, Chamado.created_at.desc()).all()
    chamados_pendentes = contar_chamados_pendentes()

    # CAMINHO ABSOLUTO PARA VERIFICAÇÃO
    path_horario = os.path.join(current_app.root_path, 'static', 'uploads', 'horario_professor.png')
    tem_horario = os.path.exists(path_horario)

    return render_template('admin/dashboard.html', posts=posts, turmas=turmas, links=links,
                           disciplinas=disciplinas, chamados=chamados,
                           chamados_pendentes=chamados_pendentes,
                           tem_horario=tem_horario, now=datetime.now())

@admin_bp.route('/upload-horario', methods=['POST'])
@login_required
def upload_horario():
    file = request.files.get('file')
    if file and file.filename != '':
        # GARANTE DIRETÓRIO ABSOLUTO
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        filepath = os.path.join(upload_path, 'horario_professor.png')
        file.save(filepath)
        flash('Horário atualizado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/post/novo', methods=['GET', 'POST'])
@admin_bp.route('/post/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def gerenciar_post(id=None):
    post = Post.query.get_or_404(id) if id else None
    if request.method == 'POST':
        if not post:
            post = Post()
            db.session.add(post)
        post.titulo = request.form.get('titulo'); post.conteudo = request.form.get('conteudo'); post.tipo = request.form.get('tipo')
        post.video_url = request.form.get('video_url'); post.is_pinned = True if request.form.get('is_pinned') else False
        post.is_draft = True if request.form.get('is_draft') else False
        post.permite_chamado = True if request.form.get('permite_chamado') else False
        post.disciplina_id = int(request.form.get('disciplina_id')) if request.form.get('disciplina_id') else None
        ag = request.form.get('scheduled_at')
        if ag: post.scheduled_at = datetime.strptime(ag, '%Y-%m-%dT%H:%M')
        pr = request.form.get('prazo')
        if pr: post.prazo = datetime.strptime(pr, '%Y-%m-%dT%H:%M')
        db.session.flush()
        post.turmas = [Turma.query.get(int(tid)) for tid in request.form.getlist('turmas') if Turma.query.get(int(tid))]
        arq = request.files.get('arquivo')
        if arq and arq.filename != '' and arquivo_permitido(arq.filename):
            d = upload_file_to_cloud(arq, custom_public_id=f"{limpar_nome_arquivo(arq.filename)}_{datetime.now().strftime('%d%m%Y')}")
            if d: post.arquivo_url = d['url']; post.arquivo_formato = d['format']
        db.session.commit()
        acao = request.form.get('acao_salvar')
        if acao == 'salvar_novo': return redirect(url_for('admin.gerenciar_post'))
        if acao == 'salvar_editar':
            flash('Post salvo!', 'success')
            return redirect(url_for('admin.gerenciar_post', id=post.id))
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/form_post.html', post=post, turmas=Turma.query.order_by(Turma.arquivada, Turma.nome).all(), disciplinas=Disciplina.query.all())

@admin_bp.route('/post/clonar/<int:id>')
@login_required
def clonar_post(id):
    original = Post.query.get_or_404(id)
    novo = Post(titulo=f"Cópia de {original.titulo}", conteudo=original.conteudo, tipo=original.tipo, video_url=original.video_url, arquivo_url=original.arquivo_url, arquivo_formato=original.arquivo_formato, disciplina_id=original.disciplina_id, is_draft=True, permite_chamado=original.permite_chamado)
    for t in original.turmas: novo.turmas.append(t)
    db.session.add(novo); db.session.commit(); flash('Post clonado!', 'info'); return redirect(url_for('admin.gerenciar_post', id=novo.id))

@admin_bp.route('/post/delete/<int:id>')
@login_required
def delete_post(id):
    p = Post.query.get_or_404(id); p.deleted_at = datetime.now(); db.session.commit(); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/turma/nova', methods=['POST'])
@login_required
def nova_turma():
    n, s, c = request.form.get('nome'), request.form.get('slug'), request.form.get('cor', '#3498db')
    if n and s and not Turma.query.filter_by(slug=s).first():
        db.session.add(Turma(nome=n, slug=s, cor=c)); db.session.commit()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/turma/<int:id>/arquivar', methods=['POST'])
@login_required
def arquivar_turma(id):
    turma = Turma.query.get_or_404(id)
    turma.arquivada = not turma.arquivada
    db.session.commit()
    msg = f'Turma "{turma.nome}" {"arquivada" if turma.arquivada else "reativada"}.'
    if is_htmx():
        resp = make_response(render_template('admin/partials/turma_row.html', t=turma))
        return hx_toast(resp, msg, 'success' if not turma.arquivada else 'warning')
    flash(msg, 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/turma/delete/<int:id>')
@login_required
def delete_turma(id):
    t = Turma.query.get_or_404(id); db.session.delete(t); db.session.commit(); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/disciplina/nova', methods=['POST'])
@login_required
def nova_disciplina():
    n, c = request.form.get('nome'), request.form.get('cor', '#6c757d')
    if n: db.session.add(Disciplina(nome=n, cor=c)); db.session.commit()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/disciplina/delete/<int:id>')
@login_required
def delete_disciplina(id):
    d = Disciplina.query.get_or_404(id); db.session.delete(d); db.session.commit(); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/link/novo', methods=['POST'])
@login_required
def novo_link():
    t, u, tids = request.form.get('titulo'), request.form.get('url'), request.form.getlist('turmas')
    if t and u:
        l = Link(titulo=t, url=u if u.startswith('http') else 'https://'+u)
        db.session.add(l)
        for tid in tids:
            tt = Turma.query.get(int(tid))
            if tt: l.turmas.append(tt)
        db.session.commit()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/link/delete/<int:id>')
@login_required
def delete_link(id):
    l = Link.query.get_or_404(id); db.session.delete(l); db.session.commit(); return redirect(url_for('admin.dashboard'))

# --- CHAMADOS DE DÚVIDA ---

@admin_bp.route('/chamados')
@login_required
def listar_chamados():
    status = request.args.get('status', 'todos')
    query = Chamado.query
    if status == 'pendentes':
        query = query.filter_by(resolvido=False)
    elif status == 'resolvidos':
        query = query.filter_by(resolvido=True)
    chamados = query.order_by(Chamado.resolvido, Chamado.created_at.desc()).all()

    if is_htmx():
        return render_template('admin/partials/chamados_lista.html',
                               chamados=chamados, status_ativo=status)
    # Acesso direto: dashboard com a aba de chamados ativa
    return redirect(url_for('admin.dashboard') + '#chamados')

@admin_bp.route('/chamado/<int:id>/linha')
@login_required
def chamado_linha(id):
    chamado = Chamado.query.get_or_404(id)
    if is_htmx():
        return render_template('admin/partials/chamado_row.html', c=chamado)
    return redirect(url_for('admin.dashboard') + '#chamados')

@admin_bp.route('/chamado/<int:id>/responder-form')
@login_required
def chamado_responder_form(id):
    chamado = Chamado.query.get_or_404(id)
    if is_htmx():
        return render_template('admin/partials/chamado_responder_form.html', c=chamado)
    return redirect(url_for('admin.dashboard') + '#chamados')

@admin_bp.route('/chamado/<int:id>/responder', methods=['POST'])
@login_required
def responder_chamado(id):
    chamado = Chamado.query.get_or_404(id)
    resposta = (request.form.get('resposta_admin') or '').strip()
    if not resposta:
        if is_htmx():
            return render_template('admin/partials/chamado_responder_form.html', c=chamado,
                                   erro='Escreva uma resposta antes de enviar.')
        flash('Escreva uma resposta antes de enviar.', 'danger')
        return redirect(url_for('admin.dashboard') + '#chamados')

    chamado.resposta_admin = resposta
    chamado.resolvido = True
    chamado.respondido_at = datetime.now()
    db.session.commit()

    if is_htmx():
        resp = make_response(render_template('admin/partials/chamado_row.html', c=chamado))
        hx_event(resp, 'chamadosCount', {'count': contar_chamados_pendentes()})
        return hx_toast(resp, f'Resposta registrada para {chamado.nome}. ✅', 'success')
    flash('Resposta registrada!', 'success')
    return redirect(url_for('admin.dashboard') + '#chamados')
