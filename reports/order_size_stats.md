# Order Size Statistics - Items per Order

An order is the bundling/shipping unit; `n_items` is how many product units it held. Weighted average is weighted by order item value. n = 98,199 orders (cancelled/unavailable orders and orders with no items excluded).

## Overall

|            |   n_orders |   mean |   weighted_avg_by_revenue |   p25 |   median |   p75 |   harmonic_mean |   std_dev |   min |   max |
|:-----------|-----------:|-------:|--------------------------:|------:|---------:|------:|----------------:|----------:|------:|------:|
| ALL ORDERS |      98199 | 1.1416 |                    1.2668 |     1 |        1 |     1 |          1.0579 |    0.5376 |     1 |    21 |

## By distance band (seller -> customer)

| distance_band   |   n_orders |   mean |   weighted_avg_by_revenue |   p25 |   median |   p75 |   harmonic_mean |   std_dev |   min |   max |
|:----------------|-----------:|-------:|--------------------------:|------:|---------:|------:|----------------:|----------:|------:|------:|
| 0-100 km        |      18151 | 1.1381 |                    1.2626 |     1 |        1 |     1 |          1.0563 |    0.5556 |     1 |    21 |
| 100-300 km      |      13634 | 1.1546 |                    1.2558 |     1 |        1 |     1 |          1.062  |    0.5589 |     1 |    11 |
| 1000+ km        |      15778 | 1.1221 |                    1.2476 |     1 |        1 |     1 |          1.049  |    0.5007 |     1 |    15 |
| 300-500 km      |      24187 | 1.1459 |                    1.2912 |     1 |        1 |     1 |          1.0602 |    0.5331 |     1 |    14 |
| 500-1000 km     |      26449 | 1.1448 |                    1.267  |     1 |        1 |     1 |          1.0601 |    0.5387 |     1 |    20 |

## By customer region

| region       |   n_orders |   mean |   weighted_avg_by_revenue |   p25 |   median |   p75 |   harmonic_mean |   std_dev |   min |   max |
|:-------------|-----------:|-------:|--------------------------:|------:|---------:|------:|----------------:|----------:|------:|------:|
| Central-West |       5728 | 1.1508 |                    1.3177 |     1 |        1 |     1 |          1.0603 |    0.6189 |     1 |    20 |
| North        |       1834 | 1.1232 |                    1.184  |     1 |        1 |     1 |          1.0497 |    0.4765 |     1 |     6 |
| Northeast    |       9305 | 1.1152 |                    1.2333 |     1 |        1 |     1 |          1.0475 |    0.4625 |     1 |    11 |
| South        |      13996 | 1.1497 |                    1.2787 |     1 |        1 |     1 |          1.0605 |    0.5591 |     1 |    15 |
| Southeast    |      67336 | 1.1432 |                    1.2682 |     1 |        1 |     1 |          1.0588 |    0.5366 |     1 |    21 |

## By order complexity (distinct sellers per order)

| sellers_per_order_band   |   n_orders |   mean |   weighted_avg_by_revenue |   p25 |   median |   p75 |   harmonic_mean |   std_dev |   min |   max |
|:-------------------------|-----------:|-------:|--------------------------:|------:|---------:|------:|----------------:|----------:|------:|------:|
| 1                        |      96922 | 1.1246 |                    1.2382 |     1 |        1 |     1 |          1.0506 |    0.5073 |     1 |    21 |
| 2                        |       1218 | 2.3596 |                    2.57   |     2 |        2 |     2 |          2.1934 |    0.9335 |     2 |    11 |
| 3+                       |         59 | 3.8475 |                    4.0028 |     3 |        3 |     4 |          3.5588 |    1.3495 |     3 |    10 |
