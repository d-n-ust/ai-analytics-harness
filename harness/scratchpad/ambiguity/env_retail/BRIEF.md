# Company brief — Harborstone Market (shared skeleton for all three artifacts)

**Business.** Harborstone Market is a regional omnichannel retailer: ~80 physical grocery +
general-merchandise stores plus a click-and-collect / delivery online channel and a loyalty program
("Harborstone Rewards"). Money comes from in-store POS baskets and online orders. There are
promotions, markdowns, returns, supplier purchase orders and inventory, and labor.

**How the data org grew (the pressure).** The company ran on store-ops spreadsheets for years, then
stood up a warehouse fast when the online channel and loyalty launched. Merchandising, Finance, and
the new e-commerce team each brought their own definitions and nobody reconciled them. "Sales" means
different things to Finance (net) and Merchandising (gross rung at the register). The classic retail
fight — which stores count as "comparable" for same-store sales — has three answers. Everyone is
competent but shipping under deadline, so there is real sprawl: an old store-ops table next to the new
POS model, units vs baskets vs transactions used loosely, inventory counted three ways, margin
defined on different costs, and loyalty "member" vs "active member" vs "enrolled" left fuzzy.

**Core entities (the shared skeleton — every artifact is about the same company).**
- stores (and regions / banners / store formats)
- transactions / baskets (POS), online orders, line items (basket lines)
- products / SKUs / categories / departments
- inventory (on-hand, on-order/in-transit, receipts, shrink/markdown)
- suppliers / purchase orders
- loyalty members / enrollments / points
- promotions / markdowns / coupons
- returns / refunds
- employees / labor hours (light)

**Retail measures are deliberately contested.** Gross vs net sales (of returns, of markdowns, of tax);
comparable-store ("comp"/same-store) sales and which stores qualify; units vs transactions vs baskets;
gross margin vs markup and which cost (landed vs standard vs last); inventory on-hand vs available vs
in-transit; loyalty member vs active member vs enrolled; store vs region vs banner. Do not resolve
these cleanly — a real team hasn't.

**Instruction to every generator:** build your artifact for THIS company, competent but rushed. Produce
natural sprawl and inconsistency. Do NOT annotate, flag, or explain the problems, and do NOT try to make
anything clean or "detectable." Write like a real team shipping under deadline. You are not being graded
on tidiness.
