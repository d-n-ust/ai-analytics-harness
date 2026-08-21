-- name: revenue_monthly
SELECT date_trunc('month', placed_at) AS month,
       SUM(total) AS revenue
FROM orders
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1;

-- name: net_revenue
SELECT SUM(net_amount) AS net_revenue
FROM orders
WHERE status IN ('completed', 'fulfilled')
  AND is_test = false;

-- name: revenue_finance
SELECT date_trunc('month', order_date) AS month,
       SUM(net_revenue) AS net_revenue
FROM fct_orders
WHERE status IN ('paid', 'fulfilled', 'partially_refunded')
  AND is_test = false
GROUP BY 1
ORDER BY 1;

-- name: monthly_revenue
SELECT date_trunc('month', ordered_at) AS month,
       SUM(amount) AS revenue
FROM orders_old
WHERE order_status = 'paid'
  AND is_test = 0
GROUP BY 1
ORDER BY 1;

-- name: gross_revenue_monthly
SELECT date_trunc('month', placed_at) AS month,
       SUM(gross_amount) AS gross_revenue
FROM orders
WHERE is_test = false
GROUP BY 1
ORDER BY 1;

-- name: revenue_topline
SELECT SUM(total) AS revenue
FROM orders
WHERE status = 'paid';

-- name: revenue_shopify_raw
SELECT date_trunc('month', processed_at) AS month,
       SUM(total_price) AS revenue
FROM raw_shopify_orders
WHERE financial_status = 'paid'
  AND test = false
GROUP BY 1
ORDER BY 1;

-- name: net_revenue_finance_pack
SELECT date_trunc('month', order_date) AS month,
       SUM(net_revenue) - SUM(refund_amount) AS net_revenue
FROM fct_orders
WHERE status IN ('paid', 'fulfilled', 'partially_refunded')
GROUP BY 1
ORDER BY 1;

-- name: total_revenue_blended
SELECT date_key,
       SUM(order_revenue) + SUM(subscription_revenue) AS total_revenue
FROM fct_revenue
GROUP BY date_key
ORDER BY date_key;

-- name: booked_revenue_monthly
SELECT date_trunc('month', issued_at) AS month,
       SUM(total) AS booked_revenue
FROM invoices
WHERE status = 'paid'
GROUP BY 1
ORDER BY 1;

-- name: revenue_from_payments
SELECT date_trunc('month', captured_at) AS month,
       SUM(amount) AS revenue
FROM payments
WHERE status = 'succeeded'
GROUP BY 1
ORDER BY 1;

-- name: orders_count_monthly
SELECT date_trunc('month', placed_at) AS month,
       COUNT(*) AS orders
FROM orders
WHERE status = 'completed'
  AND is_test = false
GROUP BY 1
ORDER BY 1;

-- name: daily_orders
SELECT CAST(placed_at AS DATE) AS day,
       COUNT(DISTINCT id) AS orders
FROM orders
WHERE state = 'active'
GROUP BY 1
ORDER BY 1;

-- name: aov_monthly
SELECT date_trunc('month', placed_at) AS month,
       SUM(total) / COUNT(*) AS aov
FROM orders
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1;

-- name: aov
SELECT AVG(revenue) AS aov
FROM fct_orders
WHERE is_test = false;

-- name: average_order_value_net
SELECT SUM(net_amount) / COUNT(DISTINCT id) AS aov
FROM orders
WHERE status IN ('paid', 'fulfilled')
  AND is_test = false
  AND is_internal = false;

-- name: customer_count
SELECT COUNT(*) AS customers
FROM customers;

-- name: total_customers
SELECT COUNT(*) AS customers
FROM dim_customers
WHERE is_test = false;

-- name: buyers
SELECT COUNT(DISTINCT customer_id) AS buyers
FROM orders
WHERE status = 'completed';

-- name: active_customers
SELECT COUNT(*) AS active_customers
FROM customers
WHERE is_active = true;

-- name: active_customers_90d
SELECT COUNT(DISTINCT customer_id) AS active_customers
FROM orders
WHERE placed_at >= current_date - INTERVAL '90 days'
  AND status IN ('paid', 'fulfilled', 'completed')
  AND is_test = false;

