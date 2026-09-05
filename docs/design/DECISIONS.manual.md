# 技術選択

React＋ViteのTypeScript SPAをS3へ静的配置。Astroも比較し、記事中心ではなく編集操作中心のためReact SPAを選択。https://react.dev/learn/build-a-react-app-from-scratch

アイコンはLucide（ISC）。https://lucide.dev/license

CloudFront＋非公開S3、API Gateway HTTP API→FastAPI Lambda→Aurora DSQL。Cognito認可コード＋PKCE。VPC、NAT Gateway、WAF、専用KMS鍵は初期構成では作らない。

DSQLは1transactionにつき1DDL、DDLとDML混在不可のため、Alembic標準の一括transactionを避けSQLファイル＋checksum台帳による小さなマイグレーターを使う。DDLは再実行可能、索引はDSQLのみASYNCで完了待ち。https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-ddl.html

ローカルはPostgreSQL16、ComposeでAPIとフロントを同時起動。専用署名トークンの開発認証を使い、Lambdaでは起動時に開発認証を拒否。AWS依存なし。

DB実行ロールはDMLだけ。migrationロールを分離。所有者subによる絞り込みとversionによる楽観ロックを行う。共有トークンはSHA256のみDBへ保存。

設計生成はOpenAPI・Python AST・SQL AST・TypeScript AST・CDK synthを入力とする。生成対象と未対応範囲はmanifestに明記し、コメントで実装説明を二重管理しない。
