-- Northwind Threads warehouse

CREATE TABLE raw_shopify_orders (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255),
    customer_id BIGINT,
    order_number VARCHAR(50),
    financial_status VARCHAR(50),
    fulfillment_status VARCHAR(50),
    total_price NUMERIC(12,2),
    subtotal_price NUMERIC(12,2),
    total_discounts NUMERIC(12,2),
    total_tax NUMERIC(12,2),
    currency VARCHAR(10),
    processed_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    test BOOLEAN,
    tags TEXT,
    raw_payload JSON
);

CREATE TABLE orders_old (
    order_id INTEGER PRIMARY KEY,
    cust_id INTEGER,
    order_status VARCHAR(30),
    amount NUMERIC(10,2),
    discount NUMERIC(10,2),
    shipping NUMERIC(10,2),
    tax NUMERIC(10,2),
    channel VARCHAR(50),
    is_test SMALLINT,
    ordered_at TIMESTAMP,
    shipped_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    customer_id BIGINT,
    order_number VARCHAR(50),
    status VARCHAR(30),
    state VARCHAR(30),
    gross_amount NUMERIC(12,2),
    net_amount NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    tax_amount NUMERIC(12,2),
    shipping_amount NUMERIC(12,2),
    total NUMERIC(12,2),
    currency VARCHAR(10),
    source VARCHAR(50),
    coupon_code VARCHAR(50),
    is_subscription BOOLEAN,
    is_test BOOLEAN,
    is_internal BOOLEAN,
    placed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE order_items (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    product_id BIGINT,
    variant_id BIGINT,
    sku VARCHAR(100),
    qty INTEGER,
    unit_price NUMERIC(10,2),
    price NUMERIC(10,2),
    line_amount NUMERIC(12,2),
    line_discount NUMERIC(10,2),
    created_at TIMESTAMP
);

CREATE TABLE customers (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    country VARCHAR(100),
    city VARCHAR(100),
    zip VARCHAR(20),
    accepts_marketing BOOLEAN,
    is_active BOOLEAN,
    lifetime_value NUMERIC(12,2),
    orders_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    email VARCHAR(255),
    full_name VARCHAR(200),
    signup_source VARCHAR(50),
    active SMALLINT,
    is_internal BOOLEAN,
    is_test BOOLEAN,
    marketing_opt_in BOOLEAN,
    first_seen_at TIMESTAMP,
    signed_up_at TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    title VARCHAR(255),
    handle VARCHAR(255),
    product_type VARCHAR(100),
    vendor VARCHAR(100),
    status VARCHAR(30),
    price NUMERIC(10,2),
    cost NUMERIC(10,2),
    active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE product_variants (
    id BIGINT PRIMARY KEY,
    product_id BIGINT,
    sku VARCHAR(100),
    variant_title VARCHAR(255),
    option1 VARCHAR(100),
    option2 VARCHAR(100),
    price NUMERIC(10,2),
    compare_at_price NUMERIC(10,2),
    unit_cost NUMERIC(10,2),
    inventory_qty INTEGER,
    is_active BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE shipments (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    carrier VARCHAR(100),
    tracking_number VARCHAR(255),
    status VARCHAR(50),
    shipping_cost NUMERIC(10,2),
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE returns (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    order_item_id BIGINT,
    customer_id BIGINT,
    reason VARCHAR(255),
    return_status VARCHAR(50),
    quantity INTEGER,
    restocked BOOLEAN,
    requested_at TIMESTAMP,
    received_at TIMESTAMP
);

CREATE TABLE refunds (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    return_id BIGINT,
    amount NUMERIC(12,2),
    refund_amount NUMERIC(12,2),
    tax_refunded NUMERIC(10,2),
    shipping_refunded NUMERIC(10,2),
    status VARCHAR(50),
    reason VARCHAR(255),
    processed_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE subscriptions (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    user_id BIGINT,
    plan VARCHAR(50),
    plan_interval VARCHAR(20),
    status VARCHAR(30),
    state VARCHAR(30),
    mrr NUMERIC(10,2),
    monthly_amount NUMERIC(10,2),
    price NUMERIC(10,2),
    is_active BOOLEAN,
    is_test BOOLEAN,
    trial_ends_at TIMESTAMP,
    started_at TIMESTAMP,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    canceled_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE subscription_events (
    id BIGINT PRIMARY KEY,
    subscription_id BIGINT,
    event_type VARCHAR(50),
    from_status VARCHAR(30),
    to_status VARCHAR(30),
    amount NUMERIC(10,2),
    occurred_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE payments (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    subscription_id BIGINT,
    customer_id BIGINT,
    provider VARCHAR(50),
    method VARCHAR(50),
    amount NUMERIC(12,2),
    gross_amount NUMERIC(12,2),
    fee NUMERIC(10,2),
    net_amount NUMERIC(12,2),
    currency VARCHAR(10),
    status VARCHAR(50),
    captured_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE invoices (
    id BIGINT PRIMARY KEY,
    subscription_id BIGINT,
    customer_id BIGINT,
    invoice_number VARCHAR(50),
    total NUMERIC(12,2),
    amount_due NUMERIC(12,2),
    amount_paid NUMERIC(12,2),
    tax NUMERIC(10,2),
    status VARCHAR(50),
    period_start DATE,
    period_end DATE,
    issued_at TIMESTAMP,
    paid_at TIMESTAMP
);

CREATE TABLE discounts (
    id BIGINT PRIMARY KEY,
    code VARCHAR(50),
    type VARCHAR(30),
    value NUMERIC(10,2),
    value_type VARCHAR(20),
    min_order_amount NUMERIC(10,2),
    usage_limit INTEGER,
    times_used INTEGER,
    active BOOLEAN,
    starts_at TIMESTAMP,
    ends_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE marketing_spend (
    id BIGINT PRIMARY KEY,
    channel VARCHAR(50),
    campaign VARCHAR(255),
    utm_campaign VARCHAR(255),
    spend NUMERIC(12,2),
    cost NUMERIC(12,2),
    impressions BIGINT,
    clicks BIGINT,
    conversions INTEGER,
    spend_date DATE,
    created_at TIMESTAMP
);

CREATE TABLE sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id BIGINT,
    customer_id BIGINT,
    anonymous_id VARCHAR(100),
    channel VARCHAR(50),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(255),
    landing_page VARCHAR(500),
    referrer VARCHAR(500),
    device VARCHAR(50),
    is_bot BOOLEAN,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE TABLE stg_orders (
    order_id BIGINT,
    customer_id BIGINT,
    order_status VARCHAR(30),
    gross_amount NUMERIC(12,2),
    net_amount NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    tax_amount NUMERIC(12,2),
    shipping_amount NUMERIC(12,2),
    is_test BOOLEAN,
    ordered_at TIMESTAMP
);

CREATE TABLE stg_customers (
    customer_id BIGINT,
    email VARCHAR(255),
    full_name VARCHAR(200),
    country VARCHAR(100),
    is_active BOOLEAN,
    is_internal BOOLEAN,
    first_order_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE stg_subscriptions (
    subscription_id BIGINT,
    customer_id BIGINT,
    plan VARCHAR(50),
    status VARCHAR(30),
    mrr NUMERIC(10,2),
    started_at TIMESTAMP,
    canceled_at TIMESTAMP
);

CREATE TABLE dim_customers (
    customer_key BIGINT PRIMARY KEY,
    customer_id BIGINT,
    user_id BIGINT,
    email VARCHAR(255),
    full_name VARCHAR(200),
    country VARCHAR(100),
    first_order_date DATE,
    last_order_date DATE,
    total_orders INTEGER,
    ltv NUMERIC(12,2),
    lifetime_revenue NUMERIC(12,2),
    is_active BOOLEAN,
    is_subscriber BOOLEAN,
    is_test BOOLEAN
);

CREATE TABLE dim_products (
    product_key BIGINT PRIMARY KEY,
    product_id BIGINT,
    variant_id BIGINT,
    sku VARCHAR(100),
    title VARCHAR(255),
    product_type VARCHAR(100),
    current_price NUMERIC(10,2),
    unit_cost NUMERIC(10,2),
    is_active BOOLEAN
);

CREATE TABLE fct_orders (
    order_key BIGINT PRIMARY KEY,
    order_id BIGINT,
    customer_key BIGINT,
    customer_id BIGINT,
    order_date DATE,
    status VARCHAR(30),
    gross_revenue NUMERIC(12,2),
    net_revenue NUMERIC(12,2),
    revenue NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    tax_amount NUMERIC(12,2),
    shipping_amount NUMERIC(12,2),
    refund_amount NUMERIC(12,2),
    item_count INTEGER,
    is_first_order BOOLEAN,
    is_test BOOLEAN
);

CREATE TABLE fct_revenue (
    revenue_key BIGINT PRIMARY KEY,
    date_key INTEGER,
    customer_id BIGINT,
    source VARCHAR(50),
    order_revenue NUMERIC(12,2),
    subscription_revenue NUMERIC(12,2),
    gross_revenue NUMERIC(12,2),
    net_revenue NUMERIC(12,2),
    booked_revenue NUMERIC(12,2),
    recognized_revenue NUMERIC(12,2)
);

CREATE VIEW completed_orders AS
SELECT *
FROM orders
WHERE status = 'completed'
  AND is_test = FALSE;

CREATE VIEW paid_orders AS
SELECT o.id,
       o.customer_id,
       o.net_amount,
       o.placed_at
FROM orders o
JOIN payments p ON p.order_id = o.id
WHERE p.status = 'captured'
  AND o.is_internal = FALSE;

CREATE VIEW active_customers AS
SELECT *
FROM customers
WHERE is_active = TRUE;

CREATE VIEW active_subscriptions AS
SELECT *
FROM subscriptions
WHERE state = 'active'
  AND is_test = FALSE;

CREATE VIEW net_revenue_daily AS
SELECT CAST(o.placed_at AS DATE) AS revenue_date,
       SUM(o.net_amount) AS net_revenue,
       SUM(o.gross_amount) AS gross_revenue
FROM orders o
WHERE o.status IN ('completed', 'fulfilled')
  AND o.is_test = FALSE
  AND o.is_internal = FALSE
GROUP BY CAST(o.placed_at AS DATE);
