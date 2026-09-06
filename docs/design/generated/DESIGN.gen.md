# 実装由来設計（自動生成）

直接編集しない。実装の構造・インターフェースを記載し、要件充足はテストで検証する。

## API

| Operation | Method | Path | 認証 |
|---|---|---|---|
| local_login | POST | `/api/auth/local` | 公開 / local限定 |
| health | GET | `/api/health` | 公開 / local限定 |
| list_notes | GET | `/api/notes` | JWT |
| create_note | POST | `/api/notes` | JWT |
| delete_note | DELETE | `/api/notes/{note_id}` | JWT |
| get_note | GET | `/api/notes/{note_id}` | JWT |
| update_note | PUT | `/api/notes/{note_id}` | JWT |
| revoke_share | DELETE | `/api/notes/{note_id}/share` | JWT |
| create_share | POST | `/api/notes/{note_id}/share` | JWT |
| get_shared | GET | `/api/shared/{token}` | 公開 / local限定 |

## DB

```sql
CREATE TABLE IF NOT EXISTS notes (id UUID PRIMARY KEY, owner_id VARCHAR(128) NOT NULL, title VARCHAR(200) NOT NULL, group_name VARCHAR(80) NOT NULL, cue TEXT NOT NULL, content TEXT NOT NULL, summary TEXT NOT NULL, tasks TEXT NOT NULL, version INT NOT NULL, updated_at TIMESTAMPTZ NOT NULL, share_hash VARCHAR(64), share_expires TIMESTAMPTZ)
COMMENT ON TABLE notes IS '利用者ごとのコーネル式ノート'
COMMENT ON COLUMN notes.id IS 'ノート識別子（ランダムUUID）'
COMMENT ON COLUMN notes.owner_id IS '所有者のCognito sub'
COMMENT ON COLUMN notes.title IS 'ノートの題名'
COMMENT ON COLUMN notes.group_name IS '科目またはプロジェクトの分類名'
COMMENT ON COLUMN notes.cue IS '問い・キーワード'
COMMENT ON COLUMN notes.content IS '自由記述の記録本文'
COMMENT ON COLUMN notes.summary IS '自分の言葉による要約'
COMMENT ON COLUMN notes.tasks IS 'チェック項目・完了状態・期日のJSON配列'
COMMENT ON COLUMN notes.version IS '同時更新検知の連番'
COMMENT ON COLUMN notes.updated_at IS '最終更新日時（UTC）'
COMMENT ON COLUMN notes.share_hash IS '共有トークンのSHA256（生トークンは保存しない）'
COMMENT ON COLUMN notes.share_expires IS '共有リンクの有効期限'
```
```sql
CREATE INDEX IF NOT EXISTS notes_owner_idx ON notes(owner_id)
```
```sql
CREATE INDEX IF NOT EXISTS notes_share_idx ON notes(share_hash)
```

## 画面と関数

- `frontend/src/App.tsx`: App, action, create, save, Brand, LoginView, submit
- `frontend/src/Editor.tsx`: Editor, change, addTask
- `frontend/src/api.ts`: api
- `frontend/src/auth.ts`: loginCognito, completeLogin, logout
- `frontend/src/domain.ts`: groupedNotes, progress
- `frontend/src/main.tsx`: 

## AWSリソース

| Logical ID | Type |
|---|---|
| ApiFunctionCE271BD4 | AWS::Lambda::Function |
| ApiLogs3D05D88B | AWS::Logs::LogGroup |
| ApiRole1873F438 | AWS::IAM::Role |
| ApiRoleDefaultPolicyCFEBAD31 | AWS::IAM::Policy |
| Database | AWS::DSQL::Cluster |
| Frontend23D93C55 | AWS::S3::Bucket |
| FrontendPolicy442AF6CA | AWS::S3::BucketPolicy |
| HeadersECA0794E | AWS::CloudFront::ResponseHeadersPolicy |
| HttpApiANYapinotes49E219FC | AWS::ApiGatewayV2::Route |
| HttpApiANYapinotesFastApiIntegration445527F5 | AWS::ApiGatewayV2::Integration |
| HttpApiANYapinotesFastApiIntegrationPermission80191C22 | AWS::Lambda::Permission |
| HttpApiANYapinotesproxy02D793B3 | AWS::ApiGatewayV2::Route |
| HttpApiANYapinotesproxyFastApiIntegrationPermission0D1CCE2E | AWS::Lambda::Permission |
| HttpApiCognitoJwt4B02D8E4 | AWS::ApiGatewayV2::Authorizer |
| HttpApiDefaultStage3EEB07D6 | AWS::ApiGatewayV2::Stage |
| HttpApiF5A9A8A7 | AWS::ApiGatewayV2::Api |
| HttpApiGETapihealth7FA5887F | AWS::ApiGatewayV2::Route |
| HttpApiGETapihealthFastApiIntegrationPermissionF0E9BEE3 | AWS::Lambda::Permission |
| HttpApiGETapisharedtoken16AC79E4 | AWS::ApiGatewayV2::Route |
| HttpApiGETapisharedtokenFastApiIntegrationPermission3DA044D2 | AWS::Lambda::Permission |
| MigrationC13A4580 | AWS::Lambda::Function |
| MigrationLogs670D4322 | AWS::Logs::LogGroup |
| MigrationRole55C404E5 | AWS::IAM::Role |
| MigrationRoleDefaultPolicy6B18891E | AWS::IAM::Policy |
| Users0A0EEA89 | AWS::Cognito::UserPool |
| UsersBrowser427D6876 | AWS::Cognito::UserPoolClient |
| UsersLogin5F5F2B8C | AWS::Cognito::UserPoolDomain |
| Web3C8945DB | AWS::CloudFront::Distribution |
| WebOrigin1S3OriginAccessControl98EE5C09 | AWS::CloudFront::OriginAccessControl |
