import sqlite3
import pandas as pd

# Nome do arquivo correto
data_file = "United States of America 2024.xlsx"

db_path = "usa_database.db"

# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Criar a tabela para armazenar os dados dos EUA
cursor.execute("""
    CREATE TABLE IF NOT EXISTS hs_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER,
        revision TEXT,
        product_code TEXT,
        product_description TEXT,
        nav_duty TEXT,
        ave REAL
    )
""")

# Carregar a aba "Data" do arquivo Excel
df = pd.read_excel(data_file, sheet_name="Data")

# Remover valores NaN da planilha e substituir por zero onde necessário
df.fillna("N/A", inplace=True)

# Selecionar as colunas corretas e renomear para bater com o banco
df_to_insert = df[["Year", "Revision", "ProductCode", "ProductDescription", "NavDuty", "AVE"]]
df_to_insert.columns = ["year", "revision", "product_code", "product_description", "nav_duty", "ave"]

# Inserir os dados na tabela HS Codes
df_to_insert.to_sql("hs_codes", conn, if_exists="replace", index=False)

# Fechar a conexão com o banco de dados
conn.commit()
conn.close()

print("📌 Banco de Dados dos EUA atualizado com sucesso!")
