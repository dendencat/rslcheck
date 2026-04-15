
"""
rsl_lint.py — RSL 静的構文チェック

Phase 1: タグ構造/名前空間/親子関係/未知タグ/多重度
Phase 2: 属性の必須/型/列挙制約の検査
Phase 3: type一意性制約の検査（<permits>/<prohibits>/<payment>/<legal>）

依存は標準ライブラリのみ。
"""
import sys
import argparse
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Set
from urllib.parse import urlparse
import re

__version__ = "0.3.0"

RSL_NS_URL = "https://rslstandard.org/rsl"


def q(tag: str) -> str:
    return f"{{{RSL_NS_URL}}}{tag}"


ALLOWED_CHILDREN: Dict[str, Set[str]] = {
    q("rsl"): {q("content")},
    q("content"): {q("license"), q("schema"), q("copyright"), q("terms")},
    q("license"): {q("permits"), q("prohibits"), q("payment"), q("legal")},
    q("payment"): {q("standard"), q("custom"), q("amount")},
    q("permits"): set(),
    q("prohibits"): set(),
    q("legal"): set(),
    q("schema"): set(),
    q("copyright"): set(),
    q("terms"): set(),
    q("standard"): set(),
    q("custom"): set(),
    q("amount"): set(),
}

CARDINALITY_RULES = {
    q("rsl"): {"min": 1, "max": 1},
    (q("rsl"), q("content")): {"min": 1, "max": None},
    (q("content"), q("license")): {"min": 1, "max": None},
    (q("content"), q("schema")): {"min": 0, "max": 1},
    (q("content"), q("copyright")): {"min": 0, "max": 1},
    (q("content"), q("terms")): {"min": 0, "max": 1},
}

# Phase 2: 属性ルール定義
PERMISSION_TYPE_VOCAB = {
    "usage",
    "distribution",
    "modification",
    "private-use",
}

# RSL標準が定義する支払いモデル語彙
PAYMENT_TYPE_VOCAB = {
    "free",
    "attribution",
    "subscription",
    "pay-per-crawl",
    "pay-per-inference",
}

ATTRIBUTE_RULES: Dict[str, Dict[str, Dict[str, object]]] = {
    q("content"): {
        "url": {"required": True, "type": "url"},
    },
    q("permits"): {
        "type": {"required": True, "enum": PERMISSION_TYPE_VOCAB},
    },
    q("prohibits"): {
        "type": {"required": True, "enum": PERMISSION_TYPE_VOCAB},
    },
    q("payment"): {
        "type": {"required": True, "enum": PAYMENT_TYPE_VOCAB},
    },
    q("amount"): {
        "currency": {"required": True, "type": "iso4217"},
    },
}

# Phase 3: type一意性チェック対象タグ（<license>直下）
TYPE_UNIQUE_TAGS = {q("permits"), q("prohibits"), q("payment"), q("legal")}

# エラーコード定義
# RSL0xx: 構造エラー
#   RSL001: XML構文エラー
#   RSL002: 名前空間エラー
#   RSL003: ルート要素エラー
#   RSL004: 未知タグ
#   RSL005: 不正な入れ子
#   RSL006: 多重度違反
# RSL1xx: 属性エラー
#   RSL101: 必須属性欠落
#   RSL102: 属性フォーマット不正
#   RSL103: 列挙値不正
# RSL2xx: 意味/一意性エラー
#   RSL201: type重複（一意性違反）


@dataclass
class LintIssue:
    """リントの検出結果（エラーまたは警告）"""
    code: str
    message: str
    severity: str = "error"   # "error" | "warning" | "info"
    path: str = ""
    line: Optional[int] = None

    def __str__(self) -> str:
        return self.message

    def __contains__(self, item: str) -> bool:
        """'substring' in issue でメッセージを検索できるようにする（後方互換性）"""
        return item in self.message


@dataclass
class LintOptions:
    """lint_file / lint_string の動作オプション"""
    quiet: bool = False
    fail_on: str = "error"   # "error" | "warning"
    max_warnings: Optional[int] = None


class RSLSyntaxError(Exception):
    pass


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _check_unknown_tags(root: ET.Element, issues: List[LintIssue]) -> None:
    for elem in root.iter():
        if elem.tag not in ALLOWED_CHILDREN:
            issues.append(LintIssue(
                code="RSL004",
                message=f"未知のタグ: <{_local(elem.tag)}>",
                severity="error",
                path=f"/{_local(elem.tag)}",
            ))


