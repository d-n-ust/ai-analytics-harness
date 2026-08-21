-- Harborstone Market data warehouse
-- schema.sql

-- =====================================================================
-- RAW / SOURCE
-- =====================================================================

CREATE TABLE store_sales_daily (
    store_id            INTEGER,
    biz_date            DATE,
    dept                VARCHAR(40),
    sales               NUMERIC(14,2),
    units               INTEGER,
    txn_count           INTEGER,
    gross_margin        NUMERIC(14,2),
    is_comp             CHAR(1),
    comp_flag           BOOLEAN,
    labor_hours         NUMERIC(8,2),
    load_ts             TIMESTAMP
);

CREATE TABLE stores (
    store_id            INTEGER PRIMARY KEY,
    store_code          VARCHAR(10),
    store_name          VARCHAR(120),
    region              VARCHAR(60),
    banner              VARCHAR(60),
    store_format        VARCHAR(40),
    square_feet         INTEGER,
    open_date           DATE,
    close_date          DATE,
    remodel_date        DATE,
    comparable          BOOLEAN,
    status              VARCHAR(20)
);

CREATE TABLE pos_transactions (
    transaction_id      BIGINT PRIMARY KEY,
    txn_id              VARCHAR(40),
    basket_id           VARCHAR(40),
    location_id         INTEGER,
    register_no         INTEGER,
    cashier_id          INTEGER,
    business_date       DATE,
    txn_ts              TIMESTAMP,
    member_id           BIGINT,
    total               NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    tax_amount          NUMERIC(12,2),
    discount_amount     NUMERIC(12,2),
    tender_type         VARCHAR(20),
    txn_status          VARCHAR(20),
    void_flag           BOOLEAN
);

CREATE TABLE pos_line_items (
    line_id             BIGINT PRIMARY KEY,
    transaction_id      BIGINT,
    basket_id           VARCHAR(40),
    line_no             INTEGER,
    sku                 VARCHAR(30),
    qty                 NUMERIC(10,3),
    unit_price          NUMERIC(12,4),
    extended_price      NUMERIC(14,2),
    line_amount         NUMERIC(14,2),
    markdown_amount     NUMERIC(12,2),
    promo_id            INTEGER,
    unit_cost           NUMERIC(12,4),
    void_flag           BOOLEAN
);

CREATE TABLE online_orders (
    order_id            BIGINT PRIMARY KEY,
    order_number        VARCHAR(30),
    customer_id         BIGINT,
    loyalty_id          VARCHAR(30),
    site_id             INTEGER,
    fulfillment_store   INTEGER,
    order_ts            TIMESTAMP,
    order_date          DATE,
    channel             VARCHAR(20),
    fulfillment_type    VARCHAR(20),
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    shipping_amount     NUMERIC(12,2),
    tax                 NUMERIC(12,2),
    discount_total      NUMERIC(12,2),
    order_status        VARCHAR(30),
    is_comp             BOOLEAN
);

CREATE TABLE online_order_lines (
    order_line_id       BIGINT PRIMARY KEY,
    order_id            BIGINT,
    order_number        VARCHAR(30),
    sku                 VARCHAR(30),
    product_id          BIGINT,
    quantity            NUMERIC(10,3),
    price               NUMERIC(12,4),
    amount              NUMERIC(14,2),
    line_discount       NUMERIC(12,2),
    landed_cost         NUMERIC(12,4),
    substituted_flag    BOOLEAN,
    status              VARCHAR(20)
);

CREATE TABLE products (
    product_id          BIGINT PRIMARY KEY,
    sku                 VARCHAR(30),
    upc                 VARCHAR(20),
    product_name        VARCHAR(200),
    brand               VARCHAR(80),
    category_id         INTEGER,
    department_id       INTEGER,
    size_desc           VARCHAR(40),
    uom                 VARCHAR(12),
    standard_cost       NUMERIC(12,4),
    last_cost           NUMERIC(12,4),
    retail_price        NUMERIC(12,4),
    active_flag         BOOLEAN,
    private_label       BOOLEAN
);

CREATE TABLE categories (
    category_id         INTEGER PRIMARY KEY,
    category_name       VARCHAR(120),
    department_id       INTEGER,
    dept_name           VARCHAR(120)
);

CREATE TABLE departments (
    department_id       INTEGER PRIMARY KEY,
    department_name     VARCHAR(120),
    division            VARCHAR(80)
);

