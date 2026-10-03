import sys
from pathlib import Path

# In the image vinu-initial-analysis / vinu-infra are pip-installed; from a checkout, put the sibling folders on the path.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT.parent / "vinu-initial-analysis", ROOT.parent / "vinu-infra"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
