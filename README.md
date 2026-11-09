# Análise de Dados com Python – MySQL

## 1. Sobre o projeto

Projeto desenvolvido na Situação de Aprendizagem do Módulo 2 – Semana 13, com foco na análise de dados de contratações públicas do Portal Nacional de Contratações Públicas (PNCP).

O objetivo é transformar dados públicos em informações úteis para apoiar o acompanhamento e a tomada de decisão pela Controladoria.

## 2. Objetivos

- Realizar tratamento e limpeza dos dados com Python.
- Organizar os dados em camadas Silver e Gold.
- Modelar os dados em um esquema estrela no MySQL.
- Desenvolver análises e indicadores no Power BI.
- Responder às questões de negócio propostas no projeto.

## 3. Arquitetura do projeto

O fluxo de processamento segue estas etapas:

1. Dados de origem: arquivos CSV do PNCP.
2. Camada Silver: tratamento e padronização dos dados com Python.
3. Camada Gold: preparação dos dados para análise.
4. MySQL: armazenamento em modelo dimensional, com tabela fato e dimensões.
5. Power BI: construção de indicadores, gráficos e análises interativas.

## 4. Tecnologias utilizadas

- Python
- MySQL
- SQL
- Power BI
- Git e GitHub

## 5. Modelagem de dados

O banco de dados utiliza um modelo dimensional em esquema estrela, com uma tabela fato de itens contratados relacionada às dimensões utilizadas nas análises.

O modelo permite analisar valores homologados, economia, fornecedores, órgãos, municípios, modalidades e perfil de gasto.

## 6. Análises desenvolvidas no Power BI

O relatório contempla as seguintes questões de negócio:

1. Economia global: valores economizados e percentual de economia.
2. Concentração de fornecedores: participação dos principais fornecedores.
3. Modalidades de contratação: comparação dos valores homologados.
4. Órgãos públicos: análise do prazo médio do ciclo de contratação.
5. Gastos regionais: valores homologados e descontos por município.
6. Perfil de gasto: distribuição entre bens, serviços e obras.

O relatório também utiliza indicadores, filtros interativos e páginas de tooltip para apresentar informações complementares.

## 7. Organização e planejamento

O projeto foi desenvolvido em sprints, contemplando preparação, tratamento de dados, construção das camadas Silver e Gold, modelagem e carga no MySQL e desenvolvimento do relatório no Power BI.

## 8. Evidências do projeto

## 9. Execução

Para reproduzir o projeto, é necessário configurar o ambiente Python, disponibilizar os arquivos de dados do PNCP e configurar a conexão com o MySQL.

Os scripts e arquivos de configuração devem ser utilizados conforme a estrutura disponibilizada neste repositório.

## 10. Vídeo de apresentação

Link do vídeo: **[INSERIR LINK PÚBLICO DO GOOGLE DRIVE]**

## 11. Considerações finais

O projeto demonstra a aplicação de técnicas de engenharia e análise de dados para transformar informações públicas em indicadores que apoiam a transparência, o monitoramento e a tomada de decisão.


**Autor:** [LUCIANA AZEVEDO]  
**Turma:** [T2]  
**Módulo:** 2 – Análise de Dados com Python – MySQL