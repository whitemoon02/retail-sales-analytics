-- Requêtes KPI exécutées par src/pipeline.py (SQLite).
-- Chaque bloc commence par une ligne de nommage (voir ci-dessous).

-- name:global_kpis
SELECT
    ROUND(SUM(revenue), 0)                                   AS chiffre_affaires,
    ROUND(SUM(margin), 0)                                    AS marge_brute,
    ROUND(100.0 * SUM(margin) / SUM(revenue), 1)             AS taux_marge_pct,
    COUNT(DISTINCT order_id)                                 AS nb_commandes,
    COUNT(DISTINCT customer_id)                              AS nb_clients,
    ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)        AS panier_moyen
FROM fact_sales;

-- name:monthly_revenue
SELECT d.year || '-' || printf('%02d', d.month) AS month,
       ROUND(SUM(f.revenue), 0)                 AS revenue,
       COUNT(DISTINCT f.order_id)               AS orders
FROM fact_sales f JOIN dim_date d USING (date_key)
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- name:yoy_growth
WITH y AS (
    SELECT d.month, d.year, SUM(f.revenue) AS revenue
    FROM fact_sales f JOIN dim_date d USING (date_key)
    GROUP BY d.year, d.month
)
SELECT cur.month,
       ROUND(cur.revenue, 0) AS revenue_2025,
       ROUND(prev.revenue, 0) AS revenue_2024,
       ROUND(100.0 * (cur.revenue - prev.revenue) / prev.revenue, 1) AS growth_pct
FROM y cur JOIN y prev ON cur.month = prev.month AND cur.year = prev.year + 1
ORDER BY cur.month;

-- name:category_performance
SELECT p.category,
       ROUND(SUM(f.revenue), 0) AS revenue,
       ROUND(100.0 * SUM(f.margin) / SUM(f.revenue), 1) AS margin_pct,
       SUM(f.quantity) AS units
FROM fact_sales f JOIN dim_product p USING (product_id)
GROUP BY p.category
ORDER BY revenue DESC;

-- name:store_ranking
SELECT s.store_name, s.region,
       ROUND(SUM(f.revenue), 0) AS revenue,
       ROUND(SUM(f.revenue) / s.surface_m2, 1) AS revenue_per_m2,
       RANK() OVER (ORDER BY SUM(f.revenue) DESC) AS rank
FROM fact_sales f JOIN dim_store s USING (store_id)
GROUP BY s.store_id
ORDER BY rank;

-- name:channel_mix
SELECT channel,
       ROUND(SUM(revenue), 0) AS revenue,
       ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM fact_sales), 1) AS share_pct
FROM fact_sales
GROUP BY channel
ORDER BY revenue DESC;
