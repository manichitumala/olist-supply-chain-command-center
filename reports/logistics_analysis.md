# Logistics / Geospatial Analysis

Correlations against Haversine seller-customer distance (zip-prefix centroids), delivered orders:

| pair                      |     n |   pearson_r |   spearman_rho |
|:--------------------------|------:|------------:|---------------:|
| distance_vs_delivery_time | 95097 |       0.393 |          0.543 |
| distance_vs_freight_cost  | 95097 |       0.315 |          0.584 |
| distance_vs_review_score  | 94458 |      -0.059 |         -0.064 |

## Late rate by distance band

| distance_band   |   n_orders |   avg_distance_km |   avg_lead_time_days |   avg_freight_value |   n_late |   late_pct |
|:----------------|-----------:|------------------:|---------------------:|--------------------:|---------:|-----------:|
| 0-100 km        |      17863 |                40 |                 6.54 |               13.36 |      799 |       4.47 |
| 100-300 km      |      13445 |               201 |                10.02 |               18.83 |      697 |       5.18 |
| 300-500 km      |      23743 |               392 |                12.45 |               22.3  |     1577 |       6.64 |
| 500-1000 km     |      26004 |               712 |                14.38 |               24.16 |     1851 |       7.12 |
| 1000+ km        |      15415 |              1736 |                19.21 |               35.57 |     1610 |      10.44 |

See `reports/charts/distance_vs_delivery_scatter.png`.
