# Embedding check — all-MiniLM-L6-v2 (local, offline)

Model: `sentence-transformers/all-MiniLM-L6-v2`. 17 metrics, 136 pairs. Two texts: NAME only, and NAME+description+synonyms.

## Check 1 — closest pairs [NAME only]

`value_moments ~ real_value_moments` ranks **#1 of 136** (cos 0.904).

```
rank    cos  verdict          pair
   1  0.904  scope_only       real_value_moments ~ value_moments
   2  0.622  different_measure moments_per_day ~ value_moments
   3  0.619  different_measure active_subscriptions ~ active_users
   4  0.612  different_measure moments_per_day ~ real_value_moments
   5  0.558  not_gated        reminder_open_rate ~ reminders_shown
   6  0.532  different_measure active_users ~ power_users
   7  0.490  different_measure active_users ~ paying_users
   8  0.490  not_gated        active_subscriptions ~ paying_users
   9  0.475  not_gated        days_per_user ~ paying_users
  10  0.464  not_gated        days_per_user ~ moments_per_day
  11  0.463  not_gated        active_users ~ days_per_user
  12  0.447  different_measure paying_users ~ power_users
```

## Check 1 — closest pairs [NAME+desc+synonyms]

`value_moments ~ real_value_moments` ranks **#3 of 136** (cos 0.665).

```
rank    cos  verdict          pair
   1  0.677  not_gated        active_subscriptions ~ paying_users
   2  0.671  not_gated        arpu ~ mrr
   3  0.665  scope_only       real_value_moments ~ value_moments
   4  0.662  different_measure moments_per_day ~ value_moments
   5  0.615  not_gated        active_users ~ days_per_user
   6  0.595  different_measure active_users ~ power_users
   7  0.584  different_measure active_users ~ paying_users
   8  0.569  different_measure moments_per_day ~ real_value_moments
   9  0.527  different_measure active_habits ~ active_subscriptions
  10  0.522  different_measure active_subscriptions ~ active_users
  11  0.520  not_gated        days_per_user ~ moments_per_day
  12  0.518  different_measure active_habits ~ active_users
```

## Check 2 — does cosine separate danger (scope_only) from safe (different_measure)?

### NAME only
```
scope_only         n=  1  cos min 0.904  mean 0.904  max 0.904
different_measure  n=  8  cos min 0.401  mean 0.520  max 0.622
not_gated          n=127  cos min 0.014  mean 0.186  max 0.558
AUC (cosine ranks scope_only above different_measure): 1.000   [0.5 = no separation, 1.0 = perfect]
top pairs the token gate MISSED (not_gated), by cosine:
   0.558  reminder_open_rate ~ reminders_shown
   0.490  active_subscriptions ~ paying_users
   0.475  days_per_user ~ paying_users
   0.464  days_per_user ~ moments_per_day
   0.463  active_users ~ days_per_user
```

### NAME+desc+synonyms
```
scope_only         n=  1  cos min 0.665  mean 0.665  max 0.665
different_measure  n=  8  cos min 0.406  mean 0.548  max 0.662
not_gated          n=127  cos min 0.122  mean 0.327  max 0.677
AUC (cosine ranks scope_only above different_measure): 1.000   [0.5 = no separation, 1.0 = perfect]
top pairs the token gate MISSED (not_gated), by cosine:
   0.677  active_subscriptions ~ paying_users
   0.671  arpu ~ mrr
   0.615  active_users ~ days_per_user
   0.520  days_per_user ~ moments_per_day
   0.516  reminder_open_rate ~ reminders_shown
```

## Check 3 — nearest-neighbour cosine vs observed mislabel rate (Test 1 run)

Per gold metric (metric_answer cases, pooled over arms): its closest other metric by cosine, and how often the agent actually got it wrong.

### NAME only  —  Spearman(nn_cos, mislabel_rate) = 0.423  (p=0.223, n=10)
```
gold metric            nearest neighbour        cos mislabel%    n
value_moments          real_value_moments     0.904     29.8%  171
active_subscriptions   active_users           0.619      0.0%   47
active_users           active_subscriptions   0.619      6.2%   48
power_users            active_users           0.532      2.1%   48
paying_users           active_users           0.490      0.0%   48
new_signups            active_users           0.425     18.8%  117
activation_rate        reminder_open_rate     0.352      0.0%   42
marketing_spend        paying_users           0.346      6.8%  132
mrr                    arpu                   0.272      0.0%   48
arpu                   mrr                    0.272      0.0%   47
```

### NAME+desc+synonyms  —  Spearman(nn_cos, mislabel_rate) = -0.527  (p=0.118, n=10)
```
gold metric            nearest neighbour        cos mislabel%    n
active_subscriptions   paying_users           0.677      0.0%   47
paying_users           active_subscriptions   0.677      0.0%   48
mrr                    arpu                   0.671      0.0%   48
arpu                   mrr                    0.671      0.0%   47
value_moments          real_value_moments     0.665     29.8%  171
active_users           days_per_user          0.615      6.2%   48
power_users            active_users           0.595      2.1%   48
new_signups            active_users           0.501     18.8%  117
activation_rate        reminder_open_rate     0.452      0.0%   42
marketing_spend        reminders_shown        0.429      6.8%  132
```

## Verdict — where embeddings help, and where they do not

- **Confusability of the known pair: strong.** Name-only, `value_moments ~ real_value_moments` is the **#1** closest pair of 136 (cos 0.904), far above the next pair (0.622). Embeddings clearly capture the one collision.
- **Better recall than the token gate.** Embeddings surface related pairs the gate cannot see because they share no token: `reminder_open_rate ~ reminders_shown` (plural defeats the gate), `arpu ~ mrr`, `active_subscriptions ~ paying_users`. This is a real upgrade for the confusability GATE.
- **But cosine is not danger.** The pairs embeddings newly surface are mostly different_measure (safe): a share vs a count, a per-user average vs a total. High cosine means 'similar', not 'silently swappable'. The single scope_only pair tops the list, but with n=1 that is one data point, not class separation (the AUC=1.0 is vacuous at n=1). The structural same-measure/different-scope test stays necessary.
- **Cosine does NOT predict observed confusion.** Nearest-neighbour cosine vs mislabel rate: Spearman 0.42 (name, n.s.) and -0.53 (with descriptions, negative). Two structural reasons, both seen in the table: `new_signups` mislabels 18.8% at LOW cosine (the welded `is_internal` scope on an unnamed sibling — no neighbour to be close to), and `active_subscriptions`/`active_users` sit at HIGH cosine with ~0% mislabels (similar names, plainly different things the agent does not confuse). So the 'LLMs are embeddings, so name-cosine predicts confusion' intuition is not supported at this n.
- **Descriptions hurt.** Adding description+synonyms pulled unrelated revenue/user concepts together and demoted the true pair from #1 to #3. Name-only is the better representation here.

**Net:** adopt embeddings to REPLACE the token-overlap gate (they fix the plural/synonym misses and rank the real collision top), keep the structural test for DANGER, and do not use cosine to predict which cases get mislabelled. Caveats: one scope_only pair and n=10 metrics make this suggestive, not settled; and a local model predicting an OpenAI agent means the strong check-1 result is trustworthy while the check-3 null is partly inconclusive — though its cause here is structural, not model weakness.