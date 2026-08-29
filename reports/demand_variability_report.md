# Demand Variability Analysis

Weekly demand computed for 72 product categories (categories need >= 8 active weeks to receive a CV classification).

## Demand class distribution

| demand_class      |   count |
|:------------------|--------:|
| Variable          |      61 |
| Stable            |       8 |
| Highly Variable   |       2 |
| Insufficient data |       1 |

## 10 most volatile categories (highest CV)

| category_en                     |   mean_weekly_demand |   coefficient_of_variation | demand_class    |   anomaly_frequency |
|:--------------------------------|---------------------:|---------------------------:|:----------------|--------------------:|
| computers                       |              5.20513 |                      1.354 | Highly Variable |               0.026 |
| food                            |              6.61039 |                      1.051 | Highly Variable |               0.039 |
| construction_tools_construction |             13.8358  |                      0.958 | Variable        |               0.03  |
| construction_tools_lights       |              6.71111 |                      0.953 | Variable        |               0.044 |
| industry_commerce_and_business  |              4.70175 |                      0.91  | Variable        |               0.07  |
| art                             |              3.40984 |                      0.901 | Variable        |               0.049 |
| cine_photo                      |              2       |                      0.878 | Variable        |               0.028 |
| signaling_and_security          |              3.55357 |                      0.865 | Variable        |               0.089 |
| books_technical                 |              4.52542 |                      0.858 | Variable        |               0.051 |
| drinks                          |              6.19672 |                      0.857 | Variable        |               0.049 |

## Anomalous weeks flagged (|Z| > 2): 188

| category_en                             | week_start          |   n_items_sold |   z_score | anomaly   |
|:----------------------------------------|:--------------------|---------------:|----------:|:----------|
| garden_tools                            | 2017-11-20 00:00:00 |            268 |   6.51138 | Spike     |
| consoles_games                          | 2017-11-20 00:00:00 |             69 |   6.00406 | Spike     |
| computers                               | 2017-08-28 00:00:00 |             44 |   5.5782  | Spike     |
| fashion_bags_accessories                | 2017-11-20 00:00:00 |             92 |   5.57071 | Spike     |
| furniture_decor                         | 2017-11-20 00:00:00 |            356 |   5.37081 | Spike     |
| toys                                    | 2017-11-27 00:00:00 |            212 |   4.86688 | Spike     |
| luggage_accessories                     | 2018-01-15 00:00:00 |             44 |   4.83773 | Spike     |
| toys                                    | 2017-11-20 00:00:00 |            209 |   4.77899 | Spike     |
| market_place                            | 2018-02-05 00:00:00 |             15 |   4.71175 | Spike     |
| food                                    | 2018-08-13 00:00:00 |             39 |   4.69393 | Spike     |
| bed_bath_table                          | 2017-11-20 00:00:00 |            438 |   4.68684 | Spike     |
| perfumery                               | 2017-11-20 00:00:00 |            131 |   4.66796 | Spike     |
| stationery                              | 2018-01-08 00:00:00 |            134 |   4.63402 | Spike     |
| kitchen_dining_laundry_garden_furniture | 2017-11-20 00:00:00 |             16 |   4.43616 | Spike     |
| unknown                                 | 2018-01-15 00:00:00 |             72 |   4.20371 | Spike     |