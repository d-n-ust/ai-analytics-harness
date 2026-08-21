# Harborstone Market — Data Dictionary / Business Glossary

_Last real update: end of Q2 (someone please refresh the loyalty section). Owner: Analytics (ping
#data-questions, Dana or Reggie usually pick it up). Fiscal calendar is retail 4-5-4 — "period" means a
fiscal period, not a calendar month._

Working reference for the warehouse (Redshift, `harborstone` cluster). Raw data lands a few different
ways: a nightly batch from the POS (NCR) into `raw_pos`, Fivetran for the e-commerce platform into
`raw_ecom` and for the loyalty platform into `raw_loyalty`, and a weekly extract from the merchandising /
ERP system into `raw_merch`. The old store-ops spreadsheets were loaded once into the `store_ops` schema
and are still hand-refreshed by someone in Finance most Mondays. Analysts should query the modelled layer
in `analytics` (`fct_*` / `dim_*`); `stg_*` are staging and not meant for direct use, but people use them.

If this doc disagrees with a dashboard, the dashboard is usually older. Trust the mart, then this doc,
then whatever's pinned in Slack. Add things as you find them.

---

## Stores, regions & banners

### `dim_store`
One row per physical store. `store_id` is the warehouse key; `store_number` is the four-digit number
everyone actually says out loud. Also carries `banner`, `region`, `district`, `format`, `square_feet`
(total, not selling floor), `open_date`, and `status`. Grain: one row per `store_id`. Online is **not**
a store here — the web channel has a synthetic store_number of `9999` in some rollups and is left out
entirely in others, so store counts move around depending on the report.

### `dim_store.banner`
The brand/format the store trades under: `HM` (Harborstone Market, full supermarket), `HX` (Harborstone
Express, small-format convenience), `HG` (Harborstone General, the larger grocery + general-merchandise
superstores). Banner is the concept; a store belongs to exactly one. Note people say "banner" loosely to
mean the format too, so "the Express banner" and "the express format" usually mean the same thing but not
always — HG stores come in two footprints and only the bigger one is really a superstore.

### `dim_store.region` / `dim_store.district`
`region` is the geographic rollup used in the leadership scorecard — historically five: `North Coast`,
`Bay`, `Inland`, `Valley`, `South`. After the Inland reorg last year it's really six (Inland split into
`Inland` and `High Desert`) but a lot of dashboards still group to the old five. `district` is the smaller
ops grouping a store manager rolls up to; there are ~14 districts. When a report says "by region" check
whether it's actually grouping on `district` — the ops weekly does, and mislabels it.

### `dim_store.comp_flag`
Boolean, whether the store counts as comparable ("comp" / same-store) for year-over-year sales. Set
`true` once a store has traded a full thirteen fiscal periods, i.e. it was open before the start of the
prior fiscal year. This is Finance's rule and this column follows Finance. Remodels and relocations don't
clear the flag here even though the merch team thinks they should. Recomputed at period close.

### `store_ops.store_master`
The legacy store list from the old store-ops spreadsheets. Predates `dim_store` and still gets
hand-edited. Uses the old three-letter store codes (`NCB`, `BAY01`, …) that don't join cleanly to
`store_id` — there's a crosswalk in `store_ops.store_xref` that's about 95% complete. Square footage here
is *selling floor* not total, so it disagrees with `dim_store.square_feet`. Only use this table if you
need a store attribute that never got migrated (lease type, remodel dates).

---

## Transactions, baskets & online orders (POS)