CREATE TABLE suppliers (
    supplier_id         INTEGER PRIMARY KEY,
    supplier_code       VARCHAR(20),
    supplier_name       VARCHAR(160),
    lead_time_days      INTEGER,
    active              BOOLEAN,
    status              VARCHAR(20)
);

CREATE TABLE purchase_orders (
    po_id               BIGINT PRIMARY KEY,
    po_number           VARCHAR(30),
    supplier_id         INTEGER,
    location_id         INTEGER,
    order_date          DATE,
    expected_date       DATE,
    po_status           VARCHAR(20),
    total_cost          NUMERIC(16,2),
    total_units         INTEGER
);

CREATE TABLE po_lines (
    po_line_id          BIGINT PRIMARY KEY,
    po_id               BIGINT,
    po_number           VARCHAR(30),
    sku                 VARCHAR(30),
    ordered_qty         NUMERIC(12,3),
    received_qty        NUMERIC(12,3),
    unit_cost           NUMERIC(12,4),
    landed_cost         NUMERIC(12,4),
    line_status         VARCHAR(20)
);

CREATE TABLE po_receipts (
    receipt_id          BIGINT PRIMARY KEY,
    po_id               BIGINT,
    po_number           VARCHAR(30),
    site_id             INTEGER,
    sku                 VARCHAR(30),
    received_qty        NUMERIC(12,3),
    receipt_date        DATE,
    receipt_ts          TIMESTAMP
);

CREATE TABLE inventory_snapshot (
    snapshot_id         BIGINT PRIMARY KEY,
    store_id            INTEGER,
    sku                 VARCHAR(30),
    snapshot_date       DATE,
    on_hand             NUMERIC(12,3),
    qty_on_hand         NUMERIC(12,3),
    available_qty       NUMERIC(12,3),
    in_transit          NUMERIC(12,3),
    on_order            NUMERIC(12,3),
    unit_cost           NUMERIC(12,4),
    standard_cost       NUMERIC(12,4)
);

CREATE TABLE inventory_shrink (
    shrink_id           BIGINT PRIMARY KEY,
    location_id         INTEGER,
    sku                 VARCHAR(30),
    shrink_date         DATE,
    reason_code         VARCHAR(20),
    qty                 NUMERIC(12,3),
    cost                NUMERIC(14,2),
    markdown_flag       BOOLEAN
);

CREATE TABLE loyalty_members (
    member_id           BIGINT PRIMARY KEY,
    customer_id         BIGINT,
    loyalty_id          VARCHAR(30),
    email               VARCHAR(200),
    enroll_date         DATE,
    enrolled_flag       BOOLEAN,
    active_flag         BOOLEAN,
    points_balance      INTEGER,
    home_store          INTEGER,
    member_status       VARCHAR(20)
);

CREATE TABLE loyalty_points_ledger (
    ledger_id           BIGINT PRIMARY KEY,
    member_id           BIGINT,
    loyalty_id          VARCHAR(30),
    txn_date            DATE,
    points_earned       INTEGER,
    points_redeemed     INTEGER,
    transaction_id      BIGINT
);

CREATE TABLE promotions (
    promo_id            INTEGER PRIMARY KEY,
    promo_code          VARCHAR(30),
    promo_name          VARCHAR(160),
    promo_type          VARCHAR(30),
    start_date          DATE,
    end_date            DATE,
    discount_pct        NUMERIC(6,3),
    funded_by           VARCHAR(30),
    status              VARCHAR(20)
);

CREATE TABLE returns_raw (
    return_id           BIGINT PRIMARY KEY,
    original_txn_id     VARCHAR(40),
    transaction_id      BIGINT,
    order_id            BIGINT,
    store_id            INTEGER,
    sku                 VARCHAR(30),
    return_date         DATE,
    return_qty          NUMERIC(10,3),
    refund_amount       NUMERIC(14,2),
    reason_code         VARCHAR(20),
    return_status       VARCHAR(20)
);

CREATE TABLE employees (
    employee_id         INTEGER PRIMARY KEY,
    store_id            INTEGER,
    role                VARCHAR(60),
    hire_date           DATE,
    active              BOOLEAN
);

