"""DQ3 diagnostic (anchors §4.2 intent) for a failed rollback_exact_maintain.

Replays the frozen harness Run unchanged, but on the rb2 check prints, for each
probe that differs, the recorded vs replayed status map and the ground-truth
head codes at t_r. DQ3 needs a ground-truth-current code shown `current` at t_r
that is no longer `current` after rollback.
Usage (from benchmark/): python -I -X utf8 ../judge/tools/rb_diag.py <dir> <size> <seed>
"""
import sys, os
sys.path.insert(0, os.getcwd())
from harness import runner
from harness.metrics import statusmap

class Diag(runner.Run):
    def _rollback(self, ad, specs, maps):
        pts = self.ds.rollback_points
        for tag in ("rb1", "rb2"):
            if tag == "rb2":
                self.maintain(ad, self.ds.final_ts)
            self.call(ad.rollback, pts[tag])
            for s in specs[tag]:
                now = statusmap(self.query(ad, s, "rb_replay").bundle)
                rec = maps[tag][s.query.query_id]
                if now != rec:
                    gt = sorted({c for ch in s.chains for c in self.truth.head_codes(ch, pts[tag])})
                    lost = [c for c in gt if "current" in rec.get(c, ()) and "current" not in now.get(c, ())]
                    print(f"{tag} t_r={pts[tag]} q={s.query.query_id} gt_head={gt}\n  recorded={dict(rec)}\n  replayed={dict(now)}\n  GT-current lost={lost}")

r = Diag(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), 900)
r.run()
print("done")
