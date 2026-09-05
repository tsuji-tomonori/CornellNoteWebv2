<!-- dev-standard:begin -->
# dev-standard lightweight guardrails

portableなblocking guardrailは次の3本だけです。

1. durableな要件を`spec/requirements/requirements.qnt`へ原子的に保つ。
2. 現在状態の設計を実装artifactから決定的に生成する。
3. 変更と受入条件に関係する検査だけを実行する。

通常の入口は`$chat-first-development`です。Quint正本からJSONを生成し、そのJSONから人向けMarkdownを生成します。生成viewは直接編集しません。

dev-standardは、このrepositoryのbranch、merge方式、CI/CD workflow、required check、PR template、commit形式を追加も変更もしません。既存のrepository指示と権限境界を優先してください。
<!-- dev-standard:end -->

## プロジェクト固有ルール
- devのpush（PR統合を含む）でE2EとPages公開。mainのCDは検査済みdevと同一treeであることを確認する。
- GitメッセージとPRコメントは日本語Gitmoji Conventional Commit形式。
- Pythonはuv、フロントはTypeScript。生成設計は直接編集しない。
- 前回の作業が中断しても復元できるように、検証状況を明記して作業ブランチへ適宜pushする。
