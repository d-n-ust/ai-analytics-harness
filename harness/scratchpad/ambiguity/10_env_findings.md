# Collision detector v2 (clustered) over the sales environment

454 grounding facts. 57 collision findings (clustered per concept). By type: {'CONCEPT_FORK': 3, 'DEFINITION_DIVERGENCE': 25, 'SCOPE_TRAP': 2, 'DUPLICATE': 5, 'NAME_COLLISION': 22}. By danger: {'high': 10, 'medium': 35, 'low': 12}.

## HIGH (10)
```
[CONCEPT_FORK] booked_revenue[sem]  ~  gross_revenue[sem]  ~  net_revenue[sem]  ~  net_sales[sem]  ~  order_revenue[sem]  ~  revenue[sem]
    same entity/table aggregated the same way over different columns — a bare concept resolves to different numbers
[CONCEPT_FORK] active_customers[sem]  ~  paying_customers[sem]  ~  total_customers[sem]
    same entity/table aggregated the same way over different columns — a bare concept resolves to different numbers
[CONCEPT_FORK] churned_mrr[sem]  ~  new_mrr[sem]
    same entity/table aggregated the same way over different columns — a bare concept resolves to different numbers
[DEFINITION_DIVERGENCE] revenue[doc]  ~  revenue[doc]  ~  revenue[sem]  ~  revenue[war]
    'revenue' documented two different ways
[DEFINITION_DIVERGENCE] active_customers[sem]  ~  active_customers[sem]  ~  active_customers[war]
    'active_customers' resolves to a different scope in semantic vs warehouse
[DEFINITION_DIVERGENCE] status[doc]  ~  status[doc]
    'status' documented two different ways
[DEFINITION_DIVERGENCE] completed_orders[sem]  ~  completed_orders[war]
    'completed_orders' resolves to a different scope in semantic vs warehouse
[DEFINITION_DIVERGENCE] active_subscriptions[sem]  ~  active_subscriptions[war]
    'active_subscriptions' resolves to a different scope in semantic vs warehouse
[SCOPE_TRAP] completed_orders[sem]  ~  order_count[sem]
    same measure; 'completed_orders' is 'order_count' plus a filter — bare question silently scoped, swap invisible
[SCOPE_TRAP] active_customers[sem]  ~  total_customers[sem]
    same measure; 'active_customers' is 'total_customers' plus a filter — bare question silently scoped, swap invisible
```

