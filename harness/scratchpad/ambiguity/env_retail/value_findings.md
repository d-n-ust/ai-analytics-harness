# Value/enum check — env_retail

Declared enums parsed from docs: 4. Filter/value violations found: **1**.

> Complements the collision detector: it reads the VALUES inside filters, not names. A filter on a value the column's documented enum lacks silently drops rows.

```
[warehouse] wh:view:v_net_sales
    filters fct_transactions.status on ['settled'] — not in documented enum ['completed', 'suspended', 'training', 'voided']
```