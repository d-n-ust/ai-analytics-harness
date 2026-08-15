# Collision detector over the sales environment (all 3 layers)

454 grounding facts (semantic + warehouse + docs). Gate = label cosine ≥ 0.55 or exact label match. 123 collisions flagged.

By type: {'CONCEPT_FORK': 14, 'DEFINITION_DIVERGENCE': 5, 'SCOPE_TRAP': 6, 'DUPLICATE': 15, 'NAME_COLLISION': 35, 'CROSS_REF': 46, 'SIBLING': 2}. By danger: {'high': 25, 'medium': 25, 'low': 73}.

## HIGH (25)

```
[CONCEPT_FORK] gross_revenue[sem]  ~  net_revenue[sem]
    'gross_revenue' and 'net_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] gross_revenue[sem]  ~  order_revenue[sem]
    'gross_revenue' and 'order_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] gross_revenue[sem]  ~  booked_revenue[sem]
    'gross_revenue' and 'booked_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] gross_revenue[sem]  ~  revenue[sem]
    'gross_revenue' and 'revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] net_revenue[sem]  ~  net_sales[sem]
    'net_revenue' and 'net_sales' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] net_revenue[sem]  ~  order_revenue[sem]
    'net_revenue' and 'order_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] net_revenue[sem]  ~  booked_revenue[sem]
    'net_revenue' and 'booked_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] net_revenue[sem]  ~  revenue[sem]
    'net_revenue' and 'revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] order_revenue[sem]  ~  booked_revenue[sem]
    'order_revenue' and 'booked_revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] order_revenue[sem]  ~  revenue[sem]
    'order_revenue' and 'revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] booked_revenue[sem]  ~  revenue[sem]
    'booked_revenue' and 'revenue' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] total_customers[sem]  ~  paying_customers[sem]
    'total_customers' and 'paying_customers' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] active_customers[sem]  ~  paying_customers[sem]
    'active_customers' and 'paying_customers' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[CONCEPT_FORK] new_mrr[sem]  ~  churned_mrr[sem]
    'new_mrr' and 'churned_mrr' aggregate the same entity/table the same way but over different columns/expressions — a bare concept resolves to different numbers
[DEFINITION_DIVERGENCE] status[doc]  ~  status[doc]
    'status' is documented with two different definitions
[DEFINITION_DIVERGENCE] revenue[doc]  ~  revenue[doc]
    'revenue' is documented with two different definitions
[DEFINITION_DIVERGENCE] completed_orders[sem]  ~  completed_orders[war]
    'completed_orders' resolves to a different scope in semantic vs warehouse
[DEFINITION_DIVERGENCE] active_customers[sem]  ~  active_customers[war]
    'active_customers' resolves to a different scope in semantic vs warehouse
[DEFINITION_DIVERGENCE] active_subscriptions[sem]  ~  active_subscriptions[war]
    'active_subscriptions' resolves to a different scope in semantic vs warehouse
[SCOPE_TRAP] order_count[sem]  ~  completed_orders[sem]
    same measure; 'completed_orders' is 'order_count' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
[SCOPE_TRAP] completed_orders[sem]  ~  order_status[sem]
    same measure; 'completed_orders' is 'order_status' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
[SCOPE_TRAP] completed_orders[sem]  ~  order_total[doc]
    same measure; 'completed_orders' is 'order_total' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
[SCOPE_TRAP] total_customers[sem]  ~  active_customers[sem]
    same measure; 'active_customers' is 'total_customers' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
[SCOPE_TRAP] paying_customers[sem]  ~  paying[sem]
    same measure; 'paying' is 'paying_customers' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
[SCOPE_TRAP] churned_mrr[sem]  ~  churned[sem]
    same measure; 'churned' is 'churned_mrr' plus a filter — a bare question is silently scoped, numbers differ, swap is invisible
```

## MEDIUM (25)

