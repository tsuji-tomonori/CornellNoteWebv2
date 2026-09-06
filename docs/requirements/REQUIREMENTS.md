<!-- tools/quintflow.pyによる自動生成。spec/requirements/requirements.qntを編集すること。 -->
# CornellNoteWebv2 要件一覧

- スキーマ版: 1
- カタログ版: 2
- Product(JSON): <code>"CornellNoteWebv2"</code>
- 更新日(JSON): <code>"2026-09-06"</code>
- 正本: `spec/requirements/requirements.qnt`
- 機械可読view: `spec/requirements/requirements.json`

| ID | 版 | 状態 | 種別 | 原子的な義務 | 検証方法 |
|---|---:|---|---|---|---|
| <code>"REQ-AUTH"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、本人のノート一覧が表示され、未認証のAPI取得は401になるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-OWNER"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、所有者以外にはノートを返さず変更しないを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-LIST"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、自身の全ノートをコレクション別に閲覧できるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-SEARCH"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、タイトルと本文・問い・まとめで絞り込めるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-EDIT"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、再読込後も三欄が保持されるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-TASK"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、保存後もタスク状態を保持するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-SHARE"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、ログイン不要で閲覧のみできるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-REVOKE"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、既存リンクでの閲覧を拒否するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-EXPIRY"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、期限切れを返すを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-CONFLICT"</code> | 1 | 有効 | 機能 | CornellNoteWebv2は、409を返し最新保存を上書きしないを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-MOBILE"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、入力と保存を横スクロールなしで利用できるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-UI"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、ユーカリミント配色とCUE・NOTE・SUMMARY・ACTIONの配置が認識できるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-COMPOSE"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、DB・バックエンド・フロントが起動して操作可能になるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-AWS"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、CloudFront・非公開S3・API Gateway・Lambda・DSQL・Cognitoを生成するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-COST"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、VPC・NAT・WAFを追加せず抑制理由を限定して記録するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-MIGRATION"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、適用済checksumを検査しテーブルと全カラムに日本語コメントがあるを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-DESIGN"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、API・DB・画面・インフラの構造を決定的に生成し差分を検知するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-TEST"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、pytest・TS単体・静的解析・CDK nag・アサーション・snapshotを検査するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-REPORT"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、全Given When Thenと右側スクリーンショットおよび品質・coverageをPagesで初期展開表示するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-DEPLOY"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、同一treeのdev検査成功を確認後にOIDC認証してCDKとフロントを配置するを**維持する**（<code>"maintain"</code>） | automated-tests-and-review |
| <code>"REQ-SQL"</code> | 1 | 有効 | 制約 | CornellNoteWebv2は、各APIのsqlファイルからgenerated/queries.pyを生成してfunctionsで呼ぶを**維持する**（<code>"maintain"</code>） | automated-tests |

## REQ-AUTH: 本人のノートにログインする

