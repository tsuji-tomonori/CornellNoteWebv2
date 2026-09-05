---
name: chat-first-development
description: Complete development requests through a lightweight three-pillar flow covering durable requirements, implementation-derived design, and only the checks relevant to the change.
---

# Chat-first Development

形式契約: `spec/skills/skills.qnt`の`name: "chat-first-development"`（保守・監査時に参照）。

開発を依頼されたとき、依頼の成果と対象repositoryの規則に従って完了まで進める。相談・評価だけの依頼は回答を成果とし、変更へ拡張しない。

## 3本柱

1. 利用者向け挙動、受入条件、恒久制約が変わる場合だけ`$maintain-canonical-requirements`でQuint要件正本を更新する。可逆な実装選択は要件へ固定しない。
2. 変更artifactを扱う宣言済みgeneratorがある場合だけ`$generate-implementation-design`で実装由来設計とdriftを確認する。生成文書を手直しせず、未対応surfaceを明示する。
3. `$inspect-quality-gates`で変更と受入条件に関係する検査を選ぶ。失敗、新しい依存、公開契約への影響が分かった場合だけ検査範囲を広げる。

## 実行と権限

- 依頼、既存の`AGENTS.md`等、変更対象、受入条件を確認し、必要な実装と検証を行う。可逆な詳細は既存規約と合理的な仮定で進め、結果・権限を左右する不足だけを質問する。
- 現在も有効な明示依頼・承認を再利用し、同じ作業の許可を取り直さない。途中の質問や訂正は、取消しがない限り元の目的へ取り込む。
- PRの作成・更新・comment・review・merge、公開、外部書込み、production、削除、高額操作は、それぞれが明示依頼・承認の対象であり、必要な権限がある場合だけ行う。code変更の依頼だけからPR操作やmergeを推測しない。
- 承認が不足する操作へ到達したら、先に独立して進められる準備を完了し、対象・効果・未充足の権限を示す。既存の承認gateや実行環境の制限を回避しない。
- 独立した読み取り・検査は一括実行できる。subagentは利用可能で、独立した仕事があり並列化が有効な場合だけ使う。人数・モデル・推論強度を固定せず、対象環境の制限に従う。

## 完了

依頼された成果、実際の検証結果、未検証範囲・残存riskを簡潔に伝える。長い作業では実行結果に基づく進捗を伝え、再開情報が必要な場合だけ`.devflow/run/`に目的・承認境界・完了・残件を残す。成功後は無目的な追加検査や文書を増やさない。

branch構成、merge rule、CI workflow、required check、commit形式、PR template、review YAMLを新たに要求しない。CIがないrepositoryではローカル検証を証拠とする。secret、PII、生ログを保存せず、検査を通すためにtest・型・lint・security controlを弱めない。

導入時だけ[bootstrap-and-conversation.md](references/bootstrap-and-conversation.md)を参照する。

<!-- BEGIN GENERATED QUINT CONTRACT -->
## Quint contract（自動生成）

このblockは`spec/skills/skills.qnt`から自動生成し、直接編集しません。
詳細・要件trace・digestは`spec/skills/skills.json`の同名契約を、契約の保守・監査時だけ参照します。
repository policyは導入先が所有します。非該当ならartifactやblocking判定を作りません。

- Skill: `chat-first-development`
- 柱: auxiliary
- repository blocking: no
- 既定portable: yes
- 適用条件: when-development-is-requested
- 起動context: `development-request`
- 外部作用capability: yes
- Authority: user-and-target-repository
- 副作用: repository-and-authorized-external-write
- 失敗状態: report-bounded
<!-- END GENERATED QUINT CONTRACT -->
