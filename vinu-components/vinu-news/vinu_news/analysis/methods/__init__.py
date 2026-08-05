"""Section-1 "news-only, no price data, ingest-time" analysis methods.

One module per method from `New-talk-/Final-implementation/01-present-
considerations/` (see `03-actual-plan-findings/01-method-separation.md`,
Section 1, for why these 9 specifically qualify to live here rather than
in `vinu-initial-analysis`). Each module exposes a small `compute(...)`-
style function (or class, where the method is stateful) whose input/
output shape matches that method's own spec file.

Where an existing `vinu_news` module already implements the same
technique (NER, sentiment lexicon, TF-IDF cosine similarity/clustering),
these modules are thin adapters around that existing code rather than
reimplementations — see each module's docstring for the specific
reuse/adapt/build-new call and why.
"""