## MEDIUM (35)
```
[DEFINITION_DIVERGENCE] country[sem]  ~  country[war]  ~  country[war]  ~  country[war]
    'country' is modelled on ['country_code'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] orders[doc]  ~  orders[sem]  ~  orders[war]
    'orders' is modelled on ['order_id'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] gross_revenue[sem]  ~  gross_revenue[war]  ~  gross_revenue[war]
    'gross_revenue' is modelled on ['gross_amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] net_revenue[sem]  ~  net_revenue[war]  ~  net_revenue[war]
    'net_revenue' is modelled on ['discount_amount', 'gross_amount', 'return_amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] mrr[sem]  ~  mrr[war]  ~  mrr[war]
    'mrr' is modelled on ['mrr_amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] refund_amount[sem]  ~  refund_amount[war]  ~  refund_amount[war]
    'refund_amount' is modelled on ['amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] source[sem]  ~  source[war]  ~  source[war]
    'source' is modelled on ['utm_source'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] plan[sem]  ~  plan[war]  ~  plan[war]
    'plan' is modelled on ['plan_name'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] order_status[sem]  ~  order_status[war]  ~  order_status[war]
    'order_status' is modelled on ['status'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] aov[doc]  ~  aov[sem]
    'aov' is modelled on ['net_amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] cac[doc]  ~  cac[sem]
    'cac' is modelled on ['marketing_spend', 'new_customers'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] roas[doc]  ~  roas[sem]
    'roas' is modelled on ['gross_revenue', 'marketing_spend'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] order_revenue[sem]  ~  order_revenue[war]
    'order_revenue' is modelled on ['case', 'else', 'end', 'net_amount', 'order_type', 'subscription', 'then', 'when'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] subscription_revenue[sem]  ~  subscription_revenue[war]
    'subscription_revenue' is modelled on ['amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] booked_revenue[sem]  ~  booked_revenue[war]
    'booked_revenue' is modelled on ['booked_amount'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] paid_orders[sem]  ~  paid_orders[war]
    'paid_orders' is modelled on ['case', 'end', 'order_id', 'paid', 'payment_status', 'then', 'when'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] marketing_spend[sem]  ~  marketing_spend[war]
    'marketing_spend' is modelled on ['spend'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] order_date[sem]  ~  order_date[war]
    'order_date' is modelled on ['order_date'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] campaign[sem]  ~  campaign[war]
    'campaign' is modelled on ['campaign_name'] but its documentation does not reference those columns
[DEFINITION_DIVERGENCE] device[sem]  ~  device[war]
    'device' is modelled on ['device_type'] but its documentation does not reference those columns
[DUPLICATE] discount_amount[doc]  ~  discount_amount[sem]  ~  discount_amount[war]
    same measure and scope under two names
[DUPLICATE] status[doc]  ~  order_status[sem]  ~  status[war]
    same measure and scope under two names
[DUPLICATE] customer_type[doc]  ~  customer_type[sem]
    same measure and scope under two names
[DUPLICATE] is_active[doc]  ~  is_active[war]
    same measure and scope under two names
[DUPLICATE] net_revenue[doc]  ~  net_revenue[war]
    same measure and scope under two names
[NAME_COLLISION] active customer[doc]  ~  active_customers[sem]  ~  active_customers[sem]
    two different 'active_customers' in the semantic layer
[NAME_COLLISION] amount[war]
    column 'amount' in 4 tables — meaning may differ
[NAME_COLLISION] customer_id[war]
    column 'customer_id' in 13 tables — meaning may differ
[NAME_COLLISION] is_active[war]
    column 'is_active' in 6 tables — meaning may differ
[NAME_COLLISION] is_test[war]
    column 'is_test' in 7 tables — meaning may differ
[NAME_COLLISION] order_id[war]
    column 'order_id' in 8 tables — meaning may differ
[NAME_COLLISION] price[war]
    column 'price' in 4 tables — meaning may differ
[NAME_COLLISION] status[war]
    column 'status' in 9 tables — meaning may differ
[NAME_COLLISION] subscription_id[war]
    column 'subscription_id' in 4 tables — meaning may differ
[NAME_COLLISION] user_id[war]
    column 'user_id' in 5 tables — meaning may differ
```

## LOW (12)
```
[NAME_COLLISION] net_revenue[doc]  ~  revenue[doc]  ~  revenue[doc]  ~  total revenue[doc]  ~  net_revenue[sem]  ~  revenue[sem]  ~  total_revenue[sem]
    'net_revenue' and 'total_revenue' read alike, different things
[NAME_COLLISION] discount_amount[doc]  ~  discount_amount[sem]  ~  discount_rate[sem]
    'discount_amount' and 'discount_rate' read alike, different things
[NAME_COLLISION] gross_revenue[sem]  ~  gross_sales[sem]
    'gross_revenue' and 'gross_sales' read alike, different things
[NAME_COLLISION] subscription revenue[doc]  ~  subscription_revenue[sem]
    'subscription_revenue' and 'subscription revenue' read alike, different things
[NAME_COLLISION] booked vs recognised revenue[doc]  ~  booked_revenue[sem]
    'booked_revenue' and 'booked vs recognised revenue' read alike, different things
[NAME_COLLISION] mrr[sem]  ~  new_mrr[sem]
    'mrr' and 'new_mrr' read alike, different things
[NAME_COLLISION] active subscriber[doc]  ~  active_subscriptions[sem]
    'active_subscriptions' and 'active subscriber' read alike, different things
[NAME_COLLISION] return rate[doc]  ~  return_rate[sem]
    'return_rate' and 'return rate' read alike, different things
[NAME_COLLISION] repeat purchase rate[doc]  ~  repeat_purchase_rate[sem]
    'repeat_purchase_rate' and 'repeat purchase rate' read alike, different things
[NAME_COLLISION] churn rate[doc]  ~  churn_rate[sem]
    'churn_rate' and 'churn rate' read alike, different things
[NAME_COLLISION] fct_order_items[doc]  ~  fct_orders[doc]
    'fct_orders' and 'fct_order_items' read alike, different things
[NAME_COLLISION] dim_product_variants[doc]  ~  dim_products[doc]
    'dim_products' and 'dim_product_variants' read alike, different things
```
