# Northwind Threads — Data Dictionary / Business Glossary

_Last meaningful update: ~mid-July. Owner: Data team (ping #data-help in Slack, Priya or Marcus usually answer)._

This is the working reference for our warehouse (Snowflake). Raw source data lands via Fivetran
(`RAW.SHOPIFY`, `RAW.STRIPE`, `RAW.RECHARGE`, `RAW.SEGMENT`, ad platforms under `RAW.ADS_*`). Analysts
should mostly query the modelled layer in `ANALYTICS` (dbt marts, `fct_*` / `dim_*`) rather than raw.
Staging models are `stg_*` and are not meant for direct consumption but people use them anyway.

If a definition here disagrees with a dashboard, the dashboard is probably older. Trust the mart, then
trust this doc, then trust the tribal knowledge. Add things as you find them.

---

## Customers & leads

### `dim_customers`
One row per customer account. Populated from Shopify customers plus anyone who signed up through the
site (newsletter, waitlist, checkout). A row exists whether or not the person has ever paid us, so this
is **not** the same as "people who bought something." We exclude internal and test accounts here —
anything on `@northwindthreads.com` or an email containing `+test` is filtered out in the staging model.
Grain: one row per `customer_id`.

### `dim_customers.customer_email`
Primary contact email, lowercased. Unique-ish — we have duplicate emails from the guest-checkout mess in
year one, so join on `customer_id`, never on email. Used for the marketing join to Klaviyo. Note the
physical column is `email` now after the Q1 cleanup; the old name `customer_email` is still aliased in a
couple of staging models so you'll see both.

### `dim_customers.status`
Lifecycle status. One of `active`, `dormant`, `churned`, `deleted` (GDPR erasure sets `deleted` and
nulls the PII). "Active" here means the customer has placed at least one order in the trailing 12 months.
Defaults to `active` on account creation even before the first purchase, so a brand-new lead reads as
active until the nightly job re-scores them.

### `dim_customers.is_active`
Boolean convenience flag. `true` when the customer has purchased in the last 90 days. Growth uses this
one for the "active base" number on the exec dashboard. Slightly redundant with `status` but computed on
a different window, so they won't always agree — is_active is the stricter one.

### `dim_customers.customer_type`
Segment label, one of `lead`, `buyer`, `subscriber`. `lead` = signed up but never completed an order.
`buyer` = has at least one paid order. `subscriber` = has an active Threads Club subscription.
`subscriber` takes precedence, so a customer who both buys one-off and subscribes shows as `subscriber`,
not `buyer`. Recomputed nightly.

### `dim_customers.acquisition_channel`
First-touch marketing channel (paid_search, paid_social, organic, referral, email, direct). Best-effort,
attributed from the first session we can tie to the account. Null for pre-2024 customers, treat null as
`direct` for reporting.

### `dim_customers.first_order_at`
Timestamp of the customer's first paid order. Null for leads. This is our acquisition date for cohorting.
Note it's first *paid* order, so a cancelled or fully-refunded first order does not count and this can be
later than the account creation date by a lot.

### `dim_customers.lifetime_value`
Precomputed LTV, in USD. Sum of net revenue from all the customer's orders to date, minus refunds. Does
**not** include subscription revenue in the current build (known gap, subscription LTV lives in the
Threads Club model). Do not use this for the blended LTV:CAC on the board deck, use the metric below.

### Leads / prospects (`stg_leads`)
People who gave us an email but have no account and no order — waitlist, quiz completions, abandoned
carts that we captured. These are **not** in `dim_customers` unless they later create an account. Marketing
counts them in "audience size"; nobody else should. There's overlap with `dim_customers.customer_type =
'lead'` and it is not deduped cleanly, so do not add the two together.

---

## Orders

### `fct_orders`
One row per order (the header, not the line). Sourced from Shopify orders. Includes one-off purchases
only — subscription renewals are their own thing and are **not** in here (see subscription_charges).
The first box of a new Threads Club sign-up *does* land here as a normal order though, which trips people
up. Grain: one row per `order_id`.

### `fct_orders.status`
Fulfilment/lifecycle status: `pending`, `paid`, `fulfilled`, `cancelled`, `refunded`, `partially_refunded`.
Defaults to `pending` at creation. Most revenue reporting filters to `status in ('paid','fulfilled',
'partially_refunded')`. Cancelled orders are kept in the table for funnel analysis, exclude them for money.

### `fct_orders.order_total`
Gross order value in USD, the amount the customer was charged. **Includes** tax and shipping, after any
discount. This is the number that should tie to Stripe. Growth's "revenue" on the top-line dashboard is
`sum(order_total)` on paid orders, so that top-line figure is tax-inclusive.

### `fct_orders.subtotal`
Merchandise value before discounts, tax and shipping. Sum of the line items. `subtotal - discount_amount
+ tax_amount + shipping_amount` should equal `order_total` (rounding aside; there are a handful of legacy
orders where it doesn't, from a promo engine bug last year).

### `fct_orders.discount_amount`
Total discount applied to the order in USD, as a positive number. If null, treat as 0 — nulls mean no
promo code was used, not missing data.

### `fct_orders.tax_amount` / `shipping_amount`
Sales tax collected and shipping charged to the customer, USD. `tax_amount` can be 0 for tax-exempt
states. Free-shipping promos show 0 in `shipping_amount` (the discount shows in `discount_amount`
instead, not always consistently — depends whether it was a code or an automatic cart rule).

### `fct_orders.net_revenue`
Modelled net revenue for the order: `subtotal - discount_amount`, i.e. merchandise net of discounts,
**excluding** tax and shipping, before returns. This is what Finance means by revenue. Refunds are handled
separately and subtracted at the reporting layer, not here. This column is the one to use for
apples-to-apples revenue across one-off orders.

### `fct_orders.channel`
Sales channel: `web`, `ios`, `retail_popup`, `wholesale`. Renamed from `source` in the spring; some older
dashboards still reference `source` and its values were lowercase-with-dashes (`retail-popup`) so watch
the join. Wholesale orders are B2B and are usually excluded from DTC reporting.

### `fct_orders.placed_at`
Order timestamp (customer's checkout time), UTC. Use this for order-date reporting. There is also a
`created_at` from Shopify which is nearly identical but can differ by a few seconds for orders created via
the admin API. Cohorting and daily revenue use `placed_at`.

### `fct_order_items`
One row per line item within an order. Grain: `order_id` + `line_item_id`. Fields: `product_id`,
`variant_id`, `quantity`, `unit_price` (per-unit list price before discount, USD), `line_total`
(`quantity * unit_price`, before line-level discounts). Bundle products explode into their component
lines here, so `count(*)` overstates "items sold" for bundles.

### `fct_shipments`
One row per physical shipment. An order can split into multiple shipments. `status` one of
`label_created`, `in_transit`, `delivered`, `returned_to_sender`. Defaults to `label_created` when the
label is bought. `shipped_at` is null until the carrier scans it. Use `delivered_at` for delivery SLA
work; it's null until the delivery webhook fires and roughly 3% never fire, so delivery rate tops out
around 97% for data reasons, not real ones.

---

## Returns & refunds

### `fct_returns`
One row per returned item / RMA line. `return_reason` is free-ish text mapped to a small enum
(`sizing`, `quality`, `changed_mind`, `damaged`, `other`). `returned_qty` is the number of units coming
back. A return is the physical goods movement; the money is the refund, and the two do not always match
1:1 (partial refunds, restocking fees).

### `fct_refunds`
One row per refund transaction from Stripe. `refund_amount` USD, positive number. If `refund_amount` is
null the refund is still pending/authorising — treat as 0 for revenue reporting until it settles.
`refunded_at` is settlement time. Note a refund can exceed the original merchandise value because it
includes refunded tax and shipping, so net revenue less refunds can occasionally go slightly negative for
a single order; that's expected.

### Return rate
Units returned divided by units shipped over a period. Ops reports it on `returned_at`. Finance reports a
$-weighted version (refund_amount / net_revenue) and calls it "refund rate," which is a different number,
so always check which one a chart means.

---

## Products

### `dim_products`
One row per product (the sellable concept, not the SKU). `product_id`, `title`, `category`, `brand_line`,
`is_active` (currently sold). `category` is one of `tops`, `bottoms`, `outerwear`, `accessories`. Merch
adds new categories faster than we update this doc, so trust the actual distinct values in the column over
this list.

### `dim_product_variants`
One row per SKU. `variant_id`, `product_id`, `sku`, `size`, `color`, `cost` (our landed unit cost, USD,
used for margin). `cost` is null for older SKUs; margin calcs coalesce it to 0 which inflates margin, be
aware. `sku` is the source of truth for inventory joins.

---

## Threads Club (subscriptions)

The subscription box launched last year and was bolted onto the order model. Terminology here drifts from
the orders side; a Threads Club member is a "subscriber," their monthly charge is a "renewal," and their
recurring value is MRR, none of which map cleanly onto `fct_orders`.

### `dim_subscriptions`
One row per subscription (from Recharge). A customer can have more than one (rare). `status` one of
`active`, `paused`, `cancelled`, `trialing`. **Active** here means the subscription is currently billing —
this is the meaning of "active subscriber." Note this is a different test than
`dim_customers.is_active`, which is about recent one-off purchase, so "active customers" and "active
subscribers" are counted differently and won't reconcile.

### `dim_subscriptions.plan_interval`
Billing interval, `monthly` or `annual`. Defaults to `monthly` if the source is missing it (almost never
happens now). Older records use the column name `billing_cycle` with values `month`/`year`; the staging
model normalises them but you'll still see `billing_cycle` in a few dashboards.

### `dim_subscriptions.mrr_amount`
Monthly recurring revenue contributed by this subscription, USD. For monthly plans it's the plan price.
For annual plans it's the annual price divided by 12. This is the normalised view used for the MRR chart.

### `fct_subscription_events`
Event log for subscriptions: `created`, `renewed`, `paused`, `resumed`, `cancelled`, `reactivated`,
`churned`. One row per event. Churn is derived: a `cancelled` event becomes `churned` in this table.
`subscription_charges` (the actual money) is separate.

### `fct_subscription_charges`
One row per successful recurring charge (renewal). This is where subscription revenue actually lives.
`charge_amount` is the amount billed for that period, USD, tax-inclusive. The first-box charge for a new
member lands in `fct_orders` instead of here, so do not double count month one.

### Active subscriber
A member with `dim_subscriptions.status = 'active'`. Paused members are **not** active. Trialing members
are counted as active on the growth dashboard but not in Finance's MRR (they're not billing yet), so the
active-subscriber count and the paying-subscriber count differ by the trial cohort.

### Subscription churn rate
Cancelled subscriptions in the period divided by active subscriptions at the start of the period. The
metrics layer uses a slightly stricter version: a member counts as churned only if they cancelled **and**
did not reactivate within 30 days, so the mart churn number runs a bit lower than the raw event count.

---

## Payments & invoices

### `fct_payments`
One row per Stripe charge/payment attempt across both one-off orders and subscriptions. `amount` is what
was captured, USD, tax-inclusive (this is money movement, not accounting revenue). `status`:
`succeeded`, `failed`, `refunded`, `disputed`. Failed payments are retained for dunning analysis.

### `fct_invoices`
Finance-side invoices, mostly for wholesale and annual subscriptions. `invoice_total` is inclusive of tax.
"**Booked** revenue" is the sum of invoiced amounts in the period the invoice is *issued*, regardless of
when the service is delivered — so an annual Threads Club plan books the full year in the sign-up month.
This is what the board deck's bookings number uses.

---

## Discounts & marketing

### `dim_discounts`
One row per promo code or automatic discount rule. `discount_type` (`percent`, `fixed`, `free_shipping`),
`value`, `starts_at`, `ends_at`. Redemption counts live on the order side, not here. Automatic cart-level
discounts don't always have a code, so `code` can be null.

### `fct_marketing_spend`
Daily ad spend by channel and campaign, unioned from Meta, Google, TikTok. Grain: `date` + `channel` +
`campaign_id`. `spend` is USD, gross of platform fees. `channel` is null for a small amount of
un-tagged spend — coalesce null to `unattributed`. This feeds CAC. Spend is reported on the platform's
attribution date, which is not the same as our order date, so day-level ROAS is noisy; use weekly.

### `fct_sessions`
Web sessions from Segment. `session_id`, `anonymous_id`, `customer_id` (null until they identify),
`landing_page`, `utm_*`, `started_at`. Used for funnel and first-touch attribution. Bot traffic is
filtered in staging but not perfectly. Marketing's "active users" is a session in the last 30 days, which
is yet another meaning of "active," unrelated to the customer/subscriber ones above.

---

## Business metrics & definitions

These are the numbers people ask for by name. Where two teams compute something differently, both are
listed because both get used.

### Revenue (net) — Finance default
`sum(fct_orders.net_revenue)` on orders with `status in ('paid','fulfilled','partially_refunded')`, minus
settled refunds, for the period. Net of discounts and returns, **excludes tax and shipping**. This is the
revenue number in the monthly finance pack and the one to use unless told otherwise.

### Revenue (gross / GMV) — Growth default
`sum(fct_orders.order_total)` on paid orders. Includes tax, shipping, and is before returns. This is the
"revenue" on the growth top-line dashboard and it runs meaningfully higher than the Finance number. When
someone says "we did $X in revenue this month" it's usually this one.

### Booked vs recognised revenue
**Booked** = invoiced/charged amount in the period it's transacted (annual subs and wholesale book the
full amount up front). **Recognised** = spread over the delivery period (an annual sub recognises 1/12
per month). Finance reports recognised for the P&L; the bookings/GMV numbers everyone quotes in standups
are booked. These will not tie out and are not supposed to.

### Subscription revenue
`sum(fct_subscription_charges.charge_amount)` for renewals in the period, plus the month-one order for new
members (which sits in `fct_orders`). Tax-inclusive. Do not confuse with **MRR**, which is a normalised
run-rate (`sum(dim_subscriptions.mrr_amount)` over active subs), not actual cash collected.

### Total revenue
One-off order revenue plus subscription revenue. Beware the basis: the blended number on the exec
dashboard adds gross order revenue (tax-inclusive) to subscription charges (tax-inclusive), while the
finance total uses net order revenue plus recognised subscription revenue. Same label, two builds.

### AOV (average order value)
`sum(order_total) / count(distinct order_id)` on paid, non-wholesale orders. Uses gross order_total, so
AOV is tax-inclusive. Some product dashboards compute it on net_revenue instead and get a lower number.

### Customer (count)
Distinct `customer_id` in `dim_customers`. When people say "how many customers do we have" they usually
mean **buyers** — accounts with at least one paid order (`customer_type in ('buyer','subscriber')`) — not
the raw account count, which includes leads. The finance customer count also strips test accounts; the
growth one occasionally doesn't, so the two land a few hundred apart.

### Buyer vs subscriber
**Buyer** = at least one completed one-off order, ever. **Subscriber** = active Threads Club membership.
Overlapping sets: a subscriber is usually also a buyer. "Members" always means subscribers. "Customers"
is ambiguous — ask.

### Active customer
The one everyone argues about. Three live definitions:
- Finance / metrics layer: `status = 'active'` **and** at least one order in the trailing 12 months.
- Growth exec dashboard: `is_active = true`, i.e. purchased in the last 90 days.
- Lifecycle/CRM: any account that opened an email or logged a session in the last 30 days.
They differ by roughly 2x between the 90-day and 12-month versions. State the window when you report it.

### LTV (lifetime value)
Board version: cumulative **net** revenue per acquired customer, including subscription revenue,
by acquisition cohort, minus refunds, undiscounted (no NPV). The precomputed
`dim_customers.lifetime_value` column is order-only and net, so it's lower — don't use the column for the
board LTV:CAC.

### CAC (customer acquisition cost)
`sum(fct_marketing_spend.spend)` in the period divided by new customers acquired in the same period. "New
customers" = accounts with `first_order_at` in the period. Blended (all spend / all new customers); we do
not have reliable paid-only CAC because organic and paid attribution is fuzzy. Spend is gross of platform
fees, so true CAC is a touch higher.

### Repeat purchase rate
Share of buyers who have placed 2 or more orders. The retention dashboard measures this within the first
90 days of the first order. The metrics layer measures it over a trailing 12-month window across all
buyers. Different windows, different denominators, so the two "repeat rate" tiles won't match.

### Churn rate
For subscriptions: see Subscription churn rate above. There is no agreed one-off "customer churn" number;
people proxy it with the inverse of the active-customer count, which inherits whichever active definition
they picked.

### Retention (cohort)
Percentage of an acquisition cohort still active in month N. "Active" here means placed an order in month
N (order retention), not the `status`/`is_active` flags. Subscription retention is tracked separately off
`fct_subscription_events` and is not the same curve.

### ROAS
Revenue attributed to ads divided by ad spend. Numerator is platform-attributed revenue (tax-inclusive,
last-click on the platform's own attribution), denominator is `fct_marketing_spend.spend`. This
disagrees with our internal first-touch model, so blended ROAS from the warehouse and ROAS from Meta
Ads Manager will never match. Report the warehouse one for internal decisions.
