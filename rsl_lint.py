
"""
rsl_lint.py — RSL 静的構文チェック

Phase 1: タグ構造/名前空間/親子関係/未知タグ/多重度（既存）
Phase 2: 属性の必須/型/列挙制約の検査（今回追加）

依存は標準ライブラリのみ。
"""
import sys
import argparse
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict, Set
from urllib.parse import urlparse
import re

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
# 仕様の詳細がドラフトのため、まずは代表的な属性のみ定義。
# - <content url> は必須かつ URL/絶対パス想定
# - <permits type> は必須かつ列挙（暫定語彙）
# - <prohibits type> も同一語彙を想定（将来調整）
# - <amount currency> は ISO4217 通貨コード（将来利用のため実装は用意）

PERMISSION_TYPE_VOCAB = {
    # 暫定：一般的なライセンス語彙（仕様に合わせて後続更新）
    "usage",
    "distribution",
    "modification",
    "private-use",
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
    q("amount"): {
        "currency": {"required": True, "type": "iso4217"},
        # 値自体（テキスト）に数値が入る想定は Phase 3 以降で扱う
    },
}

class RSLSyntaxError(Exception):
    pass

def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag

def _check_unknown_tags(root: ET.Element, issues: List[str]) -> None:
    for elem in root.iter():
        if elem.tag not in ALLOWED_CHILDREN:
            issues.append(f"未知のタグ: <{_local(elem.tag)}>")

def _check_parent_child_rules(root: ET.Element, issues: List[str]) -> None:
    for parent in root.iter():
        allowed = ALLOWED_CHILDREN.get(parent.tag, set())
        for child in list(parent):
            if child.tag not in allowed:
                issues.append(
                    f"不正な入れ子: <{_local(child.tag)}> は <{_local(parent.tag)}> の子として許可されていません"
                )

def _check_cardinality(root: ET.Element, issues: List[str]) -> None:
    if root.tag != q("rsl"):
        issues.append("ルート要素は <rsl> である必要があります")
        return
    rsl_children = [c for c in root if c.tag == q("content")]
    rule = CARDINALITY_RULES[(q("rsl"), q("content"))]
    if len(rsl_children) < rule["min"]:
        issues.append("<rsl> 直下に <content> が最低1つ必要です")
    for content in rsl_children:
        lic = [c for c in content if c.tag == q("license")]
        rule = CARDINALITY_RULES[(q("content"), q("license"))]
        if len(lic) < rule["min"]:
            issues.append("<content> 直下に <license> が最低1つ必要です")
        for opt in (q("schema"), q("copyright"), q("terms")):
            cnt = sum(1 for c in content if c.tag == opt)
            maxv = CARDINALITY_RULES[(q("content"), opt)]["max"]
            if maxv is not None and cnt > maxv:
                issues.append(
                    f"<content> 直下の <{_local(opt)}> は最大1つまでです（{cnt}個見つかりました）"
                )

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
    # http(s) スキームの絶対URL、または "/" から始まる絶対パスを許容
    if value.startswith("/"):
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

def _xpath_like(elem: ET.Element) -> str:
    # 簡易XPath風のパスを生成（同名兄弟はインデックス省略）
    parts: List[str] = []
    cur: Optional[ET.Element] = elem
    while cur is not None:
        parts.append(_local(cur.tag))
        cur = cur.getparent() if hasattr(cur, "getparent") else None
        # xml.etree には getparent がないので上手くいかないため break
        break
    # ルートからではなく要素単体名のみ返す（ElementTree の制約のため）
    return "/" + "/".join(reversed(parts))

def _check_attributes(root: ET.Element, issues: List[str]) -> None:
    for elem in root.iter():
        rules = ATTRIBUTE_RULES.get(elem.tag)
        if not rules:
            continue
        # 必須属性チェック
        for attr_name, spec in rules.items():
            required = bool(spec.get("required"))
            if required and attr_name not in elem.attrib:
                issues.append(
                    f"必須属性 '{attr_name}' が <{_local(elem.tag)}> に不足しています"
                )
        # 型/列挙チェック
        for attr_name, spec in rules.items():
            if attr_name not in elem.attrib:
                continue
            val = elem.attrib[attr_name]
            if "enum" in spec:
                allowed = spec["enum"]  # type: ignore[index]
                if val not in allowed:  # type: ignore[operator]
                    issues.append(
                        f"<{_local(elem.tag)}> の属性 '{attr_name}' の値 '{val}' は許可されていません"
                    )
            if "type" in spec:
                etype = str(spec["type"])  # type: ignore[index]
                if not _validate_attr_type(etype, val):
                    issues.append(
                        f"<{_local(elem.tag)}> の属性 '{attr_name}' は {etype} 形式である必要があります"
                    )
def _check_root_namespace_decl(root: ET.Element, issues: List[str]) -> None:
    if root.tag != q("rsl"):
        issues.append(
            f"既定名前空間（xmlns）は '{RSL_NS_URL}' を指定してください"
        )

def lint_string(xml_text: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return False, [f"XML構文エラー: {e}"]

    _check_root_namespace_decl(root, issues)
    if root.tag != q("rsl"):
        return False, issues

    _check_unknown_tags(root, issues)
    _check_parent_child_rules(root, issues)
    _check_cardinality(root, issues)
    _check_attributes(root, issues)
    return (len(issues) == 0), issues

def lint_file(path: str) -> Tuple[bool, List[str]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return lint_string(text)

def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RSL 静的構文チェッカー（タグ検査）")
    parser.add_argument("xml", help="RSL license.xml のパス")
    args = parser.parse_args(argv)

    ok, issues = lint_file(args.xml)
    if ok:
        print("OK: タグ構造は仕様に準拠しています。")
        return 0
    else:
        print("NG: 仕様逸脱が見つかりました。")
        for i, msg in enumerate(issues, 1):
            print(f"{i}. {msg}")
        return 1

if __name__ == "__main__":
    sys.exit(_main())
