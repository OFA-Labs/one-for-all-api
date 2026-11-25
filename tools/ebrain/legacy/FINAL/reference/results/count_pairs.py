"""Measures the EXPERIMENTAL review band: how many possible_same_fact pairs are flagged and what
share are truly one fact (judged with the generator's sealed chain ids; measurement only, the
adapter never sees them). Run from benchmark\\:
    .\\.venv\\Scripts\\python.exe ..\\FINAL\\reference\\results\\count_pairs.py 1000 101
"""
import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "impl"))
from harness.generate import generate  # noqa: E402

from adapter import Adapter  # noqa: E402

size, seed = int(sys.argv[1]), int(sys.argv[2])
ds = generate(size, seed)
for auto, review in ((0.70, 0.45), (0.50, 0.35)):
    ad = Adapter(tempfile.mkdtemp(), {"subject_join": "on", "join_auto_threshold": auto,
                                      "join_review_threshold": review})
    for w in ds.writes:
        ad.write(w)
    truth = {}  # adapter chain -> set of sealed truth chains of its versions
    for r in ad.db.execute("SELECT op_id, chain FROM ops WHERE role='version'"):
        s = ds.seals.get(r["op_id"])
        if s:
            truth.setdefault(r["chain"], set()).add(s.chain)
    pairs = ad.db.execute("SELECT a, b FROM links WHERE kind='possible'").fetchall()
    same = sum(1 for a, b in pairs if truth.get(a, set()) & truth.get(b, set()))
    print(f"size={size} seed={seed} auto={auto} review={review} pairs={len(pairs)} "
          f"true_same={same} precision={same / len(pairs) if pairs else 0:.3f}")
    ad.close()