-- name: new_customers_monthly
SELECT date_trunc('month', created_at) AS month,
       COUNT(*) AS new_customers
FROM customers
GROUP BY 1
ORDER BY 1;

-- name: new_customers
SELECT date_trunc('month', first_order_date) AS month,
       COUNT(*) AS new_customers
FROM dim_customers
WHERE first_order_date IS NOT NULL
  AND is_test = false
GROUP BY 1
ORDER BY 1;

-- name: first_time_buyers_monthly
SELECT date_trunc('month', order_date) AS month,
       COUNT(*) AS new_customers
FROM fct_orders
WHERE is_first_order = true
GROUP BY 1
ORDER BY 1;

-- name: mrr
SELECT SUM(mrr) AS mrr
FROM subscriptions
WHERE state = 'active'
  AND is_test = false;

-- name: mrr_current
SELECT SUM(monthly_amount) AS mrr
FROM subscriptions
WHERE is_active = true;

-- name: active_subscribers
SELECT COUNT(*) AS active_subscribers
FROM subscriptions
WHERE status = 'active';

-- name: subscription_revenue_monthly
SELECT date_trunc('month', occurred_at) AS month,
       SUM(amount) AS subscription_revenue
FROM subscription_events
WHERE event_type = 'renewed'
GROUP BY 1
ORDER BY 1;

-- name: mrr_finance
SELECT SUM(mrr) AS mrr
FROM stg_subscriptions
WHERE status = 'active';

-- name: refunds_monthly
SELECT date_trunc('month', processed_at) AS month,
       SUM(refund_amount) AS refunds
FROM refunds
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1;

-- name: refund_total
SELECT SUM(amount) AS refunds
FROM refunds;

-- name: return_rate
SELECT SUM(r.quantity)::numeric / NULLIF(SUM(oi.qty), 0) AS return_rate
FROM order_items oi
LEFT JOIN returns r ON r.order_item_id = oi.id;

-- name: discounts_monthly
SELECT date_trunc('month', placed_at) AS month,
       SUM(discount_amount) AS discounts
FROM orders
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1;

-- name: discount_total
SELECT SUM(line_discount) AS discounts
FROM order_items;

-- name: promo_redemptions
SELECT code,
       SUM(times_used) AS redemptions
FROM discounts
WHERE active = true
GROUP BY code
ORDER BY redemptions DESC;

-- name: marketing_spend_monthly
SELECT date_trunc('month', spend_date) AS month,
       SUM(spend) AS spend
FROM marketing_spend
GROUP BY 1
ORDER BY 1;

-- name: cac_monthly
SELECT m.month,
       m.spend / c.new_customers AS cac
FROM (
    SELECT date_trunc('month', spend_date) AS month, SUM(spend) AS spend
    FROM marketing_spend
    GROUP BY 1
) m
JOIN (
    SELECT date_trunc('month', first_order_date) AS month, COUNT(*) AS new_customers
    FROM dim_customers
    WHERE first_order_date IS NOT NULL
    GROUP BY 1
) c ON c.month = m.month
ORDER BY m.month;

-- name: roas_weekly
SELECT s.week,
       r.revenue / s.spend AS roas
FROM (
    SELECT date_trunc('week', spend_date) AS week, SUM(spend) AS spend
    FROM marketing_spend
    GROUP BY 1
) s
JOIN (
    SELECT date_trunc('week', placed_at) AS week, SUM(total) AS revenue
    FROM orders
    WHERE status = 'paid'
    GROUP BY 1
) r ON r.week = s.week
ORDER BY s.week;

-- name: repeat_purchase_rate
SELECT COUNT(*) FILTER (WHERE order_count >= 2)::numeric / COUNT(*) AS repeat_rate
FROM (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    WHERE status IN ('completed', 'fulfilled')
      AND is_test = false
    GROUP BY customer_id
) t;

-- name: retention_cohort
SELECT date_trunc('month', c.first_order_date) AS cohort_month,
       date_trunc('month', o.placed_at) AS order_month,
       COUNT(DISTINCT o.customer_id) AS active
FROM dim_customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: subscription_churn
SELECT date_trunc('month', canceled_at) AS month,
       COUNT(*) AS churned
FROM subscriptions
WHERE status = 'cancelled'
GROUP BY 1
ORDER BY 1;
