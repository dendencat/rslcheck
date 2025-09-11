# todo.md — 実装タスク一覧（優先度つき）

## マイルストーン M1（Phase 1強化・配布準備）
- [ ] **CLI整備**: rsl-lint エントリポイント（argparse→typer検討）と --format json|text, --quiet
- [ ] **JSONレポート**: エラー/警告/統計のJSON構造定義と出力
- [ ] **エラーコード体系**: RSL001〜 の割当、ドキュメント化
- [ ] **行・列番号**: 可能な範囲で位置情報を付与（パーサ差し替え or 再パース）
- [ ] **テスト**: Phase 1の単体テスト（pytest）、OK/NGサンプルの整備
- [ ] **CI**: GitHub Actions（lint, type-check, test, build）
- [ ] **配布**: pyproject.toml 作成、PyPIリリース準備
- [ ] **ドキュメント**: README更新、examples追加、CHANGELOG開始

## マイルストーン M2（Phase 2 属性/値検証）
- [ ] **必須属性検査**: 仕様で必須の属性定義を反映（例: `<content url>`）
- [ ] **型/フォーマット**: boolean, integer, RFC3339日時, URL, ISO4217 等のバリデータ
- [ ] **列挙制約**: type 等の語彙リスト化と検査
- [ ] **Severity導入**: warningを区別、--fail-on/--max-warnings 実装
- [ ] **多言語**: --lang en の土台（メッセージ辞書）

## マイルストーン M3（Phase 3 一意性/依存関係/参照）
- [ ] **一意性ルール**: `<permits>/<prohibits>/<payment>/<legal>` の type 重複禁止
- [ ] **依存/排他**: 仕様化（例: Aが真ならB必須/B禁止）
- [ ] **参照整合性**: id↔ref チェック（仕様に存在する場合）
- [ ] **名前空間強化**: 既定NS以外（prefix付き）入力の受容オプション

## マイルストーン M4（UX/拡張）
- [ ] **外部ルール**: --rules でYAML/JSONルールを読み込み・既定語彙にマージ
- [ ] **エディタ連携**: VS Code拡張の簡易プロトタイプ（problemMatcher）
- [ ] **パフォーマンス**: 大規模XML向けストリーム検査（iterparse）
- [ ] **出力改善**: SARIF出力（Code Scanning統合）

## 補助タスク
- [ ] サンプルの網羅（OK/NGの境界ケース）
- [ ] セキュリティテスト（XXE等）
- [ ] 仕様差分追従（Draft→1.0正式）

## 想定スケジュール（ざっくり）
- **M1**: 1〜1.5週間
- **M2**: 1.5〜2週間
- **M3**: 1.5週間
- **M4**: 1週間

（並行作業可。正式仕様が確定していない箇所はM2以降で調整）