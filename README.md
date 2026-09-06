# CornellNoteWebv2

4c「ユーカリ／ミント」をベースにしたコーネル式ノート。本人のノートをコレクション別に整理し、問い・記録・まとめ・期日付きチェックリストを編集できます。共有は7日間の閲覧リンクで、いつでも解除できます。

## ローカル起動

```sh
docker compose up --build -d --wait
```

http://localhost:5173 を開き、ユーザーAliceまたはBob、パスワード `cornell-local` でログインします。DBはPostgreSQL16。AWSのアカウントや資格情報は不要です。開発用パスワードは公開のテスト専用品です。サービスのホスト公開は127.0.0.1に制限しています。

```sh
docker compose down       # データ保持
docker compose down -v    # ローカルデータ削除
```

## 開発と検査

Python 3.12、uv 0.11、Node.js24、Docker Composeが必要です。

```sh
uv sync --locked
npm ci --prefix frontend
uv run pre-commit install
python tools/quintflow.py setup
uv run python tools/package_lambda.py
uv run python -m infra.app
uv run python tools/generate_queries.py
uv run python tools/design.py
uv run python tools/design.py --check
```

Compose起動後に以下を実行します。公開済みの開発用接続情報です。

```sh
export DATABASE_URL=postgresql://cornell:local-cornell-only@127.0.0.1:5432/cornell
uv run python tools/quality.py
npx --prefix frontend playwright install chromium
npm --prefix frontend run e2e
python tools/report.py
```

`reports/index.html` が統合レポートです。日本語Given/When/Thenの各段階に実画像を右側表示し、全ケースを常時展開します。PythonとTypeScriptのコード行カバレッジ、静的解析、フォーマッター、CDK nag、snapshotも確認できます。CIの画面は合成画像ではなく実行時のスクリーンショットです。

## 検証状況

2026-09-06: GitHub ActionsでCompose（PostgreSQL16・API・フロント）の起動、静的解析、Pythonテスト、Vitest、PC/モバイルのPlaywright 10ケースが成功。日本語Given/When/Thenの32画像と終了時12画像、計44画像を生成。

作業環境でもChromiumとローカルAPI・PostgreSQL互換PGliteで10ケースが成功。DockerがないためComposeそのものの検証はActionsで実施。通常のローカル手順は上記Composeを使用してください。

Pagesは環境保護ルールのdev許可後に再公開が成功。https://tsuji-tomonori.github.io/CornellNoteWebv2/ で公開HTMLと44画像の参照を確認済み。

## AWS構成

CloudFrontの静的配信は非公開S3、`/api/*`はAPI Gateway HTTP API→FastAPI＋MangumのLambda→Aurora DSQL。Cognitoの認可コード＋PKCEでログインし、API GatewayとFastAPIの双方でJWTを検証します。DBは実行用DMLロールとmigration用管理ロールを分離。ノートは非公開が初期値で、共有トークンはSHA256だけを保存します。

VPC、NAT、WAF、独自KMS鍵は追加していません。固定費や利用規模に対して過剰な機能のCDK nag検出には、リソース単位で理由付きの抑制を設定しています。S3公開設定・TLS・IAM権限は検査します。ログは7日保持です。

本番のDSQL／Cognitoログイン検証はAWS資格情報の設定後に必要です。ローカルPostgreSQLの成功をDSQL実環境の成功とはみなしません。

## CI/CD

- PRは型検査・静的解析・単体／DB結合／CDKテスト・E2Eを実行。
- `dev`へのpush（PRマージを含む）で同じ検査を行い、GitHub Pagesへ品質レポートを自動公開。失敗時のレポートも失敗として表示。
- `main`への統合時は、devの成功したpushと同一Git treeであることを確認してからAWS OIDC認証・CDK synth/diff/deploy・migration・フロント配信を実行。
- 初期構築ではdevまで統合。本番CDにはGitHub変数 `AWS_DEPLOY_ROLE_ARN` の設定が必要。未設定時にCDが失敗することは想定内です。

初回はAWS CDK bootstrapを対象アカウント・ap-northeast-1で行い、GitHub OIDCの `repo:tsuji-tomonori/CornellNoteWebv2:environment:production` に信頼を限定したデプロイロールを設定します。権限はCDK bootstrap deploy/file-publishing/lookupロールへのAssumeRole、対象migration LambdaへのInvokeFunction、対象S3へのListBucket/PutObjectと対象CloudFrontのCreateInvalidationに限定します。アプリ実行ロールとは別です。

## 正本と自動生成

