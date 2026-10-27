# Root-Cause Analysis: Why Are Orders Late?

Late = delivered after the promised calendar date. Population: delivered orders whose timestamps pass the silver sequence checks.

## Stage comparison, on-time vs late

| otd_status   |   n_orders |   avg_payment_days |   avg_fulfilment_days |   avg_transit_days |   median_transit_days |
|:-------------|-----------:|-------------------:|----------------------:|-------------------:|----------------------:|
| On Time      |      88587 |               0.39 |                  2.65 |               8    |                  6.96 |
| Late         |       6510 |               0.5  |                  5.57 |              27.88 |                 26.2  |

Late orders spend 3.5x longer in transit and 2.1x longer in seller fulfilment than on-time orders. Transport is the larger contributor; seller fulfilment is secondary.

## Sellers with a significantly high late rate

Ranked sellers (>= 30 orders) whose 95% Wilson lower bound on late rate is above the platform rate. Sorted by that lower bound, i.e. by strength of evidence.

| seller_id                        | state   |   n_orders |   n_delivered |   n_late |   late_rate_pct |   late_ci_low_pct |   late_ci_high_pct |   avg_fulfilment_days |   missed_limit_rate_raw |
|:---------------------------------|:--------|-----------:|--------------:|---------:|----------------:|------------------:|-------------------:|----------------------:|------------------------:|
| 54965bbe3e4f07ae045b90b0b8541f52 | PR      |         78 |            73 |       22 |           30.14 |             20.82 |              41.44 |               16.0459 |                  0.5616 |
| ede0c03645598cdfc63ca8237acbe73d | SP      |         46 |            43 |       14 |           32.56 |             20.49 |              47.48 |                3.435  |                  0.1778 |
| ad781527c93d00d89a11eecd9dcad7c1 | SP      |         44 |            38 |       12 |           31.58 |             19.08 |              47.46 |               10.894  |                  0.4615 |
| 2a1348e9addc1af5aaa619b1a3679d6b | MG      |         52 |            48 |       13 |           27.08 |             16.57 |              41    |                4.7087 |                  0.4    |
| 06a2c3af7b3aee5d69171b0e14f0ee87 | MA      |        392 |           389 |       74 |           19.02 |             15.43 |              23.22 |                4.7089 |                  0.3298 |
| 835f0f7810c76831d6c7d24c7a646d4d | SP      |         44 |            42 |       11 |           26.19 |             15.3  |              41.07 |                9.3839 |                  0.7381 |
| a49928bcdf77c55c6d6e05e09a9b4ca5 | SP      |         98 |            96 |       21 |           21.88 |             14.78 |              31.14 |                6.9696 |                  0.551  |
| beadbee30901a7f61d031b6b686095ad | SP      |         64 |            64 |       15 |           23.44 |             14.75 |              35.13 |                7.1308 |                  0.2812 |
| 712e6ed8aa4aa1fa65dab41fed5737e4 | SC      |         79 |            77 |       16 |           20.78 |             13.21 |              31.12 |                7.2176 |                  0.1899 |
| 88460e8ebdecbfecb5f9601833981930 | PR      |        248 |           246 |       42 |           17.07 |             12.89 |              22.27 |                7.5486 |                  0.4815 |
| e5a3438891c0bfdb9394643f95273d8e | SP      |        224 |           216 |       34 |           15.74 |             11.49 |              21.19 |                3.3579 |                  0.1786 |
| ef990a83bbea832f36ebe81376335aa8 | SC      |         43 |            43 |        9 |           20.93 |             11.42 |              35.21 |                1.7727 |                  0      |
| 1ca7077d890b907f89be8c954a02686a | SP      |        115 |           108 |       18 |           16.67 |             10.81 |              24.81 |                5.4356 |                  0.5263 |
| 8160255418d5aaa7dbdc9f4c64ebda44 | SP      |        385 |           380 |       52 |           13.68 |             10.59 |              17.51 |                3.6734 |                  0.2513 |
| cac4c8e7b1ca6252d8f20b2fc1a2e4af | SP      |         75 |            74 |       13 |           17.57 |             10.56 |              27.77 |                5.7504 |                  0.3108 |

## Transport hotspots (distance band x customer region, >= 100 orders)

| distance_band   | region       |   n_orders |   n_late |   avg_transit_days |   late_rate_pct |   late_ci_low_pct |   late_ci_high_pct |
|:----------------|:-------------|-----------:|---------:|-------------------:|----------------:|------------------:|-------------------:|
| 1000+ km        | Northeast    |       8434 |     1110 |              17.08 |           13.16 |             12.46 |              13.9  |
| 1000+ km        | North        |       1769 |      151 |              19.32 |            8.54 |              7.32 |               9.93 |
| 1000+ km        | South        |       1633 |      130 |              13.78 |            7.96 |              6.74 |               9.37 |
| 300-500 km      | Central-West |        226 |       18 |              12.17 |            7.96 |              5.1  |              12.24 |
| 500-1000 km     | Southeast    |      14800 |     1098 |              10.46 |            7.42 |              7.01 |               7.85 |
| 500-1000 km     | Central-West |       3796 |      268 |              11.59 |            7.06 |              6.29 |               7.92 |
| 300-500 km      | Southeast    |      19646 |     1372 |               9.21 |            6.98 |              6.64 |               7.35 |
| 1000+ km        | Southeast    |       2130 |      142 |              10.89 |            6.67 |              5.68 |               7.81 |
| 500-1000 km     | South        |       6968 |      456 |              12.07 |            6.54 |              5.99 |               7.15 |
| 500-1000 km     | Northeast    |        417 |       26 |              12.59 |            6.24 |              4.29 |               8.98 |
| 1000+ km        | Central-West |       1449 |       77 |              13.39 |            5.31 |              4.27 |               6.59 |
| 100-300 km      | Southeast    |      12443 |      659 |               6.78 |            5.3  |              4.92 |               5.7  |
| 300-500 km      | South        |       3806 |      182 |               9.11 |            4.78 |              4.15 |               5.51 |
| 0-100 km        | Southeast    |      17174 |      777 |               3.36 |            4.52 |              4.22 |               4.85 |
| 100-300 km      | South        |        877 |       33 |               7.56 |            3.76 |              2.69 |               5.24 |

## Hypothesis: do multi-seller orders have worse outcomes?

| sellers_per_order_band   |   n_orders |   n_late |   avg_lead_time_days |   avg_review_score |   n_reviews |   late_rate_pct |   late_ci_low_pct |   late_ci_high_pct |
|:-------------------------|-----------:|---------:|---------------------:|-------------------:|------------:|----------------:|------------------:|-------------------:|
| 1                        |      95195 |     6521 |                12.66 |               4.17 |       94563 |            6.85 |              6.69 |               7.01 |
| 2                        |       1216 |       13 |                 9.33 |               2.89 |        1202 |            1.07 |              0.63 |               1.82 |
| 3+                       |         59 |        0 |                 8.53 |               2.24 |          59 |            0    |              0    |               6.11 |

**Verdict:** Multi-seller orders are 1.3% of delivered orders (n=1,275). Late rate: 1.02% vs 6.85% for single-seller orders (lower; two-proportion z-test p=1.9e-16, significant). Average review: 2.86 vs 4.17 (lower; Mann-Whitney p=6e-188, significant). So the hypothesis that multi-seller orders are delivered late more often is rejected, yet customers rate them worse. This is an association, not a cause: these orders differ in basket size, sellers and categories. Split or partial deliveries are a plausible explanation, but Olist has no per-shipment timestamps to test it.
