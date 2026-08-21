# Detector on env_sales

454 grounding facts {('semantic', 'metric'): 39, ('semantic', 'dimension'): 14, ('semantic', 'segment'): 8, ('warehouse', 'table'): 25, ('warehouse', 'column'): 303, ('warehouse', 'view'): 5, ('docs', 'term'): 44, ('docs', 'column'): 16}.

69 findings. type={'CONCEPT_FORK': 3, 'DEFINITION_DIVERGENCE': 25, 'SCOPE_TRAP': 2, 'NAME_COLLISION': 34, 'DUPLICATE': 5} danger={'high': 10, 'medium': 31, 'low': 28}.

> Boundary: this flags where grounding facts DISAGREE (name + definition collisions). It does not check which definition is correct, values/enums inside a column, single-fact flaws, or join-path (fan/chasm) traps — those are complementary checks.

## HIGH (10)
```
[CONCEPT_FORK] booked_revenue[sem]  ~  gross_revenue[sem]  ~  net_revenue[sem]  ~  net_sales[sem]  ~  order_revenue[sem]  ~  revenue[sem]
[CONCEPT_FORK] active_customers[sem]  ~  paying_customers[sem]  ~  total_customers[sem]
[CONCEPT_FORK] churned_mrr[sem]  ~  new_mrr[sem]
[DEFINITION_DIVERGENCE] revenue[doc]  ~  revenue[doc]  ~  revenue[sem]  ~  revenue[war]
[DEFINITION_DIVERGENCE] active_customers[sem]  ~  active_customers[sem]  ~  active_customers[war]
[DEFINITION_DIVERGENCE] status[doc]  ~  status[doc]
[DEFINITION_DIVERGENCE] completed_orders[sem]  ~  completed_orders[war]
[DEFINITION_DIVERGENCE] active_subscriptions[sem]  ~  active_subscriptions[war]
[SCOPE_TRAP] completed_orders[sem]  ~  order_count[sem]
[SCOPE_TRAP] active_customers[sem]  ~  total_customers[sem]
```

## MEDIUM (31)
```
[DEFINITION_DIVERGENCE] country[sem]  ~  country[war]  ~  country[war]  ~  country[war]
[DEFINITION_DIVERGENCE] orders[doc]  ~  orders[sem]  ~  orders[war]
[DEFINITION_DIVERGENCE] gross_revenue[sem]  ~  gross_revenue[war]  ~  gross_revenue[war]
[DEFINITION_DIVERGENCE] net_revenue[sem]  ~  net_revenue[war]  ~  net_revenue[war]
[DEFINITION_DIVERGENCE] mrr[sem]  ~  mrr[war]  ~  mrr[war]
[DEFINITION_DIVERGENCE] refund_amount[sem]  ~  refund_amount[war]  ~  refund_amount[war]
[DEFINITION_DIVERGENCE] source[sem]  ~  source[war]  ~  source[war]
[DEFINITION_DIVERGENCE] plan[sem]  ~  plan[war]  ~  plan[war]
[DEFINITION_DIVERGENCE] order_status[sem]  ~  order_status[war]  ~  order_status[war]
[DEFINITION_DIVERGENCE] aov[doc]  ~  aov[sem]
[DEFINITION_DIVERGENCE] cac[doc]  ~  cac[sem]
[DEFINITION_DIVERGENCE] roas[doc]  ~  roas[sem]
[DEFINITION_DIVERGENCE] order_revenue[sem]  ~  order_revenue[war]
[DEFINITION_DIVERGENCE] subscription_revenue[sem]  ~  subscription_revenue[war]
[DEFINITION_DIVERGENCE] booked_revenue[sem]  ~  booked_revenue[war]
[DEFINITION_DIVERGENCE] paid_orders[sem]  ~  paid_orders[war]
[DEFINITION_DIVERGENCE] marketing_spend[sem]  ~  marketing_spend[war]
[DEFINITION_DIVERGENCE] order_date[sem]  ~  order_date[war]
[DEFINITION_DIVERGENCE] campaign[sem]  ~  campaign[war]
[DEFINITION_DIVERGENCE] device[sem]  ~  device[war]
[NAME_COLLISION] active customer[doc]  ~  active_customers[sem]  ~  active_customers[sem]
[NAME_COLLISION] amount[war]
[NAME_COLLISION] customer_id[war]
[NAME_COLLISION] email[war]
[NAME_COLLISION] is_active[war]
[NAME_COLLISION] is_test[war]
[NAME_COLLISION] order_id[war]
[NAME_COLLISION] price[war]
[NAME_COLLISION] status[war]
[NAME_COLLISION] subscription_id[war]
[NAME_COLLISION] user_id[war]
```

## LOW (28)
```
[DUPLICATE] discount_amount[doc]  ~  discount_amount[sem]  ~  discount_amount[war]
[DUPLICATE] status[doc]  ~  order_status[sem]  ~  status[war]
[DUPLICATE] customer_type[doc]  ~  customer_type[sem]
[DUPLICATE] is_active[doc]  ~  is_active[war]
[DUPLICATE] net_revenue[doc]  ~  net_revenue[war]
[NAME_COLLISION] net_revenue[doc]  ~  revenue[doc]  ~  revenue[doc]  ~  total revenue[doc]  ~  net_revenue[sem]  ~  revenue[sem]  ~  total_revenue[sem]
[NAME_COLLISION] discount_amount[doc]  ~  discount_amount[sem]  ~  discount_rate[sem]
[NAME_COLLISION] discount_amount[war]  ~  discount[war]  ~  total_discounts[war]
[NAME_COLLISION] shipping_amount[war]  ~  shipping[war]  ~  shipping_cost[war]
[NAME_COLLISION] status[war]  ~  from_status[war]  ~  to_status[war]
[NAME_COLLISION] gross_revenue[sem]  ~  gross_sales[sem]
[NAME_COLLISION] subscription revenue[doc]  ~  subscription_revenue[sem]
[NAME_COLLISION] booked vs recognised revenue[doc]  ~  booked_revenue[sem]
[NAME_COLLISION] mrr[sem]  ~  new_mrr[sem]
[NAME_COLLISION] active subscriber[doc]  ~  active_subscriptions[sem]
[NAME_COLLISION] return rate[doc]  ~  return_rate[sem]
[NAME_COLLISION] repeat purchase rate[doc]  ~  repeat_purchase_rate[sem]
[NAME_COLLISION] churn rate[doc]  ~  churn_rate[sem]
[NAME_COLLISION] fct_order_items[doc]  ~  fct_orders[doc]
[NAME_COLLISION] dim_product_variants[doc]  ~  dim_products[doc]
[NAME_COLLISION] is_test[war]  ~  test[war]
[NAME_COLLISION] order_id[war]  ~  order_item_id[war]
[NAME_COLLISION] unit_price[war]  ~  unit_cost[war]
[NAME_COLLISION] orders_count[war]  ~  total_orders[war]
[NAME_COLLISION] option1[war]  ~  option2[war]
[NAME_COLLISION] current_period_end[war]  ~  current_period_start[war]
[NAME_COLLISION] last_order_date[war]  ~  order_date[war]
[NAME_COLLISION] net_revenue[war]  ~  revenue[war]
```
