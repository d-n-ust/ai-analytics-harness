# Company brief — Northwind Threads (shared skeleton for all three artifacts)

**Business.** Northwind Threads is a direct-to-consumer apparel brand (Series B, ~18 months of fast
growth) that also runs a subscription box, "Threads Club." Revenue comes from one-off orders and from
monthly/annual club subscriptions. There are discounts/promos, returns and refunds, shipping, and
paid marketing.

**How the data org grew (the pressure).** Two analysts and one analytics engineer joined at different
times and never fully reconciled definitions. Finance and the growth team mean different things by
"revenue." A rushed rename happened mid-year. The subscription launch bolted new tables onto a model
built for one-off orders. Everyone is competent but shipping under deadline, so there is real sprawl:
duplicate-ish tables, columns that mean nearly the same thing, a metric defined in two places with a
slightly different filter, docs that drifted from the data, and scope (which customers, which order
states, gross vs net) that is sometimes governed and sometimes just baked into a query.

**Core entities (the shared skeleton — every artifact is about the same company).**
- customers (and prospects/leads)
- orders, order_items, shipments
- returns, refunds
- products, product_variants
- subscriptions (Threads Club), subscription_events
- payments, invoices
- discounts / promotions
- marketing_spend, sessions/web events

**Revenue is deliberately contested.** Gross vs net (of discounts, of returns, of tax), booked vs
recognised, order revenue vs subscription revenue, whether internal/test accounts are excluded. Do not
resolve this cleanly — a real team hasn't.

**Instruction to every generator:** build your artifact for THIS company, competent but rushed. Produce
natural sprawl and inconsistency. Do NOT annotate, flag, or explain the problems, and do NOT try to make
anything clean or "detectable." Write like a real team shipping under deadline. You are not being graded
on tidiness.