```
[DUPLICATE] order_count[sem]  ~  order_date[sem]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_count[sem]  ~  order_status[sem]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_count[sem]  ~  order_total[doc]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] discount_amount[sem]  ~  discount_amount[doc]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_date[sem]  ~  order_status[sem]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_date[sem]  ~  order_total[doc]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_status[sem]  ~  status[doc]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] customer_type[sem]  ~  customer_type[doc]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] orders[sem]  ~  orders[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] discount_amount[sem]  ~  discount_amount[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] order_date[sem]  ~  order_date[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] is_active[doc]  ~  is_active[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] status[doc]  ~  status[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] discount_amount[doc]  ~  discount_amount[war]
    same measure and scope under two names — pick-either, but a governance smell
[DUPLICATE] net_revenue[doc]  ~  net_revenue[war]
    same measure and scope under two names — pick-either, but a governance smell
[NAME_COLLISION] active_customers[sem]  ~  active_customers[sem]
    two different 'active_customers' in the semantic layer
[NAME_COLLISION] amount[war]
    column 'amount' appears in 4 tables (orders_old, payments, refunds, subscription_events...) — meaning may differ
[NAME_COLLISION] customer_id[war]
    column 'customer_id' appears in 13 tables (dim_customers, fct_orders, fct_revenue, invoices, orders, payments...) — meaning may differ
[NAME_COLLISION] is_active[war]
    column 'is_active' appears in 6 tables (customers, dim_customers, dim_products, product_variants, stg_customers, subscriptions...) — meaning may differ
[NAME_COLLISION] is_test[war]
    column 'is_test' appears in 7 tables (dim_customers, fct_orders, orders, orders_old, stg_orders, subscriptions...) — meaning may differ
[NAME_COLLISION] order_id[war]
    column 'order_id' appears in 8 tables (fct_orders, order_items, orders_old, payments, refunds, returns...) — meaning may differ
[NAME_COLLISION] price[war]
    column 'price' appears in 4 tables (order_items, product_variants, products, subscriptions...) — meaning may differ
[NAME_COLLISION] status[war]
    column 'status' appears in 9 tables (fct_orders, invoices, orders, payments, products, refunds...) — meaning may differ
[NAME_COLLISION] subscription_id[war]
    column 'subscription_id' appears in 4 tables (invoices, payments, stg_subscriptions, subscription_events...) — meaning may differ
[NAME_COLLISION] user_id[war]
    column 'user_id' appears in 5 tables (dim_customers, orders, sessions, subscriptions, users...) — meaning may differ
```

## LOW (73)

