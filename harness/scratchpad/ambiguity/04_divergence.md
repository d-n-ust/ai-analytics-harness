# T4 — divergence calibration (value_moments vs real_value_moments)

Detection is binary: the pair is AMBIGUOUS iff the numbers differ on any slice. Magnitude is the damage number, and it runs inverse to danger (small = silent, large = caught).

```
slice                  value_moments  real_value       Δ      Δ% sign
------------------------------------------------------------------
all rows                       67132       64257    2875   4.28% +
region=APAC                     7495        7248     247   3.30% +
region=Americas                24042       22872    1170   4.87% +
region=EMEA                    35595       34137    1458   4.10% +
platform=android               20812       20115     697   3.35% +
platform=ios                   22749       21843     906   3.98% +
platform=unknown                1628        1618      10   0.61% +
platform=web                   21943       20681    1262   5.75% +
channel=content_seo            12461       12016     445   3.57% +
channel=organic                14281       13864     417   2.92% +
channel=paid_search            13898       13077     821   5.91% +
channel=partnerships           14223       13633     590   4.15% +
channel=referral               12269       11667     602   4.91% +
recent 4 weeks                 16787       16075     712   4.24% +
```

## Detection verdict (binary)

- **Ambiguous: YES.** The two groundings differ on 14 of 14 slices, so they are two definitions, not one. Detection does not depend on how big Δ is.

## The three numbers

1. **Δ = 0 on every slice?** False — so this is not an alias; it is a real scope difference.
2. **Sign consistent?** True (value_moments ≥ real_value_moments on every slice, as subsumption requires — a negative would be a data or modelling bug).
3. **Magnitude by slice:** min 0.61%, max 5.91%, overall 4.28%. Verdict flips across the 2.0% notice line: **True** (1 slices silent < 2.0%, 13 loud ≥ 2.0%).

## Read

- The damage number is **~4.3% overall**, but it is slice-dependent (from 0.6% to 5.9%). So 'this collision costs ~4%' is true as a headline and false as a constant — it must be stated as a range with its slices.
- Danger is inverse to magnitude: the slices near 0.6% are the dangerous ones (a swap is invisible); the 5.9% slices are comparatively safe (someone notices). None of this changes the binary detection verdict — it only prices it.