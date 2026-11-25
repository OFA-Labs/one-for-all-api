"""Judge permalink audit, anchors.md §6 (lean plan: n = 8 per spec).

Seed = sha256("EBRAIN-AUDIT-v1|<label>|" + "|".join(sorted v1 sha256s)).
Population = distinct GitHub permalinks in the spec v2 file plus its primary
ledger. Read-only git only; nothing from kb/sources is executed.
"""
import hashlib, random, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "judge" / "blind"
PIN = {"toejough/engram": ("engram", "d2ce817c74ee4fc65645635887510b47b231230f"),
       "lianmatsuo/remcycle": ("remcycle", "be1e27cd293e607b1e0c4807fd7dfd7aef28d02e"),
       "garrytan/gbrain": ("gbrain", "b8875aab6faaea050f954f30227ebf96f13cc54c"),
       "lukaszraczylo/claude-mnemonic": ("claude-mnemonic", "f950786a0f89e588fb692b7e2e12c17aafc6c007")}
LEDGER = {"Spec-X": "ledger_P7.md", "Spec-Y": "ledger_T5.md", "Spec-Z": "ledger_R2.md"}
RX = re.compile(r"https://github\.com/([^/\s]+/[^/\s]+)/blob/([0-9a-f]{7,40})/([^\s#)\]]+)#L(\d+)(?:-L(\d+))?")
N = 8

def git(repo, *a):
    r = subprocess.run(["git", "-C", str(ROOT / "kb" / "sources" / repo), *a],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout

H = sorted(hashlib.sha256((B / f"{s}_v1.md").read_bytes()).hexdigest()
           for s in ("Spec-X", "Spec-Y", "Spec-Z"))
for label in sys.argv[1:] or ["Spec-X", "Spec-Y", "Spec-Z"]:
    rows = {}  # permalink -> citing line
    for f in (B / f"{label}_v2.md", B / LEDGER[label]):
        for line in f.read_text(encoding="utf-8").splitlines():
            for m in RX.finditer(line):
                rows.setdefault(m.group(0).rstrip(".,;:)>]"), (f.name, line))
    seed = int(hashlib.sha256(("EBRAIN-AUDIT-v1|" + label + "|" + "|".join(H)).encode()).hexdigest()[:16], 16)
    pop = sorted(rows)
    sample = random.Random(seed).sample(pop, min(N, len(pop)))
    print(f"=== {label} seed={seed} N={len(pop)} n={len(sample)}")
    for pl in sample:
        m = RX.match(pl)
        repo, sha, path, a = m.group(1), m.group(2), m.group(3), int(m.group(4))
        b = int(m.group(5) or a)
        src, line = rows[pl]
        print(f"\n--- {pl}\n    from {src}: {line[:300]}")
        if repo not in PIN:
            print("    VERDICT-INPUT: OFF-REGISTRY"); continue
        folder, pin = PIN[repo]
        print(f"    pin_ok={sha == pin}")
        rc, t = git(folder, "cat-file", "-t", sha)
        if t.strip() != "commit":
            print("    VERDICT-INPUT: commit missing -> FABRICATED"); continue
        rc, body = git(folder, "show", f"{sha}:{path}")
        if rc:
            print("    VERDICT-INPUT: path missing at sha"); continue
        lines = body.splitlines()
        print(f"    file_lines={len(lines)} range_ok={a <= len(lines)}")
        ids = set(re.findall(r"`([^`]{3,60})`", line))
        rng = "\n".join(lines[a - 1:b]); win = "\n".join(lines[max(0, a - 16):b + 15])
        hits = {i: ("range" if i in rng else "window" if i in win else "file" if i in body else "absent") for i in ids}
        print(f"    ident_hits={hits}")
        for i, l in enumerate(lines[a - 1:min(b, a + 7)], a):
            print(f"    {i:5}| {l[:150]}")