def _check_parent_child_rules(root: ET.Element, issues: List[LintIssue]) -> None:
    for parent in root.iter():
        allowed = ALLOWED_CHILDREN.get(parent.tag, set())
        for child in list(parent):
            if child.tag not in allowed:
                issues.append(LintIssue(
                    code="RSL005",
                    message=(
                        f"不正な入れ子: <{_local(child.tag)}> は"
                        f" <{_local(parent.tag)}> の子として許可されていません"
                    ),
                    severity="error",
                    path=f"/{_local(parent.tag)}/{_local(child.tag)}",
                ))


def _check_cardinality(root: ET.Element, issues: List[LintIssue]) -> None:
    if root.tag != q("rsl"):
        issues.append(LintIssue(
            code="RSL003",
            message="ルート要素は <rsl> である必要があります",
            severity="error",
            path="/",
        ))
        return
    rsl_children = [c for c in root if c.tag == q("content")]
    rule = CARDINALITY_RULES[(q("rsl"), q("content"))]
    if len(rsl_children) < rule["min"]:
        issues.append(LintIssue(
            code="RSL006",
            message="<rsl> 直下に <content> が最低1つ必要です",
            severity="error",
            path="/rsl",
        ))
    for content in rsl_children:
        lic = [c for c in content if c.tag == q("license")]
        rule = CARDINALITY_RULES[(q("content"), q("license"))]
        if len(lic) < rule["min"]:
            issues.append(LintIssue(
                code="RSL006",
                message="<content> 直下に <license> が最低1つ必要です",
                severity="error",
                path="/rsl/content",
            ))
        for opt in (q("schema"), q("copyright"), q("terms")):
            cnt = sum(1 for c in content if c.tag == opt)
            maxv = CARDINALITY_RULES[(q("content"), opt)]["max"]
            if maxv is not None and cnt > maxv:
                issues.append(LintIssue(
                    code="RSL006",
                    message=(
                        f"<content> 直下の <{_local(opt)}> は最大1つまでです"
                        f"（{cnt}個見つかりました）"
                    ),
                    severity="error",
                    path="/rsl/content",
                ))


def _is_bool(value: str) -> bool:
    return value.lower() in {"true", "false", "1", "0", "yes", "no"}


_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}) )?$".strip()
)


def _is_rfc3339(value: str) -> bool:
    # 簡易チェック（厳密な検証は将来拡張）。
    # 日付のみ (YYYY-MM-DD) も許容。
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return True
    return _RFC3339_RE.fullmatch(value) is not None


def _is_url(value: str) -> bool:
    # http(s) スキームの絶対URL、または "/" から始まる（ただし "//" ではない）絶対パスを許容
    if value.startswith("/") and not value.startswith("//"):
        return True
    try:
        p = urlparse(value)
    except Exception:
        return False
    return p.scheme in {"http", "https"} and bool(p.netloc)


def _is_iso4217(value: str) -> bool:
    return len(value) == 3 and value.isalpha() and value.upper() == value


def _is_int(value: str) -> bool:
    return value.isdigit() or (value.startswith("-") and value[1:].isdigit())


def _validate_attr_type(expected_type: str, value: str) -> bool:
    if expected_type == "boolean":
        return _is_bool(value)
    if expected_type == "integer":
        return _is_int(value)
    if expected_type == "rfc3339":
        return _is_rfc3339(value)
    if expected_type == "url":
        return _is_url(value)
    if expected_type == "iso4217":
        return _is_iso4217(value)
    # 未知タイプ: とりあえず通す（将来拡張）
    return True


def _check_attributes(root: ET.Element, issues: List[LintIssue]) -> None:
    for elem in root.iter():
        rules = ATTRIBUTE_RULES.get(elem.tag)
        if not rules:
            continue
        # 必須属性チェック
        for attr_name, spec in rules.items():
            required = bool(spec.get("required"))
            if required and attr_name not in elem.attrib:
                issues.append(LintIssue(
                    code="RSL101",
                    message=f"必須属性 '{attr_name}' が <{_local(elem.tag)}> に不足しています",
                    severity="error",
                    path=f"/{_local(elem.tag)}",
                ))
        # 型/列挙チェック
        for attr_name, spec in rules.items():
            if attr_name not in elem.attrib:
                continue
            val = elem.attrib[attr_name]
            if "enum" in spec:
                allowed = spec["enum"]  # type: ignore[index]
                if val not in allowed:  # type: ignore[operator]
                    issues.append(LintIssue(
                        code="RSL103",
                        message=(
                            f"<{_local(elem.tag)}> の属性 '{attr_name}' の値"
                            f" '{val}' は許可されていません"
                        ),
                        severity="error",
                        path=f"/{_local(elem.tag)}",
                    ))
            if "type" in spec:
                etype = str(spec["type"])  # type: ignore[index]
                if not _validate_attr_type(etype, val):
                    issues.append(LintIssue(
                        code="RSL102",
                        message=(
                            f"<{_local(elem.tag)}> の属性 '{attr_name}'"
                            f" は {etype} 形式である必要があります"
                        ),
                        severity="error",
                        path=f"/{_local(elem.tag)}",
                    ))


