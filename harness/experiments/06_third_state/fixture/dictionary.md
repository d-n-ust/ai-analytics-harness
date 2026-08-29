Data dictionary for the star schema. Written as a warehouse's own table comments would be —
describing grain and non-obvious columns — with no reference to any evaluation question.

dim_users        one row per account. `is_internal` marks staff and test accounts. `platform` is
                 the account's registered client, `channel` how it was acquired.
dim_habits       one row per habit a user created. `category` groups habits by subject.
fct_value_moments one row per COMPLETED HABIT. `completed_ts` is when it was completed; there is no
                 duration or session-length column anywhere in this warehouse. `source` is the
                 client that recorded the completion (widget, app, api), not a product area or
                 feature. `habit_id` joins to dim_habits.
fct_reminders    one row per reminder sent.
fct_subscriptions one row per subscription contract. `billed_amount` is the amount for the whole
                 term, so an annual plan is twelve months of revenue in one row. `status` and
                 `is_active` differ: a refunded term is not active but has a status of its own.
fct_marketing_spend one row per channel per day.
fct_referrals    one row per referral.
