# Portal Acadêmico (portaltac) — v2 experimental

Portal de turmas para professor e alunos: avisos, materiais e atividades com
foco **mobile-first**. Esta é uma versão experimental para inspirar a versão
final.

## Stack

- **Backend:** Flask + SQLAlchemy + Flask-Migrate + Flask-Login + Flask-WTF (CSRF)
- **Frontend:** Bootstrap 5, **HTMX 2** (interações sem recarregar página), **TipTap 2** (editor de texto via CDN), FontAwesome, FullCalendar, Google Fonts (Inter)
- **Uploads:** Cloudinary (anexos de posts)
- **PWA:** manifest + service worker com cache offline básico

## Novidades da v2

| Feature | Como funciona |
|---|---|
| **HTMX em tudo** | Filtros do feed (chips), curtidas, formulário de chamado, paginação do admin e respostas de chamados trocam só fragmentos HTML. Rotas detectam o header `HX-Request` e devolvem página completa como fallback. |
| **Editor TipTap** | Substitui o CKEditor. Toolbar com negrito, itálico, sublinhado, H2/H3, listas, citação, link, código e limpar formatação. Preenche o `<textarea name="conteudo">`; se o CDN falhar, o textarea continua utilizável. |
| **Curtidas** | `POST /api/post/<id>/like` sem login; cookie `liked_<id>` evita duplo like (segundo clique desfaz). |
| **Chamados de dúvida** | Toggle "Permitir chamado de dúvida" por post. Aluno envia nome/e-mail/dúvida; professor responde na aba **Chamados** do dashboard (badge com pendentes). |
| **Arquivar turma** | `POST /admin/turma/<id>/arquivar` alterna o estado. Turmas arquivadas somem da home e ficam acinzentadas no admin com badge "Arquivada". |
| **Storage plugável** | Aba **Sistema** do dashboard: escolha onde os anexos são guardados — **Local** (pasta do servidor), **SML Storage API** (Firebase, fluxo getUploadUrl → PUT → confirmUpload), **Supabase Storage** (REST) ou **Cloudinary** (env). Se a API não responder, o upload **cai automaticamente no salvamento local** e o admin é avisado. Botão "Testar conexão" valida as credenciais antes de salvar. |
| **Backup JSON** | Aba **Sistema**: exporta posts, biblioteca de links, turmas, disciplinas e chamados em um `.json`; a restauração só adiciona o que não existe (deduplicada por chaves naturais — nada é sobrescrito/apagado). |
| **Toasts** | Feedback via header `HX-Trigger` (`showToast`) + flash messages convertidas em snackbar. |
| **Redesign** | Tokens de design (índigo `#4F46E5`), fonte Inter, dashboard com sidebar fixa, formulário de post em 2 colunas com sidebar sticky, bottom-nav mobile, hero da turma. |

## Rodando localmente

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=run.py
flask db upgrade                      # cria/atualiza o banco (instance/portal.db)
ADMIN_PASSWORD=suasenha flask create-admin   # cria o usuário "professor"
flask run
```

Variáveis de ambiente opcionais: `SECRET_KEY`, `DATABASE_URL`,
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`,
`ADMIN_USERNAME`.

## Armazenamento de anexos

Configurável em **Admin → Sistema** (gravado no banco, tabela `configuracao`; variáveis
de ambiente homônimas em maiúsculas servem de fallback):

| Provedor | Campos | Observações |
|---|---|---|
| `local` (padrão) | — | salva em `app/static/uploads/posts/AAAA-MM/` |
| `sml` | `sml_base_url`, `sml_api_key`, `sml_projeto` | SML Storage API (Firebase); limite 10 MB por arquivo |
| `supabase` | `supabase_url`, `supabase_key` (service_role), `supabase_bucket` | o bucket precisa ser público para os alunos |
| `cloudinary` | variáveis `CLOUDINARY_*` no ambiente | comportamento original mantido |

Em qualquer provedor de API, falha de conexão ⇒ **fallback automático para salvamento
local** (o post nunca fica sem anexo por instabilidade da API).

## Migrations

- `e614d240e2fd` — baseline com o schema original
- `4845a79d3a2b` — v2: `post.likes`, `post.permite_chamado`, `turma.arquivada`, tabela `chamado` (com `server_default` para backfill seguro)
- `c1e17f34506b` — tabela `configuracao` (storage plugável)

**Banco novo:** apenas `flask db upgrade`.
**Banco existente (produção, criado antes das migrations):** marque a baseline e aplique só o delta v2:

```bash
flask db stamp e614d240e2fd
flask db upgrade
```

## Estrutura

```
app/
├── blueprints/        # main (público), admin, auth, api
├── services/          # upload (Cloudinary) e queries do admin
├── templates/
│   ├── main/partials/   # fragmentos HTMX (feed, like, chamado)
│   └── admin/partials/  # fragmentos HTMX (tabela de posts, chamados, turmas)
├── static/css/style.css # design system
└── static/js/editor.js  # TipTap via esm.sh
scripts/               # utilitários de diagnóstico do banco
config.py              # configuração via variáveis de ambiente
run.py                 # entry point + comando create-admin
```
