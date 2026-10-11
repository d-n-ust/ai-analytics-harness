# Value search for large dimensions: step A (prototype, 2026-10-11)

Can code build a short list of candidate values for a phrase, so the decision model chooses among
about 15 options instead of every value of every dimension? Design and motivation: findings, section
39, "Large dimensions". This folder tests only the short list (recall at k). No decision model is
called, and nothing here is wired into the reader.

    uv run --with sentence-transformers --with rapidfuzz --with geonamescache python evaluate.py

- `shortlist.py`: word search (rapidfuzz) and embedding search (local sentence-transformers), merged
  by reciprocal rank.
- `evaluate.py`: the values, the test phrases and the scoring. `results.json` is version 2;
  `results_v1.json` is version 1.

## Data

The city dimension holds every city of 15,000 people or more in the fixture's eight countries, from
GeoNames (geonamescache 3.0.2): 12,409 distinct names. The test phrases:

| set | phrases | source |
|---|---|---|
| exact | 100 | sampled city names |
| typo | 100 | the same names, two inner letters swapped |
| other_name | 100 | another name GeoNames records for one of the 400 largest cities |
| common_name | 19 | names people commonly use (Bombay, München, Big Apple), written for this test |
| absent | 19 | large cities outside the eight countries |

Two of these sets are weak. `other_name` contains transliterations no user types ("shykagw" for
Chicago), so it does not measure user behaviour. `common_name` was written by the author. Neither
should be quoted as a result; a blind set is needed (see "Next").

## Version 1: one short list over all dimensions

The 33 values of the small dimensions and the 12,409 cities shared one short list. The cities crowded
the small dimensions out: "the UK", "Europe" and "Big Apple" missed at rank 15, and "Samsung phone"
reached android only at rank 13. Version 2 searches only the large dimension. The small dimensions
stay whole lists in the multiple-choice question, as in the reader today.

## Version 2: the city dimension alone

Recall at 1 / 5 / 15, in percent (329 phrases; milliseconds per search on a laptop CPU):

| method | exact | typo | other_name (weak) | common_name (weak) | ms |
|---|---|---|---|---|---|
| word, WRatio | 100 / 100 / 100 | 80 / 99 / 100 | 35 / 57 / 69 | 16 / 37 / 42 | 9.8 |
| word, ratio | 100 / 100 / 100 | 92 / 100 / 100 | 55 / 68 / 78 | 21 / 42 / 42 | 0.4 |
| meaning, multilingual-e5-small | 99 / 100 / 100 | 87 / 99 / 99 | 38 / 54 / 62 | 42 / 79 / 84 | 11.0 |
| meaning, all-MiniLM-L6-v2 | 100 / 100 / 100 | 31 / 43 / 49 | 16 / 27 / 32 | 42 / 63 / 68 | 8.4 |
| both, e5-small + ratio | 100 / 100 / 100 | 96 / 99 / 100 | 49 / 65 / 79 | 26 / 68 / 79 | 11.7 |
| both, MiniLM + ratio | 100 / 100 / 100 | 55 / 79 / 99 | 30 / 53 / 71 | 16 / 84 / 84 | 8.9 |

- Typos are solved by word search alone: `ratio` puts the right city first 92 times in 100 and in the
  top 5 every time. `WRatio` is worse, because its partial matching scores short values highly ("Madrid"
  scored 90 against "ID" in version 1).
- Other names are not solved by either search. Calcutta, Madras, Big Apple, Rio and Sampa missed at
  rank 15 with every method. These are facts about the city, not meanings of its name: an alias table
  (GeoNames has one) is the fix, searched by words, with embeddings as a fallback.
- An English-only model fails on spelling (31 percent at rank 1 for typos). If embeddings are used,
  the model must be multilingual.
- Building the e5-small index for 12,409 values took about 2 minutes on a laptop CPU; a search takes
  about 12 ms.

## Absence cannot be read from a score

Six of the 25 large foreign cities first chosen as "absent" are names of cities in the list: Rome,
Moscow, Lima, Dhaka, Vienna and Amsterdam (Rome, Georgia; Lima, Ohio). An exact match is therefore not
enough to ground a value in a large dimension: "Rome" would be answered with Rome, Georgia, and the
answer would look grounded. Each option must carry its context ("Rome, Georgia, United States"), and
the answer must state it.

The best word score of the remaining absent cities overlaps the scores of present ones (`ratio`:
absent 57 to 83, typos 80 to 100, other names 50 to 96). No threshold separates a typo of a present
city from a city that is not there. In a large dimension, "not in the data" can follow only from a
complete list and a failed search for every recorded name; otherwise the analyst asks.

## Expert review (2026-10-11)

The question-to-SQL and AI-engineering reviews placed the approach by dimension type:

| dimension type | value search | the decision model |
|---|---|---|
| descriptive categories, hierarchies (embed the path), multilingual concepts | embeddings and words | chooses from the short list |
| places, companies, customers | an alias table by words first, embeddings as fallback; context in each option | chooses, and the answer states the value with its context |
| people | words and phonetic matching; privacy review first | chooses |
| codes, IDs, SKUs | exact, prefix or format rule only: the nearest vector to SKU-10442 is SKU-10443 | not used |
| numbers, dates, bands | a grammar, as periods are parsed today | not used |
| groups of values ("brand campaigns") | a modelled attribute (campaign type), not search | as today |

## Where this goes: candidate search

The design that follows from this prototype is in the findings, section 39 ("How a parameter is
grounded"): a parameter is grounded by a rule or by a dimension search; a dimension search is a
candidate search and then a resolution (an exact match by code, or a judgement by the decision model
over the candidates). This folder is the first strategy test of the candidate search: `all`, `words`
and `meaning`. The `aliases` and `hierarchy` strategies are next. GeoNames records each city's state
(`admin1code`), so the fixture gets a country, state and city hierarchy without new data.

## Next

1. A descriptive dimension (for example a product category list), the case embeddings are made for.
2. An alias table for cities, and the same test with aliases indexed; the state level, and the test
   with the parent stated in the question against flat search.
3. Blind-written phrases (the replication procedure: an outside writer, labels registered first),
   reported per dimension type.
4. Step B: the short list in the reader's multiple-choice question, end to end, with the miss path
   tested on purpose (namesakes such as Rome; a right value missing from the list), counting silent
   wrong answers.
5. The short list and its scores stored with the reading, so a replay after the index changes is
   marked stale rather than reading different options.
