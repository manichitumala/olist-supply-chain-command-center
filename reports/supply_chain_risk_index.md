# Supply Chain Risk Index

52 categories (>= 100 orders and enough demand history to classify).

Risk = 40% Demand + 35% Delivery + 25% Seller. Each input is a percentile rank across categories, so **the index ranks categories against each other; it is not an absolute probability of failure**. Tiers: top 20% High, next 40% Medium, bottom 40% Low.

Seller risk only covers sellers with enough orders to be scored; `scored_revenue_share` shows how much of each category's revenue that is.

## Tier distribution

| risk_tier   |   count |
|:------------|--------:|
| HIGH RISK   |      10 |
| MEDIUM RISK |      21 |
| LOW RISK    |      21 |

## Highest-risk categories

| category_en                     |   n_orders |   late_rate_pct |   coefficient_of_variation |   demand_risk |   delivery_risk |   seller_risk |   scored_revenue_share |   supply_chain_risk | risk_tier   |
|:--------------------------------|-----------:|----------------:|---------------------------:|--------------:|----------------:|--------------:|-----------------------:|--------------------:|:------------|
| christmas_supplies              |        127 |            8    |                       1.28 |         68.27 |           92.31 |         96.15 |                   0.69 |                83.7 | HIGH RISK   |
| home_confort                    |        397 |            9.44 |                       0.77 |         66.35 |           94.87 |         90.38 |                   0.99 |                82.3 | HIGH RISK   |
| signaling_and_security          |        140 |            4.35 |                       1.3  |         87.02 |           65.38 |         92.31 |                   0.25 |                80.8 | HIGH RISK   |
| fashion_underwear_beach         |        121 |            9.4  |                       1.06 |         67.79 |           48.72 |        100    |                   0.42 |                69.2 | HIGH RISK   |
| art                             |        201 |            6.15 |                       1.26 |         95.19 |           17.95 |         94.23 |                   0.61 |                67.9 | HIGH RISK   |
| office_furniture                |       1272 |            8.05 |                       0.65 |         25.96 |           91.67 |         98.08 |                   0.88 |                67   | HIGH RISK   |
| drinks                          |        296 |            5.23 |                       1.21 |         82.21 |           51.28 |         59.62 |                   0.53 |                65.7 | HIGH RISK   |
| construction_tools_construction |        746 |            7.34 |                       1.21 |         83.17 |           67.31 |         32.69 |                   0.64 |                65   | HIGH RISK   |
| home_construction               |        489 |            6    |                       1    |         48.08 |           70.51 |         80.77 |                   0.59 |                64.1 | HIGH RISK   |
| books_technical                 |        260 |            8.2  |                       1.24 |         92.31 |           37.18 |         55.77 |                   0.61 |                63.9 | HIGH RISK   |
