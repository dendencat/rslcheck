import pathlib

import rsl_lint as rl


BASE = pathlib.Path(__file__).resolve().parent.parent


def test_ok_sample_passes():
    ok, issues = rl.lint_file(str(BASE / "sample" / "license-ok.xml"))
    assert ok, f"unexpected issues: {issues}"


def test_content_requires_url_attribute():
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
    assert any("必須属性 'url'" in msg for msg in issues)


def test_content_url_must_be_url_or_abs_path():
    for bad in ["foo", "htp://invalid", "//missing-scheme"]:
        xml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<rsl xmlns='https://rslstandard.org/rsl'>"
            f"  <content url='{bad}'>"
            "    <license><permits type='usage'>x</permits></license>"
            "  </content>"
            "</rsl>"
        )
        ok, issues = rl.lint_string(xml)
        assert not ok
        assert any("url は url 形式" in msg or "url は url 形式" in msg for msg in issues)

    for good in ["/", "/path", "https://example.com", "http://example.com/a"]:
        xml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<rsl xmlns='https://rslstandard.org/rsl'>"
            f"  <content url='{good}'>"
            "    <license><permits type='usage'>x</permits></license>"
            "  </content>"
            "</rsl>"
        )
        ok, issues = rl.lint_string(xml)
        assert ok, f"should accept {good}: {issues}"


def test_permits_requires_type_enum():
    xml_missing = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits>train-ai</permits></license>"
        "  </content>"
        "</rsl>"
    )
    ok, issues = rl.lint_string(xml_missing)
    assert not ok
    assert any("必須属性 'type'" in msg for msg in issues)

    xml_bad_enum = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rsl xmlns='https://rslstandard.org/rsl'>"
        "  <content url='/'>"
        "    <license><permits type='unknown'>train-ai</permits></license>"
        "  </content>"
        "</rsl>"
    )
    ok, issues = rl.lint_string(xml_bad_enum)
    assert not ok
    assert any("許可されていません" in msg for msg in issues)