CREATE TABLE labor_hours (
    labor_id            BIGINT PRIMARY KEY,
    employee_id         INTEGER,
    location_id         INTEGER,
    work_date           DATE,
    hours               NUMERIC(8,2),
    hours_worked        NUMERIC(8,2),
    labor_cost          NUMERIC(12,2)
);

-- =====================================================================
-- STAGING
-- =====================================================================

CREATE TABLE stg_transactions (
    txn_id              VARCHAR(40),
    basket_id           VARCHAR(40),
    store_id            INTEGER,
    business_date       DATE,
    member_id           BIGINT,
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    tax_amount          NUMERIC(12,2),
    discount_amount     NUMERIC(12,2),
    units               NUMERIC(12,3),
    status              VARCHAR(20),
    void_flag           BOOLEAN
);

CREATE TABLE stg_line_items (
    line_id             BIGINT,
    txn_id              VARCHAR(40),
    basket_id           VARCHAR(40),
    sku                 VARCHAR(30),
    product_id          BIGINT,
    qty                 NUMERIC(10,3),
    unit_price          NUMERIC(12,4),
    line_amount         NUMERIC(14,2),
    extended_price      NUMERIC(14,2),
    markdown_amount     NUMERIC(12,2),
    unit_cost           NUMERIC(12,4),
    landed_cost         NUMERIC(12,4),
    void_flag           BOOLEAN
);

CREATE TABLE stg_orders (
    order_id            BIGINT,
    order_number        VARCHAR(30),
    customer_id         BIGINT,
    site_id             INTEGER,
    fulfillment_store   INTEGER,
    order_date          DATE,
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    units               NUMERIC(12,3),
    order_status        VARCHAR(30)
);

CREATE TABLE stg_inventory (
    store_id            INTEGER,
    sku                 VARCHAR(30),
    snapshot_date       DATE,
    qty_on_hand         NUMERIC(12,3),
    available_qty       NUMERIC(12,3),
    in_transit          NUMERIC(12,3),
    unit_cost           NUMERIC(12,4)
);

CREATE TABLE stg_products (
    product_id          BIGINT,
    sku                 VARCHAR(30),
    product_name        VARCHAR(200),
    category_id         INTEGER,
    department_id       INTEGER,
    standard_cost       NUMERIC(12,4),
    landed_cost         NUMERIC(12,4),
    retail_price        NUMERIC(12,4)
);

-- =====================================================================
-- MARTS
-- =====================================================================

CREATE TABLE dim_store (
    store_key           INTEGER PRIMARY KEY,
    store_id            INTEGER,
    location_id         INTEGER,
    store_name          VARCHAR(120),
    region              VARCHAR(60),
    banner              VARCHAR(60),
    store_format        VARCHAR(40),
    open_date           DATE,
    is_comparable       BOOLEAN
);

CREATE TABLE dim_product (
    product_key         INTEGER PRIMARY KEY,
    product_id          BIGINT,
    sku                 VARCHAR(30),
    product_name        VARCHAR(200),
    category_id         INTEGER,
    category_name       VARCHAR(120),
    department_id       INTEGER,
    department_name     VARCHAR(120),
    standard_cost       NUMERIC(12,4),
    landed_cost         NUMERIC(12,4)
);

CREATE TABLE dim_customer (
    customer_key        INTEGER PRIMARY KEY,
    customer_id         BIGINT,
    member_id           BIGINT,
    loyalty_id          VARCHAR(30),
    enroll_date         DATE,
    active_flag         BOOLEAN,
    home_store          INTEGER
);

CREATE TABLE dim_date (
    date_key            INTEGER PRIMARY KEY,
    calendar_date       DATE,
    fiscal_week         INTEGER,
    fiscal_period       INTEGER,
    fiscal_year         INTEGER,
    day_of_week         INTEGER,
    is_holiday          BOOLEAN
);

CREATE TABLE fct_transactions (
    txn_key             BIGINT PRIMARY KEY,
    transaction_id      BIGINT,
    basket_id           VARCHAR(40),
    store_key           INTEGER,
    store_id            INTEGER,
    date_key            INTEGER,
    business_date       DATE,
    member_id           BIGINT,
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    tax_amount          NUMERIC(12,2),
    discount_amount     NUMERIC(12,2),
    units               NUMERIC(12,3),
    basket_size         NUMERIC(12,3),
    status              VARCHAR(20),
    is_comp             BOOLEAN
);

