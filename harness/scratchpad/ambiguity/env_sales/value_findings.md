# Value/enum check — env_sales

Declared enums parsed from docs: 4. Filter/value violations found: **1**.

> Complements the collision detector: it reads the VALUES inside filters, not names. A filter on a value the column's documented enum lacks silently drops rows.

```
[semantic] sl:completed_orders
    filters fct_orders.status on ['completed', 'delivered'] — not in documented enum ['cancelled', 'fulfilled', 'paid', 'partially_refunded', 'pending', 'refunded']
```