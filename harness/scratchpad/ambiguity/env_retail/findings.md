# Detector on env_retail

525 grounding facts {('semantic', 'metric'): 39, ('semantic', 'dimension'): 16, ('semantic', 'segment'): 8, ('warehouse', 'table'): 35, ('warehouse', 'column'): 361, ('warehouse', 'view'): 6, ('docs', 'term'): 47, ('docs', 'column'): 13}.

61 findings. type={'CONCEPT_FORK': 3, 'SCOPE_TRAP': 2, 'DEFINITION_DIVERGENCE': 10, 'DUPLICATE': 7, 'NAME_COLLISION': 38, 'SIBLING': 1} danger={'high': 5, 'medium': 43, 'low': 13}.

## HIGH (5)
```
[CONCEPT_FORK] comp_sales[sem]  ~  comparable_store_sales[sem]  ~  gross_sales[sem]  ~  net_sales[sem]  ~  same_store_sales[sem]  ~  store_sales[sem]
[CONCEPT_FORK] gross_margin[sem]  ~  margin_standard[sem]
[CONCEPT_FORK] inventory_available[sem]  ~  inventory_on_hand[sem]
[SCOPE_TRAP] gross_sales[sem]  ~  store_sales[sem]
[SCOPE_TRAP] net_sales[sem]  ~  same_store_sales[sem]
```

## MEDIUM (43)
```
[DEFINITION_DIVERGENCE] net_sales[doc]  ~  net_sales[sem]  ~  net_sales[war]  ~  net_sales[war]  ~  net_sales[war]  ~  net_sales[war]  ~  net_sales[war]  ~  net_sales[war]  ~  net_sales[war]
[DEFINITION_DIVERGENCE] gross_sales[doc]  ~  gross_sales[sem]  ~  gross_sales[war]  ~  gross_sales[war]  ~  gross_sales[war]  ~  gross_sales[war]  ~  gross_sales[war]  ~  gross_sales[war]
[DEFINITION_DIVERGENCE] units[doc]  ~  units[sem]  ~  units[war]  ~  units[war]  ~  units[war]  ~  units[war]  ~  units[war]
[DEFINITION_DIVERGENCE] order_date[sem]  ~  order_date[war]  ~  order_date[war]  ~  order_date[war]  ~  order_date[war]
[DEFINITION_DIVERGENCE] business_date[sem]  ~  business_date[war]  ~  business_date[war]  ~  business_date[war]
[DEFINITION_DIVERGENCE] gross_margin[sem]  ~  gross_margin[war]  ~  gross_margin[war]
[DEFINITION_DIVERGENCE] store_format[sem]  ~  store_format[war]  ~  store_format[war]
[DEFINITION_DIVERGENCE] shrink[doc]  ~  shrink[sem]
[DEFINITION_DIVERGENCE] online_orders[sem]  ~  online_orders[war]
[DEFINITION_DIVERGENCE] loyalty_members[sem]  ~  loyalty_members[war]
[DUPLICATE] banner[doc]  ~  banner[war]
[DUPLICATE] gross_sales[doc]  ~  gross_sales[war]
[DUPLICATE] net_sales[doc]  ~  net_sales[war]
[DUPLICATE] tax_amount[doc]  ~  tax_amount[war]
[DUPLICATE] status[doc]  ~  status[war]
[DUPLICATE] member_id[doc]  ~  member_id[war]
[DUPLICATE] refund_amount[doc]  ~  refund_amount[war]
[NAME_COLLISION] members / active members / enrolled[doc]  ~  active_members[sem]  ~  enrolled_members[sem]  ~  active_members[sem]
[NAME_COLLISION] basket_id[war]
[NAME_COLLISION] category_id[war]
[NAME_COLLISION] customer_id[war]
[NAME_COLLISION] department_id[war]
[NAME_COLLISION] gross_sales[war]
[NAME_COLLISION] landed_cost[war]
[NAME_COLLISION] location_id[war]
[NAME_COLLISION] loyalty_id[war]
[NAME_COLLISION] member_id[war]
[NAME_COLLISION] net_sales[war]
[NAME_COLLISION] order_date[war]
[NAME_COLLISION] order_id[war]
[NAME_COLLISION] order_number[war]
[NAME_COLLISION] product_id[war]
[NAME_COLLISION] qty[war]
[NAME_COLLISION] site_id[war]
[NAME_COLLISION] sku[war]
[NAME_COLLISION] standard_cost[war]
[NAME_COLLISION] status[war]
[NAME_COLLISION] store_id[war]
[NAME_COLLISION] store_key[war]
[NAME_COLLISION] transaction_id[war]
[NAME_COLLISION] unit_cost[war]
[NAME_COLLISION] units[war]
[NAME_COLLISION] void_flag[war]
```

## LOW (13)
```
[NAME_COLLISION] net sales[doc]  ~  net_sales[doc]  ~  net_sales[sem]  ~  net_sales_finance[sem]
[NAME_COLLISION] sales[doc]  ~  retail_sales[sem]  ~  store_sales[sem]
[NAME_COLLISION] inventory[doc]  ~  inventory_available[sem]  ~  inventory_on_hand[sem]
[NAME_COLLISION] revenue[doc]  ~  total_revenue[sem]
[NAME_COLLISION] comparable_store_sales[sem]  ~  comparable_stores[sem]
[NAME_COLLISION] average basket / average transaction value[doc]  ~  average_basket_value[sem]
[NAME_COLLISION] gross margin[doc]  ~  gross_margin[sem]
[NAME_COLLISION] loyalty[doc]  ~  loyalty_members[sem]
[NAME_COLLISION] transactions & baskets[doc]  ~  transactions, baskets & online orders[doc]
[NAME_COLLISION] fct_transaction_lines[doc]  ~  fct_transactions[doc]
[NAME_COLLISION] status[doc]  ~  status`[doc]
[NAME_COLLISION] fct_online_orders[doc]  ~  fct_purchase_orders[doc]
[SIBLING] comparable_store_sales[sem]  ~  store_sales[sem]
```
