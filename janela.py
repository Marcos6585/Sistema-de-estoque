# estoque_app.py
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import shutil
from datetime import datetime

# ---------------- Configurações ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "estoque.db")

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "123"

# ---------------- Banco de Dados ----------------
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        cargo TEXT CHECK(cargo IN ('administrador','funcionario')) NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT NOT NULL,
        quantidade INTEGER CHECK(quantidade >= 0) NOT NULL DEFAULT 0,
        preco_unitario REAL CHECK(preco_unitario >= 0) NOT NULL DEFAULT 0.0,
        fornecedor TEXT
    )
    """)

    # Tabela de histórico de movimentações (entradas/saídas)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL,
        tipo TEXT CHECK(tipo IN ('entrada','saida')) NOT NULL,
        usuario TEXT,
        data_hora TEXT NOT NULL,
        observacao TEXT,
        FOREIGN KEY(produto_id) REFERENCES produtos(id)
    )
    """)

    # Cria admin padrão caso não exista
    cur.execute("SELECT id FROM usuarios WHERE nome = ?", (DEFAULT_ADMIN_USER,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO usuarios (nome, senha, cargo) VALUES (?, ?, ?)",
            (DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS, "administrador")
        )

    conn.commit()
    conn.close()

# ---------------- Operações de BD ----------------
def verificar_login(nome, senha):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cargo FROM usuarios WHERE nome=? AND senha=?", (nome, senha))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def listar_produtos():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, categoria, quantidade, preco_unitario, fornecedor FROM produtos ORDER BY nome")
    rows = cur.fetchall()
    conn.close()
    return rows

def inserir_produto(nome, categoria, quantidade, preco, fornecedor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO produtos (nome, categoria, quantidade, preco_unitario, fornecedor)
            VALUES (?, ?, ?, ?, ?)
        """, (nome, categoria, quantidade, preco, fornecedor))
        conn.commit()
    finally:
        conn.close()

def atualizar_produto(prod_id, nome, categoria, quantidade, preco, fornecedor):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE produtos
            SET nome=?, categoria=?, quantidade=?, preco_unitario=?, fornecedor=?
            WHERE id=?
        """, (nome, categoria, quantidade, preco, fornecedor, prod_id))
        conn.commit()
    finally:
        conn.close()

def remover_produto(prod_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM produtos WHERE id=?", (prod_id,))
        conn.commit()
    finally:
        conn.close()

def listar_usuarios():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, cargo FROM usuarios ORDER BY nome")
    rows = cur.fetchall()
    conn.close()
    return rows

def inserir_usuario(nome, senha, cargo):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO usuarios (nome, senha, cargo) VALUES (?, ?, ?)",
                    (nome, senha, cargo))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Usuário já existe."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remover_usuario(user_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM usuarios WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()

