USE pncp_controladoria;

SELECT 'dim_orgao' AS tabela, COUNT(*) AS total FROM dim_orgao
UNION ALL
SELECT 'dim_fornecedor', COUNT(*) FROM dim_fornecedor
UNION ALL
SELECT 'dim_modalidade', COUNT(*) FROM dim_modalidade
UNION ALL
SELECT 'dim_localidade', COUNT(*) FROM dim_localidade;


USE pncp_controladoria;

-- Visualizar os primeiros órgãos e fornecedores
SELECT * FROM dim_orgao LIMIT 5;
SELECT * FROM dim_fornecedor LIMIT 5;



SELECT 
    COUNT(*) AS total_linhas, 
    SUM(valor_total_homologado) AS valor_total_homologado 
FROM fato_item_contratado;

USE pncp_controladoria;
DELETE FROM fato_item_contratado;

USE pncp_controladoria;

SELECT 
    COUNT(*) AS total_linhas, 
    SUM(valor_total_homologado) AS valor_total_homologado 
FROM fato_item_contratado;

USE pncp_controladoria;
SELECT COUNT(*) FROM fato_item_contratado;


USE pncp_controladoria;
TRUNCATE TABLE fato_item_contratado;

USE pncp_controladoria;
SELECT COUNT(*) AS total_linhas, SUM(valor_total_homologado) AS valor_total FROM fato_item_contratado;

USE pncp_controladoria;

SELECT 
    COUNT(*) AS total_linhas, 
    FORMAT(SUM(valor_total_homologado), 2) AS valor_total_homologado 
FROM fato_item_contratado;