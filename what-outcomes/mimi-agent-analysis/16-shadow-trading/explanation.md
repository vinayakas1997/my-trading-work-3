# Shadow Trading

## What This Angle Studies
Extracts trading patterns from history: FIFO roundtrip pairing, K-Means clustering, auto-extracted entry/exit rules, silhouette score.

## Results
K-Means clustering (k=3) on synthetic trades produces 3 clusters: cluster 0 (n=57, short hold=1.5d), cluster 1 (n=12, long hold=14.5d), cluster 2 (n=31, medium hold=6.3d). Silhouette score=0.45 (moderate separation). Entry hour clustering adds temporal dimension.

## Execution Time
~0.5s

### Bugs Found
None.