CREATE TABLE fct_sales_line (
    sales_line_key      BIGINT PRIMARY KEY,
    transaction_id      BIGINT,
    order_id            BIGINT,
    basket_id           VARCHAR(40),
    store_key           INTEGER,
    product_key         INTEGER,
    date_key            INTEGER,
    channel             VARCHAR(20),
    qty                 NUMERIC(12,3),
    quantity            NUMERIC(12,3),
    unit_price          NUMERIC(12,4),
    extended_price      NUMERIC(14,2),
    line_amount         NUMERIC(14,2),
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    markdown_amount     NUMERIC(12,2),
    unit_cost           NUMERIC(12,4),
    landed_cost         NUMERIC(12,4),
    standard_cost       NUMERIC(12,4),
    gross_margin        NUMERIC(14,2)
);

CREATE TABLE fct_orders (
    order_key           BIGINT PRIMARY KEY,
    order_id            BIGINT,
    order_number        VARCHAR(30),
    customer_key        INTEGER,
    site_id             INTEGER,
    store_key           INTEGER,
    date_key            INTEGER,
    order_date          DATE,
    gross_sales         NUMERIC(14,2),
    net_sales           NUMERIC(14,2),
    amount              NUMERIC(14,2),
    units               NUMERIC(12,3),
    fulfillment_type    VARCHAR(20),
    order_status        VARCHAR(30)
);

CREATE TABLE fct_inventory_daily (
    inv_key             BIGINT PRIMARY KEY,
    store_key           INTEGER,
    store_id            INTEGER,
    product_key         INTEGER,
    sku                 VARCHAR(30),
    date_key            INTEGER,
    snapshot_date       DATE,
    on_hand             NUMERIC(12,3),
    qty_on_hand         NUMERIC(12,3),
    available_qty       NUMERIC(12,3),
    in_transit          NUMERIC(12,3),
    on_order            NUMERIC(12,3),
    unit_cost           NUMERIC(12,4),
    standard_cost       NUMERIC(12,4),
    inventory_value     NUMERIC(16,2)
);

CREATE TABLE fct_returns (
    return_key          BIGINT PRIMARY KEY,
    return_id           BIGINT,
    transaction_id      BIGINT,
    order_id            BIGINT,
    store_key           INTEGER,
    product_key         INTEGER,
    date_key            INTEGER,
    return_qty          NUMERIC(10,3),
    refund_amount       NUMERIC(14,2),
    reason_code         VARCHAR(20),
    return_status       VARCHAR(20)
);

-- =====================================================================
-- VIEWS
-- =====================================================================

CREATE VIEW v_comp_store_sales AS
SELECT
    d.store_id,
    d.biz_date,
    d.dept,
    d.sales,
    d.units,
    d.gross_margin
FROM store_sales_daily d
WHERE d.is_comp = 'Y';

CREATE VIEW v_settled_transactions AS
SELECT
    t.transaction_id,
    t.basket_id,
    t.location_id,
    t.business_date,
    t.member_id,
    t.net_sales,
    t.total,
    t.tax_amount,
    t.discount_amount
FROM pos_transactions t
WHERE t.txn_status = 'settled'
  AND t.void_flag = false;

CREATE VIEW v_net_sales AS
SELECT
    f.store_key,
    f.date_key,
    SUM(f.net_sales) AS net_sales,
    SUM(f.units) AS units
FROM fct_transactions f
WHERE f.status = 'settled'
  AND f.is_comp = true
GROUP BY f.store_key, f.date_key;

CREATE VIEW v_active_members AS
SELECT
    m.member_id,
    m.customer_id,
    m.loyalty_id,
    m.enroll_date,
    m.points_balance,
    m.home_store
FROM loyalty_members m
WHERE m.active_flag = true
  AND m.enrolled_flag = true;

CREATE VIEW v_valid_line_items AS
SELECT
    l.line_id,
    l.transaction_id,
    l.basket_id,
    l.sku,
    l.qty,
    l.unit_price,
    l.extended_price,
    l.line_amount,
    l.unit_cost
FROM pos_line_items l
WHERE l.void_flag = false;

CREATE VIEW v_available_inventory AS
SELECT
    i.store_id,
    i.sku,
    i.snapshot_date,
    i.available_qty,
    i.in_transit
FROM inventory_snapshot i
WHERE i.available_qty > 0;
