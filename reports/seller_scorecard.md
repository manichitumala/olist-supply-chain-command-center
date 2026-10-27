# Seller Performance Scorecard

3,095 sellers; **634 ranked** (>= 30 distinct orders). The rest are listed in `data/exports/seller_scorecard.csv` as *Insufficient volume* with their order counts.

## Method

- Metrics are computed per seller-order, not per item.
- Late and cancellation rates are shrunk toward the platform rate with an empirical-Bayes Beta prior (late-rate prior = Beta(8.1, 113.0), i.e. worth ~121 orders). Review averages use a prior worth ~5 reviews.
- Score = 30% on-time + 25% fulfilment speed + 20% cancellation + 15% review + 10% freight/price, each as a percentile rank (0-100) among ranked sellers.
- **Tiers are relative**: top 25% Excellent, next 50% Good, next 15% At Risk, bottom 10% Critical.
- **Absolute flag**: `late_rate_flag` is set when the 95% Wilson lower bound of a seller's late rate exceeds the platform late rate (6.69%). 81 ranked sellers are flagged.

## Tier distribution

| performance_tier    |   count |
|:--------------------|--------:|
| Excellent           |     158 |
| Good                |     317 |
| At Risk             |      95 |
| Critical            |      64 |
| Insufficient volume |    2461 |

## Sellers with a statistically significant late-delivery problem

| seller_id                        | state   |   n_orders |   late_rate_raw |   late_rate_ci_low |   late_rate_ci_high |   late_rate_adj |   avg_fulfilment_days |   avg_review_adj |   seller_score | performance_tier   |
|:---------------------------------|:--------|-----------:|----------------:|-------------------:|--------------------:|----------------:|----------------------:|-----------------:|---------------:|:-------------------|
| 54965bbe3e4f07ae045b90b0b8541f52 | PR      |         78 |          0.3014 |             0.2082 |              0.4144 |          0.1552 |               16.0459 |           3.0652 |           19.5 | Critical           |
| ede0c03645598cdfc63ca8237acbe73d | SP      |         46 |          0.3256 |             0.2049 |              0.4748 |          0.1349 |                3.435  |           3.5774 |           10.8 | Critical           |
| ad781527c93d00d89a11eecd9dcad7c1 | SP      |         44 |          0.3158 |             0.1908 |              0.4746 |          0.1265 |               10.894  |           3.1669 |            3.7 | Critical           |
| 2a1348e9addc1af5aaa619b1a3679d6b | MG      |         52 |          0.2708 |             0.1657 |              0.41   |          0.125  |                4.7087 |           3.1998 |            8.4 | Critical           |
| 06a2c3af7b3aee5d69171b0e14f0ee87 | MA      |        392 |          0.1902 |             0.1543 |              0.2322 |          0.161  |                4.7089 |           3.9909 |           28.9 | At Risk            |
| 835f0f7810c76831d6c7d24c7a646d4d | SP      |         44 |          0.2619 |             0.153  |              0.4107 |          0.1173 |                9.3839 |           3.4132 |            8.6 | Critical           |
| a49928bcdf77c55c6d6e05e09a9b4ca5 | SP      |         98 |          0.2188 |             0.1478 |              0.3114 |          0.1342 |                6.9696 |           3.0597 |           22.5 | Critical           |
| beadbee30901a7f61d031b6b686095ad | SP      |         64 |          0.2344 |             0.1475 |              0.3513 |          0.125  |                7.1308 |           3.9187 |           21.9 | Critical           |
| 712e6ed8aa4aa1fa65dab41fed5737e4 | SC      |         79 |          0.2078 |             0.1321 |              0.3112 |          0.1218 |                7.2176 |           3.4247 |           22.4 | Critical           |
| 88460e8ebdecbfecb5f9601833981930 | PR      |        248 |          0.1707 |             0.1289 |              0.2227 |          0.1366 |                7.5486 |           3.4256 |           12.1 | Critical           |
| e5a3438891c0bfdb9394643f95273d8e | SP      |        224 |          0.1574 |             0.1149 |              0.2119 |          0.125  |                3.3579 |           3.9224 |           14.4 | Critical           |
| ef990a83bbea832f36ebe81376335aa8 | SC      |         43 |          0.2093 |             0.1142 |              0.3521 |          0.1044 |                1.7727 |           3.6733 |           32.5 | At Risk            |
| 1ca7077d890b907f89be8c954a02686a | SP      |        115 |          0.1667 |             0.1081 |              0.2481 |          0.1141 |                5.4356 |           2.403  |           27.1 | At Risk            |
| 8160255418d5aaa7dbdc9f4c64ebda44 | SP      |        385 |          0.1368 |             0.1059 |              0.1751 |          0.12   |                3.6734 |           3.9363 |           35.1 | At Risk            |
| cac4c8e7b1ca6252d8f20b2fc1a2e4af | SP      |         75 |          0.1757 |             0.1056 |              0.2777 |          0.1083 |                5.7504 |           3.5606 |           18.2 | Critical           |

## Bottom 10 ranked sellers

