import os
import pandas as pd
import numpy as np

# Diretórios oficiais do projeto
RAW_DIR = "Data/raw"
SILVER_DIR = "Data/silver"

def limpar_documento(doc):
    """Remove pontuação e garante zeros à esquerda (14 dig p/ CNPJ, 11 p/ CPF)."""
    if pd.isna(doc):
        return np.nan
    doc_limpo = ''.join(filter(str.isdigit, str(doc)))
    if not doc_limpo:
        return np.nan
    if len(doc_limpo) <= 11:
        return doc_limpo.zfill(11)
    return doc_limpo.zfill(14)

def limpar_valor(valor):
    if pd.isna(valor):
        return np.nan

    val_str = str(valor).strip()

    if not val_str:
        return np.nan

    # Remove símbolo monetário e espaços comuns/especiais
    val_str = val_str.replace("R$", "")
    val_str = val_str.replace("\xa0", "")
    val_str = val_str.replace(" ", "")

    # Trata separadores brasileiros e internacionais
    if "," in val_str and "." in val_str:
        if val_str.rfind(",") > val_str.rfind("."):
            val_str = val_str.replace(".", "").replace(",", ".")
        else:
            val_str = val_str.replace(",", "")

    elif "," in val_str:
        val_str = val_str.replace(",", ".")

    elif val_str.count(".") > 1:
        partes = val_str.split(".")
        val_str = "".join(partes[:-1]) + "." + partes[-1]

    try:
        return float(val_str)
    except ValueError:
        return np.nan

def processar_camada_silver():
    print("🥈 === PROCESSANDO CAMADA SILVER (SPRINT 3) ===\n")
    
    # Garante que a pasta Data/silver existe
    os.makedirs(SILVER_DIR, exist_ok=True)
    print(f"📁 Diretórios validados: '{RAW_DIR}' -> '{SILVER_DIR}'\n")

    arquivos = ["compras.csv", "itens.csv", "resultados.csv"]

    for arq in arquivos:
        caminho_raw = os.path.join(RAW_DIR, arq)
        caminho_silver = os.path.join(SILVER_DIR, arq)

        if not os.path.exists(caminho_raw):
            print(f"⚠️ Arquivo {arq} não encontrado em '{RAW_DIR}'. Pulando...")
            continue

        print(f"🔄 Processando e higienizando {arq}...")
        df = pd.read_csv(caminho_raw, dtype=str, low_memory=False)

        # Trata colunas de documento (CNPJ/CPF)
        cols_doc = [c for c in df.columns if 'ni_' in c.lower() or 'cnpj' in c.lower() or 'cpf' in c.lower()]
        for c in cols_doc:
            df[c] = df[c].apply(limpar_documento)

        # Trata colunas de valor monetário ou quantidade
        cols_val = [c for c in df.columns if 'valor' in c.lower() or 'quantidade' in c.lower()]
        for c in cols_val:
            df[c] = df[c].apply(limpar_valor)

        # Salva o resultado limpo na camada Silver
        df.to_csv(caminho_silver, index=False, encoding='utf-8')
        print(f"✅ Salvo com sucesso em '{caminho_silver}' ({len(df)} linhas)\n")

    print("✨ Camada Silver gerada com sucesso na pasta Data/silver/!")

if __name__ == '__main__':
    processar_camada_silver()