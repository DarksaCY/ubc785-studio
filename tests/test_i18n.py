import ast
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from u785 import i18n


def _keys():
    for path in glob.glob(os.path.join(ROOT, "u785", "**", "*.py"), recursive=True):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                yield os.path.relpath(path, ROOT), node.lineno, node.args[0].value


def test_every_ui_string_has_russian():
    missing = [f"{f}:{line} {key!r}" for f, line, key in _keys() if key not in i18n.RU]
    assert not missing, "\n".join(missing)


def test_placeholders_match():
    import string
    fields = lambda s: sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)
    bad = [k for k, v in i18n.RU.items() if fields(k) != fields(v)]
    assert not bad, bad


def test_switching():
    try:
        assert i18n._("Connect") == "Connect"
        i18n.set_language("ru")
        assert i18n._("Connect") == "Подключить"
        assert i18n._("Read {ok} of {total} in {secs:.0f} s", ok=1, total=2, secs=3.4) == "Прочитано 1 из 2 за 3 с"
        i18n.set_language("xx")
        assert i18n.language() == "en"
    finally:
        i18n.set_language("en")