| seller_id                        | state   |   n_orders |   late_rate_raw |   late_rate_ci_low |   late_rate_ci_high |   late_rate_adj |   avg_fulfilment_days |   avg_review_adj |   seller_score | performance_tier   |
|:---------------------------------|:--------|-----------:|----------------:|-------------------:|--------------------:|----------------:|----------------------:|-----------------:|---------------:|:-------------------|
| 6973a06f484aacf400ece213dbf3d946 | SP      |         95 |          0.1461 |             0.0874 |              0.234  |          0.1006 |                5.7388 |           3.5889 |           12.2 | Critical           |
| 850913d59ce317156b00f3705f1c3edb | SP      |         32 |          0.1724 |             0.076  |              0.3455 |          0.0875 |                4.9585 |           3.521  |           12.2 | Critical           |
| 88460e8ebdecbfecb5f9601833981930 | PR      |        248 |          0.1707 |             0.1289 |              0.2227 |          0.1366 |                7.5486 |           3.4256 |           12.1 | Critical           |
| b17b679f4f5ce2e03ce6968c62648246 | SP      |         55 |          0.16   |             0.0834 |              0.2851 |          0.0943 |                3.9485 |           3.739  |           11.4 | Critical           |
| d20b021d3efdf267a402c402a48ea64b | SP      |         90 |          0.1628 |             0.0995 |              0.2549 |          0.1069 |                3.6608 |           3.7056 |           10.8 | Critical           |
| ede0c03645598cdfc63ca8237acbe73d | SP      |         46 |          0.3256 |             0.2049 |              0.4748 |          0.1349 |                3.435  |           3.5774 |           10.8 | Critical           |
| 855668e0971d4dfd7bef1b6a4133b41b | SP      |        312 |          0.1267 |             0.0937 |              0.1691 |          0.1096 |                5.8673 |           3.7768 |           10.7 | Critical           |
| 835f0f7810c76831d6c7d24c7a646d4d | SP      |         44 |          0.2619 |             0.153  |              0.4107 |          0.1173 |                9.3839 |           3.4132 |            8.6 | Critical           |
| 2a1348e9addc1af5aaa619b1a3679d6b | MG      |         52 |          0.2708 |             0.1657 |              0.41   |          0.125  |                4.7087 |           3.1998 |            8.4 | Critical           |
| ad781527c93d00d89a11eecd9dcad7c1 | SP      |         44 |          0.3158 |             0.1908 |              0.4746 |          0.1265 |               10.894  |           3.1669 |            3.7 | Critical           |

## Top 10 ranked sellers

| seller_id                        | state   |   n_orders |   late_rate_raw |   late_rate_ci_low |   late_rate_ci_high |   late_rate_adj |   avg_fulfilment_days |   avg_review_adj |   seller_score | performance_tier   |
|:---------------------------------|:--------|-----------:|----------------:|-------------------:|--------------------:|----------------:|----------------------:|-----------------:|---------------:|:-------------------|
| c3cfdc648177fdbbbb35635a37472c53 | PR      |        278 |          0.0144 |             0.0056 |              0.0364 |          0.0304 |                1.5643 |           4.4629 |           89.9 | Excellent          |
| 725c32fa80c2faacc4fc88450d27314e | SP      |         89 |          0.0112 |             0.002  |              0.0609 |          0.0435 |                0.8343 |           4.4951 |           88.9 | Excellent          |
| 289cdb325fb7e7f891c38608bf9e0962 | SP      |        110 |          0.0183 |             0.005  |              0.0644 |          0.0441 |                1.2725 |           4.5528 |           88.7 | Excellent          |
| 8ae520247981aa06bc94abddf5f46d34 | SC      |         65 |          0      |             0      |              0.0558 |          0.0437 |                1.064  |           4.4219 |           87.6 | Excellent          |
| 9f505651f4a6abe901a56cdc21508025 | SP      |        397 |          0.0407 |             0.0252 |              0.0651 |          0.047  |                0.9767 |           4.3371 |           87.5 | Excellent          |
| d921b68bf747894be13a97ae52b0f386 | MG      |         77 |          0.013  |             0.0023 |              0.07   |          0.0461 |                1.2445 |           4.5312 |           87.2 | Excellent          |
| d566c37fa119d5e66c4e9052e83ee4ea | SP      |         65 |          0      |             0      |              0.0558 |          0.0437 |                1.0349 |           4.6463 |           86   | Excellent          |
| ac3508719a1d8f5b7614b798f70af136 | RS      |        103 |          0.0198 |             0.0054 |              0.0693 |          0.0457 |                1.2265 |           4.5809 |           85.7 | Excellent          |
| 744dac408745240a2c2528fb1b6028f3 | PR      |         79 |          0.0128 |             0.0023 |              0.0691 |          0.0459 |                1.5878 |           4.5424 |           84.6 | Excellent          |
| de722cd6dad950a92b7d4f82673f8833 | PE      |        339 |          0.0356 |             0.0205 |              0.0612 |          0.044  |                1.5982 |           4.2909 |           83.8 | Excellent          |

Caveat: delivery outcome, fulfilment time and review are recorded per order, so in multi-seller orders (~1.3%) every seller inherits the order's values.
