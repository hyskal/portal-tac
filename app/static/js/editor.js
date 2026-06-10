/*
 * Editor TipTap (via CDN esm.sh) para o formulário de posts.
 * Preenche o <textarea name="conteudo"> a cada alteração; se o CDN
 * falhar, o textarea continua visível e utilizável como fallback.
 */
const VERSAO = '2.6.6';
const CDN = (pkg) => `https://esm.sh/@tiptap/${pkg}@${VERSAO}`;

const textarea = document.getElementById('conteudo');
const mount = document.getElementById('tiptapContent');
const toolbar = document.getElementById('tiptapToolbar');
const form = document.getElementById('postForm');

async function iniciarEditor() {
    if (!textarea || !mount || !toolbar) return;

    const [core, starterKit, underline, link, placeholder] = await Promise.all([
        import(CDN('core')),
        import(CDN('starter-kit')),
        import(CDN('extension-underline')),
        import(CDN('extension-link')),
        import(CDN('extension-placeholder')),
    ]);

    const editor = new core.Editor({
        element: mount,
        extensions: [
            starterKit.default.configure({ heading: { levels: [2, 3] } }),
            underline.default,
            link.default.configure({ openOnClick: false, autolink: true }),
            placeholder.default.configure({ placeholder: 'Escreva o conteúdo da postagem...' }),
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
