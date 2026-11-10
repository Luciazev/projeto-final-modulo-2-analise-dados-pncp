
import os
import re
import shutil
import unicodedata
from datetime import datetime

import pandas as pd


SILVER_DIR = "Data/silver"
GOLD_DIR = "Data/gold"

ARQUIVO_FATO = os.path.join(
    GOLD_DIR, "fato_itens_homologados.csv"
)

ARQUIVO_REJEITADOS = os.path.join(
    GOLD_DIR, "itens_rejeitados.csv"
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def converter_numero(valor):
    if pd.isna(valor):
        return float("nan")

    texto = str(valor).strip()

    if texto.lower() in ("", "nan", "none", "null"):
        return float("nan")

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")

    elif "," in texto:
        texto = texto.replace(",", ".")

    elif texto.count(".") > 1:
        partes = texto.split(".")
        texto = "".join(partes[:-1]) + "." + partes[-1]

    try:
        return float(texto)
    except (ValueError, TypeError):
        return float("nan")


def converter_data(serie):
    formatos = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%Y/%m/%d",
        "%Y%m%d",
        "%d.%m.%Y",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S"
    ]

    def converter(valor):
        if pd.isna(valor):
            return pd.NaT

        texto = str(valor).strip()

        if not texto:
            return pd.NaT

        for formato in formatos:
            try:
                data = pd.to_datetime(
                    texto,
                    format=formato
                )

                # Remove fuso horário, preservando
                # a data e a hora informadas no arquivo.
                if data.tzinfo is not None:
                    data = data.tz_localize(None)

                return data

            except (ValueError, TypeError):
                continue

        return pd.NaT

    return pd.to_datetime(
        serie.apply(converter),
        errors="coerce"
    )


def texto_normalizado(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)

    return "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )


def verdadeiro(valor):
    return texto_normalizado(valor) in (
        "true", "1", "sim", "s", "yes", "verdadeiro"
    )


def registrar_rejeicao(df, condicao, motivo):
    mascara = (
        condicao &
        (df["motivo_rejeicao"] == "")
    )

    df.loc[mascara, "motivo_rejeicao"] = motivo


# ============================================================
# PROCESSAMENTO GOLD
# ============================================================

