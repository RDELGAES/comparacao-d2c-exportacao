import sqlite3
import pandas as pd

# Nome do arquivo correto
file_path = "Brazil 2024.xlsx"

# Nome do banco de dados
db_path = "ncm_database.db"

# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Criar a tabela para armazenar os dados da planilha
cursor.execute("""
    CREATE TABLE IF NOT EXISTS ncm (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT,
        year INTEGER,
        revision TEXT,
        product_code TEXT,
        product_description TEXT,
        nav_duty REAL,
        ave REAL
    )
""")

# Carregar a aba "Data" do arquivo Excel
df = pd.read_excel(file_path, sheet_name="Data")

# Remover valores NaN da planilha e substituir por zero onde necessário
df.fillna(0, inplace=True)

# Selecionar as colunas corretas e renomear para bater com o banco
df_to_insert = df[["ReportingCountry", "Year", "Revision", "ProductCode", "ProductDescription", "NavDuty", "AVE"]]
df_to_insert.columns = ["country", "year", "revision", "product_code", "product_description", "nav_duty", "ave"]

# Inserir os dados na tabela NCM
df_to_insert.to_sql("ncm", conn, if_exists="replace", index=False)

# Fechar a conexão com o banco de dados
conn.commit()
conn.close()

print("📌 Banco de Dados atualizado com sucesso!")

