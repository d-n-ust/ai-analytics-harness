# Check 1 validation — OpenAI text-embedding-3-small vs local MiniLM (NAME only)

`value_moments ~ real_value_moments` rank: **OpenAI #1** (cos 0.816), **MiniLM #1** (cos 0.904) of 136 pairs.

Rank agreement between the two models across all 136 pair cosines: Spearman **0.712** (p=2.3e-22).

## OpenAI top-12 closest pairs
```
rank  oai_cos  mini_cos  verdict          pair
   1  0.816    0.904     scope_only       real_value_moments ~ value_moments
   2  0.638    0.619     different_measure active_subscriptions ~ active_users
   3  0.600    0.532     different_measure active_users ~ power_users
   4  0.589    0.433     different_measure active_habits ~ active_users
   5  0.570    0.558     not_gated        reminder_open_rate ~ reminders_shown
   6  0.542    0.464     not_gated        days_per_user ~ moments_per_day
   7  0.534    0.401     different_measure active_habits ~ active_subscriptions
   8  0.507    0.490     different_measure active_users ~ paying_users
   9  0.505    0.425     not_gated        active_subscriptions ~ new_signups
  10  0.505    0.622     different_measure moments_per_day ~ value_moments
  11  0.502    0.475     not_gated        days_per_user ~ paying_users
  12  0.480    0.612     different_measure moments_per_day ~ real_value_moments
```

## Verdict

- OpenAI **confirms** the local finding: the known collision is the #1 closest pair by name.
- The two models rank pairs the same way (Spearman 0.71), so Check 1 is not an artifact of the small local model — the strong signal survives the model swap.
- This validates embeddings as the confusability GATE. It says nothing new about the danger axis or mislabel prediction (Checks 2 and 3), whose conclusions stand.