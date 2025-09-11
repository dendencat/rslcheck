# requirements.md — RSL 静的構文チェックツール 要件定義

## 目的
RSL（Responsible/Restricted Software License; 仕様は提供PDFに準拠）のライセンスドキュメント（XML想定）に対して、静的な構文・仕様準拠チェックを自動化します。CIでの自動検証とエディタ／CLIでの手動検証の両方を想定します。

## 対象スコープ（第1〜3段階）
- **Phase 1（実装済みの最小）**: タグ構造の妥当性
  - ルート要素が `<rsl>` であること
  - 既定NS: `xmlns="https://rslstandard.org/rsl"`
  - 親子関係・未知タグ検出
  - 必須・最大出現回数（例: `<content>` 1+, `<license>` 1+、`<schema>/<copyright>/<terms>` 0..1）
- **Phase 2**: 属性・値の検査
  - 必須属性の有無（例: `<content url>` など仕様で定義されたもの）
  - 属性値の型・フォーマット（ブール、整数、ISO 8601/RFC 3339日時、URL、ISO 4217通貨コード等）
  - 文字列の列挙制約（例: `type` に対する決め打ち語彙）
- **Phase 3**: 参照整合性と一意性
  - `<permits>/<prohibits>/<payment>/<legal>` の `type` ごとの一意性（同一typeの重複禁止）
  - 文書内ID/参照の整合性（仕様に存在する場合）
  - 相互排他・依存関係（例: AがあるときはB必須／禁止、数量範囲制約など）

> 注: 仕様の語彙・属性名・必須性は提供資料（RSL 1.0 Draft / OLP 1.0 Draft / Getting Started）に合わせて後続PRで確定させます。本要件では検査カテゴリとI/Fを先行定義します。

## 非スコープ（当面）
- 文章の法的解釈（ライセンス条項の意味論）
- 外部リソースのオンライン検証（URL疎通、支払い先検証 等）
- 署名/暗号化の検証

## 入力/出力仕様
- **入力**: RSL XMLファイル（UTF-8）。将来拡張でYAML/JSON表現→内部XMLへ変換も検討。
- **出力**:
  - **CLI**: 人間可読なテキスト（OK/NG、エラー一覧、エラー件数）。終了コード 0=OK / 1=NG。
  - **機械可読**: `--format json` でJSON出力（エラー配列、警告配列、統計、バージョン）。
  - **Severity**: `error`/`warning`/`info` をサポート（Phase 1では error のみ必須、warningは任意）。

### エラー・メッセージ仕様
- 構成: `code`（短い識別子）、`message`（日本語）、`path`（XPath風 or 位置情報）、`line`/`column`（取得可能な範囲で）
- 例: `RSL001`, `ルート要素は <rsl> である必要があります`, `/rsl`, `line:1`

## コマンドラインI/F
```bash
rsl-lint [OPTIONS] <path-or-glob>

OPTIONS:
  -q, --quiet              エラーのみ表示
  --format json|text       出力フォーマット（既定: text）
  --rules <path>           カスタムルール定義（YAML/JSON; 仕様語彙の追加や上書き）
  --max-warnings <n>       許容warning数（超過で終了コード=1）
  --fail-on error|warn    失敗判定の閾値（既定: error）
  --stdin                  標準入力から読み込む
  --version                バージョン表示
```

## ライブラリI/F（Python）
```python
from rsl_lint import lint_file, lint_string, LintOptions

ok, report = lint_file("license.xml", options=LintOptions(format='json'))
# report は {errors:[], warnings:[], stats:{...}} を想定
```
LintOptions で NS/語彙の拡張、警告閾値、フォーマットを指定可能。

## 仕様モデル（内部）
- 語彙定義: 許可タグ、親子関係、多重度、必須属性、型、列挙値、依存関係を辞書で定義。
- 名前空間: 既定NSにバインド。将来、プレフィックス付き入力も受容（オプション）。
- 拡張: --rules でJSON/YAMLの外部ルールをロードして上書き可能。

## パフォーマンス/容量要件
- 1MB 程度のXMLを100ms〜数百msで検査可能であること（目安）。
- 大規模ファイル対応はストリームパーサへの差し替えで対応可（将来）。

## 品質要件
- Py3.9+ 対応。依存は標準ライブラリ優先。
- 単体テストカバレッジ 80% 以上（Phase 1基準）。
- 例外は握り潰さず、ユーザーフレンドリーなメッセージを返す。

## ログ/トレース
- RSL_LINT_DEBUG=1 でデバッグログを出力。

## 配布/運用
- PyPI配布（rsl-lint）。pip install rsl-lint でCLI/ライブラリ同梱。
- セマンティックバージョニング（MAJOR.MINOR.PATCH）。
- GitHub Actions でテスト/型検査/ビルド/発行。

## セキュリティ
- 外部リソースへアクセスしない。
- XML外部実体（XXE）を無効化（標準ライブラリ利用時でも明示テスト）。

## 国際化
- 既定は日本語メッセージ。--lang en で英語へ切替（後続フェーズ）。

## サンプル（Phase 1）
- OK例とNG例を examples/ に同梱。CIで回帰テストに利用。

## 受け入れ基準（Phase 1 完了定義）
- CLI/ライブラリの両I/Fで、タグ構造・NS・多重度・未知タグ・不正入れ子を確実に検出。
- 代表的なOK/NGサンプルで期待どおりの結果と終了コード。
- ドキュメント（README/requirements/todo/CHANGELOG）が整備されている。