### `fct_transactions`
One row per completed in-store POS transaction — one basket, one trip through the register. "Basket" and
"transaction" are used interchangeably across the team. Grain: `transaction_id`. Carries `store_id`,
`register_id`, `cashier_id`, `business_date`, `transaction_ts`, `member_id`, and the money columns below.
POS only — online orders are their own table. (A blended "all-channel transactions" view was bolted on
last quarter that unions online orders in, which is why some transaction counts include web and some
don't.) Suspended and voided transactions are excluded here; the register audit still counts them, so
store-level transaction counts from ops run a little higher than ours.

### `fct_transactions.gross_sales`
Total merchandise rung at the register for the basket, in USD, **before** returns and markdowns and
**excluding** sales tax. This is what Merchandising means when they say "sales." Line-level discounts
(the price already knocked down at the register) are reflected in the rung price, but post-sale markdown
allocations are not. This is the number the merch daily flash runs on.

### `fct_transactions.net_sales`
Gross less returns and less markdown/promo allocations booked back to the basket, USD. Net of tax. This
is Finance's revenue basis at the transaction level. In practice returns are matched to the *original*
basket where we can identify it, so a heavy return day can push an individual store's net_sales below its
gross by more than that day's own returns. Older partitions (before the summer refactor) still have tax
folded into this column, so trailing-year comparisons on net_sales can be off by the tax rate — check the
partition date.

### `fct_transactions.tax_amount`
Sales tax collected on the basket, USD. Varies by store jurisdiction. Zero on fully tax-exempt baskets
(WIC, some resale). `gross_sales + tax_amount` is roughly what the customer paid, before any tender-level
rounding.

### `fct_transactions.status`
Transaction disposition: `completed`, `voided`, `suspended`, `training`. Defaults to `completed` — the
POS only sends us finalized baskets in the nightly batch, so anything not explicitly flagged is treated as
a completed sale. `training` rows are register-training baskets and should always be excluded from sales;
they're not always excluded in the older views.

### `fct_transactions.member_id`
Loyalty account tied to the basket, or null for a non-loyalty (unidentified) sale. Foreign key to
`dim_member`. This column used to be called `loyalty_id` and before that `rewards_id`; both aliases still
show up in staging and a couple of dashboards. Attach rate ("loyalty penetration") is baskets with a
non-null `member_id` over all baskets.

### `fct_transaction_lines`
One row per basket line — one scanned item/price on the receipt. Grain: `transaction_id` + `line_no`.
Fields: `sku`, `department_id`, `quantity`, `unit_retail`, `extended_retail` (`quantity * unit_retail`
before line discount), `discount_amount` (positive; **if null treat as 0**, null means no discount not
missing). Units = `sum(quantity)`. Careful: weighed items (produce, deli, bulk) carry weight in
`quantity` (pounds), not a count of eaches, so summing `quantity` for a "units sold" number mixes pounds
and pieces. One physical item sold as a multi-buy ("3 for $5") can also be one line with quantity 3 or
three lines with quantity 1 depending on the register program.

### `fct_online_orders`
One row per online order (click-and-collect and delivery), from `raw_ecom`. Grain: `order_id`. This is the
web analogue of a basket but the model is different — an order has a `fulfillment_type`
(`pickup` / `delivery`), a `fulfillment_store_id` (the store that picks it), and its own `order_status`.
Money columns mirror the POS ones (`gross_sales`, `net_sales`) but online `gross_sales` is captured
*after* substitutions and out-of-stocks are resolved, so it reflects what was actually fulfilled, not what
was ordered. Whether these rows count as "transactions" depends on the report (see `fct_transactions`).

### `fct_online_orders.order_status`
`cart`, `placed`, `picking`, `fulfilled`, `cancelled`, `refunded`. Defaults to `placed` on submission.
Revenue reporting filters to `fulfilled` (and `refunded` for the return side). `cart` rows are abandoned
baskets kept for funnel work — never money. `picking` orders have been paid-authorized but not yet
handed over, so same-day cutoffs can leave revenue sitting in `picking` at period close.

### `fct_order_lines`
One row per online order line. Grain: `order_id` + `line_no`. Same shape as `fct_transaction_lines`
(`sku`, `quantity`, `unit_retail`, `extended_retail`). Substituted items show the substitute's SKU with
an `is_substitution` flag; the originally-ordered SKU is only kept in `raw_ecom`, so lost-sales analysis
on subs has to go back to raw.

### `store_ops.daily_sales`
Legacy one-row-per-store-per-day sales table from the old spreadsheets, still refreshed by Finance. `sales`
here is the gross figure rung at the register and it **includes sales tax** (the old registers reported
tax-in). This is the number in the long-running "sales by store" spreadsheet leadership has watched for
years, so it's referenced constantly even though it doesn't tie to `fct_transactions.gross_sales` (which
is tax-exclusive) or to net. Use the POS model for anything new; this is here because people still pull it.

---

## Products & merchandise hierarchy

### `dim_product`
One row per SKU — the sellable unit, keyed by `sku`. Carries `upc`, `description`, `department_id`,
`category`, `subcategory`, `brand`, `size`, `uom` (each / lb / ct), `is_private_label`, and the cost
columns below. Grain: one row per `sku`. Some UPCs map to more than one `sku` after vendor pack changes;
join inventory and sales on `sku`, not `upc`.

### `dim_product` cost columns (`landed_cost`, `standard_cost`, `last_cost`)
Three costs live on the product, all USD per selling unit, and margin depends on which you pick.
`landed_cost` is delivered cost including freight and allowances — Finance uses this for reported gross
margin. `standard_cost` is the planning cost merchandising sets each season and holds flat — the merch
margin reports use this one, so merch and finance margin never quite agree. `last_cost` is the most recent
PO cost and drifts with every receipt. Any of the three can be null on newer or one-off SKUs; the margin
models coalesce a null cost to 0, which shows those items at ~100% margin, so watch for suspiciously high
margin on new items.

### `dim_department`
The merchandise hierarchy: `department_id` → `category` → `subcategory`, plus a `division` roll-up
(Grocery, Fresh, General Merchandise, Pharmacy). One row per department. The `category`/`subcategory`
strings on `dim_product` are supposed to match this table but merch adds and renames categories faster
than either gets updated, so trust the distinct values in the data over any list written down here.

---

## Inventory

### `fct_inventory_snapshot`
Daily snapshot of inventory by store and SKU. Grain: `store_id` + `sku` + `snapshot_date`. The headline
column is `on_hand` — the physical unit count we believe is in the building (from perpetual inventory,
corrected at each physical count). `on_hand` can go negative between a sale and its receipt posting; those
are real and usually self-correct, don't filter them out blindly. Snapshot is taken after the nightly
close, so intraday it's stale.

### `fct_inventory_snapshot.available`
`on_hand` minus `reserved`, where `reserved` is units held for online pick orders and customer holds not
yet rung. **If `reserved` is null treat it as 0**, so `available` equals `on_hand` for stores with no
online picking. This is the number the e-commerce site uses to decide what it can promise. It is a
different number from `on_hand`, and "in stock" means `available > 0` on the site but usually means
`on_hand > 0` in a store-ops conversation.

### `fct_inventory_snapshot.in_transit` / `on_order`
`on_order` is units on an open purchase order not yet received; `in_transit` is the subset that has
shipped from the supplier/DC and is on its way. "Owned inventory" in the buying reports means
`on_hand + in_transit` (some buyers use `on_hand + on_order`), so the same store's inventory reads three
ways depending on which report you're in: on-hand, available, or owned. State which one when you quote an
inventory number.

### `fct_inventory_receipts`
One row per received PO line — goods physically booked into a store/DC. Grain: `receipt_id` + `line_no`.
Fields: `sku`, `store_id`, `po_id`, `received_qty`, `received_cost` (the actual landed cost on that
receipt, which is what feeds `last_cost`), `received_ts`. A receipt reduces `on_order` and increases
`on_hand`; the two don't always move on the same night, so end-of-period owned-inventory can double-count
a receipt for a day.

---

## Suppliers & purchase orders

### `dim_supplier`
One row per supplier/vendor, keyed by `supplier_id`. Carries `supplier_name`, `vendor_number` (the ERP
number buyers use), `is_dsd` (direct-store-delivery vs warehouse-shipped), and default lead time. DSD
suppliers (bread, soda, chips) deliver straight to stores and their receipts don't flow through a PO the
same way, so DSD volume is thin in `fct_purchase_orders` and shows up mainly as receipts.

### `fct_purchase_orders`
Purchase order headers. Grain: `po_id`. Fields: `supplier_id`, `ship_to` (store or DC), `order_date`,
`expected_date`, `po_status`, `po_cost_total`. `po_status` defaults to `open` on creation; lifecycle is
`open` → `partial` → `received` → `closed`, plus `cancelled`. An `open` PO with a past `expected_date` is
a late/overdue PO, which is how the fill-rate report finds them. Costs here are at PO cost (close to
`last_cost` at the time), not landed.

### `fct_po_lines`
One row per PO line. Grain: `po_id` + `line_no`. Fields: `sku`, `ordered_qty`, `received_qty`,
`unit_cost`. Fill rate is `received_qty / ordered_qty` at the line, aggregated up. Lines can over-receive
(`received_qty > ordered_qty`) on catch-weight items, so fill rate can exceed 100% and gets capped in
some reports and not others.

---

## Loyalty (Harborstone Rewards)

### `dim_member`
One row per Harborstone Rewards account, keyed by `member_id`. A row exists the moment a card/account is
issued, including cards handed out at the register that were never completed with contact details. So the
raw row count is "members" in the broadest sense and is bigger than any marketable or active number.
Carries `enrolled_date`, `enrollment_channel`, `email`, `marketing_optin`, `status`, and
`last_transaction_date`.

### `dim_member.status` (member vs active member vs enrolled)
`status` is `active`, `inactive`, or `closed`, and **defaults to `active`** when the account is created,
so a card that never shopped reads as active until the nightly re-score. "Active member" is meant to be a
member with a transaction in the trailing 90 days — that's what the merchandising loyalty dashboard
counts. Finance and CRM use a trailing-12-month window for "active," so the active-member count is roughly
double on their side. Separately, "enrolled" is a narrower thing: an account with
`marketing_optin = true` and a valid email (a completed enrollment, not just a card), which is the number
the CRM team calls "members" when they talk about email reach. So member, active member, and enrolled are
three different populations and get quoted interchangeably.

### `fct_loyalty_points`
Points ledger, one row per points event (`earned`, `redeemed`, `expired`, `adjusted`). Grain:
`ledger_id`. `points` is signed (earn positive, redeem/expire negative); current balance is the running
sum per `member_id`. Points earned tie to a basket via `transaction_id` where we have it, but promotional
and service-recovery point grants have no basket, so points earned won't reconcile to sales.

---

## Promotions, markdowns & coupons

### `dim_promotion`
One row per promotion/offer, keyed by `promo_id`. Fields: `promo_type` (`temp_price_reduction`,
`multibuy`, `coupon`, `clearance`), `start_date`, `end_date`, funding (`vendor_funded` vs `retailer_funded`).
The *effect* of a promo (the money) lands on the basket line or in markdowns, not here — this is just the
offer definition.

### `fct_markdowns`
One row per markdown event on a store/SKU. Grain: `store_id` + `sku` + `markdown_date`. `markdown_amount`
is the retail value given up (positive USD). Two kinds get mixed in: permanent/clearance markdowns
(price permanently lowered) and promotional markdowns (temporary). Net sales subtracts markdown
allocations; gross sales does not, which is a big part of why gross and net diverge. If `markdown_amount`
is null, treat as 0.

### `fct_coupon_redemptions`
One row per coupon redeemed on a basket. Grain: `transaction_id` + `coupon_id`. `discount_value` is the
amount taken off (positive USD). Manufacturer coupons are reimbursed by the vendor and store coupons are
our own cost, but `is_vendor_funded` is only reliably populated for digital coupons; paper-coupon funding
is often null, so don't trust the funded/unfunded split before the digital-coupon cutover date.

---

## Returns & refunds

### `fct_returns`
One row per returned line / return transaction. Grain: `return_id` + `line_no`. Fields: `sku`,
`returned_qty`, `return_reason` (small enum: `defective`, `changed_mind`, `wrong_item`, `spoilage`,
`other`), `original_transaction_id` where the return could be matched to its original basket. A return is
the goods movement; the money is the refund. Returns reduce net sales but not gross sales.

### `fct_returns.refund_amount`
Amount refunded to the customer for the return, positive USD, tax included (we refund the tax the customer
paid). Can exceed the item's current retail if the original was bought at a higher price or with tax, so a
single SKU's net can go slightly negative on a heavy-return day; that's expected. Unmatched returns (no
`original_transaction_id`) are refunded at current retail and are a known source of shrink noise.

---

## Labor (light)

### `dim_employee`
One row per employee, keyed by `employee_id`. Carries `home_store_id`, `role`, `hire_date`,
`status` (`active` / `terminated` / `leave`). Cashiers link to baskets via `cashier_id` on
`fct_transactions`. Employees can work shifts at a store that isn't their home store; those hours are
tagged to the worked store in labor, not the home store, so headcount-by-store and hours-by-store won't
agree.

### `fct_labor_hours`
One row per employee per shift (roughly). Grain: `employee_id` + `store_id` + `business_date` + `shift`.
`hours` is paid hours; `hours_worked` excludes paid breaks and is what the productivity metrics use.
Sales-per-labor-hour uses `net_sales` over `hours_worked` in the ops report but `gross_sales` over `hours`
in the old store-ops sheet, so the two productivity numbers don't line up.

---

## Business metrics & definitions

These are the numbers people ask for by name. Where two teams compute one differently, both are listed
because both get used — say which one you mean.

### Sales (gross) — Merchandising default
`sum(fct_transactions.gross_sales)` for in-store, plus online `gross_sales` if the report is all-channel.
Merchandise rung at the register, before returns and markdowns, excluding tax. This is the "sales" number
on the merch daily flash and it runs higher than the finance figure. When a buyer says "the category did
$X," it's this.

### Net sales
Gross less returns and less markdown/promo allocations. `sum(fct_transactions.net_sales)`. Net of tax
(in current partitions — see the column note). This is the closer-to-revenue figure and the one on the
period P&L walk. Comp sales are usually reported on net.

### Revenue — Finance default
Net sales for the period, net of returns and markdowns, excluding tax, plus recognized online revenue.
This is what Finance means by "revenue" and what ties to the financials. It is not the same as gross
sales and not the same as gross merchandise value, and the gap between "sales" and "revenue" is one of the
most common reconciliation questions we get. When numbers don't match, first check gross-vs-net and
whether tax is in or out.

### Comparable-store sales (comp / same-store)
Year-over-year sales for stores open long enough to compare, on the same weeks. The store-qualification
rule is not settled:
- Finance / the P&L: a store is comp once it has traded thirteen full fiscal periods (open before the
  start of the prior fiscal year) — this is what `dim_store.comp_flag` follows.
- Merchandising: a store is comp after twelve months open, so a store can be comp for merch a period
  before it's comp for finance.
- The regional ops scorecard: open a full 52 weeks **and** no major remodel or relocation during the
  compared period, which excludes stores the other two include.
Comp is reported on net sales, calendar-shifted to align fiscal weeks. Different qualification rule =
different comp number, so always state which stores are in the base.

### Transactions & baskets
A transaction is a basket is a trip through the register — used interchangeably. Count =
`count(distinct transaction_id)` on `fct_transactions` with `status = 'completed'`. Whether online orders
are added in depends on the view (the blended all-channel count adds them, the store P&L doesn't).
Suspended/voided are out here but in the register audit count, so ops transaction counts run a bit higher.

### Units
`sum(quantity)` over the sold lines (`fct_transaction_lines`, plus online lines for all-channel). Units,
transactions, and baskets get used loosely — "we sold 40,000 units" and "we had 12,000 baskets" are
different denominators, don't mix them. Weighed items carry pounds in `quantity`, so unit counts blend
eaches and pounds and slightly overstate "items."

### Average basket / average transaction value
Average basket (also "basket size," also ATV — average transaction value) is sales over transactions.
The merch dashboard uses gross sales over completed transactions; the finance version uses net sales over
transactions and comes in lower. Units per basket is `units / transactions` and is a separate KPI people
sometimes call "basket size" too, which is why "basket size went up" is ambiguous — dollars or items.

### Gross margin
`(sales − cost of goods) / sales`, as a percent. The moving part is which cost. Finance computes it on
`landed_cost` against net sales — this is reported gross margin. Merchandising computes it on
`standard_cost` (against gross or net depending on the report), so the merch margin and the finance margin
disagree by the landed-vs-standard cost gap. Vendor-funded / deal reports sometimes use `last_cost`.
Null costs coalesce to 0 and show ~100% margin, so a spike in category margin is often a new-item cost
gap, not a real win.

### Markup
`(retail − cost) / cost`, a percent, and larger than the margin percent on the same item. "Markup" and
"margin" get said interchangeably in merch conversations even though they're different denominators
(cost vs retail); confirm which one a target refers to. Initial markup (IMU) is set on planning
(`standard_cost`); maintained markup is after markdowns and shrink.

### Inventory position (on-hand / available / owned)
Three inventory numbers, don't assume which one a report means. On-hand = physical units
(`fct_inventory_snapshot.on_hand`). Available = on-hand minus reserved, what the site can promise. Owned =
on-hand plus in-transit (some buyers use on-hand plus on-order), what the buying reports plan against.
Inventory dollars value units at cost (usually landed) unless the report says "at retail."

### Sell-through & weeks of supply
Sell-through = units sold / (units sold + on-hand) over a period, as a percent — a clearance/seasonal
health number. Weeks of supply = on-hand units / average weekly unit sales. Both depend on which
inventory number you feed them (on-hand vs available vs owned), so a clearance decision can look different
depending on whose inventory figure went in.

### Shrink
Inventory loss — the gap between book inventory (perpetual) and counted inventory at a physical count,
valued at cost. Includes theft, spoilage, damage, and unmatched returns. Reported as a percent of sales,
but which sales (gross or net) isn't consistent across the shrink deck and the P&L, so shrink % moves a
little depending on the denominator.

### Members / active members / enrolled
Three loyalty populations, quoted interchangeably. Members = accounts in `dim_member` (broadest, includes
register-issued cards that never shopped). Enrolled = completed enrollments with `marketing_optin = true`
and a valid email — the CRM/email-reach number. Active members = members with a transaction recently,
where "recently" is 90 days on the merch dashboard and 12 months for finance/CRM, so the active-member
count roughly doubles depending on the window. Always state the window and which population.

### Loyalty sales penetration
Share of sales (or baskets) tied to a loyalty account. Basket version = baskets with a non-null
`member_id` over all baskets. Dollar version = gross sales on identified baskets over total gross sales;
the two run several points apart because loyalty baskets are bigger. Which one "loyalty penetration" means
depends on the slide — the exec deck uses the dollar version, the store scorecard uses baskets.
