import json
import re

from fciwatch.cli import main


def test_demo_makes_a_valid_report(tmp_path, capsys):
    out = tmp_path / "demo.html"
    assert main(["demo", "--out", str(out), "--days", "60"]) == 0
    html = out.read_text(encoding="utf-8")
    assert "SYNTHETIC DEMO DATA" in html
    assert "ir123_ir120" in html
    # The embedded data must be valid JSON.
    blob = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL).group(1)
    data = json.loads(blob.replace("<\\/", "</"))
    assert len(data["pairs"]) == 3


def test_report_from_csv(tmp_path):
    from fciwatch.synthetic import make_synthetic_records

    csv = tmp_path / "results.csv"
    make_synthetic_records(days=40).to_csv(csv, index=False)
    out = tmp_path / "r.html"
    assert main(["report", str(csv), "--out", str(out)]) == 0
    assert "Summary" in out.read_text(encoding="utf-8")
