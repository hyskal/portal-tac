"""
Backup e restauração do conteúdo do portal em JSON
(turmas, disciplinas, links/biblioteca, posts e chamados).

A restauração só ADICIONA itens que ainda não existem (deduplicados por
chaves naturais: slug da turma, nome da disciplina, título+URL do link,
título+agendamento do post). Nada é sobrescrito nem apagado.
"""
from datetime import datetime

from app.extensions import db
from app.models import Turma, Disciplina, Link, Post, Chamado, Anotacao

FORMATO = 'portal-tac-backup'
VERSAO = 3


def _iso(dt):
    return dt.isoformat() if dt else None


def _dt(valor):
    return datetime.fromisoformat(valor) if valor else None


def exportar_backup():
    return {
        'formato': FORMATO,
        'versao': VERSAO,
        'gerado_em': datetime.now().isoformat(),
        'turmas': [{
            'id': t.id, 'nome': t.nome, 'slug': t.slug, 'cor': t.cor,
            'arquivada': bool(t.arquivada),
        } for t in Turma.query.order_by(Turma.id).all()],
        'disciplinas': [{
            'id': d.id, 'nome': d.nome, 'cor': d.cor,
        } for d in Disciplina.query.order_by(Disciplina.id).all()],
        'links': [{
            'id': l.id, 'titulo': l.titulo, 'url': l.url,
            'turmas': [t.slug for t in l.turmas],
        } for l in Link.query.order_by(Link.id).all()],
        'posts': [{
            'id': p.id, 'titulo': p.titulo, 'conteudo': p.conteudo, 'tipo': p.tipo,
            'created_at': _iso(p.created_at), 'scheduled_at': _iso(p.scheduled_at),
            'prazo': _iso(p.prazo), 'deleted_at': _iso(p.deleted_at),
            'is_draft': bool(p.is_draft), 'is_pinned': bool(p.is_pinned),
            'likes': p.likes or 0, 'permite_chamado': bool(p.permite_chamado),
            'visualizacoes': p.visualizacoes or 0,
            'arquivo_url': p.arquivo_url, 'arquivo_public_id': p.arquivo_public_id,
            'arquivo_formato': p.arquivo_formato, 'video_url': p.video_url,
            'disciplina': p.disciplina.nome if p.disciplina else None,
            'turmas': [t.slug for t in p.turmas],
        } for p in Post.query.order_by(Post.id).all()],
        'chamados': [{
            'id': c.id, 'post_id': c.post_id, 'nome': c.nome, 'email': c.email,
            'telefone': c.telefone, 'duvida': c.duvida, 'created_at': _iso(c.created_at),
            'resolvido': bool(c.resolvido), 'resposta_admin': c.resposta_admin,
            'respondido_at': _iso(c.respondido_at),
        } for c in Chamado.query.order_by(Chamado.id).all()],
        'anotacoes': [{
            'id': a.id, 'titulo': a.titulo, 'descricao': a.descricao,
            'data': _iso(a.data), 'hora': a.hora.strftime('%H:%M') if a.hora else None,
            'cor': a.cor, 'created_at': _iso(a.created_at),
            'turmas': [t.slug for t in a.turmas],
        } for a in Anotacao.query.order_by(Anotacao.id).all()],
    }


