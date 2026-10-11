"""English language resources of the typed reader: closed word classes and the shapes of date, series
and split phrases. Nothing here is a fact about the data: values, dimensions, periods and rules come
from the layer and the calendar. A test (harness/tests/test_typed_reader.py) fails if a value or a
dimension name of the experiment's layer appears in these lists.
"""
from __future__ import annotations

import re

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"

# Season names are not here: they are values of the calendar's season attribute, and come from it.
DATE_WORDS = re.compile(rf"\b(?:{_MONTHS}|(?:19|20)\d\d|q[1-4]|h[12]|first half|"
                        r"second half|last (?:week|month|quarter|year)|this (?:week|month|quarter|year)|"
                        r"year to date|ytd)\b", re.I)

SERIES_WORDS = re.compile(r"\b(?:week by week|month by month|day by day|weekly|monthly|daily|quarterly|trend|"
                          r"over time|change[ds]?)\b", re.I)

BY_PHRASE = re.compile(r"\b(?:by|per|for each)\s+(\w+(?:\s+\w+)?)", re.I)

# Words that join a value to the rest of a phrase and restrict nothing ("users on Android").
_JOINING = {"the", "a", "an", "of", "on", "from", "in", "for", "with", "and", "or", "who", "that", "across"}

# Closed grammatical classes: articles, prepositions, conjunctions, pronouns, auxiliary and modal verbs,
# question words, and the words that shape figures ("except", "together"), which the reading states.
# They never narrow what is counted, and the classes do not grow with new questions.
_GRAMMAR = set("""a an the this that these those some any each every all both either neither no of in on at
by for from to into onto over under during within without about across through per than as and or but nor
so if then i me my we us our you your he him his she her it its they them their what which who whom whose
when where why how many much is are was were be been being am do does did done have has had having will
would shall should can could may might must there here not
except excluding besides apart other only also just together combined versus vs with via side""".split())

_UNITS = {"daily": "day", "weekly": "week", "monthly": "month", "quarterly": "quarter", "yearly": "year",
          "day by day": "day", "week by week": "week", "month by month": "month"}

_NEGATION = re.compile(r"\b(?:not|non|except|excluding|other than|apart from|besides|without|but)\s+(?:\w+\s+){0,2}$", re.I)

_TIME_UNITS = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}

# The words before the category in a split phrase: "by", "split by", "broken down by", "across".
_SPLIT_LEAD = re.compile(r"^\s*(?:(?:broken\s+down|break\s+down|split|segmented|grouped|group)\s+)?"
                         r"(?:by|per|for each|across)\s+", re.I)