```
[CROSS_REF] net_revenue[sem]  ~  net_revenue[doc]
    'net_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] revenue[sem]  ~  revenue[doc]
    'revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] orders[sem]  ~  orders[doc]
    'orders' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] aov[sem]  ~  aov[doc]
    'aov' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] cac[sem]  ~  cac[doc]
    'cac' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] roas[sem]  ~  roas[doc]
    'roas' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] channel[sem]  ~  channel[doc]
    'channel' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] status[sem]  ~  status[doc]
    'status' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] gross_revenue[sem]  ~  gross_revenue[war]
    'gross_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] net_revenue[sem]  ~  net_revenue[war]
    'net_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] order_revenue[sem]  ~  order_revenue[war]
    'order_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] subscription_revenue[sem]  ~  subscription_revenue[war]
    'subscription_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] booked_revenue[sem]  ~  booked_revenue[war]
    'booked_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] revenue[sem]  ~  revenue[war]
    'revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] paid_orders[sem]  ~  paid_orders[war]
    'paid_orders' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] mrr[sem]  ~  mrr[war]
    'mrr' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] returns[sem]  ~  returns[war]
    'returns' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] refund_amount[sem]  ~  refund_amount[war]
    'refund_amount' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] discount_amount[sem]  ~  discount_amount[war]
    'discount_amount' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] marketing_spend[sem]  ~  marketing_spend[war]
    'marketing_spend' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] sessions[sem]  ~  sessions[war]
    'sessions' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] channel[sem]  ~  channel[war]
    'channel' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] source[sem]  ~  source[war]
    'source' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] campaign[sem]  ~  campaign[war]
    'campaign' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] country[sem]  ~  country[war]
    'country' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] plan[sem]  ~  plan[war]
    'plan' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] order_status[sem]  ~  order_status[war]
    'order_status' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] status[sem]  ~  status[war]
    'status' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] device[sem]  ~  device[war]
    'device' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] active[sem]  ~  active[war]
    'active' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] dim_customers[doc]  ~  dim_customers[war]
    'dim_customers' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] status[doc]  ~  status[war]
    'status' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] is_active[doc]  ~  is_active[war]
    'is_active' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] first_order_at[doc]  ~  first_order_at[war]
    'first_order_at' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] lifetime_value[doc]  ~  lifetime_value[war]
    'lifetime_value' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] orders[doc]  ~  orders[war]
    'orders' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] fct_orders[doc]  ~  fct_orders[war]
    'fct_orders' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] discount_amount[doc]  ~  discount_amount[war]
    'discount_amount' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] net_revenue[doc]  ~  net_revenue[war]
    'net_revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] channel[doc]  ~  channel[war]
    'channel' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] placed_at[doc]  ~  placed_at[war]
    'placed_at' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] products[doc]  ~  products[war]
    'products' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] dim_products[doc]  ~  dim_products[war]
    'dim_products' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] plan_interval[doc]  ~  plan_interval[war]
    'plan_interval' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] revenue[doc]  ~  revenue[war]
    'revenue' is both modelled and documented; prose consistency not machine-checked
[CROSS_REF] ltv[doc]  ~  ltv[war]
    'ltv' is both modelled and documented; prose consistency not machine-checked
[NAME_COLLISION] gross_revenue[sem]  ~  gross_sales[sem]
    'gross_revenue' and 'gross_sales' read alike, different things
[NAME_COLLISION] net_revenue[sem]  ~  total_revenue[sem]
    'net_revenue' and 'total_revenue' read alike, different things
[NAME_COLLISION] net_revenue[sem]  ~  revenue[doc]
    'net_revenue' and 'revenue' read alike, different things
[NAME_COLLISION] net_revenue[sem]  ~  total revenue[doc]
    'net_revenue' and 'total revenue' read alike, different things
[NAME_COLLISION] subscription_revenue[sem]  ~  subscription revenue[doc]
    'subscription_revenue' and 'subscription revenue' read alike, different things
[NAME_COLLISION] total_revenue[sem]  ~  revenue[sem]
    'total_revenue' and 'revenue' read alike, different things
[NAME_COLLISION] total_revenue[sem]  ~  net_revenue[doc]
    'total_revenue' and 'net_revenue' read alike, different things
[NAME_COLLISION] total_revenue[sem]  ~  revenue[doc]
    'total_revenue' and 'revenue' read alike, different things
[NAME_COLLISION] total_revenue[sem]  ~  total revenue[doc]
    'total_revenue' and 'total revenue' read alike, different things
[NAME_COLLISION] booked_revenue[sem]  ~  booked vs recognised revenue[doc]
    'booked_revenue' and 'booked vs recognised revenue' read alike, different things
[NAME_COLLISION] revenue[sem]  ~  net_revenue[doc]
    'revenue' and 'net_revenue' read alike, different things
[NAME_COLLISION] revenue[sem]  ~  total revenue[doc]
    'revenue' and 'total revenue' read alike, different things
[NAME_COLLISION] active_customers[sem]  ~  active customer[doc]
    'active_customers' and 'active customer' read alike, different things
[NAME_COLLISION] mrr[sem]  ~  new_mrr[sem]
    'mrr' and 'new_mrr' read alike, different things
[NAME_COLLISION] active_subscriptions[sem]  ~  active subscriber[doc]
    'active_subscriptions' and 'active subscriber' read alike, different things
[NAME_COLLISION] return_rate[sem]  ~  return rate[doc]
    'return_rate' and 'return rate' read alike, different things
[NAME_COLLISION] discount_amount[sem]  ~  discount_rate[sem]
    'discount_amount' and 'discount_rate' read alike, different things
[NAME_COLLISION] discount_rate[sem]  ~  discount_amount[doc]
    'discount_rate' and 'discount_amount' read alike, different things
[NAME_COLLISION] repeat_purchase_rate[sem]  ~  repeat purchase rate[doc]
    'repeat_purchase_rate' and 'repeat purchase rate' read alike, different things
[NAME_COLLISION] churn_rate[sem]  ~  churn rate[doc]
    'churn_rate' and 'churn rate' read alike, different things
[NAME_COLLISION] fct_orders[doc]  ~  fct_order_items[doc]
    'fct_orders' and 'fct_order_items' read alike, different things
[NAME_COLLISION] net_revenue[doc]  ~  revenue[doc]
    'net_revenue' and 'revenue' read alike, different things
[NAME_COLLISION] net_revenue[doc]  ~  total revenue[doc]
    'net_revenue' and 'total revenue' read alike, different things
[NAME_COLLISION] dim_products[doc]  ~  dim_product_variants[doc]
    'dim_products' and 'dim_product_variants' read alike, different things
[NAME_COLLISION] revenue[doc]  ~  total revenue[doc]
    'revenue' and 'total revenue' read alike, different things
[SIBLING] active_customers[sem]  ~  active[sem]
    same measure, incomparable scopes — a question must name one
[SIBLING] active_subscriptions[sem]  ~  active_customers[sem]
    same measure, incomparable scopes — a question must name one
```