def importar_backup(data):
    if not isinstance(data, dict) or data.get('formato') != FORMATO:
        raise ValueError('O arquivo não parece ser um backup do Portal (formato inválido).')

    resumo = {'turmas': 0, 'disciplinas': 0, 'links': 0, 'posts': 0, 'chamados': 0,
              'anotacoes': 0, 'ignorados': 0}

    # --- Turmas (chave natural: slug) ---
    turmas_por_slug = {t.slug: t for t in Turma.query.all()}
    for td in data.get('turmas', []):
        slug = (td.get('slug') or '').strip()
        if not slug:
            continue
        if slug in turmas_por_slug:
            resumo['ignorados'] += 1
            continue
        t = Turma(nome=td.get('nome') or slug, slug=slug,
                  cor=td.get('cor') or '#3498db', arquivada=bool(td.get('arquivada')))
        db.session.add(t)
        turmas_por_slug[slug] = t
        resumo['turmas'] += 1

    # --- Disciplinas (chave natural: nome) ---
    disc_por_nome = {d.nome: d for d in Disciplina.query.all()}
    for dd in data.get('disciplinas', []):
        nome = (dd.get('nome') or '').strip()
        if not nome:
            continue
        if nome in disc_por_nome:
            resumo['ignorados'] += 1
            continue
        d = Disciplina(nome=nome, cor=dd.get('cor') or '#6c757d')
        db.session.add(d)
        disc_por_nome[nome] = d
        resumo['disciplinas'] += 1

    # --- Links / Biblioteca (chave natural: título + URL) ---
    links_existentes = {(l.titulo, l.url) for l in Link.query.all()}
    for ld in data.get('links', []):
        titulo, url = (ld.get('titulo') or '').strip(), (ld.get('url') or '').strip()
        if not (titulo and url):
            continue
        if (titulo, url) in links_existentes:
            resumo['ignorados'] += 1
            continue
        l = Link(titulo=titulo, url=url)
        for slug in ld.get('turmas', []):
            if slug in turmas_por_slug:
                l.turmas.append(turmas_por_slug[slug])
        db.session.add(l)
        links_existentes.add((titulo, url))
        resumo['links'] += 1

    # --- Posts (chave natural: título + scheduled_at) ---
    posts_existentes = {(p.titulo, p.scheduled_at): p for p in Post.query.all()}
    mapa_post = {}  # id do backup -> Post (para religar os chamados)
    for pd in data.get('posts', []):
        titulo = (pd.get('titulo') or '').strip()
        if not titulo:
            continue
        scheduled = _dt(pd.get('scheduled_at')) or datetime.now()
        chave = (titulo, scheduled)
        if chave in posts_existentes:
            mapa_post[pd.get('id')] = posts_existentes[chave]
            resumo['ignorados'] += 1
            continue
        p = Post(
            titulo=titulo, conteudo=pd.get('conteudo'),
            tipo=pd.get('tipo') or 'aviso',
            created_at=_dt(pd.get('created_at')) or datetime.now(),
            scheduled_at=scheduled, prazo=_dt(pd.get('prazo')),
            deleted_at=_dt(pd.get('deleted_at')),
            is_draft=bool(pd.get('is_draft')), is_pinned=bool(pd.get('is_pinned')),
            likes=int(pd.get('likes') or 0),
            permite_chamado=bool(pd.get('permite_chamado')),
            visualizacoes=int(pd.get('visualizacoes') or 0),
            arquivo_url=pd.get('arquivo_url'), arquivo_public_id=pd.get('arquivo_public_id'),
            arquivo_formato=pd.get('arquivo_formato'), video_url=pd.get('video_url'),
        )
        if pd.get('disciplina') and pd['disciplina'] in disc_por_nome:
            p.disciplina = disc_por_nome[pd['disciplina']]
        for slug in pd.get('turmas', []):
            if slug in turmas_por_slug:
                p.turmas.append(turmas_por_slug[slug])
        db.session.add(p)
        posts_existentes[chave] = p
        mapa_post[pd.get('id')] = p
        resumo['posts'] += 1

    db.session.flush()

    # --- Chamados (chave natural: post + email + created_at) ---
    chamados_existentes = {(c.post_id, c.email, c.created_at) for c in Chamado.query.all()}
    for cd in data.get('chamados', []):
        post = mapa_post.get(cd.get('post_id'))
        if post is None or not cd.get('email'):
            resumo['ignorados'] += 1
            continue
        created = _dt(cd.get('created_at')) or datetime.now()
        if (post.id, cd['email'], created) in chamados_existentes:
            resumo['ignorados'] += 1
            continue
        db.session.add(Chamado(
            post=post, nome=cd.get('nome') or 'Estudante', email=cd['email'],
            telefone=cd.get('telefone'), duvida=cd.get('duvida') or '', created_at=created,
            resolvido=bool(cd.get('resolvido')),
            resposta_admin=cd.get('resposta_admin'),
            respondido_at=_dt(cd.get('respondido_at')),
        ))
        resumo['chamados'] += 1

    # --- Anotações do calendário (chave natural: título + data) ---
    anotacoes_existentes = {(a.titulo, a.data) for a in Anotacao.query.all()}
    for ad in data.get('anotacoes', []):
        titulo = (ad.get('titulo') or '').strip()
        data_anot = _dt(ad.get('data'))
        if not (titulo and data_anot):
            continue
        data_anot = data_anot.date() if isinstance(data_anot, datetime) else data_anot
        if (titulo, data_anot) in anotacoes_existentes:
            resumo['ignorados'] += 1
            continue
        a = Anotacao(titulo=titulo, descricao=ad.get('descricao'),
                     data=data_anot, cor=ad.get('cor') or '#4F46E5',
                     created_at=_dt(ad.get('created_at')) or datetime.now())
        if ad.get('hora'):
            a.hora = datetime.strptime(ad['hora'], '%H:%M').time()
        for slug in ad.get('turmas', []):
            if slug in turmas_por_slug:
                a.turmas.append(turmas_por_slug[slug])
        db.session.add(a)
        anotacoes_existentes.add((titulo, data_anot))
        resumo['anotacoes'] += 1

    db.session.commit()
    return resumo
