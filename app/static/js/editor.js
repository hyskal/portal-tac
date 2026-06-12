/*
 * Editor TipTap (via CDN esm.sh) para o formulário de posts.
 * Preenche o <textarea name="conteudo"> a cada alteração; se o CDN
 * falhar, o textarea continua visível e utilizável como fallback.
 * Imagens: upload via /admin/api/upload-imagem (usa o storage configurado,
 * com fallback local) ou inserção por URL.
 */
const VERSAO = '2.6.6';
const CDN = (pkg) => `https://esm.sh/@tiptap/${pkg}@${VERSAO}`;
const URL_UPLOAD_IMAGEM = '/admin/api/upload-imagem';

const textarea = document.getElementById('conteudo');
const mount = document.getElementById('tiptapContent');
const toolbar = document.getElementById('tiptapToolbar');
const form = document.getElementById('postForm');
const inputImagem = document.getElementById('editorImagemInput');

function tokenCSRF() {
    const campo = form ? form.querySelector('input[name="csrf_token"]') : null;
    return campo ? campo.value : '';
}

async function enviarImagem(arquivo) {
    const dados = new FormData();
    dados.append('imagem', arquivo);
    const resp = await fetch(URL_UPLOAD_IMAGEM, {
        method: 'POST',
        headers: { 'X-CSRFToken': tokenCSRF() },
        body: dados,
    });
    const json = await resp.json();
    if (!resp.ok || !json.success) throw new Error(json.error || 'Falha no upload');
    return json;
}

async function iniciarEditor() {
    if (!textarea || !mount || !toolbar) return;

    const [core, starterKit, underline, link, placeholder, image] = await Promise.all([
        import(CDN('core')),
        import(CDN('starter-kit')),
        import(CDN('extension-underline')),
        import(CDN('extension-link')),
        import(CDN('extension-placeholder')),
        import(CDN('extension-image')),
    ]);

    const editor = new core.Editor({
        element: mount,
        extensions: [
            starterKit.default.configure({ heading: { levels: [2, 3] } }),
            underline.default,
            link.default.configure({ openOnClick: false, autolink: true }),
            placeholder.default.configure({ placeholder: 'Escreva o conteúdo da postagem...' }),
            image.default.configure({ inline: false, allowBase64: false }),
        ],
        content: textarea.value || '',
        onUpdate({ editor }) {
            textarea.value = editor.getHTML();
        },
    });

    // Editor montado: esconde o textarea (vira o "espelho" do conteúdo)
    textarea.hidden = true;
    toolbar.hidden = false;

    const comandos = {
        bold:        (c) => c.toggleBold(),
        italic:      (c) => c.toggleItalic(),
        underline:   (c) => c.toggleUnderline(),
        h2:          (c) => c.toggleHeading({ level: 2 }),
        h3:          (c) => c.toggleHeading({ level: 3 }),
        bulletList:  (c) => c.toggleBulletList(),
        orderedList: (c) => c.toggleOrderedList(),
        blockquote:  (c) => c.toggleBlockquote(),
        code:        (c) => c.toggleCode(),
        clear:       (c) => c.clearNodes().unsetAllMarks(),
    };

    function inserirImagemPorUrl() {
        const url = window.prompt('Endereço (URL) da imagem:');
        if (url) editor.chain().focus().setImage({ src: url }).run();
    }

    if (inputImagem) {
        inputImagem.addEventListener('change', async () => {
            const arquivo = inputImagem.files[0];
            inputImagem.value = '';
            if (!arquivo) return;
            const aviso = typeof showToast === 'function' ? showToast : () => {};
            try {
                aviso('Enviando imagem...', 'info');
                const r = await enviarImagem(arquivo);
                editor.chain().focus().setImage({ src: r.url }).run();
                aviso(r.fallback ? 'API indisponível — imagem salva localmente.' : 'Imagem inserida! 🖼️',
                      r.fallback ? 'warning' : 'success');
            } catch (e) {
                console.warn('Upload de imagem falhou:', e);
                aviso('Upload falhou — você pode inserir por URL.', 'danger');
                inserirImagemPorUrl();
            }
        });
    }

    toolbar.querySelectorAll('button[data-cmd]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const cmd = btn.dataset.cmd;
            if (cmd === 'link') {
                const atual = editor.getAttributes('link').href || '';
                const url = window.prompt('Endereço do link (deixe vazio para remover):', atual);
                if (url === null) return;
                if (url === '') {
                    editor.chain().focus().extendMarkRange('link').unsetLink().run();
                } else {
                    const href = /^https?:\/\//i.test(url) ? url : 'https://' + url;
                    editor.chain().focus().extendMarkRange('link').setLink({ href }).run();
                }
                return;
            }
            if (cmd === 'image') {
                if (inputImagem) inputImagem.click(); else inserirImagemPorUrl();
                return;
            }
            if (cmd === 'imageUrl') {
                inserirImagemPorUrl();
                return;
            }
            const acao = comandos[cmd];
            if (acao) acao(editor.chain().focus()).run();
        });
    });

    // Estado ativo dos botões da toolbar
    const checagens = {
        bold: () => editor.isActive('bold'),
        italic: () => editor.isActive('italic'),
        underline: () => editor.isActive('underline'),
        h2: () => editor.isActive('heading', { level: 2 }),
        h3: () => editor.isActive('heading', { level: 3 }),
        bulletList: () => editor.isActive('bulletList'),
        orderedList: () => editor.isActive('orderedList'),
        blockquote: () => editor.isActive('blockquote'),
        link: () => editor.isActive('link'),
        code: () => editor.isActive('code'),
        image: () => editor.isActive('image'),
    };
    const atualizarToolbar = () => {
        toolbar.querySelectorAll('button[data-cmd]').forEach((btn) => {
            const check = checagens[btn.dataset.cmd];
            btn.classList.toggle('is-active', check ? check() : false);
        });
    };
    editor.on('transaction', atualizarToolbar);
    editor.on('selectionUpdate', atualizarToolbar);

    // Garantia extra: sincroniza antes do submit
    if (form) {
        form.addEventListener('submit', () => {
            textarea.value = editor.getHTML();
        });
    }
}

iniciarEditor().catch((err) => {
    console.warn('Editor avançado indisponível — usando textarea simples.', err);
    if (textarea) textarea.hidden = false;
});
