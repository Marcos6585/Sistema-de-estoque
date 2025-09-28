# dashboard.py
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import hashlib
import io

# ----------------- Banco -----------------
DB_PATH = "estoque.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Criar tabelas se não existirem
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    cargo TEXT CHECK(cargo IN ('administrador', 'funcionario')) NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    quantidade INTEGER CHECK(quantidade >= 0) DEFAULT 0,
    preco_unitario REAL CHECK(preco_unitario >= 0) DEFAULT 0.0,
    fornecedor TEXT,
    UNIQUE(nome, categoria)
)
""")
conn.commit()

# ----------------- Utilitários -----------------
def hash_senha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def criar_admin_padrao():
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (nome, senha, cargo) VALUES (?, ?, ?)",
                       ("admin", hash_senha("admin"), "administrador"))
        conn.commit()

criar_admin_padrao()

# ----------------- CRUD Produtos e Usuários -----------------
def carregar_produtos():
    df = pd.read_sql_query("SELECT * FROM produtos", conn)
    return df

def carregar_usuarios():
    df = pd.read_sql_query("SELECT * FROM usuarios", conn)
    return df

def cadastrar_produto(nome, categoria, quantidade, preco_unitario, fornecedor):
    if not nome.strip():
        return False, "Nome do produto é obrigatório."
    if quantidade < 0:
        return False, "Quantidade não pode ser negativa."
    if preco_unitario < 0:
        return False, "Preço não pode ser negativo."
    try:
        cursor.execute("""
            INSERT INTO produtos (nome, categoria, quantidade, preco_unitario, fornecedor)
            VALUES (?, ?, ?, ?, ?)
        """, (nome.title().strip(), categoria, int(quantidade), float(preco_unitario), fornecedor.title().strip()))
        conn.commit()
        return True, "Produto cadastrado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Produto já existe nessa categoria."

def deletar_produto(id_produto):
    cursor.execute("DELETE FROM produtos WHERE id=?", (id_produto,))
    conn.commit()

def cadastrar_usuario(nome, senha, cargo):
    if not nome.strip() or not senha:
        return False, "Nome e senha são obrigatórios."
    if cargo not in ("administrador", "funcionario"):
        return False, "Cargo inválido."
    try:
        cursor.execute("INSERT INTO usuarios (nome, senha, cargo) VALUES (?, ?, ?)",
                       (nome.strip(), hash_senha(senha), cargo))
        conn.commit()
        return True, "Usuário cadastrado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Já existe um usuário com esse nome."

def deletar_usuario(id_usuario):
    cursor.execute("DELETE FROM usuarios WHERE id=?", (id_usuario,))
    conn.commit()

def autenticar_usuario(nome, senha):
    h = hash_senha(senha)
    cursor.execute("SELECT id, nome, cargo FROM usuarios WHERE nome=? AND senha=?", (nome, h))
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "nome": row[1], "cargo": row[2]}
    return None

# ----------------- Helpers para download (corrigido) -----------------
def gerar_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

def gerar_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="estoque")
    return output.getvalue()

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="Dashboard de Estoque - Finalzona", layout="wide")
st.title("📦 Dashboard de Estoque — Finalzona")

if "user" not in st.session_state:
    st.session_state.user = None

with st.sidebar:
    st.header("Acesso")
    if not st.session_state.user:
        nome_login = st.text_input("Usuário")
        senha_login = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            user = autenticar_usuario(nome_login.strip(), senha_login)
            if user:
                st.session_state.user = user
                st.success(f"Bem-vindo(a), {user['nome']} ({user['cargo']})")
            else:
                st.error("Usuário ou senha incorretos.")
        st.markdown("---")
        st.info("Se não houver usuários cadastrados, existe um admin padrão: **admin / admin**")
    else:
        st.write(f"👤 **{st.session_state.user['nome']}**")
        st.write(f"📌 Cargo: **{st.session_state.user['cargo']}**")
        if st.button("Sair"):
            st.session_state.user = None
            st.experimental_rerun()

menu_ops = ["Produtos"]
if st.session_state.user:
    menu_ops = ["Produtos", "Cadastro", "Deleção", "Usuários", "Relatórios"]

menu = st.sidebar.selectbox("Menu", menu_ops)

def style_estoque(df, limite_baixo=5):
    if df.empty:
        return df
    styled = df.style.format({
        "preco_unitario": "R${:,.2f}",
        "quantidade": "{:,d}"
    }).applymap(lambda v: "background-color: #ffcccc" if (isinstance(v, (int,)) and v <= limite_baixo) else "",
               subset=["quantidade"])
    return styled

# -------------------------------- Produtos --------------------------------
if menu == "Produtos":
    st.subheader("📋 Produtos e Relatórios Rápidos")
    df = carregar_produtos()

    col1, col2, col3, col4 = st.columns(4)
    total_itens = int(df["quantidade"].sum()) if not df.empty else 0
    valor_total = float((df["quantidade"] * df["preco_unitario"]).sum()) if not df.empty else 0.0
    produtos_unicos = int(df.shape[0]) if not df.empty else 0
    estoque_baixo = int(df[df["quantidade"] <= 5].shape[0]) if not df.empty else 0

    col1.metric("Quantidade total", f"{total_itens}")
    col2.metric("Valor total em estoque", f"R${valor_total:,.2f}")
    col3.metric("Produtos únicos", f"{produtos_unicos}")
    col4.metric("Produtos com estoque baixo (<=5)", f"{estoque_baixo}")

    st.sidebar.header("Filtros de Visualização (Produtos)")
    if df.empty:
        st.warning("Nenhum produto cadastrado ainda.")
        st.stop()

    categorias = ["Todas"] + sorted(df["categoria"].dropna().unique().tolist())
    cat_select = st.sidebar.selectbox("Categoria", categorias)

    fornecedores = ["Todos"] + sorted(df["fornecedor"].dropna().unique().tolist())
    forn_select = st.sidebar.selectbox("Fornecedor", fornecedores)

    preco_min = st.sidebar.number_input("Preço mínimo", min_value=0.0, value=float(df["preco_unitario"].min()))
    preco_max = st.sidebar.number_input("Preço máximo", min_value=0.0, value=float(df["preco_unitario"].max()))

    qtd_min = st.sidebar.number_input("Quantidade mínima", min_value=0, value=int(df["quantidade"].min()))
    qtd_max = st.sidebar.number_input("Quantidade máxima", min_value=0, value=int(df["quantidade"].max()))

    busca = st.sidebar.text_input("Buscar por nome")

    ordenar_por = st.sidebar.selectbox("Ordenar por", ["Nenhum", "Nome", "Preço", "Quantidade"])
    ordem = st.sidebar.radio("Ordem", ["Crescente", "Decrescente"])

    df_filtrado = df.copy()
    if cat_select != "Todas":
        df_filtrado = df_filtrado[df_filtrado["categoria"] == cat_select]
    if forn_select != "Todos":
        df_filtrado = df_filtrado[df_filtrado["fornecedor"] == forn_select]
    df_filtrado = df_filtrado[(df_filtrado["preco_unitario"] >= preco_min) & (df_filtrado["preco_unitario"] <= preco_max)]
    df_filtrado = df_filtrado[(df_filtrado["quantidade"] >= qtd_min) & (df_filtrado["quantidade"] <= qtd_max)]
    if busca:
        df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(busca, case=False, na=False)]
    if ordenar_por != "Nenhum":
        asc = ordem == "Crescente"
        if ordenar_por == "Nome":
            df_filtrado = df_filtrado.sort_values("nome", ascending=asc)
        elif ordenar_por == "Preço":
            df_filtrado = df_filtrado.sort_values("preco_unitario", ascending=asc)
        elif ordenar_por == "Quantidade":
            df_filtrado = df_filtrado.sort_values("quantidade", ascending=asc)

    tab1, tab2 = st.tabs(["Tabela", "Gráficos"])
    with tab1:
        st.subheader("📦 Tabela de Produtos (filtrada)")
        styled = style_estoque(df_filtrado, limite_baixo=5)
        st.dataframe(styled, use_container_width=True)

        col_down1, col_down2 = st.columns(2)
        with col_down1:
            csv_bytes = gerar_csv_bytes(df_filtrado)
            st.download_button("⬇️ Baixar CSV", data=csv_bytes, file_name="estoque_filtrado.csv", mime="text/csv")
        with col_down2:
            excel_bytes = gerar_excel_bytes(df_filtrado)
            st.download_button("⬇️ Baixar Excel", data=excel_bytes, file_name="estoque_filtrado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab2:
        st.subheader("📊 Gráficos")
        graf_cat = df_filtrado.groupby("categoria")["quantidade"].sum().reset_index()
        if not graf_cat.empty:
            fig_bar = px.bar(graf_cat, x="categoria", y="quantidade", title="Quantidade por Categoria", labels={"quantidade":"Quantidade","categoria":"Categoria"})
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados para gráfico de quantidade por categoria.")

        graf_pie = graf_cat.copy()
        if not graf_pie.empty:
            fig_pie = px.pie(graf_pie, names="categoria", values="quantidade", title="Proporção de Itens por Categoria")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sem dados para gráfico de pizza.")

# -------------------------------- Cadastro --------------------------------
elif menu == "Cadastro":
    if not st.session_state.user:
        st.warning("Você precisa fazer login para acessar essa área.")
        st.stop()

    st.subheader("➕ Cadastrar Produto")
    col_left, col_right = st.columns(2)
    with col_left:
        nome = st.text_input("Nome do produto")
        categoria = st.selectbox("Categoria", ["Alimentos", "Higiene Pessoal", "Eletrônicos", "Vestuário e Acessórios", "Limpeza", "Outros"])
        quantidade = st.number_input("Quantidade", min_value=0, value=0, step=1)
    with col_right:
        preco = st.number_input("Preço unitário (R$)", min_value=0.0, value=0.0, step=0.01)
        fornecedor = st.text_input("Fornecedor (opcional)")
        if st.button("Cadastrar produto"):
            ok, msg = cadastrar_produto(nome, categoria, quantidade, preco, fornecedor)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")
    st.subheader("👥 Cadastrar Usuário (apenas admins podem criar outros usuários)")
    if st.session_state.user["cargo"] != "administrador":
        st.info("Apenas administradores podem cadastrar usuários.")
    else:
        with st.form("form_cad_user"):
            nome_u = st.text_input("Nome do usuário", key="u_nome")
            senha_u = st.text_input("Senha", type="password", key="u_senha")
            cargo_u = st.selectbox("Cargo", ["administrador", "funcionario"], key="u_cargo")
            sub = st.form_submit_button("Cadastrar Usuário")
            if sub:
                ok, msg = cadastrar_usuario(nome_u, senha_u, cargo_u)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# -------------------------------- Deleção --------------------------------
elif menu == "Deleção":
    if not st.session_state.user:
        st.warning("Você precisa fazer login para acessar essa área.")
        st.stop()

    st.subheader("🗑️ Deletar Produto (somente admin)")
    df = carregar_produtos()
    if df.empty:
        st.info("Nenhum produto cadastrado.")
    else:
        if st.session_state.user["cargo"] != "administrador":
            st.info("Apenas administradores podem deletar produtos.")
        else:
            sel = st.selectbox("Escolha o produto para deletar", df["nome"] + " | " + df["categoria"] + " (ID: " + df["id"].astype(str) + ")")
            id_sel = int(sel.split("ID: ")[1].replace(")", ""))
            if st.button("Deletar produto selecionado"):
                deletar_produto(id_sel)
                st.success("Produto deletado.")
                st.experimental_rerun()

# -------------------------------- Usuários --------------------------------
elif menu == "Usuários":
    if not st.session_state.user:
        st.warning("Você precisa fazer login para acessar essa área.")
        st.stop()

    st.subheader("🔒 Gerenciamento de Usuários")
    dfu = carregar_usuarios()
    if dfu.empty:
        st.info("Nenhum usuário cadastrado além do padrão.")
    else:
        st.dataframe(dfu, use_container_width=True)

    st.markdown("---")
    if st.session_state.user["cargo"] == "administrador":
        st.subheader("🗑️ Deletar Usuário")
        dfu = carregar_usuarios()
        opcoes = dfu["nome"] + " (ID: " + dfu["id"].astype(str) + ")"
        sel_u = st.selectbox("Selecione usuário para deletar", opcoes)
        idu = int(sel_u.split("ID: ")[1].replace(")", ""))
        nome_sel = sel_u.split(" (ID")[0]
        if nome_sel == st.session_state.user["nome"]:
            st.warning("Você não pode deletar o usuário que está logado.")
        else:
            if st.button("Deletar usuário selecionado"):
                deletar_usuario(idu)
                st.success("Usuário deletado.")
                st.experimental_rerun()
    else:
        st.info("Somente administradores podem deletar usuários.")

# -------------------------------- Relatórios --------------------------------
elif menu == "Relatórios":
    if not st.session_state.user:
        st.warning("Você precisa fazer login para acessar essa área.")
        st.stop()

    st.subheader("📑 Relatórios e Resumos")
    df = carregar_produtos()
    if df.empty:
        st.info("Sem dados para gerar relatório.")
        st.stop()

    total_valor = (df["quantidade"] * df["preco_unitario"]).sum()
    st.metric("Valor total em estoque", f"R${total_valor:,.2f}")
    st.write("Produtos por categoria:")
    st.table(df.groupby("categoria")[["quantidade"]].sum().reset_index())

    st.markdown("### ⬇️ Downloads")
    st.download_button("Baixar CSV (completo)", data=gerar_csv_bytes(df), file_name="estoque_completo.csv", mime="text/csv")
    st.download_button("Baixar Excel (completo)", data=gerar_excel_bytes(df), file_name="estoque_completo.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ----------------- Fim -----------------
st.markdown("---")

