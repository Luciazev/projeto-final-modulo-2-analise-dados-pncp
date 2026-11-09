USE pncp_controladoria;

SELECT 
    f.nome_fornecedor,
    COUNT(fit.sk_item) AS qtd_itens,
    SUM(fit.valor_total_homologado) AS valor_total_homologado
FROM fato_item_contratado fit
JOIN dim_fornecedor f ON fit.sk_fornecedor = f.sk_fornecedor
GROUP BY f.nome_fornecedor
ORDER BY valor_total_homologado DESC
LIMIT 5;