Dev Standardのdefaultとcommit-styleを導入済み。要件正本は `spec/requirements/requirements.qnt`。`uv run python tools/design.py` が要件・実装由来の設計を [docs/generated](docs/generated/README.gen.md) のMarkdownとして生成します。Quintの型・不変条件・trace検証とJSON直列化を、固定済みDev Standardの処理でメモリ上に実行します。生成JSONは保存しません。標準の配布ファイルや検証を改変せず、プロジェクト側のadapter `tools/requirements_view.py` が出力形式を担当します。

- API: 10操作それぞれにIF・詳細設計・シーケンス・メッセージ・SQL・テスト観点の6種類。OpenAPIと実際の有効routeを一対一照合し、入出力のネスト・型・必須・制約、Python ASTの分岐とエラー、各SQLと生成ラッパーを記載します。
- DB: 各テーブルの日本語説明・全カラム・型・NULL・キー・制約・index、全体ER図、CRUD、migrationとchecksum。管理台帳schema_migrationsも実装から抽出します。
- 要件: 全体一覧・要件ごとの仕様と日本語Given/When/Then・設計/実装/テストへの対応表。
- 画面/テスト/AWS: TypeScriptの型・関数・JSX属性、E2Eソースの日本語シナリオ、pytestのassert、CDK synthのリソース・IAM・抑制理由・outputs。
- 生成管理: 入力ファイルのSHA-256と文書一覧。`--check`は未更新・余剰文書を検知し、書込みを行いません。未対応の構文はエラーにします。静的に抽出したテスト観点は、実行済みの証拠と区別します。

CIは文書を再生成し、一致検査・品質・E2Eが成功した後、`docs/generated/`の差分だけをdevへ通常pushします。同時更新時は強制pushせず失敗します。GITHUB_TOKENによる文書commitはCIを再帰起動せず、同じ実行内でPagesとMarkdown artifactを公開します。mainのCDは成功したdev実行の`verified-revision` artifactにある元commit・反映後commit・treeと照合します。artifactは90日保持するため、古い結果が失効した場合はdev検証を再実行してください。

出力形式の変更は利用者のMarkdown指定を優先します。依存管理・CDK設定・テストsnapshot・標準ツールの導入receiptなど、ドキュメント以外のJSONは各ツールに必要なため保持します。

`docs/design/DESIGN_GUIDE.manual.md` は実装前に定めた見た目の判断、`DECISIONS.manual.md` は技術選択の理由です。ソースコメントを第二の設計書にはせず、DBの日本語コメントと外部型定義の限定的な補足のみを置きます。

マイグレーションは `backend/migrations/*.sql` の順序付きSQLとchecksum台帳です。DSQLの1transaction1DDL制約に対応し、再実行時は適用済みファイルの変更を拒否します。スキーマ変更は既存ファイルを書き換えず新しいSQLファイルを追加してください。

## ライセンス

Lucide IconsはISCライセンス。配布時の通知は `THIRD_PARTY_NOTICES.md` を参照してください。

## SQLの編集と自動生成

参照元Lazunexとbootstrap-fastapi-designに従い、各APIの `sql/NNN_query_name.sql` を正本とします。先頭行は日本語の処理概要、1ファイル1文、SELECT列は列挙します。PostgreSQL/psycopgの名前付き `%(column_name)s` を使用し、値は常に別引数でバインドします。文字列置換やSQLへの値の埋め込みは行いません。

`uv run python tools/generate_queries.py` はSQL ASTとmigration DDLから引数・行のPydanticモデルと `generated/queries.py` を生成します。生成ラッパーは同じAPIのSQLファイルを読み込むDB portを呼び、`functions.py` が呼出順序・業務判定・transactionを持ちます。routerはfunctionsだけを呼びます。共通repositoryへの業務SQL集約は廃止しました。

変更後は以下を実行します。生成Pythonと `docs/generated/queries.gen.md` は直接編集しません。

```sh
uv run sqlfluff lint backend/src/app/apis backend/migrations
uv run python tools/generate_queries.py
uv run python tools/design.py
uv run python tools/generate_queries.py --check
```

SQLFluffでは既存のPostgreSQLカラム `content/summary/tasks/version` を許可し、適用済みmigrationの1スペース字下げをそのまま検査します。

SQLFluffのJSON診断、生成差分・境界検査、型検査、既存API結合テストをCIの品質レポートに掲載します。未対応のJOIN・副問合せ・計算結果列は型を推測して通さず、ジェネレーターが明示エラーにします。適用済みmigrationはchecksumを保持するため整形し直さず、新しい変更は追加ファイルで扱います。
