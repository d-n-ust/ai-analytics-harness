# The combined pipeline on 5 isolated examples

GATE = embedding cosine ≥ 0.4 (all-MiniLM-L6-v2, name-only). MEANING = agreement on declared entity/agg/base (unit dropped). SCOPE = subsumption of the declared filters. Danger = SCOPE TRAP (same measure, one scope inside the other, names confusable).

## 1. Bare vs scoped — the core trap

`orders` ~ `completed_orders`  — embedding cos **0.738**  (embed gate PASS, token gate pass)

- **class:** SCOPE TRAP (high)
- **action:** clarify
- **why:** same measure; 'completed_orders' is 'orders' plus a filter -> a bare question is silently scoped, numbers differ, swap is invisible

## 2. Similar name, different measure

`active_users` ~ `active_subscriptions`  — embedding cos **0.619**  (embed gate PASS, token gate pass)

- **class:** safe
- **action:** answer
- **why:** different measure (differs in entity, agg, base) -> numbers land far apart, a swap is loud

## 3. Sibling vs sibling

`food_orders` ~ `drink_orders`  — embedding cos **0.647**  (embed gate PASS, token gate pass)

- **class:** sibling (low)
- **action:** note
- **why:** same measure, incomparable scopes -> a question must name one; not a silent default swap

## 4. Alias — identical definition, two names

`gross_revenue` ~ `total_revenue`  — embedding cos **0.815**  (embed gate PASS, token gate pass)

- **class:** vague
- **action:** answer either
- **why:** identical definition under two names -> alias; same number always

## 5. Recall win — synonym, no shared token, subsumption

`revenue` ~ `net_sales`  — embedding cos **0.538**  (embed gate PASS, token gate MISS)

- **class:** SCOPE TRAP (high)
- **action:** clarify
- **why:** same measure; 'net_sales' is 'revenue' plus a filter -> a bare question is silently scoped, numbers differ, swap is invisible

## Summary

```
example                                        cos tokgate class              action       
1. Bare vs scoped — the core trap            0.738    pass SCOPE TRAP (high)  clarify      
2. Similar name, different measure           0.619    pass safe               answer       
3. Sibling vs sibling                        0.647    pass sibling (low)      note         
4. Alias — identical definition, two names   0.815    pass vague              answer either
5. Recall win — synonym, no shared token, su 0.538    MISS SCOPE TRAP (high)  clarify      
```

What the 5 show, together:

- **#1** the core trap is flagged: same measure, bare vs scoped -> **clarify**.
- **#2** a similar NAME with a different MEASURE is not flagged -> **answer**. Embeddings alone would warn here; the structural stage correctly stands it down.
- **#3** two scoped siblings are not a silent-default trap -> **note**, not clarify. The subsumption test kills the sibling noise that over-fired in Test 2.
- **#4** an identical definition under two names is an **alias** -> answer either; never asked about.
- **#5** a dangerous pair whose names share **no token** (`revenue`/`net_sales`) is caught by the embedding gate (cos 0.54) though the old token gate MISSES it. This is the recall win, and it is a real scope trap -> **clarify**.

Divergence stays binary throughout: #1, #3, #5 have differing definitions so the numbers CAN differ (flag on that fact, not on a percentage); #4 is identical so it never can. Magnitude is left for pricing the consequence, not for detection.