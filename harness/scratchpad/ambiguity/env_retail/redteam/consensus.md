# Red-team consensus / dispute analysis (retail)

Judges: 1=80 findings, 2=96, 3=76 (2 findings had no distinctive entity label and were skipped). Clustered into 47 distinct candidate collisions.

Only **high-danger** disagreements are escalated (a medium/low split is not worth your time). Consensus-high: **9** settled. High-danger disputes to rule: **16**.

## Settled — all 3 judges rated HIGH (no human needed)
```
doc_vs_schema_model_names             active, active_flag, active_members, available, available_qty
member_filter_columns_phantom         active, active_flag, active_members, enroll_date, enrolled_flag
store_key_sprawl                      channel, dim_store, fct_online_orders, fulfillment_store, location
many_sales_metrics_collide            daily_sales, fct_transactions, gross_sales, merch_sales, net_sales
comp_three_qualification_rules        close_date, comp_flag, comp_sales, comp_stores, comparable
returns_column_names_and_phantom_return_amt  fct_returns, line_no, net sales, order_id, original_txn_id
units_baskets_transactions_denominator  basket_id, baskets, fct_transaction_lines, fct_transactions, online_orders
shrink_wrong_base_table               fct_markdowns, inventory_shrink, inventory_snapshot, markdown_flag, reason_code
v_net_sales_hidden_comp_filter        is_comp, net sales, net_sales, sales, v_net_sales
```

## ESCALATE — high-danger DISPUTES (your call)

`n=high/3` is how many judges called it HIGH; J1=finance, J2=merch, J3=data-eng (dash = that judge did not flag it at all).
```
[2/3 high] semantic_phantom_measures          J1=medium J2=high J3=high
    items: available, available_qty, department_name, dept_name, fct_inventory_daily, fct_orders
    why: Most semantic measures and filter columns (gross_amt, net_sales_amt, ext_ring_amt, on_hand_qty, reserved_qty, months_open, last_pu
[2/3 high] margin_which_cost_which_denominator J1=high J2=medium J3=high
    items: dim_product, extended_price, fct_inventory_daily, fct_sales_line, gross_margin, gross_margin_pct
    why: gross_margin uses unit/ext cost, gross_margin_pct uses landed_cost over net sales, margin_standard uses standard cost, and two pre
[2/3 high] online_status_filter_missing       J1=high J2=- J3=high
    items: average_order_value, channel, fct_online_orders, net sales, online_orders, online_sales
    why: The docs are explicit that online revenue must filter to 'fulfilled' and that 'cart' rows are abandoned baskets that are never mon
[2/3 high] store_ops_sales_tax_in             J1=high J2=high J3=-
    items: daily_sales, retail_sales, sales, store_sales_daily, v_comp_store_sales
    why: The long-watched leadership 'sales by store' number (retail_sales / store_ops.daily_sales.sales / store_sales_daily.sales) is gros
[2/3 high] is_comp_value_Y_vs_true_vs_1       J1=- J2=high J3=high
    items: comp_flag, fct_transactions, is_comp, store_sales_daily, v_comp_store_sales
    why: Comp is filtered as CHAR 'Y' on the legacy table, boolean true on the fact, and integer 1 in the semantic layer. Applying the wron
[2/3 high] aov_mislabeled_and_overlapping     J1=high J2=high J3=-
    items: average_basket_value, average_order_value
    why: aov ('average order value') actually computes in-store net sales over POS transactions, not online order value; average_order_valu
[1/3 high] loyalty_penetration_basket_vs_dollar J1=medium J2=high J3=medium
    items: baskets, fct_transactions, loyalty, loyalty sales penetration, member_id, sales
    why: Penetration is baskets-with-member over all baskets (store scorecard) or loyalty dollars over total dollars (exec deck); loyalty b
[1/3 high] store_identifier_codes             J1=medium J2=medium J3=high
    items: banner, dim_store, region, square_feet, store_code, store_format
    why: The warehouse key is store_id, the spoken id is a four-digit store_number (which the schema does not actually have — it has store_
[1/3 high] channel_column_on_pos_missing      J1=high J2=medium J3=-
    items: channel, online_channel, pos_transactions, store, store_channel, store_sales
    why: store_sales and the store_channel segment filter channel='store' on pos_transactions, but pos_transactions has no channel column (
[1/3 high] region_five_vs_six                 J1=medium J2=high J3=-
    items: dim_store, region
    why: Region was five, is now six (Inland split into Inland and High Desert), but many dashboards still roll to the old five. A 'by regi
[1/3 high] inventory_three_numbers            J1=high J2=- J3=-
    items: available, inventory, inventory position (on, inventory_available, inventory_on_hand
    why: Inventory reads three ways (on-hand physical, available = on-hand minus reserved, owned = on-hand plus in-transit/on-order). Only 
[1/3 high] v_active_members_flag_based        J1=high J2=- J3=-
    items: active_members, dim_member, v_active_members
    why: v_active_members defines active by active_flag AND enrolled_flag, with no recency window, while the metric uses 90-day purchase an
[1/3 high] gross_margin_pct_mixes_gross_and_net J1=- J2=high J3=-
    items: gross margin, gross_margin_pct, markup, sales
    why: The metric divides a gross-ring-based margin by net sales, mixing gross in the numerator with net in the denominator. Because net 
[1/3 high] product_key_sprawl                 J1=- J2=high J3=-
    items: dim_product, product_id, product_key
    why: POS lines carry sku only, online lines carry sku and product_id, sales facts carry product_key, and one UPC can map to multiple SK
[1/3 high] gross_amt_column_missing_on_base   J1=- J2=high J3=-
    items: gross_sales, pos_transactions
    why: The semantic gross_sales metric reads measure gross_amt from pos_transactions, but pos_transactions has no gross column at all — o
[1/3 high] average_basket_gross_vs_net        J1=- J2=high J3=-
    items: average_basket_value, transactions
    why: Docs note the merch ATV uses gross over completed transactions and the finance version uses net, coming in lower. The semantic aov
```