def _check_type_uniqueness(root: ET.Element, issues: List[LintIssue]) -> None:
    """Phase 3: <permits>/<prohibits>/<payment>/<legal> の type 属性一意性チェック。

    RSL標準では、<license> 直下の各要素は同一 type 属性値を複数持てない。
    """
    for license_elem in root.iter(q("license")):
        seen: Dict[str, Set[str]] = {}  # ローカルタグ名 -> 出現済み type 値の集合
        for child in license_elem:
            if child.tag not in TYPE_UNIQUE_TAGS:
                continue
            tag_local = _local(child.tag)
            type_val = child.attrib.get("type")
            if type_val is None:
                continue  # 必須チェックは _check_attributes が担う
            if tag_local not in seen:
                seen[tag_local] = set()
            if type_val in seen[tag_local]:
                issues.append(LintIssue(
                    code="RSL201",
                    message=(
                        f"<{tag_local}> の type='{type_val}' が"
                        f" <license> 内で重複しています"
                    ),
                    severity="error",
                    path=f"/rsl/content/license/{tag_local}",
                ))
            else:
                seen[tag_local].add(type_val)


def _check_root_namespace_decl(root: ET.Element, issues: List[LintIssue]) -> None:
    if root.tag != q("rsl"):
        issues.append(LintIssue(
            code="RSL002",
            message=f"既定名前空間（xmlns）は '{RSL_NS_URL}' を指定してください",
            severity="error",
            path="/",
        ))


def lint_string(
    xml_text: str,
    options: Optional[LintOptions] = None,
) -> Tuple[bool, List[LintIssue]]:
    issues: List[LintIssue] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return False, [LintIssue(code="RSL001", message=f"XML構文エラー: {e}", severity="error")]

    _check_root_namespace_decl(root, issues)
    if root.tag != q("rsl"):
        return False, issues

    _check_unknown_tags(root, issues)
    _check_parent_child_rules(root, issues)
    _check_cardinality(root, issues)
    _check_attributes(root, issues)
    _check_type_uniqueness(root, issues)
    return (len(issues) == 0), issues


def lint_file(
    path: str,
    options: Optional[LintOptions] = None,
) -> Tuple[bool, List[LintIssue]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return lint_string(text, options)


def _format_text(ok: bool, issues: List[LintIssue], quiet: bool = False) -> str:
    lines: List[str] = []
    if ok:
        if not quiet:
            lines.append("OK: タグ構造は仕様に準拠しています。")
    else:
        lines.append("NG: 仕様逸脱が見つかりました。")
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        for idx, issue in enumerate(errors, 1):
            lines.append(f"{idx}. [{issue.code}] {issue.message}")
        if not quiet and warnings:
            for idx, issue in enumerate(warnings, 1):
                lines.append(f"  W{idx}. [{issue.code}] {issue.message}")
        lines.append(f"エラー: {len(errors)}件, 警告: {len(warnings)}件")
    return "\n".join(lines)


def _format_json(ok: bool, issues: List[LintIssue]) -> str:
    errors = [asdict(i) for i in issues if i.severity == "error"]
    warnings = [asdict(i) for i in issues if i.severity == "warning"]
    infos = [asdict(i) for i in issues if i.severity == "info"]
    result = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(infos),
        },
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rsl-lint",
        description="RSL 静的構文チェッカー",
    )
    parser.add_argument(
        "xml",
        nargs="?",
        help="RSL license.xml のパス（--stdin 使用時は省略可）",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="エラーのみ表示（OK の場合は何も出力しない）",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
        help="出力フォーマット（既定: text）",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="標準入力から XML を読み込む",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    if args.stdin:
        xml_text = sys.stdin.read()
        ok, issues = lint_string(xml_text)
    elif args.xml:
        ok, issues = lint_file(args.xml)
    else:
        parser.error("ファイルパスか --stdin を指定してください")
        return 2

    if args.fmt == "json":
        print(_format_json(ok, issues))
    else:
        output = _format_text(ok, issues, quiet=args.quiet)
        if output:
            print(output)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_main())
