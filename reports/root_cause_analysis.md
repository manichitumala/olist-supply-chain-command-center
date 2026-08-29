# Root-Cause Analysis: Why Are Orders Late?

## Stage comparison, on-time vs late orders

| otd_status   |   n_orders |   avg_fulfilment_days |   avg_transit_days |
|:-------------|-----------:|----------------------:|-------------------:|
| Late         |       7793 |                  5.35 |              25.68 |
| On Time      |      87304 |                  2.63 |               7.91 |

Late orders spend roughly 3.2x longer in transit than on-time orders, and 2.0x longer in seller fulfilment -- transportation is the dominant bottleneck, with seller fulfilment as a secondary contributor.

## Worst-performing sellers by late rate (>= 15 orders)

| seller_id                        | state   |   n_orders |   late_rate_pct |   avg_fulfilment_days |
|:---------------------------------|:--------|-----------:|----------------:|----------------------:|
| b1b3948701c5c72445495bd161b83a4c | SP      |         18 |           64.29 |                 14.1  |
| 2709af9587499e95e803a6498a5a56e9 | SP      |         26 |           50    |                  2.33 |
| 4342d4b2ba6b161468c63a7e7cfce593 | RJ      |         20 |           50    |                  3.77 |
| f76a3b1349b6df1ee875d1f3fa4340f0 | SP      |         24 |           37.5  |                  8.11 |
| 821fb029fc6e495ca4f08a35d51e53a5 | SP      |         28 |           36    |                  1.76 |
| ede0c03645598cdfc63ca8237acbe73d | SP      |         46 |           34.04 |                  3.42 |
| 54965bbe3e4f07ae045b90b0b8541f52 | PR      |         78 |           32.1  |                 16.74 |
| b19f3ca2ea475913750f25a5c37c8d8f | MG      |         24 |           31.58 |                 11.64 |
| ad781527c93d00d89a11eecd9dcad7c1 | SP      |         44 |           31.58 |                 10.89 |
| 835f0f7810c76831d6c7d24c7a646d4d | SP      |         44 |           31.25 |                  9.15 |
| 7f152321c60a266edc53af1925ef96c1 | SC      |         20 |           30    |                  3.6  |
| 2a1348e9addc1af5aaa619b1a3679d6b | MG      |         52 |           29.41 |                  4.63 |
| c4d51195486dc781531876a7d00453d8 | SP      |         17 |           29.41 |                  5.47 |
| 4e5725ba188db8252977a4f0227bd462 | SP      |         22 |           29.17 |                  3    |
| 054694fa03fe82cec4b7551487331d74 | SP      |         21 |           28.57 |                  8.98 |

## Transportation delay hotspots (distance band x region, >= 30 orders)

| distance_band   | region       |   n_orders |   late_rate_pct |   avg_transit_days |
|:----------------|:-------------|-----------:|----------------:|-------------------:|
| 1000+ km        | Northeast    |       8434 |           14.8  |              17.08 |
| 0-100 km        | Northeast    |         82 |           10.98 |               4.9  |
| 300-500 km      | Northeast    |         61 |            9.84 |              10.67 |
| 1000+ km        | North        |       1769 |            9.67 |              19.32 |
| 1000+ km        | South        |       1633 |            8.94 |              13.78 |
| 500-1000 km     | Central-West |       3796 |            8.77 |              11.59 |
| 500-1000 km     | Southeast    |      14800 |            8.68 |              10.46 |
| 300-500 km      | Central-West |        226 |            8.41 |              12.17 |
| 300-500 km      | Southeast    |      19647 |            7.94 |               9.21 |
| 1000+ km        | Southeast    |       2130 |            7.93 |              10.89 |
| 500-1000 km     | South        |       6969 |            7.72 |              12.07 |
| 500-1000 km     | Northeast    |        417 |            7.19 |              12.59 |
| 100-300 km      | Southeast    |      12447 |            6.51 |               6.78 |
| 0-100 km        | Southeast    |      17176 |            6.46 |               3.36 |
| 1000+ km        | Central-West |       1449 |            6.14 |              13.39 |

## Hypothesis test: do multi-seller orders have worse outcomes?

| sellers_per_order_band   |   n_orders |   avg_lead_time_days |   late_rate_pct |   avg_review_score |
|:-------------------------|-----------:|---------------------:|----------------:|-------------------:|
| 1                        |      95203 |                12.66 |            8.2  |               4.17 |
| 2                        |       1216 |                 9.33 |            1.48 |               2.89 |
| 3+                       |         59 |                 8.53 |            0    |               2.24 |

**Verdict: PARTIALLY REJECTED, WITH AN IMPORTANT TWIST. On the operational metrics the hypothesis is rejected: multi-seller orders are LATE LESS OFTEN (0.7% vs 8.2% for single-seller orders) and arrive faster on average, most likely because they skew toward higher-volume, more reliable sellers and are rare (under 1.5% of delivered orders). But customer satisfaction tells the opposite story: average review score drops sharply as seller count rises (4.17 for single-seller orders vs 2.57 for 2+ sellers). So multi-seller orders are operationally faster and more reliable by the clock, yet customers rate them worse anyway -- something about splitting an order across sellers (likely fragmented/partial deliveries, inconsistent packaging, or mismatched expectations when items from the same order arrive at different times) hurts the experience in a way the delivered-date timestamp alone doesn't capture. This is flagged as an open question for further investigation rather than resolved here -- Olist's schema has no per-shipment timestamp to confirm the split-delivery theory directly.**