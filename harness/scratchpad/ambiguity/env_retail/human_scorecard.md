# Human-gold scorecard (retail)

Human high-danger gold: **22** collisions (9 red-team-consensus + 13 practitioner-confirmed).

Who agrees with the human:
```
  detector (v3) recall on human gold ... 5/22 (23%)
  original LLM gold recall on human ... 14/22 (64%)
```

Per collision (D = v3 detector flagged high, G = original LLM gold flagged high):
```
  [DG] comp_three_qualification_rules             (consensus)
  [DG] doc_vs_schema_model_names                  (consensus)
  [DG] many_sales_metrics_collide                 (consensus)
  [.G] member_filter_columns_phantom              (consensus)
  [..] returns_column_names_and_phantom_return_amt (consensus)
  [..] shrink_wrong_base_table                    (consensus)
  [.G] store_key_sprawl                           (consensus)
  [.G] units_baskets_transactions_denominator     (consensus)
  [.G] v_net_sales_hidden_comp_filter             (consensus)
  [..] aov_mislabeled_and_overlapping             (you-ruled)
  [..] average_basket_gross_vs_net                (you-ruled)
  [..] gross_margin_pct_mixes_gross_and_net       (you-ruled)
  [DG] inventory_three_numbers                    (you-ruled)
  [.G] is_comp_value_Y_vs_true_vs_1               (you-ruled)
  [.G] loyalty_penetration_basket_vs_dollar       (you-ruled)
  [DG] margin_which_cost_which_denominator        (you-ruled)
  [.G] online_status_filter_missing               (you-ruled)
  [..] product_key_sprawl                         (you-ruled)
  [..] region_five_vs_six                         (you-ruled)
  [.G] store_identifier_codes                     (you-ruled)
  [.G] store_ops_sales_tax_in                     (you-ruled)
  [..] v_active_members_flag_based                (you-ruled)
```

D. = the detector missed it; .G = only the LLM gold had it; .. = BOTH missed a collision the human confirmed (the real blind spots).

**Both missed (8):** returns_column_names_and_phantom_return_amt, shrink_wrong_base_table, v_active_members_flag_based, gross_margin_pct_mixes_gross_and_net, product_key_sprawl, aov_mislabeled_and_overlapping, region_five_vs_six, average_basket_gross_vs_net