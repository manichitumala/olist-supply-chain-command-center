# Seller Performance Scorecard

Scored 1,794 sellers with >= 5 orders using: 30% On-Time Delivery, 25% Fulfilment Speed, 20% Cancellation Rate, 15% Review Score, 10% Freight Efficiency (all min-max normalised 0-100 first; 'lower is better' metrics are inverted before weighting).

## Tier distribution

| performance_tier   |   count |
|:-------------------|--------:|
| Excellent          |    1070 |
| Good               |     661 |
| At Risk            |      48 |
| Critical           |      15 |

## Bottom 10 sellers (highest operational risk)

| seller_id                        | state   | region    |   n_orders |   n_items |   total_revenue |   otd_pct |   avg_fulfilment_days |   cancellation_rate_pct |   avg_review_score |   avg_freight_to_price_pct |   seller_score | performance_tier   |   seller_risk_score |
|:---------------------------------|:--------|:----------|-----------:|----------:|----------------:|----------:|----------------------:|------------------------:|-------------------:|---------------------------:|---------------:|:-------------------|--------------------:|
| 6219ba2359cfb97f2e38fd4c321eb309 | SP      | Southeast |          6 |         6 |          487.5  |     40    |                 18.71 |                    0    |               3.4  |                      24.95 |           53.7 | Critical           |                46.3 |
| 538caafddff204241cecbf3a02e6b3cf | SP      | Southeast |          9 |         9 |          148.3  |     50    |                 12.95 |                   11.11 |               2.56 |                      66.33 |           53   | Critical           |                47   |
| eebb3372362aa9a46975164bed19a7e7 | SP      | Southeast |          7 |         8 |          591.92 |     50    |                  7.91 |                   25    |               2.29 |                      20.17 |           51.7 | Critical           |                48.3 |
| 633ecdf879b94b5337cca303328e4a25 | SP      | Southeast |          6 |         6 |         1037.6  |     33.33 |                 15    |                    0    |               1.8  |                      10.19 |           48.6 | Critical           |                51.4 |
| 312ba1d77e9c332ef21f9598b7f64cd7 | SP      | Southeast |          9 |        10 |          756    |     42.86 |                 10.79 |                   30    |               2.7  |                      18.6  |           45.9 | Critical           |                54.1 |
| b1b3948701c5c72445495bd161b83a4c | SP      | Southeast |         18 |        18 |        24699.2  |     35.71 |                 14.1  |                   11.11 |               1.72 |                       2.73 |           45.3 | Critical           |                54.7 |
| 6cf476a4ca74498db55cbccdaa9dcfb6 | SP      | Southeast |          6 |         7 |          939.93 |     50    |                 22.4  |                   14.29 |               2.71 |                      44.82 |           44.3 | Critical           |                55.7 |
| 44f091b5abab8018f682fce8124b85e5 | SP      | Southeast |          6 |         6 |         1680.1  |     33.33 |                 10.89 |                   33.33 |               2.5  |                      10.64 |           40.2 | Critical           |                59.8 |
| 6ee85be3693ed79a8e80718743d80655 | SP      | Southeast |          9 |        13 |          484.5  |     60    |                 16.92 |                   38.46 |               1.92 |                      38.41 |           39.2 | Critical           |                60.8 |
| 8c3b533c63cca56240f94f1e3a6b18ef | MG      | Southeast |          5 |         8 |         3312.16 |     20    |                 27.89 |                    0    |               1.33 |                      29.45 |           29.4 | Critical           |                70.6 |

## Top 10 sellers

| seller_id                        | state   | region       |   n_orders |   n_items |   total_revenue |   otd_pct |   avg_fulfilment_days |   cancellation_rate_pct |   avg_review_score |   avg_freight_to_price_pct |   seller_score | performance_tier   |   seller_risk_score |
|:---------------------------------|:--------|:-------------|-----------:|----------:|----------------:|----------:|----------------------:|------------------------:|-------------------:|---------------------------:|---------------:|:-------------------|--------------------:|
| 0ad80de75c811326389cfb1daba7d45e | RJ      | Southeast    |          6 |         6 |         1449.4  |       100 |                  0.9  |                       0 |               5    |                       8.37 |           99.4 | Excellent          |                 0.6 |
| 01ed254b9ff8407dfb9d99ba1e17d923 | SP      | Southeast    |          5 |         5 |         1465.99 |       100 |                  1.02 |                       0 |               5    |                       6.16 |           99.3 | Excellent          |                 0.7 |
| 2addf05f476d0637864454e93ba673d5 | DF      | Central-West |         12 |        12 |         4552    |       100 |                  1.1  |                       0 |               5    |                       8.76 |           99.2 | Excellent          |                 0.8 |
| 74871d19219c7d518d0090283e03c137 | SP      | Southeast    |          6 |         7 |          550.04 |       100 |                  0.65 |                       0 |               5    |                      22.33 |           99.1 | Excellent          |                 0.9 |
| 297d5eccd19fa9a83b2630071ff105e4 | PR      | South        |          8 |         8 |          834.97 |       100 |                  0.9  |                       0 |               5    |                      16.93 |           99.1 | Excellent          |                 0.9 |
| c8c1bea22194a4eefa2dc9a9fa89f536 | SC      | South        |          7 |        13 |         1266    |       100 |                  0.59 |                       0 |               5    |                      29    |           99   | Excellent          |                 1   |
| 5c030029b5916fed0986310385ec9009 | SC      | South        |          7 |        10 |         4164.4  |       100 |                  0.82 |                       0 |               4.9  |                      18.52 |           98.7 | Excellent          |                 1.3 |
| 5d76d80a2f5f39c891b996a1bf4c9853 | SP      | Southeast    |          6 |         6 |         1238.5  |       100 |                  0.76 |                       0 |               4.83 |                      13.3  |           98.6 | Excellent          |                 1.4 |
| bb2afe2061d53c6968aa0cffa233a8ec | SP      | Southeast    |          5 |         6 |          549.4  |       100 |                  0.67 |                       0 |               4.83 |                      18.58 |           98.6 | Excellent          |                 1.4 |
| adbe70ab2c97442046d393988c8d1d27 | SP      | Southeast    |          5 |         5 |          289.5  |       100 |                  1.34 |                       0 |               5    |                      22.83 |           98.5 | Excellent          |                 1.5 |