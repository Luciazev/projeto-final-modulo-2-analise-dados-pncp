"""
Carregador seguro PNCP -> MySQL
Cria tabelas paralelas com sufixo _nova. Não altera as tabelas originais.

Execução:
    python src/carregar_corrigido.py

Requisitos:
    pip install pandas sqlalchemy pymysql python-dotenv
"""

import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


# ---------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
GOLD_FILE = BASE_DIR / "Data" / "gold" / "fato_itens_homologados.csv"
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "pncp_controladoria")

TABLES = [
    "dim_orgao_nova",
    "dim_fornecedor_nova",
    "dim_modalidade_nova",
    "dim_localidade_nova",
    "fato_item_contratado_nova",
]

REQUIRED_COLUMNS = [
    "numero_controle_pncp",
    "numero_item",
    "cnpj_orgao",
    "razao_social_orgao",
    "ni_fornecedor",
    "nome_fornecedor",
    "modalidade_id",
    "modalidade_nome",
    "cod_ibge",
    "uf_sigla",
    "municipio",
    "data_publicacao",
    "data_homologacao",
    "descricao_item",
    "perfil_gasto",
    "quantidade",
    "valor_unitario_estimado",
    "valor_unitario_homologado",
    "valor_total_estimado",
    "valor_total_homologado",
    "comparavel",
    "economia_valor",
    "dias_ciclo",
]

UF_INFO = {
    "AC": ("Acre", "Norte"), "AL": ("Alagoas", "Nordeste"),
    "AP": ("Amapá", "Norte"), "AM": ("Amazonas", "Norte"),
    "BA": ("Bahia", "Nordeste"), "CE": ("Ceará", "Nordeste"),
    "DF": ("Distrito Federal", "Centro-Oeste"),
    "ES": ("Espírito Santo", "Sudeste"), "GO": ("Goiás", "Centro-Oeste"),
    "MA": ("Maranhão", "Nordeste"), "MT": ("Mato Grosso", "Centro-Oeste"),
    "MS": ("Mato Grosso do Sul", "Centro-Oeste"),
    "MG": ("Minas Gerais", "Sudeste"), "PA": ("Pará", "Norte"),
    "PB": ("Paraíba", "Nordeste"), "PR": ("Paraná", "Sul"),
    "PE": ("Pernambuco", "Nordeste"), "PI": ("Piauí", "Nordeste"),
    "RJ": ("Rio de Janeiro", "Sudeste"), "RN": ("Rio Grande do Norte", "Nordeste"),
    "RS": ("Rio Grande do Sul", "Sul"), "RO": ("Rondônia", "Norte"),
    "RR": ("Roraima", "Norte"), "SC": ("Santa Catarina", "Sul"),
    "SP": ("São Paulo", "Sudeste"), "SE": ("Sergipe", "Nordeste"),
    "TO": ("Tocantins", "Norte"),
}


def clean_text(value, default="Não informado"):
    if pd.isna(value):
        return default
    value = str(value).strip()
    return value if value and value.lower() not in {"nan", "none", "null"} else default


def clean_identifier(value, default):
    value = clean_text(value, default)
    # Identificadores PNCP são tratados como texto; remove apenas espaços.
    return value.replace(" ", "") if value != default else default


def as_int(value, default=0):
    if pd.isna(value) or str(value).strip() == "":
        return default
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return default


def as_decimal(value, scale=2, default="0"):
    if pd.isna(value) or str(value).strip() == "":
        value = default
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        number = Decimal(default)
    quantum = Decimal("1").scaleb(-scale)
    return number.quantize(quantum, rounding=ROUND_HALF_UP)


