# Supply Chain Risk Index

Supply Chain Risk = 40% Demand Risk + 35% Delivery Risk + 25% Seller Risk, each component min-max normalised to 0-100 across categories before blending.

## Risk tier distribution

| risk_tier   |   count |
|:------------|--------:|
| LOW RISK    |      44 |
| MEDIUM RISK |      24 |
| HIGH RISK   |       0 |

## Highest-risk categories (management should investigate first)

| category_en                       |   n_orders |   total_revenue |   coefficient_of_variation | demand_class    |   anomaly_frequency |   demand_risk |   late_rate_pct |   avg_delay_days_when_late |   transit_time_stddev_hours |   delivery_risk |   revenue_weighted_seller_risk |   seller_risk |   supply_chain_risk | risk_tier   |
|:----------------------------------|-----------:|----------------:|---------------------------:|:----------------|--------------------:|--------------:|----------------:|---------------------------:|----------------------------:|----------------:|-------------------------------:|--------------:|--------------------:|:------------|
| furniture_mattress_and_upholstery |         38 |         4368.08 |                       0.67 | Variable        |                0.12 |         62.64 |           13.51 |                      15.71 |                      349.62 |           85.07 |                           7.63 |          7.63 |                56.7 | MEDIUM RISK |
| home_comfort_2                    |         24 |          760.27 |                       0.44 | Stable          |                0.1  |         40.91 |           16.67 |                      12.33 |                      255.13 |           74.81 |                          10.16 |         10.16 |                45.1 | MEDIUM RISK |
| computers                         |        181 |       222963    |                       1.35 | Highly Variable |                0.03 |         59.09 |            6.53 |                      10.1  |                      214.38 |           41.59 |                           7.44 |          7.44 |                40.1 | MEDIUM RISK |
| signaling_and_security            |        140 |        21509.2  |                       0.86 | Variable        |                0.09 |         59.44 |            5.58 |                      11.23 |                      204.83 |           40.11 |                           7.97 |          7.97 |                39.8 | MEDIUM RISK |
| food                              |        449 |        29243.5  |                       1.05 | Highly Variable |                0.04 |         47.15 |            9.82 |                       9.69 |                      248.1  |           52.96 |                           8.8  |          8.8  |                39.6 | MEDIUM RISK |
| home_confort                      |        397 |        58572    |                       0.65 | Variable        |                0.06 |         34.27 |           10.26 |                      12.47 |                      275.43 |           62.32 |                           9.79 |          9.79 |                38   | MEDIUM RISK |
| christmas_supplies                |        127 |         8787.83 |                       0.71 | Variable        |                0.04 |         28.47 |           12    |                      10.86 |                      280.98 |           64.34 |                          10.74 |         10.74 |                36.6 | MEDIUM RISK |
| tablets_printing_image            |         79 |         7528.41 |                       0.59 | Variable        |                0.11 |         53.7  |            7.23 |                       9.28 |                      165.91 |           35.74 |                           8.34 |          8.34 |                36.1 | MEDIUM RISK |
| industry_commerce_and_business    |        235 |        39669.6  |                       0.91 | Variable        |                0.07 |         53.1  |            7.58 |                       8.46 |                      180.96 |           37.03 |                           7.6  |          7.6  |                36.1 | MEDIUM RISK |
| home_appliances_2                 |        231 |       110650    |                       0.62 | Variable        |                0.03 |         18.98 |            6.93 |                      19.93 |                      334.3  |           74.83 |                           7.98 |          7.98 |                35.8 | MEDIUM RISK |