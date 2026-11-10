USE pncp_controladoria;

-- Limpeza e Consulta Top 5 Fornecedores
SELECT 
    f.razao_social,
    COUNT(fit.sk_item) AS qtd_itens,
    SUM(fit.valor_total_homologado) AS valor_total_homologado
FROM fato_item_contratado fit
JOIN dim_fornecedor f ON fit.sk_fornecedor = f.sk_fornecedor
GROUP BY f.razao_social
ORDER BY valor_total_homologado DESC
LIMIT 5;

USE pncp_controladoria;

DESCRIBE dim_fornecedor;


