# Score — env_retail

Detector 61 vs gold 79.

## Recall
```
high     18/19 (95%)
medium   34/47 (72%)
low      8/13 (62%)
TOTAL    60/79 (76%)
```
## Precision
```
53/61 (87%)
```
## Missed gold

**high:** available_computed_vs_stored
**medium:** region_five_vs_six; region_actually_district; online_channel_store_9999; basket_size_dollars_or_items; on_hand_duplicate_columns; promo_flag_does_not_exist; hours_vs_hours_worked; category_strings_drift_from_hierarchy; extended_price_vs_line_amount; points_balance_three_ways; is_comp_char_vs_boolean; dsd_thin_in_purchase_orders; order_status_completed_value_absent
**low:** fill_rate_over_100_capped_inconsistently; receipt_timing_double_counts_owned; coupon_funding_null_before_cutover; discount_fields_scattered; supplier_and_dim_supplier_names