要件ID(JSON): <code>"REQ-AUTH"</code>
タイトル(JSON): <code>"本人のノートにログインする"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"本人のノート一覧が表示され、未認証のAPI取得は401になる"</code>
CornellNoteWebv2は、本人のノート一覧が表示され、未認証のAPI取得は401になるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-AUTH"</code> 前提: ログインしていない利用者。条件: 正しい認証でログインする。期待結果: 本人のノート一覧が表示され、未認証のAPI取得は401になる。
  - criterion(JSON Object): <code>{"given":"ログインしていない利用者","id":"AC-AUTH","then":"本人のノート一覧が表示され、未認証のAPI取得は401になる","when":"正しい認証でログインする"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/auth.py","frontend/src/auth.ts"]</code>
- テスト: <code>["backend/tests/test_api.py","frontend/src/auth.test.ts","frontend/e2e/notes.spec.ts"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-OWNER: 他人のノートを保護する

要件ID(JSON): <code>"REQ-OWNER"</code>
タイトル(JSON): <code>"他人のノートを保護する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"所有者以外にはノートを返さず変更しない"</code>
CornellNoteWebv2は、所有者以外にはノートを返さず変更しないを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-OWNER"</code> 前提: 二人の利用者が存在する。条件: 他人のノートIDで取得・変更する。期待結果: 所有者以外にはノートを返さず変更しない。
  - criterion(JSON Object): <code>{"given":"二人の利用者が存在する","id":"AC-OWNER","then":"所有者以外にはノートを返さず変更しない","when":"他人のノートIDで取得・変更する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/apis/notes/get_note/functions.py"]</code>
- テスト: <code>["backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-LIST: ノートを分類して表示する

要件ID(JSON): <code>"REQ-LIST"</code>
タイトル(JSON): <code>"ノートを分類して表示する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"自身の全ノートをコレクション別に閲覧できる"</code>
CornellNoteWebv2は、自身の全ノートをコレクション別に閲覧できるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-LIST"</code> 前提: ノートにコレクションが設定されている。条件: 一覧画面を開く。期待結果: 自身の全ノートをコレクション別に閲覧できる。
  - criterion(JSON Object): <code>{"given":"ノートにコレクションが設定されている","id":"AC-LIST","then":"自身の全ノートをコレクション別に閲覧できる","when":"一覧画面を開く"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/App.tsx","frontend/src/domain.ts"]</code>
- テスト: <code>["frontend/src/domain.test.ts","frontend/e2e/notes.spec.ts"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-SEARCH: ノートの内容を検索する

要件ID(JSON): <code>"REQ-SEARCH"</code>
タイトル(JSON): <code>"ノートの内容を検索する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"タイトルと本文・問い・まとめで絞り込める"</code>
CornellNoteWebv2は、タイトルと本文・問い・まとめで絞り込めるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-SEARCH"</code> 前提: 複数のノートがある。条件: 語句を入力する。期待結果: タイトルと本文・問い・まとめで絞り込める。
  - criterion(JSON Object): <code>{"given":"複数のノートがある","id":"AC-SEARCH","then":"タイトルと本文・問い・まとめで絞り込める","when":"語句を入力する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/domain.ts"]</code>
- テスト: <code>["frontend/src/domain.test.ts","frontend/e2e/notes.spec.ts"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-EDIT: コーネル式の三欄を編集する

要件ID(JSON): <code>"REQ-EDIT"</code>
タイトル(JSON): <code>"コーネル式の三欄を編集する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"再読込後も三欄が保持される"</code>
CornellNoteWebv2は、再読込後も三欄が保持されるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-EDIT"</code> 前提: 本人のノートを開いている。条件: 問い・記録・まとめを保存する。期待結果: 再読込後も三欄が保持される。
  - criterion(JSON Object): <code>{"given":"本人のノートを開いている","id":"AC-EDIT","then":"再読込後も三欄が保持される","when":"問い・記録・まとめを保存する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/Editor.tsx","backend/src/app/apis/notes/update_note/functions.py"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts","backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-TASK: チェックリストを管理する

要件ID(JSON): <code>"REQ-TASK"</code>
タイトル(JSON): <code>"チェックリストを管理する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"保存後もタスク状態を保持する"</code>
CornellNoteWebv2は、保存後もタスク状態を保持するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-TASK"</code> 前提: ノートを編集中。条件: 期日付きタスクを追加・完了・削除する。期待結果: 保存後もタスク状態を保持する。
  - criterion(JSON Object): <code>{"given":"ノートを編集中","id":"AC-TASK","then":"保存後もタスク状態を保持する","when":"期日付きタスクを追加・完了・削除する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/Editor.tsx","backend/src/app/models.py"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts","backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-SHARE: 閲覧リンクを発行する

要件ID(JSON): <code>"REQ-SHARE"</code>
タイトル(JSON): <code>"閲覧リンクを発行する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"ログイン不要で閲覧のみできる"</code>
CornellNoteWebv2は、ログイン不要で閲覧のみできるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-SHARE"</code> 前提: 所有者がノートを保存している。条件: 共有範囲を確認してリンクを発行する。期待結果: ログイン不要で閲覧のみできる。
  - criterion(JSON Object): <code>{"given":"所有者がノートを保存している","id":"AC-SHARE","then":"ログイン不要で閲覧のみできる","when":"共有範囲を確認してリンクを発行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/apis/notes/create_share/functions.py","frontend/src/App.tsx"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts","backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-REVOKE: 共有リンクを解除する

要件ID(JSON): <code>"REQ-REVOKE"</code>
タイトル(JSON): <code>"共有リンクを解除する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"既存リンクでの閲覧を拒否する"</code>
CornellNoteWebv2は、既存リンクでの閲覧を拒否するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-REVOKE"</code> 前提: 有効な共有リンクがある。条件: 所有者が共有を解除する。期待結果: 既存リンクでの閲覧を拒否する。
  - criterion(JSON Object): <code>{"given":"有効な共有リンクがある","id":"AC-REVOKE","then":"既存リンクでの閲覧を拒否する","when":"所有者が共有を解除する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/apis/notes/revoke_share/functions.py"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts","backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-EXPIRY: 共有リンクの期限を守る

要件ID(JSON): <code>"REQ-EXPIRY"</code>
タイトル(JSON): <code>"共有リンクの期限を守る"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"期限切れを返す"</code>
CornellNoteWebv2は、期限切れを返すを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-EXPIRY"</code> 前提: 発行から7日が経過する。条件: リンクを開く。期待結果: 期限切れを返す。
  - criterion(JSON Object): <code>{"given":"発行から7日が経過する","id":"AC-EXPIRY","then":"期限切れを返す","when":"リンクを開く"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/apis/notes/get_shared/functions.py"]</code>
- テスト: <code>["backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-CONFLICT: 同時更新の上書きを防ぐ

要件ID(JSON): <code>"REQ-CONFLICT"</code>
タイトル(JSON): <code>"同時更新の上書きを防ぐ"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"409を返し最新保存を上書きしない"</code>
CornellNoteWebv2は、409を返し最新保存を上書きしないを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `functional`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"functional"</code>

受入条件:
- <code>"AC-CONFLICT"</code> 前提: 同じノートを複数画面で開く。条件: 古いversionで保存する。期待結果: 409を返し最新保存を上書きしない。
  - criterion(JSON Object): <code>{"given":"同じノートを複数画面で開く","id":"AC-CONFLICT","then":"409を返し最新保存を上書きしない","when":"古いversionで保存する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/apis/notes/update_note/functions.py"]</code>
- テスト: <code>["backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-MOBILE: スマートフォンで編集する

要件ID(JSON): <code>"REQ-MOBILE"</code>
タイトル(JSON): <code>"スマートフォンで編集する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"入力と保存を横スクロールなしで利用できる"</code>
CornellNoteWebv2は、入力と保存を横スクロールなしで利用できるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-MOBILE"</code> 前提: 幅の狭い画面を使う。条件: 三欄を切り替えて操作する。期待結果: 入力と保存を横スクロールなしで利用できる。
  - criterion(JSON Object): <code>{"given":"幅の狭い画面を使う","id":"AC-MOBILE","then":"入力と保存を横スクロールなしで利用できる","when":"三欄を切り替えて操作する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/style.css"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-UI: 4cの見た目を採用する

要件ID(JSON): <code>"REQ-UI"</code>
タイトル(JSON): <code>"4cの見た目を採用する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"ユーカリミント配色とCUE・NOTE・SUMMARY・ACTIONの配置が認識できる"</code>
CornellNoteWebv2は、ユーカリミント配色とCUE・NOTE・SUMMARY・ACTIONの配置が認識できるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"product"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-UI"</code> 前提: 添付4c案を参照する。条件: 画面を確認する。期待結果: ユーカリミント配色とCUE・NOTE・SUMMARY・ACTIONの配置が認識できる。
  - criterion(JSON Object): <code>{"given":"添付4c案を参照する","id":"AC-UI","then":"ユーカリミント配色とCUE・NOTE・SUMMARY・ACTIONの配置が認識できる","when":"画面を確認する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["frontend/src/style.css"]</code>
- テスト: <code>["frontend/e2e/notes.spec.ts"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-COMPOSE: AWS不要で全体を起動する

要件ID(JSON): <code>"REQ-COMPOSE"</code>
タイトル(JSON): <code>"AWS不要で全体を起動する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"DB・バックエンド・フロントが起動して操作可能になる"</code>
CornellNoteWebv2は、DB・バックエンド・フロントが起動して操作可能になるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-COMPOSE"</code> 前提: Docker Composeが利用できる。条件: docker compose up --buildを実行する。期待結果: DB・バックエンド・フロントが起動して操作可能になる。
  - criterion(JSON Object): <code>{"given":"Docker Composeが利用できる","id":"AC-COMPOSE","then":"DB・バックエンド・フロントが起動して操作可能になる","when":"docker compose up --buildを実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["compose.yaml"]</code>
- テスト: <code>[".github/workflows/verify.yml"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-AWS: 指定のサーバーレス構成を生成する

要件ID(JSON): <code>"REQ-AWS"</code>
タイトル(JSON): <code>"指定のサーバーレス構成を生成する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"CloudFront・非公開S3・API Gateway・Lambda・DSQL・Cognitoを生成する"</code>
CornellNoteWebv2は、CloudFront・非公開S3・API Gateway・Lambda・DSQL・Cognitoを生成するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-AWS"</code> 前提: Python CDKを実行する。条件: synthとアサーションテストを実行する。期待結果: CloudFront・非公開S3・API Gateway・Lambda・DSQL・Cognitoを生成する。
  - criterion(JSON Object): <code>{"given":"Python CDKを実行する","id":"AC-AWS","then":"CloudFront・非公開S3・API Gateway・Lambda・DSQL・Cognitoを生成する","when":"synthとアサーションテストを実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["infra/stack.py"]</code>
- テスト: <code>["infra/tests/test_stack.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-COST: 常時課金の追加セキュリティを抑える

要件ID(JSON): <code>"REQ-COST"</code>
タイトル(JSON): <code>"常時課金の追加セキュリティを抑える"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"VPC・NAT・WAFを追加せず抑制理由を限定して記録する"</code>
CornellNoteWebv2は、VPC・NAT・WAFを追加せず抑制理由を限定して記録するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-COST"</code> 前提: CDK nagを適用する。条件: インフラを確認する。期待結果: VPC・NAT・WAFを追加せず抑制理由を限定して記録する。
  - criterion(JSON Object): <code>{"given":"CDK nagを適用する","id":"AC-COST","then":"VPC・NAT・WAFを追加せず抑制理由を限定して記録する","when":"インフラを確認する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["infra/stack.py"]</code>
- テスト: <code>["infra/tests/test_stack.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-MIGRATION: スキーマを追跡して適用する

要件ID(JSON): <code>"REQ-MIGRATION"</code>
タイトル(JSON): <code>"スキーマを追跡して適用する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"適用済checksumを検査しテーブルと全カラムに日本語コメントがある"</code>
CornellNoteWebv2は、適用済checksumを検査しテーブルと全カラムに日本語コメントがあるを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-MIGRATION"</code> 前提: DBを初期化または更新する。条件: migrationを実行する。期待結果: 適用済checksumを検査しテーブルと全カラムに日本語コメントがある。
  - criterion(JSON Object): <code>{"given":"DBを初期化または更新する","id":"AC-MIGRATION","then":"適用済checksumを検査しテーブルと全カラムに日本語コメントがある","when":"migrationを実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["backend/src/app/migrate.py","backend/migrations/001_notes.sql"]</code>
- テスト: <code>["backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-DESIGN: 実装由来の設計を生成する

要件ID(JSON): <code>"REQ-DESIGN"</code>
タイトル(JSON): <code>"実装由来の設計を生成する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"API・DB・画面・インフラの構造を決定的に生成し差分を検知する"</code>
CornellNoteWebv2は、API・DB・画面・インフラの構造を決定的に生成し差分を検知するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-DESIGN"</code> 前提: 実装が更新される。条件: 設計生成とdrift検査を実行する。期待結果: API・DB・画面・インフラの構造を決定的に生成し差分を検知する。
  - criterion(JSON Object): <code>{"given":"実装が更新される","id":"AC-DESIGN","then":"API・DB・画面・インフラの構造を決定的に生成し差分を検知する","when":"設計生成とdrift検査を実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["tools/design.py","tools/frontend_design.mjs"]</code>
- テスト: <code>["tests/test_design.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-TEST: 品質検査を継続する

要件ID(JSON): <code>"REQ-TEST"</code>
タイトル(JSON): <code>"品質検査を継続する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"pytest・TS単体・静的解析・CDK nag・アサーション・snapshotを検査する"</code>
CornellNoteWebv2は、pytest・TS単体・静的解析・CDK nag・アサーション・snapshotを検査するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-TEST"</code> 前提: 変更が作成される。条件: 品質検査を実行する。期待結果: pytest・TS単体・静的解析・CDK nag・アサーション・snapshotを検査する。
  - criterion(JSON Object): <code>{"given":"変更が作成される","id":"AC-TEST","then":"pytest・TS単体・静的解析・CDK nag・アサーション・snapshotを検査する","when":"品質検査を実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["tools/quality.py"]</code>
- テスト: <code>[".github/workflows/verify.yml"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-REPORT: 日本語E2E証跡を公開する

要件ID(JSON): <code>"REQ-REPORT"</code>
タイトル(JSON): <code>"日本語E2E証跡を公開する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"全Given When Thenと右側スクリーンショットおよび品質・coverageをPagesで初期展開表示する"</code>
CornellNoteWebv2は、全Given When Thenと右側スクリーンショットおよび品質・coverageをPagesで初期展開表示するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-REPORT"</code> 前提: devに変更が統合される。条件: ActionsがE2Eを実行する。期待結果: 全Given When Thenと右側スクリーンショットおよび品質・coverageをPagesで初期展開表示する。
  - criterion(JSON Object): <code>{"given":"devに変更が統合される","id":"AC-REPORT","then":"全Given When Thenと右側スクリーンショットおよび品質・coverageをPagesで初期展開表示する","when":"ActionsがE2Eを実行する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>["tools/report.py"]</code>
- テスト: <code>[".github/workflows/verify.yml"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-DEPLOY: 検査済みのコードだけをデプロイする

要件ID(JSON): <code>"REQ-DEPLOY"</code>
タイトル(JSON): <code>"検査済みのコードだけをデプロイする"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"同一treeのdev検査成功を確認後にOIDC認証してCDKとフロントを配置する"</code>
CornellNoteWebv2は、同一treeのdev検査成功を確認後にOIDC認証してCDKとフロントを配置するを**維持する**。
行為enum: <code>"maintain"</code>

根拠: 利用者の初期構築依頼を継続的に満たす
根拠(JSON): <code>"利用者の初期構築依頼を継続的に満たす"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"initial-implementation"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-DEPLOY"</code> 前提: mainに変更が統合される。条件: CDを開始する。期待結果: 同一treeのdev検査成功を確認後にOIDC認証してCDKとフロントを配置する。
  - criterion(JSON Object): <code>{"given":"mainに変更が統合される","id":"AC-DEPLOY","then":"同一treeのdev検査成功を確認後にOIDC認証してCDKとフロントを配置する","when":"CDを開始する"}</code>

要求源(JSON List): <code>["user:2026-09-05-cornellnoteweb"]</code>
検証方法: automated-tests-and-review
検証証跡: GitHub Actions quality / E2E / Pages
検証(JSON Object): <code>{"evidence":"GitHub Actions quality / E2E / Pages","method":"automated-tests-and-review"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/DESIGN.gen.md"]</code>
- 実装: <code>[".github/workflows/deploy.yml"]</code>
- テスト: <code>[".github/workflows/deploy.yml"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>

## REQ-SQL: API単位のSQLから型付きクエリを生成し静的解析する

要件ID(JSON): <code>"REQ-SQL"</code>
タイトル(JSON): <code>"API単位のSQLから型付きクエリを生成し静的解析する"</code>
主体(JSON): <code>"CornellNoteWebv2"</code>
対象(JSON): <code>"各APIのsqlファイルからgenerated/queries.pyを生成してfunctionsで呼ぶ"</code>
CornellNoteWebv2は、各APIのsqlファイルからgenerated/queries.pyを生成してfunctionsで呼ぶを**維持する**。
行為enum: <code>"maintain"</code>

根拠: SQLとPythonの二重管理を避け、参照元の開発ルールに整合する
根拠(JSON): <code>"SQLとPythonの二重管理を避け、参照元の開発ルールに整合する"</code>

項目版: 1 / 状態: `active` / 種別: `constraint`
変更識別子: <code>"sql-refactor"</code>
分類: scope=<code>"project"</code> / category=<code>"nonfunctional"</code>

受入条件:
- <code>"AC-SQL"</code> 前提: APIのSQLまたはDDLが変更される。条件: コード生成と品質検査を実行する。期待結果: 型付き引数・行モデル・SQLファイル読込ラッパーが生成され、SQLFluffと差分・境界検査が不備を検出する。
  - criterion(JSON Object): <code>{"given":"APIのSQLまたはDDLが変更される","id":"AC-SQL","then":"型付き引数・行モデル・SQLファイル読込ラッパーが生成され、SQLFluffと差分・境界検査が不備を検出する","when":"コード生成と品質検査を実行する"}</code>

要求源(JSON List): <code>["user:2026-09-06-sql-layout"]</code>
検証方法: automated-tests
検証証跡: SQLFluff、tests/test_queries.py、DB結合テストとE2E
検証(JSON Object): <code>{"evidence":"SQLFluff、tests/test_queries.py、DB結合テストとE2E","method":"automated-tests"}</code>
トレース(JSON List、順序保持):
- 設計: <code>["docs/design/generated/queries.gen.json"]</code>
- 実装: <code>["backend/src/app/apis/notes/update_note/functions.py","tools/generate_queries.py","backend/src/app/db.py"]</code>
- テスト: <code>["tests/test_queries.py","backend/tests/test_integration.py"]</code>
- 参照資料: <code>["AGENTS.md"]</code>
廃止理由: <code>""</code>
後継要件: <code>""</code>