def processar_camada_gold():

    print("\n======================================")
    print(" PROCESSAMENTO DA CAMADA GOLD")
    print("======================================")

    os.makedirs(GOLD_DIR, exist_ok=True)

    arquivos = {
        "compras": os.path.join(SILVER_DIR, "compras.csv"),
        "itens": os.path.join(SILVER_DIR, "itens.csv"),
        "resultados": os.path.join(SILVER_DIR, "resultados.csv")
    }

    for nome, caminho in arquivos.items():
        if not os.path.exists(caminho):
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho}"
            )

    # --------------------------------------------------------
    # 1. LEITURA
    # --------------------------------------------------------

    print("\n1. Lendo arquivos Silver...")

    compras = pd.read_csv(
        arquivos["compras"],
        dtype=str,
        low_memory=False
    )

    itens = pd.read_csv(
        arquivos["itens"],
        dtype=str,
        low_memory=False
    )

    resultados = pd.read_csv(
        arquivos["resultados"],
        dtype=str,
        low_memory=False
    )

    print("Compras:", len(compras))
    print("Itens:", len(itens))
    print("Resultados:", len(resultados))

    # --------------------------------------------------------
    # 2. PADRONIZAR CHAVES
    # --------------------------------------------------------

    print("\n2. Preparando chaves PNCP...")

    for df in (compras, itens, resultados):
        df["numero_controle_pncp"] = (
            df["numero_controle_pncp"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    itens["numero_item"] = (
        itens["numero_item"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    resultados["numero_item"] = (
        resultados["numero_item"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    compras = compras[
        compras["numero_controle_pncp"] != ""
    ].copy()

    itens = itens[
        (itens["numero_controle_pncp"] != "") &
        (itens["numero_item"] != "")
    ].copy()

    resultados = resultados[
        (resultados["numero_controle_pncp"] != "") &
        (resultados["numero_item"] != "")
    ].copy()

    duplicados_itens = itens.duplicated(
        ["numero_controle_pncp", "numero_item"]
    ).sum()

    if duplicados_itens:
        raise ValueError(
            f"Existem {duplicados_itens} itens duplicados "
            "na Silver. Fato não será gerada."
        )

    duplicados_compras = compras.duplicated(
        ["numero_controle_pncp"]
    ).sum()

    if duplicados_compras:
        raise ValueError(
            f"Existem {duplicados_compras} compras duplicadas "
            "na Silver. Verifique antes do processamento."
        )

    # --------------------------------------------------------
    # 3. REMOVER RESULTADOS CANCELADOS
    # --------------------------------------------------------

    print("\n3. Removendo resultados cancelados...")

    cancelamento = (
        resultados["data_cancelamento"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    cancelados = cancelamento != ""

    total_cancelados = int(cancelados.sum())

    resultados = resultados[~cancelados].copy()

    print("Resultados cancelados:", total_cancelados)

    # --------------------------------------------------------
    # 4. SELECIONAR VENCEDORES
    # --------------------------------------------------------

    print("\n4. Selecionando vencedores...")

    resultados["_ordem"] = pd.to_numeric(
        resultados["ordem_classificacao_srp"],
        errors="coerce"
    ).fillna(1)

    resultados["_sequencial"] = pd.to_numeric(
        resultados["sequencial_resultado"],
        errors="coerce"
    ).fillna(float("inf"))

    resultados = resultados.sort_values(
        by=[
            "numero_controle_pncp",
            "numero_item",
            "_ordem",
            "_sequencial"
        ],
        ascending=True
    )

    vencedores = resultados.drop_duplicates(
        subset=[
            "numero_controle_pncp",
            "numero_item"
        ],
        keep="first"
    ).copy()

    print("Vencedores selecionados:", len(vencedores))

    # --------------------------------------------------------
    # 5. CRUZAR ITENS E RESULTADOS
    # --------------------------------------------------------

    print("\n5. Cruzando itens e resultados...")

    fato = pd.merge(
        itens,
        vencedores,
        on=[
            "numero_controle_pncp",
            "numero_item"
        ],
        how="inner",
        validate="one_to_one",
        suffixes=("_item", "_resultado")
    )

    print("Itens com resultado:", len(fato))

    # --------------------------------------------------------
    # 6. INCORPORAR COMPRAS
    # --------------------------------------------------------

    print("\n6. Incorporando dados das compras...")

    fato = pd.merge(
        fato,
        compras,
        on="numero_controle_pncp",
        how="left",
        validate="many_to_one",
        suffixes=("", "_compra")
    )

    # --------------------------------------------------------
    # 7. CONVERTER VALORES
    # --------------------------------------------------------

    print("\n7. Convertendo valores numéricos...")

    colunas_numericas = [
        "quantidade",
        "quantidade_homologada",
        "valor_unitario_estimado",
        "valor_unitario_homologado",
        "valor_total_estimado",
        "valor_total_homologado"
    ]

    for coluna in colunas_numericas:
        fato[coluna] = fato[coluna].map(converter_numero)

    # Usa quantidade homologada quando positiva.
    fato["quantidade_final"] = fato[
        "quantidade_homologada"
    ].where(
        fato["quantidade_homologada"].notna() &
        (fato["quantidade_homologada"] > 0),
        fato["quantidade"]
    )

    # Total = valor unitário x quantidade.
    fato["valor_total_estimado_calculado"] = (
        fato["valor_unitario_estimado"] *
        fato["quantidade_final"]
    )

    fato["valor_total_homologado_calculado"] = (
        fato["valor_unitario_homologado"] *
        fato["quantidade_final"]
    )

    # --------------------------------------------------------
    # 8. REJEIÇÕES
    # --------------------------------------------------------

    print("\n8. Aplicando regras de rejeição...")

    fato["motivo_rejeicao"] = ""

    registrar_rejeicao(
        fato,
        fato["quantidade_final"].isna() |
        (fato["quantidade_final"] <= 0),
        "Quantidade inválida"
    )

    registrar_rejeicao(
        fato,
        fato["valor_unitario_estimado"].isna() |
        (fato["valor_unitario_estimado"] <= 0),
        "Valor estimado inválido"
    )

    registrar_rejeicao(
        fato,
        fato["valor_unitario_homologado"].isna() |
        (fato["valor_unitario_homologado"] <= 0),
        "Valor homologado inválido"
    )

    fato["_sigiloso"] = fato["sigiloso"].map(verdadeiro)

    registrar_rejeicao(
        fato,
        fato["_sigiloso"],
        "Orçamento sigiloso"
    )

    razao = (
        fato["valor_total_homologado_calculado"] /
        fato["valor_total_estimado_calculado"].replace(
            0, float("nan")
        )
    )

    registrar_rejeicao(
        fato,
        razao > 1000,
        "Valor homologado superior a 1000 vezes o estimado"
    )

    registrar_rejeicao(
        fato,
        (
            fato["valor_total_estimado_calculado"] >
            1_000_000_000_000
        ) |
        (
            fato["valor_total_homologado_calculado"] >
            1_000_000_000_000
        ),
        "Valor total superior a R$ 1 trilhão"
    )

    rejeitados = fato[
        fato["motivo_rejeicao"] != ""
    ].copy()

    fato = fato[
        fato["motivo_rejeicao"] == ""
    ].copy()

    print("Itens rejeitados:", len(rejeitados))

    # --------------------------------------------------------
    # 9. PERFIL DE GASTO
    # --------------------------------------------------------

    print("\n9. Classificando perfil de gasto...")

    def classificar_perfil(linha):

        descricao = texto_normalizado(
            linha["descricao"]
        )

        objeto = texto_normalizado(
            linha["objeto_compra"]
        )

        texto = descricao + " " + objeto

        if re.search(
            r"\b(obra|obras|construcao|construcoes|reforma|reformas|engenharia)\b",
            texto
        ):
            return "Obras/Engenharia"

        tipo = texto_normalizado(
            linha["material_ou_servico"]
        )

        if "material" in tipo or "bem" in tipo:
            return "Bens"

        if "servico" in tipo:
            return "Serviços"

        return "Não classificado"

    fato["perfil_gasto"] = fato.apply(
        classificar_perfil,
        axis=1
    )

    # --------------------------------------------------------
    # 10. COMPARABILIDADE E ECONOMIA
    # --------------------------------------------------------

    print("\n10. Calculando comparabilidade...")

    modalidade = pd.to_numeric(
        fato["modalidade_id"],
        errors="coerce"
    )

    razao = (
        fato["valor_total_homologado_calculado"] /
        fato["valor_total_estimado_calculado"].replace(
            0, float("nan")
        )
    )

    fato["comparavel"] = (
        modalidade.notna() &
        (modalidade != 12) &
        razao.between(0.1, 10, inclusive="both")
    ).astype(int)

    fato["economia_valor"] = pd.NA

    mascara = fato["comparavel"] == 1

    fato.loc[mascara, "economia_valor"] = (
        fato.loc[mascara, "valor_total_estimado_calculado"] -
        fato.loc[mascara, "valor_total_homologado_calculado"]
    )

    # --------------------------------------------------------
    # 11. CICLO DA COMPRA
    # --------------------------------------------------------

    print("\n11. Calculando ciclo da compra...")

    fato["data_publicacao"] = converter_data(
        fato["data_publicacao"]
    )

    fato["data_homologacao"] = converter_data(
        fato["data_resultado"]
    )

    # Homologação anterior à publicação é inválida.
    # A comparação considera somente o dia.
    data_invalida = (
        fato["data_publicacao"].notna() &
        fato["data_homologacao"].notna() &
        (
            fato["data_homologacao"].dt.normalize() <
            fato["data_publicacao"].dt.normalize()
        )
    )

    fato.loc[
        data_invalida,
        "data_homologacao"
    ] = pd.NaT

    # Calcula o ciclo ignorando os horários.
    ciclo_valido = (
        fato["data_publicacao"].notna() &
        fato["data_homologacao"].notna()
    )

    fato["dias_ciclo"] = pd.Series(
        pd.NA,
        index=fato.index,
        dtype="Int64"
    )

    fato.loc[ciclo_valido, "dias_ciclo"] = (
        fato.loc[
            ciclo_valido, "data_homologacao"
        ].dt.normalize() -
        fato.loc[
            ciclo_valido, "data_publicacao"
        ].dt.normalize()
    ).dt.days

    # --------------------------------------------------------
    # 12. MONTAR FATO FINAL
    # --------------------------------------------------------

    print("\n12. Montando tabela Fato...")

    fato["numero_item"] = pd.to_numeric(
        fato["numero_item"],
        errors="coerce"
    )

    if fato["numero_item"].isna().any():
        raise ValueError(
            "Existem números de item inválidos."
        )

    fato["numero_item"] = fato["numero_item"].astype(int)

    fato_final = pd.DataFrame({

        "numero_controle_pncp":
            fato["numero_controle_pncp"],

        "numero_item":
            fato["numero_item"],

        "cnpj_orgao":
            fato["cnpj_orgao"],

        "razao_social_orgao":
            fato["razao_social_orgao"],

        "ni_fornecedor":
            fato["ni_fornecedor"],

        "nome_fornecedor":
            fato["nome_fornecedor"],

        "modalidade_id":
            fato["modalidade_id"],

        "modalidade_nome":
            fato["modalidade_nome"],

        "cod_ibge":
            fato["cod_ibge"],

        "uf_sigla":
            fato["uf_sigla"],

        "municipio":
            fato["municipio"],

        "data_publicacao":
            fato["data_publicacao"].dt.strftime("%Y-%m-%d"),

        "data_homologacao":
            fato["data_homologacao"].dt.strftime("%Y-%m-%d"),

        "descricao_item":
            fato["descricao"],

        "perfil_gasto":
            fato["perfil_gasto"],

        "quantidade":
            fato["quantidade_final"],

        "valor_unitario_estimado":
            fato["valor_unitario_estimado"],

        "valor_unitario_homologado":
            fato["valor_unitario_homologado"],

        "valor_total_estimado":
            fato["valor_total_estimado_calculado"],

        "valor_total_homologado":
            fato["valor_total_homologado_calculado"],

        "comparavel":
            fato["comparavel"],

        "economia_valor":
            fato["economia_valor"],

        "dias_ciclo":
            fato["dias_ciclo"]
    })

    duplicados = fato_final.duplicated(
        ["numero_controle_pncp", "numero_item"]
    ).sum()

    if duplicados:
        raise ValueError(
            f"Foram encontrados {duplicados} registros duplicados "
            "na Fato. Arquivo não será salvo."
        )

    # --------------------------------------------------------
    # 13. AUDITORIA
    # --------------------------------------------------------

    print("\n======================================")
    print(" AUDITORIA GOLD")
    print("======================================")

    volume = fato_final["valor_total_homologado"].sum()

    comparaveis = fato_final[
        fato_final["comparavel"] == 1
    ]

    estimado_comp = comparaveis[
        "valor_total_estimado"
    ].sum()

    homologado_comp = comparaveis[
        "valor_total_homologado"
    ].sum()

    economia = estimado_comp - homologado_comp

    percentual = (
        economia / estimado_comp * 100
        if estimado_comp > 0 else 0
    )

    ciclos = fato_final["dias_ciclo"].dropna()

    print("Itens na Fato:", len(fato_final))
    print("Itens rejeitados:", len(rejeitados))

    print(f"Volume homologado: R$ {volume:,.2f}")
    print(f"Estimado comparável: R$ {estimado_comp:,.2f}")
    print(f"Economia comparável: R$ {economia:,.2f}")
    print(f"Economia percentual: {percentual:.2f}%")
    print("Itens comparáveis:", len(comparaveis))

    sobrepreco = (
        comparaveis["valor_total_homologado"] >
        comparaveis["valor_total_estimado"]
    ).sum()

    print("Itens com sobrepreço:", int(sobrepreco))
    print("Ciclos válidos:", len(ciclos))

    if len(ciclos):
        print(f"Ciclo médio: {ciclos.mean():.1f} dias")
        print(f"Ciclo máximo: {ciclos.max():.0f} dias")

    print(
        "Itens sem ciclo:",
        int(fato_final["dias_ciclo"].isna().sum())
    )

    print("\nPerfil de gasto:")
    print(fato_final["perfil_gasto"].value_counts().to_string())

    # --------------------------------------------------------
    # 14. SALVAR COM BACKUP
    # --------------------------------------------------------

    print("\n14. Salvando arquivos...")

    temporario = ARQUIVO_FATO + ".tmp"

    fato_final.to_csv(
        temporario,
        index=False,
        encoding="utf-8"
    )

    if os.path.exists(ARQUIVO_FATO):

        horario = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup = ARQUIVO_FATO + f".backup_{horario}"

        shutil.copy2(
            ARQUIVO_FATO,
            backup
        )

        print("Backup anterior criado:", backup)

    os.replace(
        temporario,
        ARQUIVO_FATO
    )

    rejeitados.to_csv(
        ARQUIVO_REJEITADOS,
        index=False,
        encoding="utf-8"
    )

    print("\nFato salva:", ARQUIVO_FATO)
    print("Rejeitados salvos:", ARQUIVO_REJEITADOS)
    print("Colunas da Fato:", len(fato_final.columns))
    print("Linhas da Fato:", len(fato_final))

    print("\nCAMADA GOLD FINALIZADA.")


if __name__ == "__main__":
    processar_camada_gold()
