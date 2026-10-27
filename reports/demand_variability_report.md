# Demand Variability Analysis

Weekly units sold for 74 categories over 86 full weeks (2017-01-02 to 2018-08-20), zero-sales weeks included. 54 categories have >= 100 units and are classified.

## CV classification

| demand_class    |   count |
|:----------------|--------:|
| Variable        |      34 |
| Highly Variable |      17 |
| Stable          |       3 |

## Syntetos-Boylan classification (inventory-planning view)

| sbc_class    |   count |
|:-------------|--------:|
| Smooth       |      28 |
| Lumpy        |      11 |
| Erratic      |      11 |
| Intermittent |       4 |

## 10 most volatile classified categories

| category_en                     |   total_items |   mean_weekly_demand |   coefficient_of_variation |   zero_week_share | demand_class    | sbc_class    |   anomaly_weeks |
|:--------------------------------|--------------:|---------------------:|---------------------------:|------------------:|:----------------|:-------------|----------------:|
| computers                       |           203 |                2.36  |                      2.281 |             0.547 | Highly Variable | Lumpy        |               2 |
| construction_tools_lights       |           301 |                3.5   |                      1.631 |             0.488 | Highly Variable | Lumpy        |               5 |
| costruction_tools_tools         |           103 |                1.198 |                      1.487 |             0.57  | Highly Variable | Intermittent |               7 |
| industry_commerce_and_business  |           264 |                3.07  |                      1.35  |             0.349 | Highly Variable | Lumpy        |               5 |
| furniture_bedroom               |           109 |                1.267 |                      1.311 |             0.384 | Highly Variable | Lumpy        |               5 |
| signaling_and_security          |           199 |                2.314 |                      1.298 |             0.349 | Highly Variable | Lumpy        |               5 |
| christmas_supplies              |           152 |                1.767 |                      1.283 |             0.43  | Highly Variable | Lumpy        |               3 |
| art                             |           207 |                2.407 |                      1.256 |             0.302 | Highly Variable | Lumpy        |               7 |
| books_technical                 |           266 |                3.093 |                      1.244 |             0.326 | Highly Variable | Lumpy        |               6 |
| construction_tools_construction |           926 |               10.767 |                      1.211 |             0.233 | Highly Variable | Erratic      |               5 |

## Anomalous category-weeks (|Z| > 2): 192

Z-scores are measured against each category's whole-period mean, so in fast-growing categories later weeks lean toward 'Spike'. Trend-adjusted detection belongs to the forecasting phase.

| category_en                             | week_start   |   n_items_sold |   z_score | anomaly   |
|:----------------------------------------|:-------------|---------------:|----------:|:----------|
| computers                               | 2017-08-28   |             44 |      7.73 | Spike     |
| garden_tools                            | 2017-11-20   |            268 |      6.51 | Spike     |
| consoles_games                          | 2017-11-20   |             69 |      5.93 | Spike     |
| fashion_bags_accessories                | 2017-11-20   |             92 |      5.69 | Spike     |
| furniture_decor                         | 2017-11-20   |            356 |      5.48 | Spike     |
| toys                                    | 2017-11-27   |            212 |      4.82 | Spike     |
| food                                    | 2018-08-13   |             39 |      4.8  | Spike     |
| market_place                            | 2018-02-05   |             15 |      4.79 | Spike     |
| bed_bath_table                          | 2017-11-20   |            438 |      4.74 | Spike     |
| toys                                    | 2017-11-20   |            209 |      4.73 | Spike     |
| luggage_accessories                     | 2018-01-15   |             44 |      4.68 | Spike     |
| furniture_bedroom                       | 2018-07-23   |              9 |      4.65 | Spike     |
| perfumery                               | 2017-11-20   |            131 |      4.61 | Spike     |
| stationery                              | 2018-01-08   |            134 |      4.6  | Spike     |
| kitchen_dining_laundry_garden_furniture | 2017-11-20   |             16 |      4.37 | Spike     |
