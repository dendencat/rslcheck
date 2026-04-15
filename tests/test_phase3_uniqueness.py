"""
tests/test_phase3_uniqueness.py — Phase 3: type一意性制約のテスト
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import rsl_lint as rl

BASE = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Phase 3: type一意性
# ---------------------------------------------------------------------------

def _xml(license_body: str) -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        f"    <license>{license_body}</license>"
        "  </content>"
        "</rsl>"
    )


def test_permits_duplicate_type_is_error():
    xml = _xml(
        "<permits type='usage'>x</permits>"
        "<permits type='usage'>y</permits>"
    )
    ok, issues = rl.lint_string(xml)
    assert not ok
    rsl201 = [i for i in issues if i.code == "RSL201"]
    assert rsl201, f"RSL201 が検出されませんでした: {issues}"
    assert "usage" in rsl201[0].message


def test_prohibits_duplicate_type_is_error():
    xml = _xml(
        "<permits type='usage'>x</permits>"
        "<prohibits type='distribution'>x</prohibits>"
        "<prohibits type='distribution'>y</prohibits>"
    )
    ok, issues = rl.lint_string(xml)
    assert not ok
    rsl201 = [i for i in issues if i.code == "RSL201"]
    assert rsl201
    assert "distribution" in rsl201[0].message


def test_payment_duplicate_type_is_error():
    xml = _xml(
        "<permits type='usage'>x</permits>"
        "<payment type='free'/>"
        "<payment type='free'/>"
    )
    ok, issues = rl.lint_string(xml)
    assert not ok
    rsl201 = [i for i in issues if i.code == "RSL201"]
    assert rsl201
    assert "free" in rsl201[0].message


def test_different_types_are_ok():
    xml = _xml(
        "<permits type='usage'>x</permits>"
        "<permits type='distribution'>y</permits>"
        "<prohibits type='modification'>z</prohibits>"
    )
    ok, issues = rl.lint_string(xml)
    assert ok, f"異なる type は許容されるはず: {issues}"


def test_same_type_in_different_licenses_is_ok():
    """別々の <license> 要素なら同じ type が重複しても OK"""
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='usage'>x</permits></license>"
        "    <license><permits type='usage'>y</permits></license>"
        "  </content>"
        "</rsl>"
    )
    ok, issues = rl.lint_string(xml)
    assert ok, f"別 license での重複は許容されるはず: {issues}"


# ---------------------------------------------------------------------------
# Phase 2: payment type検証（RSL標準語彙）
# ---------------------------------------------------------------------------

def test_payment_valid_types():
    for ptype in ["free", "attribution", "subscription", "pay-per-crawl", "pay-per-inference"]:
        xml = _xml(f"<permits type='usage'>x</permits><payment type='{ptype}'/>")
        ok, issues = rl.lint_string(xml)
        assert ok, f"'{ptype}' は有効な payment type のはず: {issues}"


def test_payment_invalid_type():
    xml = _xml("<permits type='usage'>x</permits><payment type='unknown-model'/>")
    ok, issues = rl.lint_string(xml)
    assert not ok
    rsl103 = [i for i in issues if i.code == "RSL103"]
    assert rsl103, f"RSL103 が検出されませんでした: {issues}"


def test_payment_missing_type():
    xml = _xml("<permits type='usage'>x</permits><payment/>")
    ok, issues = rl.lint_string(xml)
    assert not ok
    rsl101 = [i for i in issues if i.code == "RSL101"]
    assert rsl101, f"RSL101 が検出されませんでした: {issues}"


# ---------------------------------------------------------------------------
# エラーコード体系
# ---------------------------------------------------------------------------

def test_issue_has_code():
    xml = _xml("<permits>no-type</permits>")
    ok, issues = rl.lint_string(xml)
    assert not ok
    for issue in issues:
        assert hasattr(issue, "code"), "LintIssue に code 属性がない"
        assert hasattr(issue, "severity"), "LintIssue に severity 属性がない"
        assert issue.code.startswith("RSL"), f"コードが RSL で始まらない: {issue.code}"


def test_xml_parse_error_is_rsl001():
    ok, issues = rl.lint_string("<broken xml")
    assert not ok
    assert issues[0].code == "RSL001"


def test_namespace_error_is_rsl002():
    ok, issues = rl.lint_string("<rsl><content url='/'><license><permits type='usage'/></license></content></rsl>")
    assert not ok
    assert any(i.code == "RSL002" for i in issues)


def test_unknown_tag_is_rsl004():
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='usage'>x</permits></license>"
        "    <unknown-tag/>"
        "  </content>"
        "</rsl>"
    )
    ok, issues = rl.lint_string(xml)
    assert not ok
    assert any(i.code == "RSL004" for i in issues)


def test_missing_required_attr_is_rsl101():
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content>"
        "    <license><permits type='usage'>x</permits></license>"
        "  </content>"
        "</rsl>"
    )
    ok, issues = rl.lint_string(xml)
    assert not ok
    assert any(i.code == "RSL101" for i in issues)


# ---------------------------------------------------------------------------
# JSON出力・CLIオプション
# ---------------------------------------------------------------------------

def test_format_json_returns_valid_json():
    xml = _xml("<permits type='usage'>x</permits>")
    ok, issues = rl.lint_string(xml)
    result_str = rl._format_json(ok, issues)
    result = json.loads(result_str)
    assert "ok" in result
    assert "errors" in result
    assert "warnings" in result
    assert "stats" in result
    assert result["ok"] is True


def test_format_json_ng():
    xml = _xml("<permits type='usage'>x</permits><permits type='usage'>y</permits>")
    ok, issues = rl.lint_string(xml)
    result_str = rl._format_json(ok, issues)
    result = json.loads(result_str)
    assert result["ok"] is False
    assert len(result["errors"]) >= 1
    err = result["errors"][0]
    assert "code" in err
    assert "message" in err
    assert "severity" in err


def test_cli_format_json(tmp_path):
    """--format json でJSON出力が得られること"""
    lic = tmp_path / "license.xml"
    lic.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='usage'>x</permits></license>"
        "  </content>"
        "</rsl>",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(BASE / "rsl_lint.py"), "--format", "json", str(lic)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True


def test_cli_quiet_ok_produces_no_output(tmp_path):
    """--quiet + OK のとき何も出力しない"""
    lic = tmp_path / "license.xml"
    lic.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='usage'>x</permits></license>"
        "  </content>"
        "</rsl>",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(BASE / "rsl_lint.py"), "--quiet", str(lic)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_cli_stdin(tmp_path):
    """--stdin で標準入力から読み込めること"""
    xml_text = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='usage'>x</permits></license>"
        "  </content>"
        "</rsl>"
    )
    result = subprocess.run(
        [sys.executable, str(BASE / "rsl_lint.py"), "--stdin"],
        input=xml_text,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_version():
    result = subprocess.run(
        [sys.executable, str(BASE / "rsl_lint.py"), "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert rl.__version__ in result.stdout


def test_format_text_shows_error_count():
    xml = _xml("<permits>no-type</permits>")
    ok, issues = rl.lint_string(xml)
    output = rl._format_text(ok, issues)
    assert "エラー:" in output


def test_backward_compat_string_in_issue():
    """既存コード: 'substring' in issue が動作すること（後方互換性）"""
    xml = _xml("<permits>no-type</permits>")
    ok, issues = rl.lint_string(xml)
    assert any("必須属性 'type'" in msg for msg in issues)
