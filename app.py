# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import streamlit as st
import sqlite3
import pandas as pd
import requests
from decouple import config
import numpy as np
from bs4 import BeautifulSoup
import streamlit.components.v1 as components  # Import para componentes customizados

# Declarar o componente customizado (removido da navegação)
# meu_componente = components.declare_component(
#     "meu_componente",
#     path="meu_componente/frontend/build"
# )

# Configuração da página (primeira instrução)
st.set_page_config(page_title="Comparação de Modelos: D2C vs. Exportação", layout="wide")

# Injeção de CSS customizado conforme design do Figma
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
        body {
            background-color: #F5F7FA;
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 0;
        }
        .stButton>button {
            background-color: #007BFF;
            color: white;
            border-radius: 4px;
            padding: 0.5rem 1rem;
            border: none;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #0056b3;
        }
        .card {
            background: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        .header {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        .subheader {
            font-size: 1.25rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# Inicializa valores padrão no session_state, se ainda não existirem
default_keys = {
    "dados_salvos": False,
    "dados_inseridos": {},
    "item_altura": 10,
    "item_largura": 10,
    "item_profundidade": 10,
    "item_peso": 0.5,
    "item_preco": 50.0,
    "item_quantidade": 1,
    "master_altura": 40,
    "master_largura": 40,
    "master_profundidade": 40,
    "master_max_peso": 50.0,
    "armazenagem": 0.50,   # custo de armazenagem por item
    "frete_local": 5.00,    # custo de frete local por item
    "tax_rate": 0.0         # taxa de imposto (em formato decimal)
}
for key, value in default_keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Carrega API Key do .env
API_KEY = config("SHIPSMART_API_KEY")

# ------------------------- FUNÇÕES AUXILIARES -------------------------
def carregar_ncm():
    conn = sqlite3.connect("ncm_database.db")
    df = pd.read_sql_query("SELECT product_code, product_description FROM ncm", conn)
    conn.close()
    return df

def buscar_sugestoes_ncm(ncm_parcial, df_ncm):
    df_filtrado = df_ncm[df_ncm["product_code"].astype(str).str.startswith(str(ncm_parcial))]
    return df_filtrado.values.tolist() if not df_filtrado.empty else []

def carregar_hs_usa():
    conn = sqlite3.connect("usa_database.db")
    df = pd.read_sql_query("SELECT product_code, product_description, ave FROM hs_codes", conn)
    conn.close()
    return df

def buscar_hs_usa_ia(ncm_6_digitos, df_hs_usa):
    resultados = df_hs_usa[df_hs_usa["product_code"].astype(str).str.startswith(str(ncm_6_digitos))]
    return resultados.values.tolist() if not resultados.empty else []

def buscar_hs_10_digitos(hs_code_6):
    url = f"https://hts.usitc.gov/search?q={hs_code_6}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        for row in soup.find_all("tr", class_=["odd", "even"]):
            cols = row.find_all("td")
            if len(cols) > 1:
                codigo = cols[0].text.strip()
                taxa = cols[-1].text.strip()
                if codigo.startswith(str(hs_code_6)):
                    return codigo, taxa
    return None, None

def calcular_frete_d2c(altura, largura, profundidade, peso, preco, quantidade):
    url = "https://api.shipsmart.com.br/v2/quotation?level=simple"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    pacotes = [{
        "name": f"Pacote {i+1}",
        "height": altura,
        "width": largura,
        "depth": profundidade,
        "weight": peso,
        "price": preco
    } for i in range(quantidade)]

    payload = {
        "object": "not_doc",
        "type": "simple",
        "tax": "receiver",
        "insurance": False,
        "residential_delivery": False,
        "non_stackable": False,
        "currency_quote": "USD",
        "currency_payment": "USD",
        "address_sender": {"country_code": "BR"},
        "address_receiver": {"country_code": "US"},
        "boxes": pacotes
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        fretes = response.json()
        if "data" in fretes and "carriers" in fretes["data"]:
            opcoes_frete = fretes["data"]["carriers"]
            frete_mais_barato = min(opcoes_frete, key=lambda x: float(x["currency_payment_amount"]))
            return frete_mais_barato["name"], float(frete_mais_barato["currency_payment_amount"])
    return None, None

def calcular_caixa_master(item_altura, item_largura, item_profundidade, item_peso, item_quantidade, item_preco,
                          master_altura, master_largura, master_profundidade, master_max_peso):
    item_volume = item_altura * item_largura * item_profundidade
    master_volume = master_altura * master_largura * master_profundidade
    cap_by_volume = master_volume // item_volume
    cap_by_weight = master_max_peso // item_peso
    capacity = int(min(cap_by_volume, cap_by_weight))
    if capacity <= 0:
        capacity = 1

    num_boxes = int(np.ceil(item_quantidade / capacity))
    total_weight = item_quantidade * item_peso
    boxes = []
    remaining = item_quantidade

    for i in range(num_boxes):
        items_in_box = capacity if remaining >= capacity else remaining
        box_weight = items_in_box * item_peso
        box_price = items_in_box * item_preco  
        boxes.append({
            "name": f"Caixa {i+1}",
            "height": master_altura,
            "width": master_largura,
            "depth": master_profundidade,
            "weight": box_weight,
            "price": box_price
        })
        remaining -= items_in_box

    return num_boxes, total_weight, capacity, boxes

def calcular_frete_formal(boxes):
    url = "https://api.shipsmart.com.br/v2/quotation?level=simple"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    payload = {
        "object": "not_doc",
        "type": "simple",
        "tax": "receiver",
        "insurance": False,
        "currency_quote": "USD",
        "currency_payment": "USD",
        "address_sender": {"country_code": "BR"},
        "address_receiver": {"country_code": "US"},
        "boxes": boxes
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        if "data" in data and "carriers" in data["data"]:
            opcoes_frete = data["data"]["carriers"]
            frete_mais_barato = min(opcoes_frete, key=lambda x: float(x["currency_payment_amount"]))
            return frete_mais_barato["name"], float(frete_mais_barato["currency_payment_amount"])
    return None, None

# ============================
# PÁGINAS DO APP
# ============================
def page_dados():
    st.title("Etapa 1: Inserir Dados")
    with st.container():
        st.subheader("Classificação NCM")
        ncm_parcial = st.text_input("Digite pelo menos 4 dígitos do NCM", key="ncm_input")
        if len(ncm_parcial) >= 4:
            df_ncm = carregar_ncm()
            sugestoes_ncm = buscar_sugestoes_ncm(ncm_parcial, df_ncm)
            if sugestoes_ncm:
                escolha = st.selectbox("Selecione o NCM correspondente:", 
                                       [f"{codigo} - {descricao}" for codigo, descricao in sugestoes_ncm],
                                       key="ncm_select")
                codigo_ncm_selecionado = escolha.split(" - ")[0]
                df_hs_usa = carregar_hs_usa()
                hs_usa = buscar_hs_usa_ia(codigo_ncm_selecionado[:6], df_hs_usa)
                if hs_usa:
                    melhor_hs = min(hs_usa, key=lambda x: float(x[2]) if x[2] != "N/A" else float("inf"))
                    st.write(f"**Taxa de Importação (AVE):** {melhor_hs[2]}")
                    st.session_state.tax_rate = float(melhor_hs[2]) if melhor_hs[2] != "N/A" else 0.0
        else:
            st.warning("Digite pelo menos 4 dígitos do NCM para ver sugestões.")

    st.markdown("---")
    st.subheader("Dados do Item")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Altura (cm)", min_value=1, value=10, key="item_altura")
    with col2:
        st.number_input("Largura (cm)", min_value=1, value=10, key="item_largura")
    with col3:
        st.number_input("Profundidade (cm)", min_value=1, value=10, key="item_profundidade")
    col4, col5 = st.columns(2)
    with col4:
        st.number_input("Peso (kg)", min_value=0.1, value=0.5, format="%.2f", key="item_peso")
    with col5:
        st.number_input("Valor (USD)", min_value=1.0, value=50.0, format="%.2f", key="item_preco")
    st.number_input("Quantidade de itens", min_value=1, value=1, key="item_quantidade")

    st.markdown("---")
    st.subheader("Dados da Caixa Master")
    col6, col7, col8 = st.columns(3)
    with col6:
        st.number_input("Altura (cm)", min_value=1, value=40, key="master_altura")
    with col7:
        st.number_input("Largura (cm)", min_value=1, value=40, key="master_largura")
    with col8:
        st.number_input("Profundidade (cm)", min_value=1, value=40, key="master_profundidade")
    st.number_input("Peso máximo suportado (kg)", min_value=1.0, value=50.0, format="%.2f", key="master_max_peso")

    st.markdown("---")
    st.subheader("Custos Adicionais para Frete Formal")
    col9, col10 = st.columns(2)
    with col9:
        st.number_input("Custo de Armazenagem por item (USD)", min_value=0.0, value=0.50, format="%.2f", key="armazenagem")
    with col10:
        st.number_input("Custo de Frete Local por item (USD)", min_value=0.0, value=5.00, format="%.2f", key="frete_local")

    if st.button("Salvar Dados e Avançar para D2C"):
        st.session_state.dados_inseridos = {
            "item_altura": st.session_state.item_altura,
            "item_largura": st.session_state.item_largura,
            "item_profundidade": st.session_state.item_profundidade,
            "item_peso": st.session_state.item_peso,
            "item_preco": st.session_state.item_preco,
            "item_quantidade": st.session_state.item_quantidade,
            "master_altura": st.session_state.master_altura,
            "master_largura": st.session_state.master_largura,
            "master_profundidade": st.session_state.master_profundidade,
            "master_max_peso": st.session_state.master_max_peso,
            "armazenagem": st.session_state.armazenagem,
            "frete_local": st.session_state.frete_local,
            "tax_rate": st.session_state.tax_rate
        }
        st.session_state.dados_salvos = True
        st.success("Dados salvos com sucesso!")
        st.write("Registro dos dados:", st.session_state.dados_inseridos)

def page_d2c():
    st.title("Etapa 2: Calcular Frete D2C")

    if not st.session_state.get("dados_salvos", False):
        st.error("Salve os dados na Etapa 1 primeiro.")
        return

    st.write("**Dados Utilizados:**", st.session_state.dados_inseridos)

    if st.button("Calcular Frete D2C"):
        dados = st.session_state.dados_inseridos
        nome, valor = calcular_frete_d2c(
            dados["item_altura"],
            dados["item_largura"],
            dados["item_profundidade"],
            dados["item_peso"],
            dados["item_preco"],
            1  # Envio individual
        )
        if nome:
            st.session_state.frete_d2c = f"Frete D2C por item: {nome} - ${valor:.2f}"
            st.session_state.frete_d2c_value = valor
            st.success("Frete D2C calculado com sucesso!")
        else:
            st.error("Erro ao calcular Frete D2C.")

    if "frete_d2c" in st.session_state:
        st.info(st.session_state.frete_d2c)

def page_formal():
    st.title("Etapa 3: Calcular Frete Formal")

    if not st.session_state.get("dados_salvos", False):
        st.error("Salve os dados na Etapa 1 primeiro.")
        return

    st.write("**Dados Utilizados:**", st.session_state.dados_inseridos)
    dados = st.session_state.dados_inseridos

    if st.button("Calcular Caixa Master"):
        num_boxes, total_weight, capacity, boxes = calcular_caixa_master(
            dados["item_altura"],
            dados["item_largura"],
            dados["item_profundidade"],
            dados["item_peso"],
            dados["item_quantidade"],
            dados["item_preco"],
            dados["master_altura"],
            dados["master_largura"],
            dados["master_profundidade"],
            dados["master_max_peso"]
        )
        st.session_state.master_boxes = boxes
        st.session_state.num_boxes = num_boxes
        st.session_state.total_weight = total_weight
        st.session_state.capacity = capacity

        st.subheader("Configuração da Caixa Master")
        st.write(f"Caixas necessárias: **{num_boxes}**")
        st.write(f"Peso total dos itens: **{total_weight} kg**")
        st.write(f"Capacidade máxima por caixa: **{capacity} itens**")
        st.table(pd.DataFrame(boxes))

    if st.button("Calcular Frete Formal"):
        if "master_boxes" not in st.session_state:
            st.error("Primeiro calcule a configuração da Caixa Master.")
        else:
            nome, valor = calcular_frete_formal(st.session_state.master_boxes)
            if nome:
                st.session_state.frete_formal = f"Frete Formal consolidado: {nome} - ${valor:.2f}"
                # Total de itens (soma dos itens em todas as caixas)
                total_items = sum([box["price"] / dados["item_preco"] for box in st.session_state.master_boxes])
                st.write("Total de itens nas caixas:", total_items)

                custo_frete_por_item = valor / total_items
                total_valor_itens = dados["item_preco"] * dados["item_quantidade"]

                if total_valor_itens < 800:
                    imposto_por_item = 0
                else:
                    imposto_por_item = dados["tax_rate"] * dados["item_preco"]

                # Custo total considerando armazenagem e frete local
                custo_armazenagem_total = dados["armazenagem"] * total_items
                custo_frete_local_total = dados["frete_local"] * total_items

                custo_total_formal = valor + (imposto_por_item * total_items) + custo_armazenagem_total + custo_frete_local_total
                formal_cost_per_item = custo_total_formal / total_items

                st.session_state.formal_cost_per_item = formal_cost_per_item
                st.session_state.formal_breakdown = {
                    "Frete Formal Total": valor,
                    "Quantidade de Itens": total_items,
                    "Custo de Frete por Item": custo_frete_por_item,
                    "Imposto por Item": imposto_por_item,
                    "Custo de Armazenagem Total": custo_armazenagem_total,
                    "Custo de Armazenagem por Item": custo_armazenagem_total / total_items,
                    "Custo de Frete Local Total": custo_frete_local_total,
                    "Custo de Frete Local por Item": custo_frete_local_total / total_items,
                    "Total Formal por Item": formal_cost_per_item,
                }
                st.success("Frete Formal calculado com sucesso!")
            else:
                st.error("Erro ao calcular Frete Formal.")

    if "frete_formal" in st.session_state:
        st.info(st.session_state.frete_formal)

def page_resultado():
    st.title("Etapa 4: Resultado Final")

    if "frete_d2c" not in st.session_state or "formal_cost_per_item" not in st.session_state:
        st.error("Calcule os fretes D2C e Formal nas etapas anteriores.")
        return

    d2c_valor_str = st.session_state.frete_d2c.split('$')[-1]
    try:
        d2c_valor = float(d2c_valor_str)
    except:
        d2c_valor = st.session_state.frete_d2c_value

    formal_valor = st.session_state.formal_cost_per_item

    st.write(f"**D2C - Custo por item:** ${d2c_valor:.2f}")
    st.write(f"**Formal - Custo por item:** ${formal_valor:.2f}")

    # Calcular custo total para cada cenário (quantidade total de itens * custo por item)
    total_items = st.session_state.dados_inseridos["item_quantidade"]
    total_d2c = total_items * d2c_valor
    total_formal = total_items * formal_valor

    # Cria um DataFrame para o gráfico de barras
    df_chart = pd.DataFrame({
        "Cenário": ["D2C", "Formal"],
        "Custo Total (USD)": [total_d2c, total_formal]
    })

    st.subheader("Comparação de Custo Total por Cenário")
    st.bar_chart(df_chart.set_index("Cenário"))

    st.subheader("Memória de Cálculo (Formal)")
    breakdown_data = [
        {"Item": "Frete Formal Total", "Valor (USD)": f"${st.session_state.formal_breakdown['Frete Formal Total']:.2f}"},
        {"Item": "Quantidade de Itens", "Valor (USD)": st.session_state.formal_breakdown["Quantidade de Itens"]},
        {"Item": "Custo de Frete por Item", "Valor (USD)": f"${st.session_state.formal_breakdown['Custo de Frete por Item']:.2f}"},
        {"Item": "Imposto por Item", "Valor (USD)": f"${st.session_state.formal_breakdown['Imposto por Item']:.2f}"},
        {"Item": "Custo de Armazenagem Total", "Valor (USD)": f"${st.session_state.formal_breakdown['Custo de Armazenagem Total']:.2f}"},
        {"Item": "Custo de Armazenagem por Item", "Valor (USD)": f"${st.session_state.formal_breakdown['Custo de Armazenagem por Item']:.2f}"},
        {"Item": "Custo de Frete Local Total", "Valor (USD)": f"${st.session_state.formal_breakdown['Custo de Frete Local Total']:.2f}"},
        {"Item": "Custo de Frete Local por Item", "Valor (USD)": f"${st.session_state.formal_breakdown['Custo de Frete Local por Item']:.2f}"},
        {"Item": "Total Formal por Item", "Valor (USD)": f"${st.session_state.formal_breakdown['Total Formal por Item']:.2f}"}
    ]
    st.table(pd.DataFrame(breakdown_data))


# ============================
# NAVEGAÇÃO LATERAL
# ============================
etapa = st.sidebar.radio(
    "Navegação",
    ["1. Inserir Dados", "2. Frete D2C", "3. Frete Formal", "4. Resultado Final"]
)

if etapa == "1. Inserir Dados":
    page_dados()
elif etapa == "2. Frete D2C":
    page_d2c()
elif etapa == "3. Frete Formal":
    page_formal()
elif etapa == "4. Resultado Final":
    page_resultado()

















































