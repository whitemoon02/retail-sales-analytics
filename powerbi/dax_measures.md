# Mesures DAX — modèle Power BI

Importer `data/processed/fact_sales.csv`, `dim_date.csv` et les tables `dim_*` de `retail.db`
(ou via ODBC SQLite), puis créer les relations :

| Table de faits | Colonne | Dimension | Colonne |
|---|---|---|---|
| fact_sales | date_key | dim_date | date_key |
| fact_sales | product_id | dim_product | product_id |
| fact_sales | store_id | dim_store | store_id |
| fact_sales | customer_id | dim_customer | customer_id |

Marquer `dim_date` comme table de dates.

```dax
CA = SUM ( fact_sales[revenue] )

Marge = SUM ( fact_sales[margin] )

Taux de marge % = DIVIDE ( [Marge], [CA] )

Nb commandes = DISTINCTCOUNT ( fact_sales[order_id] )

Panier moyen = DIVIDE ( [CA], [Nb commandes] )

CA N-1 = CALCULATE ( [CA], SAMEPERIODLASTYEAR ( dim_date[date] ) )

Croissance YoY % = DIVIDE ( [CA] - [CA N-1], [CA N-1] )

CA cumul annuel = TOTALYTD ( [CA], dim_date[date] )

CA moyenne mobile 3 mois =
AVERAGEX (
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH ),
    [CA]
)

Part du CA % =
DIVIDE ( [CA], CALCULATE ( [CA], ALL ( dim_product[category] ) ) )

Rang magasin =
RANKX ( ALL ( dim_store[store_name] ), [CA], , DESC )

Clients actifs = DISTINCTCOUNT ( fact_sales[customer_id] )
```

## Pages du rapport proposées

1. **Synthèse** : cartes CA, marge, panier moyen, croissance YoY ; courbe CA mensuel N vs N-1.
2. **Produits** : CA et taux de marge par catégorie, top 10 produits, matrice catégorie × mois.
3. **Magasins** : carte par région, classement CA/m², mix canaux.
4. **Clients** : segments RFM (import `rfm_segments.csv`), répartition fidélité.
