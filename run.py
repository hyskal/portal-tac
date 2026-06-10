import os

from app import create_app
from app.extensions import db
from app.models import User, Turma, Disciplina, Post

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Turma': Turma, 'Disciplina': Disciplina, 'Post': Post}


@app.cli.command('create-admin')
def create_admin():
    """Cria (ou atualiza a senha de) um usuário professor via ADMIN_USERNAME/ADMIN_PASSWORD."""
    username = os.environ.get('ADMIN_USERNAME', 'professor')
    password = os.environ.get('ADMIN_PASSWORD')
    if not password:
        print('Defina ADMIN_PASSWORD no ambiente.')
        return
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username)
        db.session.add(user)
    user.set_password(password)
    db.session.commit()
    print(f'Usuário "{username}" pronto.')


if __name__ == '__main__':
    app.run(debug=True)
