RSL Linter — RSL 静的構文チェックツール
===

## 概要
RSL（Really Simple Licensing / Responsible/Restricted Software License）のXMLライセンス文書を検査する静的リンターです。RSL 1.0 ドラフト仕様（_docs 配下の資料）に基づき、タグ構造や属性の妥当性を機械的にチェックします。

> 注意: 本レポジトリは現在試験段階のものであり、商用向けに作成されておりません。本レポジトリ内のソースコードを使用したことにより不利益が発生したとしても、作成者は一切の責任を負いません。

## 対応範囲（現状）
- Phase 1（実装済み）
  - ルート要素 <rsl> と既定名前空間 xmlns="https://rslstandard.org/rsl"
  - 親子関係の検証、不正な入れ子の検出
  - 未知タグの検出
  - 多重度チェック（例: <content> 1+, <license> 1+、<schema>/<copyright>/<terms> 0..1）
- Phase 2（属性/値検証・第1弾）
  - 必須属性チェック
  - 属性値の型/フォーマット検証（URL, ISO4217 通貨コード）
  - 列挙値制約（type 属性の語彙）

## 現在の属性ルール（暫定）
- <content>
  - url（必須）: `http(s)://...` の絶対URL または `/` で始まる絶対パス
- <permits>, <prohibits>
  - type（必須）: `{usage, distribution, modification, private-use}`
- <amount>
  - currency（必須）: ISO 4217（大文字3文字）

注: 語彙や必須性はドラフト仕様に基づく暫定版です。正式仕様の確定に合わせて調整されます。

## 仕様資料
- _docs/ 配下に RSL 1.0 / OLP 1.0 のドラフトPDFと要件定義（requirements.md）、タスク（todo.md）が含まれます。
- 仕様の曖昧な箇所は _docs/requirements.md を優先します。

## 必要要件
- Python 3.9 以上
- 外部依存なし（標準ライブラリのみ使用）

## インストール/取得
- 開発/検証目的の場合はリポジトリをクローンしてそのまま実行できます。
```
    git clone <this-repo-url>
    cd rslcheck
    python3 --version  # 3.9+
```

## 使い方（CLI）
現状はスクリプトとして実行します（将来 rsl-lint エントリポイントを提供予定）。

    python3 rsl_lint.py <path/to/license.xml>

- 検査に合格した場合は OK、逸脱がある場合は NG とエラー一覧を表示します。
- 終了コードは、エラーなし=0、エラーあり=1 を返します。

### 実行例
- OK 例
```bash
    python3 rsl_lint.py sample/license-ok.xml
    # => OK: タグ構造は仕様に準拠しています。
```

- 必須属性不足
```bash
    python3 rsl_lint.py sample/license-missing-url.xml
    # => NG: 必須属性 'url' が <content> に不足しています
```
- URL形式エラー
```bash
    python3 rsl_lint.py sample/license-bad-url.xml
    # => NG: <content> の属性 'url' は url 形式である必要があります
```

- 列挙外エラー
```bash 
    python3 rsl_lint.py sample/license-bad-permits-type.xml
    # => NG: <permits> の属性 'type' の値 'unknown' は許可されていません
```

## ライブラリAPI
Pythonコードからも呼び出せます。

```python
    from rsl_lint import lint_file, lint_string

    ok, issues = lint_file("sample/license-ok.xml")
    if not ok:
        for msg in issues:
            print(msg)

- lint_string(xml_text: str) -> tuple[bool, list[str]]
- lint_file(path: str) -> tuple[bool, list[str]]
```

返り値は (`ok, issues`)。`ok=True` でエラーなし、`issues` に日本語のメッセージを格納します。

## サンプル
- OK: sample/license-ok.xml
- NG: sample/license-ng.xml, sample/license-missing-url.xml, sample/license-bad-url.xml, sample/license-bad-permits-type.xml

## テスト
- 単体テストは pytest を使用しています。
```bash
    python3 -m pip install pytest
    pytest -q
```

- 追加済みテスト: tests/test_phase2_attributes.py

## ロードマップ（抜粋）
- Phase 2 続き
  - 追加の属性/型（boolean, integer, RFC3339日時）への本格適用
  - JSON出力（--format json）と Severity（error/warning）
  - CLIオプション: --quiet, --fail-on, --max-warnings
- Phase 3
  - type の一意性、依存・排他関係、参照整合性（id/ref）
- Phase 4
  - 外部ルールファイル --rules（YAML/JSON）
  - SARIF出力やエディタ連携

## セキュリティ
- 外部リソースへアクセスしません。
- XML 外部実体（XXE）などの安全性は標準ライブラリ使用範囲で配慮し、今後テストを追加します。

## 開発指針
- 依存は可能な限り標準ライブラリのみ。
- メッセージは既定で日本語。将来的に --lang en を検討。
- 仕様差分は _docs/requirements.md とPDFの最新版に追随します。