# Movimentações (histórico)
def inserir_movimentacao(produto_id, quantidade, tipo, usuario=None, observacao=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        now = datetime.now().isoformat(sep=' ', timespec='seconds')
        cur.execute("""
            INSERT INTO movimentacoes (produto_id, quantidade, tipo, usuario, data_hora, observacao)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (produto_id, quantidade, tipo, usuario, now, observacao))
        conn.commit()
    finally:
        conn.close()

def listar_movimentacoes(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, p.nome, m.quantidade, m.tipo, m.usuario, m.data_hora, m.observacao
        FROM movimentacoes m
        LEFT JOIN produtos p ON p.id = m.produto_id
        ORDER BY m.data_hora DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ---------------- Integração com Dashboard ----------------
def abrir_dashboard():
    streamlit_path = shutil.which("streamlit")
    dashboard_file = os.path.join(BASE_DIR, "dashboard.py")

    if not os.path.exists(dashboard_file):
        messagebox.showerror("Dashboard", f"Arquivo 'dashboard.py' não encontrado em:\n{BASE_DIR}")

    if not streamlit_path:
        messagebox.showerror("Dashboard", "Streamlit não foi encontrado. Instale com:\n\npip install streamlit")


    try:
        subprocess.Popen([streamlit_path, "run", dashboard_file], cwd=BASE_DIR)
        messagebox.showinfo("Dashboard", "Abrindo dashboard (Streamlit). Verifique o navegador.")
    except Exception as e:
        messagebox.showerror("Dashboard", f"Erro ao abrir dashboard:\n{e}")

# ---------------- Interface Tkinter ----------------
def abrir_login():
    def tentar_login():
        usuario = e_user.get().strip()
        senha = e_pass.get().strip()
        if not usuario or not senha:
            messagebox.showwarning("Aviso", "Preencha usuário e senha.")

        cargo = verificar_login(usuario, senha)
        if cargo:
            root.destroy()
            abrir_main(usuario, cargo)
        else:
            messagebox.showerror("Erro", "Usuário ou senha incorretos!")

    root = tk.Tk()
    root.title("Login - Sistema de Estoque")
    root.geometry("340x180")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=12)
    frm.pack(expand=True, fill="both")

    ttk.Label(frm, text="Usuário:").grid(row=0, column=0, sticky="w")
    e_user = ttk.Entry(frm); e_user.grid(row=0, column=1, padx=6, pady=6)
    ttk.Label(frm, text="Senha:").grid(row=1, column=0, sticky="w")
    e_pass = ttk.Entry(frm, show="*"); e_pass.grid(row=1, column=1, padx=6, pady=6)

    ttk.Button(frm, text="Entrar", command=tentar_login).grid(row=2, column=0, columnspan=2, pady=12)
    ttk.Label(frm, text=f"(admin padrão: {DEFAULT_ADMIN_USER} / {DEFAULT_ADMIN_PASS})", foreground="gray").grid(row=3, column=0, columnspan=2)

    root.mainloop()

def abrir_main(usuario, cargo):
    app = tk.Tk()
    app.title(f"Sistema de Estoque — {usuario} ({cargo})")
    app.geometry("980x640")

    # Menu simples (melhora UI)
    menubar = tk.Menu(app)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Abrir dashboard", command=abrir_dashboard)
    file_menu.add_separator()
    file_menu.add_command(label="Sair", command=app.quit)
    menubar.add_cascade(label="Arquivo", menu=file_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="Sobre", command=lambda: messagebox.showinfo("Sobre", "Sistema de Estoque — versão simples"))
    menubar.add_cascade(label="Ajuda", menu=help_menu)

    app.config(menu=menubar)

    nb = ttk.Notebook(app)
    nb.pack(expand=True, fill="both")

    # ----- Tab Produtos -----
    tab_prod = ttk.Frame(nb)
    nb.add(tab_prod, text="Produtos")

    top_prod = ttk.Frame(tab_prod, padding=8)
    top_prod.pack(fill="x")

    ttk.Label(top_prod, text="Pesquisar:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(top_prod, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=6)

    def aplicar_pesquisa():
        termo = search_var.get().strip().lower()
        atualizar_treeview_produtos(termo)

    ttk.Button(top_prod, text="Ir", command=aplicar_pesquisa).pack(side="left")
    ttk.Button(top_prod, text="Atualizar", command=lambda: atualizar_treeview_produtos("")).pack(side="right")

    cols = ("id", "nome", "categoria", "quantidade", "preco", "fornecedor")
    tree = ttk.Treeview(tab_prod, columns=cols, show="headings", selectmode="browse", height=18)
    tree.heading("nome", text="Nome")
    tree.heading("categoria", text="Categoria")
    tree.heading("quantidade", text="Qtd")
    tree.heading("preco", text="Preço (R$)")
    tree.heading("fornecedor", text="Fornecedor")
    tree.column("id", width=0, stretch=False)
    tree.column("nome", width=300)
    tree.column("categoria", width=140)
    tree.column("quantidade", width=80, anchor="center")
    tree.column("preco", width=120, anchor="e")
    tree.column("fornecedor", width=260)
    tree.pack(expand=True, fill="both", padx=8, pady=8)

    # Botões de produtos (organizados em frames)
    btn_frame = ttk.Frame(tab_prod, padding=8)
    btn_frame.pack(fill="x")

    left_btns = ttk.Frame(btn_frame)
    left_btns.pack(side="left")
    right_btns = ttk.Frame(btn_frame)
    right_btns.pack(side="right")

    def abrir_form_produto(edit=False):
        sel = tree.selection()
        prod_id = None
        dados = None
        if edit:
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um produto para editar.")
                return
            prod_id = int(tree.set(sel[0], "id"))
            dados = (
                tree.set(sel[0], "nome"),
                tree.set(sel[0], "categoria"),
                tree.set(sel[0], "quantidade"),
                tree.set(sel[0], "preco"),
                tree.set(sel[0], "fornecedor")
            )

        top = tk.Toplevel(app)
        top.title("Editar Produto" if edit else "Cadastrar Produto")
        top.geometry("420x360")
        top.transient(app)
        top.grab_set()

        ttk.Label(top, text="Nome:").pack(anchor="w", padx=10, pady=(10,0))
        e_nome = ttk.Entry(top); e_nome.pack(fill="x", padx=10)
        ttk.Label(top, text="Categoria:").pack(anchor="w", padx=10, pady=(8,0))
        e_cat = ttk.Entry(top); e_cat.pack(fill="x", padx=10)
        ttk.Label(top, text="Quantidade:").pack(anchor="w", padx=10, pady=(8,0))
        e_qtd = ttk.Entry(top); e_qtd.pack(fill="x", padx=10)
        ttk.Label(top, text="Preço (ex: 12,50 ou 12.50):").pack(anchor="w", padx=10, pady=(8,0))
        e_preco = ttk.Entry(top); e_preco.pack(fill="x", padx=10)
        ttk.Label(top, text="Fornecedor (opcional):").pack(anchor="w", padx=10, pady=(8,0))
        e_for = ttk.Entry(top); e_for.pack(fill="x", padx=10)

        if edit and dados:
            e_nome.insert(0, dados[0])
            e_cat.insert(0, dados[1])
            e_qtd.insert(0, dados[2])
            e_preco.insert(0, dados[3])
            e_for.insert(0, dados[4])


        def salvar():
            nome = e_nome.get().strip()
            cat = e_cat.get().strip()
            qtd = e_qtd.get().strip()
            preco = e_preco.get().strip().replace(",", ".")  
            forn = e_for.get().strip()

            if not nome:
                messagebox.showerror("Erro", "Nome é obrigatório.")
  
            if not cat:
                messagebox.showerror("Erro", "Categoria é obrigatória.")
                
            if not qtd:
                messagebox.showerror("Erro", "Quantidade é obrigatória.")
           
            if not preco:
                messagebox.showerror("Erro", "Preço é obrigatório.")
           

            # quantidade deve ser inteiro não-negativo
            try:
                qtd_i = int(qtd)
                if qtd_i < 0:
                    raise ValueError("Quantidade negativa")
            except Exception:
                messagebox.showerror("Erro", "Quantidade deve ser inteiro >= 0.")


            # preço deve ser número >= 0
            try:
                preco_f = float(preco)
                if preco_f < 0:
                    raise ValueError("Preço negativo")
            except Exception:
                messagebox.showerror("Erro", "Preço deve ser número >= 0 (use vírgula ou ponto).")


            try:
                if edit:
                    atualizar_produto(prod_id, nome, cat, qtd_i, preco_f, forn)
                    messagebox.showinfo("Sucesso", "Produto atualizado.")
                else:
                    inserir_produto(nome, cat, qtd_i, preco_f, forn)
                    messagebox.showinfo("Sucesso", "Produto cadastrado.")
                top.destroy()
                atualizar_treeview_produtos()
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar produto: {e}")

        ttk.Button(top, text="Salvar", command=salvar).pack(pady=12)

    def deletar_produto_ui():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um produto para deletar.")

        prod_id = int(tree.set(sel[0], "id"))
        nome = tree.set(sel[0], "nome")
        if messagebox.askyesno("Confirmar", f"Deletar produto '{nome}'?"):
            try:
                remover_produto(prod_id)
                messagebox.showinfo("Sucesso", "Produto removido.")
                atualizar_treeview_produtos()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível remover: {e}")

    # Funções para entrada/saída de estoque (controle)
    def registrar_movimentacao_ui(tipo):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um produto para registrar movimentação.")

        prod_id = int(tree.set(sel[0], "id"))
        nome = tree.set(sel[0], "nome")
        qtd_atual = int(tree.set(sel[0], "quantidade"))
        prompt = f"Quantidade para {'entrada' if tipo=='entrada' else 'saída'} de '{nome}':"
        # pede quantidade via dialog simples
        try:
            resp = simpledialog.askstring("Registrar " + ("Entrada" if tipo == "entrada" else "Saída"), prompt, parent=app)
            if resp is None:
                return  # cancelou
            resp = resp.strip()
            if not resp:
                messagebox.showerror("Erro", "Quantidade inválida.")

            if not resp.isdigit():
                messagebox.showerror("Erro", "Digite um número inteiro válido.")

            qtd = int(resp)
            if qtd <= 0:
                messagebox.showerror("Erro", "Quantidade deve ser maior que zero.")

            if tipo == "saida" and qtd > qtd_atual:
                messagebox.showerror("Erro", f"Não há estoque suficiente (atual: {qtd_atual}).")


            # atualiza quantidade no produto
            nova_qtd = qtd_atual + qtd if tipo == "entrada" else qtd_atual - qtd
            # atualiza DB
            atualizar_produto(prod_id, tree.set(sel[0], "nome"), tree.set(sel[0], "categoria"), nova_qtd, float(tree.set(sel[0], "preco").replace(",", ".")), tree.set(sel[0], "fornecedor"))
            # insere movimentacao
            inserir_movimentacao(prod_id, qtd, tipo, usuario=usuario, observacao=None)
            messagebox.showinfo("Sucesso", f"Movimentação registrada ({tipo}) — nova qtd: {nova_qtd}")
            atualizar_treeview_produtos()
            atualizar_treeview_movimentacoes()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao registrar movimentação: {e}")

    ttk.Button(left_btns, text="Novo Produto", command=lambda: abrir_form_produto(edit=False)).pack(side="left", padx=6)
    ttk.Button(left_btns, text="Editar Produto", command=lambda: abrir_form_produto(edit=True)).pack(side="left", padx=6)
    ttk.Button(left_btns, text="Deletar Produto", command=deletar_produto_ui).pack(side="left", padx=6)

    ttk.Button(right_btns, text="Registrar Entrada", command=lambda: registrar_movimentacao_ui("entrada")).pack(side="right", padx=6)
    ttk.Button(right_btns, text="Registrar Saída", command=lambda: registrar_movimentacao_ui("saida")).pack(side="right", padx=6)
    ttk.Button(right_btns, text="Abrir Dashboard", command=abrir_dashboard).pack(side="right", padx=6)

    def atualizar_treeview_produtos(filter_term=""):
        for r in tree.get_children():
            tree.delete(r)
        try:
            produtos = listar_produtos()
            termo = filter_term.lower() if filter_term else None
            for p in produtos:
                pid, nome, cat, qtd, preco, forn = p
                preco_str = f"{float(preco):.2f}"
                linha = (pid, nome, cat, qtd, preco_str, forn or "")
                if termo:
                    if termo in nome.lower() or termo in cat.lower() or termo in (forn or "").lower():
                        tree.insert("", "end", values=linha)
                else:
                    tree.insert("", "end", values=linha)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar produtos: {e}")

    atualizar_treeview_produtos()

    # ----- Tab Movimentações (Histórico) -----
    tab_mov = ttk.Frame(nb)
    nb.add(tab_mov, text="Movimentações")

    top_mov = ttk.Frame(tab_mov, padding=8)
    top_mov.pack(fill="x")

    ttk.Label(top_mov, text="Últimas movimentações:").pack(side="left")
    ttk.Button(top_mov, text="Atualizar", command=lambda: atualizar_treeview_movimentacoes()).pack(side="right")

    cols_mov = ("id", "produto", "quantidade", "tipo", "usuario", "data", "obs")
    tree_mov = ttk.Treeview(tab_mov, columns=cols_mov, show="headings", height=18)
    tree_mov.heading("produto", text="Produto")
    tree_mov.heading("quantidade", text="Qtd")
    tree_mov.heading("tipo", text="Tipo")
    tree_mov.heading("usuario", text="Usuário")
    tree_mov.heading("data", text="Data/Hora")
    tree_mov.heading("obs", text="Observação")
    tree_mov.column("id", width=0, stretch=False)
    tree_mov.column("produto", width=260)
    tree_mov.column("quantidade", width=70, anchor="center")
    tree_mov.column("tipo", width=80, anchor="center")
    tree_mov.column("usuario", width=120, anchor="center")
    tree_mov.column("data", width=160)
    tree_mov.column("obs", width=200)
    tree_mov.pack(expand=True, fill="both", padx=8, pady=8)

    def atualizar_treeview_movimentacoes():
        for r in tree_mov.get_children():
            tree_mov.delete(r)
        try:
            movs = listar_movimentacoes()
            for m in movs:
                mid, produto, quantidade, tipo, usuario_m, data_hora, obs = m
                tree_mov.insert("", "end", values=(mid, produto or "—", quantidade, tipo, usuario_m or "—", data_hora, obs or ""))
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar movimentações: {e}")

    atualizar_treeview_movimentacoes()

    # ----- Tab Usuários (só para admin) -----
    if cargo == "administrador":
        tab_user = ttk.Frame(nb)
        nb.add(tab_user, text="Usuários")

        top_user = ttk.Frame(tab_user, padding=8)
        top_user.pack(fill="x")

        ttk.Button(top_user, text="Novo Usuário", command=lambda: abrir_criar_usuario(app, atualizar_usuarios)).pack(side="left", padx=6)
        ttk.Button(top_user, text="Deletar Usuário Selecionado", command=lambda: deletar_usuario_ui()).pack(side="left", padx=6)

        tree_users = ttk.Treeview(tab_user, columns=("id","nome","cargo"), show="headings", selectmode="browse", height=18)
        tree_users.heading("nome", text="Nome")
        tree_users.heading("cargo", text="Cargo")
        tree_users.column("id", width=0, stretch=False)
        tree_users.column("nome", width=320)
        tree_users.column("cargo", width=160, anchor="center")
        tree_users.pack(expand=True, fill="both", padx=8, pady=8)

        def atualizar_usuarios():
            for r in tree_users.get_children():
                tree_users.delete(r)
            try:
                users = listar_usuarios()
                for u in users:
                    uid, nomeu, cargou = u
                    tree_users.insert("", "end", values=(uid, nomeu, cargou))
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar usuários: {e}")

        def deletar_usuario_ui():
            sel = tree_users.selection()
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um usuário para deletar.")

            uid = int(tree_users.set(sel[0], "id"))
            nomeu = tree_users.set(sel[0], "nome")
            if nomeu == DEFAULT_ADMIN_USER:
                messagebox.showwarning("Aviso", f"Usuário '{DEFAULT_ADMIN_USER}' não pode ser removido.")
                return
            if messagebox.askyesno("Confirmar", f"Deletar usuário '{nomeu}'?"):
                try:
                    remover_usuario(uid)
                    messagebox.showinfo("Sucesso", "Usuário removido.")
                    atualizar_usuarios()
                except Exception as e:
                    messagebox.showerror("Erro", f"Não foi possível remover usuário: {e}")

        atualizar_usuarios()

    app.mainloop()

def abrir_criar_usuario(parent, atualiza_callback):
    top = tk.Toplevel(parent)
    top.title("Cadastrar Usuário")
    top.geometry("360x220")
    top.transient(parent)
    top.grab_set()

    ttk.Label(top, text="Nome:").pack(anchor="w", padx=10, pady=(10,0))
    e_nome = ttk.Entry(top); e_nome.pack(fill="x", padx=10)
    ttk.Label(top, text="Senha:").pack(anchor="w", padx=10, pady=(8,0))
    e_senha = ttk.Entry(top, show="*"); e_senha.pack(fill="x", padx=10)
    ttk.Label(top, text="Cargo:").pack(anchor="w", padx=10, pady=(8,0))
    cargo_var = tk.StringVar(value="funcionario")
    frm = ttk.Frame(top); frm.pack(anchor="w", padx=10)
    ttk.Radiobutton(frm, text="Administrador", variable=cargo_var, value="administrador").pack(side="left", padx=6)
    ttk.Radiobutton(frm, text="Funcionário", variable=cargo_var, value="funcionario").pack(side="left", padx=6)

    def salvar_usuario():
        nome = e_nome.get().strip()
        senha = e_senha.get().strip()
        cargo = cargo_var.get()
        if not nome or not senha:
            messagebox.showerror("Erro", "Preencha nome e senha.")

        ok, err = inserir_usuario(nome, senha, cargo)
        if ok:
            messagebox.showinfo("Sucesso", "Usuário criado.")
            top.destroy()
            atualiza_callback()
        else:
            messagebox.showerror("Erro", f"Não foi possível criar usuário: {err}")

    ttk.Button(top, text="Salvar", command=salvar_usuario).pack(pady=12)

# ---------------- Start ----------------
if __name__ == "__main__":
    init_db()
    abrir_login()