def as_date(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def main():
    print("=== CARGA SEGURA PNCP / MYSQL ===")

    if not all([DB_USER, DB_PASS, DB_HOST, DB_NAME]):
        raise RuntimeError(
            "Configuração incompleta no .env. Verifique DB_USER, DB_PASS, DB_HOST e DB_NAME."
        )

    if not GOLD_FILE.exists():
        raise FileNotFoundError(f"Arquivo Gold não encontrado: {GOLD_FILE}")

    print(f"Gold encontrado: {GOLD_FILE}")
    df = pd.read_csv(GOLD_FILE, dtype=str, keep_default_na=False)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes no Gold: {missing}")

    if len(df) == 0:
        raise ValueError("O arquivo Gold está vazio.")

    df = df[REQUIRED_COLUMNS].copy()
    df["numero_controle_pncp"] = df["numero_controle_pncp"].map(
        lambda x: clean_text(x, "")
    )
    df["numero_item"] = df["numero_item"].map(lambda x: as_int(x, -1))

    if (df["numero_controle_pncp"] == "").any() or (df["numero_item"] < 0).any():
        raise ValueError("Há chave PNCP/item vazia ou inválida.")

    duplicates = df.duplicated(
        subset=["numero_controle_pncp", "numero_item"], keep=False
    )
    if duplicates.any():
        raise ValueError(
            f"Foram encontradas {int(duplicates.sum())} linhas em chaves PNCP/item duplicadas."
        )

    print(f"Registros Gold validados: {len(df):,}")
    print("Chave composta PNCP + item: sem duplicidades.")

    url = URL.create(
        "mysql+pymysql",
        username=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(url, pool_pre_ping=True)

    # Verificação de segurança: consulta individual evita sobrescrever qualquer
    # tabela-alvo que já exista, mesmo que esteja vazia ou parcialmente carregada.
    with engine.connect() as conn:
        existing_names = []
        for table_name in TABLES:
            found = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = :db AND table_name = :table_name
                    """
                ),
                {"db": DB_NAME, "table_name": table_name},
            ).scalar_one()
            if found:
                existing_names.append(table_name)

    if existing_names:
        raise RuntimeError(
            "CARGA CANCELADA por segurança. Estas tabelas _nova já existem: "
            + ", ".join(existing_names)
            + ". Nenhuma tabela foi alterada. Não as apague; informe este resultado."
        )

    print("Nenhuma tabela _nova existe. Preparando dimensões e FATO...")

    # -----------------------------------------------------------------
    # Preparar dimensões com chaves naturais corretas
    # -----------------------------------------------------------------

    orgao_map = {}
    fornecedor_map = {}
    modalidade_map = {}
    localidade_map = {}

    orgaos = {}
    fornecedores = {}
    modalidades = {}
    localidades = {}

    for row in df.to_dict("records"):
        cnpj = clean_identifier(row["cnpj_orgao"], "00000000000000")
        nome_orgao = clean_text(row["razao_social_orgao"])
        orgaos[cnpj] = nome_orgao

        ni = clean_identifier(row["ni_fornecedor"], "00000000000000")
        nome_fornecedor = clean_text(row["nome_fornecedor"])
        fornecedores[ni] = nome_fornecedor

        modalidade_id = as_int(row["modalidade_id"], -1)
        modalidade_nome = clean_text(row["modalidade_nome"])
        modalidades[modalidade_id] = modalidade_nome

        uf = clean_text(row["uf_sigla"], "EX").upper()[:2]
        if uf in UF_INFO:
            uf_nome, regiao = UF_INFO[uf]
        else:
            uf, uf_nome, regiao = "EX", "Não informado", "Não informado"
        localidades[uf] = (uf_nome, regiao)

    orgaos.setdefault("00000000000000", "Não informado")
    fornecedores.setdefault("00000000000000", "Não informado")
    modalidades.setdefault(-1, "Não informado")
    localidades.setdefault("EX", ("Não informado", "Não informado"))

    # -----------------------------------------------------------------
    # DDL: tabelas paralelas. Não há DROP, DELETE ou TRUNCATE.
    # -----------------------------------------------------------------

    ddl = [
        """
        CREATE TABLE dim_orgao_nova (
            sk_orgao INT NOT NULL,
            cnpj_orgao VARCHAR(14) NOT NULL,
            nome_orgao VARCHAR(255) NOT NULL,
            poder VARCHAR(50) NOT NULL,
            PRIMARY KEY (sk_orgao),
            UNIQUE KEY uq_orgao_cnpj_nova (cnpj_orgao)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE dim_fornecedor_nova (
            sk_fornecedor INT NOT NULL,
            ni_fornecedor VARCHAR(20) NOT NULL,
            nome_fornecedor VARCHAR(255) NOT NULL,
            tipo_pessoa VARCHAR(50) NOT NULL,
            porte VARCHAR(50) NOT NULL,
            PRIMARY KEY (sk_fornecedor),
            UNIQUE KEY uq_fornecedor_ni_nova (ni_fornecedor)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE dim_modalidade_nova (
            sk_modalidade INT NOT NULL,
            modalidade_id INT NOT NULL,
            nome_modalidade VARCHAR(100) NOT NULL,
            PRIMARY KEY (sk_modalidade),
            UNIQUE KEY uq_modalidade_id_nova (modalidade_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE dim_localidade_nova (
            sk_localidade INT NOT NULL,
            uf_sigla CHAR(2) NOT NULL,
            uf_nome VARCHAR(50) NOT NULL,
            regiao VARCHAR(50) NOT NULL,
            PRIMARY KEY (sk_localidade),
            UNIQUE KEY uq_localidade_uf_nova (uf_sigla)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE fato_item_contratado_nova (
            sk_item BIGINT NOT NULL AUTO_INCREMENT,
            numero_controle_pncp VARCHAR(80) NOT NULL,
            numero_item INT NOT NULL,
            sk_orgao INT NOT NULL,
            sk_fornecedor INT NOT NULL,
            sk_modalidade INT NOT NULL,
            sk_localidade INT NOT NULL,
            cod_ibge VARCHAR(10) NULL,
            municipio VARCHAR(150) NOT NULL,
            data_publicacao DATE NULL,
            data_homologacao DATE NULL,
            descricao_item TEXT,
            perfil_gasto VARCHAR(100) NOT NULL,
            quantidade DECIMAL(18,4) NOT NULL,
            valor_unitario_estimado DECIMAL(18,4) NOT NULL,
            valor_unitario_homologado DECIMAL(18,4) NOT NULL,
            valor_total_estimado DECIMAL(18,2) NOT NULL,
            valor_total_homologado DECIMAL(18,2) NOT NULL,
            comparavel TINYINT(1) NOT NULL,
            economia_valor DECIMAL(18,2) NOT NULL,
            dias_ciclo INT NOT NULL,
            PRIMARY KEY (sk_item),
            UNIQUE KEY uq_fato_pncp_item_nova (numero_controle_pncp, numero_item),
            KEY ix_fato_orgao_nova (sk_orgao),
            KEY ix_fato_fornecedor_nova (sk_fornecedor),
            KEY ix_fato_modalidade_nova (sk_modalidade),
            KEY ix_fato_localidade_nova (sk_localidade),
            KEY ix_fato_data_publicacao_nova (data_publicacao),
            KEY ix_fato_data_homologacao_nova (data_homologacao),
            CONSTRAINT fk_fato_orgao_nova FOREIGN KEY (sk_orgao)
                REFERENCES dim_orgao_nova(sk_orgao),
            CONSTRAINT fk_fato_fornecedor_nova FOREIGN KEY (sk_fornecedor)
                REFERENCES dim_fornecedor_nova(sk_fornecedor),
            CONSTRAINT fk_fato_modalidade_nova FOREIGN KEY (sk_modalidade)
                REFERENCES dim_modalidade_nova(sk_modalidade),
            CONSTRAINT fk_fato_localidade_nova FOREIGN KEY (sk_localidade)
                REFERENCES dim_localidade_nova(sk_localidade)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]

    # SKs determinísticas para facilitar auditoria e reexecução controlada.
    orgao_rows = [{"sk_orgao": -1, "cnpj_orgao": "00000000000000",
                   "nome_orgao": "Não informado", "poder": "Não informado"}]
    for sk, (cnpj, nome) in enumerate(
        sorted((k, v) for k, v in orgaos.items() if k != "00000000000000"), start=1
    ):
        orgao_map[cnpj] = sk
        orgao_rows.append({"sk_orgao": sk, "cnpj_orgao": cnpj[:14],
                           "nome_orgao": nome[:255], "poder": "Não informado"})
    orgao_map["00000000000000"] = -1

    fornecedor_rows = [{"sk_fornecedor": -1, "ni_fornecedor": "00000000000000",
                        "nome_fornecedor": "Não informado",
                        "tipo_pessoa": "Não informado", "porte": "Não informado"}]
    for sk, (ni, nome) in enumerate(
        sorted((k, v) for k, v in fornecedores.items() if k != "00000000000000"), start=1
    ):
        fornecedor_map[ni] = sk
        fornecedor_rows.append({"sk_fornecedor": sk, "ni_fornecedor": ni[:20],
                                "nome_fornecedor": nome[:255],
                                "tipo_pessoa": "Não informado", "porte": "Não informado"})
    fornecedor_map["00000000000000"] = -1

    modalidade_rows = [{"sk_modalidade": -1, "modalidade_id": -1,
                        "nome_modalidade": "Não informado"}]
    for sk, (mid, nome) in enumerate(
        sorted((k, v) for k, v in modalidades.items() if k != -1), start=1
    ):
        modalidade_map[mid] = sk
        modalidade_rows.append({"sk_modalidade": sk, "modalidade_id": mid,
                                "nome_modalidade": nome[:100]})
    modalidade_map[-1] = -1

    localidade_rows = [{"sk_localidade": -1, "uf_sigla": "EX",
                        "uf_nome": "Não informado", "regiao": "Não informado"}]
    for sk, (uf, info) in enumerate(
        sorted((k, v) for k, v in localidades.items() if k != "EX"), start=1
    ):
        uf_nome, regiao = info
        localidade_map[uf] = sk
        localidade_rows.append({"sk_localidade": sk, "uf_sigla": uf,
                                "uf_nome": uf_nome, "regiao": regiao})
    localidade_map["EX"] = -1

    fato_rows = []
    for row in df.to_dict("records"):
        cnpj = clean_identifier(row["cnpj_orgao"], "00000000000000")
        ni = clean_identifier(row["ni_fornecedor"], "00000000000000")
        mid = as_int(row["modalidade_id"], -1)
        uf = clean_text(row["uf_sigla"], "EX").upper()[:2]
        if uf not in UF_INFO:
            uf = "EX"

        cod_ibge = clean_text(row["cod_ibge"], "")
        fato_rows.append({
            "numero_controle_pncp": row["numero_controle_pncp"],
            "numero_item": int(row["numero_item"]),
            "sk_orgao": orgao_map.get(cnpj, -1),
            "sk_fornecedor": fornecedor_map.get(ni, -1),
            "sk_modalidade": modalidade_map.get(mid, -1),
            "sk_localidade": localidade_map.get(uf, -1),
            "cod_ibge": cod_ibge[:10] if cod_ibge else None,
            "municipio": clean_text(row["municipio"]),
            "data_publicacao": as_date(row["data_publicacao"]),
            "data_homologacao": as_date(row["data_homologacao"]),
            "descricao_item": clean_text(row["descricao_item"], ""),
            "perfil_gasto": clean_text(row["perfil_gasto"]),
            "quantidade": as_decimal(row["quantidade"], 4),
            "valor_unitario_estimado": as_decimal(row["valor_unitario_estimado"], 4),
            "valor_unitario_homologado": as_decimal(row["valor_unitario_homologado"], 4),
            "valor_total_estimado": as_decimal(row["valor_total_estimado"], 2),
            "valor_total_homologado": as_decimal(row["valor_total_homologado"], 2),
            "comparavel": 1 if as_int(row["comparavel"], 0) == 1 else 0,
            "economia_valor": as_decimal(row["economia_valor"], 2),
            "dias_ciclo": as_int(row["dias_ciclo"], 0),
        })

    insert_statements = {
        "dim_orgao_nova": (
            "INSERT INTO dim_orgao_nova "
            "(sk_orgao, cnpj_orgao, nome_orgao, poder) "
            "VALUES (:sk_orgao, :cnpj_orgao, :nome_orgao, :poder)"
        ),
        "dim_fornecedor_nova": (
            "INSERT INTO dim_fornecedor_nova "
            "(sk_fornecedor, ni_fornecedor, nome_fornecedor, tipo_pessoa, porte) "
            "VALUES (:sk_fornecedor, :ni_fornecedor, :nome_fornecedor, :tipo_pessoa, :porte)"
        ),
        "dim_modalidade_nova": (
            "INSERT INTO dim_modalidade_nova "
            "(sk_modalidade, modalidade_id, nome_modalidade) "
            "VALUES (:sk_modalidade, :modalidade_id, :nome_modalidade)"
        ),
        "dim_localidade_nova": (
            "INSERT INTO dim_localidade_nova "
            "(sk_localidade, uf_sigla, uf_nome, regiao) "
            "VALUES (:sk_localidade, :uf_sigla, :uf_nome, :regiao)"
        ),
        "fato_item_contratado_nova": (
            "INSERT INTO fato_item_contratado_nova "
            "(numero_controle_pncp, numero_item, sk_orgao, sk_fornecedor, "
            "sk_modalidade, sk_localidade, cod_ibge, municipio, data_publicacao, "
            "data_homologacao, descricao_item, perfil_gasto, quantidade, "
            "valor_unitario_estimado, valor_unitario_homologado, valor_total_estimado, "
            "valor_total_homologado, comparavel, economia_valor, dias_ciclo) "
            "VALUES (:numero_controle_pncp, :numero_item, :sk_orgao, :sk_fornecedor, "
            ":sk_modalidade, :sk_localidade, :cod_ibge, :municipio, :data_publicacao, "
            ":data_homologacao, :descricao_item, :perfil_gasto, :quantidade, "
            ":valor_unitario_estimado, :valor_unitario_homologado, :valor_total_estimado, "
            ":valor_total_homologado, :comparavel, :economia_valor, :dias_ciclo)"
        ),
    }

    print("Criando tabelas _nova...")
    try:
        with engine.begin() as conn:
            for statement in ddl:
                conn.execute(text(statement))

            conn.execute(text(insert_statements["dim_orgao_nova"]), orgao_rows)
            conn.execute(text(insert_statements["dim_fornecedor_nova"]), fornecedor_rows)
            conn.execute(text(insert_statements["dim_modalidade_nova"]), modalidade_rows)
            conn.execute(text(insert_statements["dim_localidade_nova"]), localidade_rows)

            batch_size = 500
            fato_sql = text(insert_statements["fato_item_contratado_nova"])
            for start in range(0, len(fato_rows), batch_size):
                conn.execute(fato_sql, fato_rows[start:start + batch_size])

        print("Carga concluída. Conferindo contagens e integridade...")
        with engine.connect() as conn:
            counts = {}
            for table_name in TABLES:
                counts[table_name] = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table_name}`")
                ).scalar_one()

            fk_orphans = conn.execute(text("""
                SELECT
                    SUM(o.sk_orgao IS NULL) AS orgao_orfao,
                    SUM(f.sk_fornecedor IS NULL) AS fornecedor_orfao,
                    SUM(m.sk_modalidade IS NULL) AS modalidade_orfao,
                    SUM(l.sk_localidade IS NULL) AS localidade_orfao
                FROM fato_item_contratado_nova fato
                LEFT JOIN dim_orgao_nova o ON fato.sk_orgao = o.sk_orgao
                LEFT JOIN dim_fornecedor_nova f ON fato.sk_fornecedor = f.sk_fornecedor
                LEFT JOIN dim_modalidade_nova m ON fato.sk_modalidade = m.sk_modalidade
                LEFT JOIN dim_localidade_nova l ON fato.sk_localidade = l.sk_localidade
            """)).mappings().one()

        print("\n=== RESULTADO DA CARGA ===")
        for table_name, count in counts.items():
            print(f"{table_name}: {count:,}")
        print("Órfãos nas chaves das dimensões:", dict(fk_orphans))

        if counts["fato_item_contratado_nova"] != len(df):
            raise RuntimeError("A contagem da FATO nova diverge da quantidade do Gold.")
        if any(int(value or 0) != 0 for value in fk_orphans.values()):
            raise RuntimeError("Foram encontradas chaves estrangeiras sem correspondência.")

        print("\nVALIDAÇÃO BÁSICA APROVADA.")
        print("As tabelas originais não foram alteradas.")
        print("Não faça migração/cutover antes de revisar os resultados.")

    except Exception:
        print(
            "\nATENÇÃO: houve erro durante a criação/carga. "
            "As tabelas originais continuam preservadas. "
            "Tabelas _nova eventualmente criadas foram mantidas para inspeção; "
            "não as apague nem execute novamente antes de revisar o erro."
        )
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERRO: {exc}")
        sys.exit(1)
