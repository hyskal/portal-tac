from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- TABELAS DE ASSOCIAÇÃO ---
post_turmas = db.Table('post_turmas',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('turma_id', db.Integer, db.ForeignKey('turma.id'), primary_key=True)
)

link_turmas = db.Table('link_turmas',
    db.Column('link_id', db.Integer, db.ForeignKey('link.id'), primary_key=True),
    db.Column('turma_id', db.Integer, db.ForeignKey('turma.id'), primary_key=True)
)

# --- MODELOS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    cor = db.Column(db.String(7), default="#3498db") 
    links = db.relationship('Link', secondary=link_turmas, lazy='subquery',
        backref=db.backref('turmas', lazy=True))

class Disciplina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cor = db.Column(db.String(7), default="#6c757d") # Cinza padrão
    # Relacionamento reverso (opcional, mas útil)
    posts = db.relationship('Post', backref='disciplina', lazy=True)

class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(300), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    scheduled_at = db.Column(db.DateTime, default=datetime.now)
    prazo = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_draft = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    tipo = db.Column(db.String(50), nullable=False, default='aviso') 
    
    arquivo_url = db.Column(db.String(500), nullable=True) 
    arquivo_public_id = db.Column(db.String(100), nullable=True)
    arquivo_formato = db.Column(db.String(10), nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    visualizacoes = db.Column(db.Integer, default=0)

    # Relacionamentos
    turmas = db.relationship('Turma', secondary=post_turmas, lazy='subquery',
        backref=db.backref('posts', lazy=True))
    
    # Novo: Disciplina (1 post pertence a 1 disciplina, ou nenhuma)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplina.id'), nullable=True)