"""T-050..T-052: comment-convention lint (FINAL/03-interfaces.md section 1).

Reads <ROOT>/ebrain/store.py (same relative path in FINAL/reference/impl and one-for-all-api);
override with env EBRAIN_TAGS_SRC. Fails when a function whose docstring says EXPERIMENTAL has no
'# UNTESTED:' + 'settle:' comment, or a capacity config key lacks '# LIMIT:'.
"""
import ast

from conftest import STORE_SRC

CAPACITY_KEYS = ("capacity_soft", "capacity_hard", "rank_max_chains", "max_text_chars")


def _src() -> str:
    with open(STORE_SRC, encoding="utf-8") as f:
        return f.read()


def test_T050_experimental_functions_carry_untested_tag():
    text = _src()
    missing = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if "EXPERIMENTAL" in (ast.get_docstring(node) or ""):
                seg = ast.get_source_segment(text, node) or ""
                if "# UNTESTED:" not in seg or "settle:" not in seg:
                    missing.append(node.name)
    assert not missing, f"EXPERIMENTAL functions without '# UNTESTED: ... settle:': {missing}"


def test_T051_capacity_keys_carry_limit_tag():
    lines = _src().splitlines()
    for key in CAPACITY_KEYS:
        hit = [ln for ln in lines if ln.strip().startswith(f'"{key}":')]
        assert hit and all("# LIMIT:" in ln for ln in hit), key


def test_T052_tags_present_for_real():
    text = _src()
    assert text.count("# UNTESTED:") >= 3 and text.count("# LIMIT:") >= 6


def test_T013_store_and_models_import_only_stdlib():
    import os
    import sys
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    banned = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "xmlrpc", "webbrowser"}
    pkg = os.path.dirname(STORE_SRC)
    for name in ("store.py", "models.py", "facts.py"):
        with open(os.path.join(pkg, name), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in allowed and m not in banned, f"{name} imports {m}"


def test_T028_api_opens_store_only_per_request():
    import os
    with open(os.path.join(os.path.dirname(STORE_SRC), "api.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "Store"]
    opener = next(fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and fn.name == "open_store")
    inside = [n for n in ast.walk(opener) if n in calls]
    assert len(calls) == 1 and len(inside) == 1  # the only Store(...) is the per-request dependency
