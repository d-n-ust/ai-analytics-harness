# Static scan — `preflight scan models/ --dialect metricflow`

```text
1 findings — high 1, medium 0, low 0

HIGH (1)
  [SCOPE_TRAP] active_accounts[sem]  ~  active_users[sem]
      same measure; 'active_users' is 'active_accounts' plus a filter — bare question silently scoped, swap invisible
```

## Agreement with the hand labels

The case file declares **1** contested concept(s), labelled by reading the layer rather than by reading this report. The scan names **1** of them.

| hand-labelled candidates | named by the scan |
|---|---|
| `active_accounts` · `active_users` | yes |

Where the two disagree the hand label stands and the disagreement is the finding. A detector that both writes the ground truth and enforces it at query time proves nothing, which is why these two numbers are produced by separate passes over the same files.
