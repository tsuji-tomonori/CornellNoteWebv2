---
name: maintain-canonical-requirements
description: Discover, classify, atomize, and maintain durable product or project requirements in Quint, then deterministically generate JSON and human-readable documentation.
---

# Maintain Canonical Requirements

形式契約: `spec/skills/skills.qnt`の`name: "maintain-canonical-requirements"`（保守・監査時に参照）。

会話から、今後も維持する必要がある要件だけを形式仕様へ反映する。これは1本目のガードレールである。

既存catalogにdurable obligationのdeltaがある場合、または新しいrepositoryで正本を初期化する場合に起動する。初回bootstrapは変更work itemを前提にせず、対象product、source、最初の原子的要件、acceptanceを入力として型付きcatalogを作る。

## Authority

1. `spec/requirements/requirements.qnt`: 編集する唯一の要件正本
2. `spec/requirements/requirements.json`: Quintから生成する機械可読view。直接編集しない
3. `docs/requirements/REQUIREMENTS.md`: JSONから生成する人向けview。直接編集しない
4. `docs/standards/REQUIREMENT-CLASSIFICATION.md`: 分類規則
5. Git履歴: add / update / retireの履歴

生成順序は常に `requirements.qnt → requirements.json → REQUIREMENTS.md` とする。生成viewを修正して正本との差を隠さない。

新しいrepositoryでは`assets/requirements.template.qnt`を`spec/requirements/requirements.qnt`の初期形として使用し、対象productの型付きcatalogへ置き換える。既存のwork itemや変更履歴を要求せず、JSON templateを一次入力にしない。

## Classification

各要件は次を明確にする。

- `scope`: 利用者またはconsumerへ提供する挙動・品質は`product`、開発・保守・配布・文書化の恒久義務は`project`
- `category`: 能力・変換・応答は`functional`、品質・制約・工程・deliverableは`nonfunctional`

新規または意味更新する要件では`scope`と`category`を対で指定する。

## Solution specificity

technology、architecture、tool、path、工程、成果物を名指しする候補は、そのまま永続化せず次を確認する。

1. それを外すと失われるobservableな義務は何か。
2. exact choiceが法令、契約、public compatibility、既存platform、承認済みADR等で必要か。
3. 今回だけの実装指示か、将来も維持する義務か。
4. 要件、ADR、実装、生成設計、一時contextのどこが正しい置き場所か。

可逆な実装選択は要件へ固定しない。exact choiceが必要ならsource、rationale、scope、verificationを持たせる。

## Workflow

1. 利用者の目的、対象、制約、例外、受入条件を確認する。
2. 永続義務と今回だけの作業情報を分ける。
3. 一つの主体、一つの行為、一つの対象、一つの検証可能な義務へ原子化する。
4. `add`、`update`、`retire`を決め、IDとrevision履歴を保つ。
5. `spec/requirements/requirements.qnt`だけを編集する。
6. `python tools/quintflow.py generate`でJSONとMarkdownを生成する。
7. `python tools/quintflow.py check`で型、形式不変条件、生成drift、Skill coverageを検査する。
8. 現在すでに存在する実装、test、文書、生成設計だけをrequirement IDへtraceする。未実装の下流artifactは捏造せず、後続実装へtrace追加をhandoffする。

削除はせず`retire`し、理由と変更識別子を残す。結果を変える曖昧さだけを確認し、可逆な詳細は対象repositoryの既存規約へ委任する。

## Boundary

- CI workflow、required check、branch、merge ruleを要件管理の前提にしない。
- 変更ごとの要件文書、review YAML、test logを要件正本にしない。
- 一時差分が必要な場合だけ`.devflow/run/`を使い、完了後に残さない。

## Completion

- Quintが型検査を通り、要件IDが一意である。
- 要件が原子的かつ検証可能である。
- classificationが対で指定され、retirementが明示的である。
- sourceとverificationが現在の要件authorityに対応する。
- JSONとMarkdownが正本から再生成され、driftがない。
- 現在存在する下流artifactへのtraceが正しく、将来作成するartifactのtraceは後続工程へhandoffされている。将来pathの存在はこのSkillの完了条件にしない。

<!-- BEGIN GENERATED QUINT CONTRACT -->
## Quint contract（自動生成）

このblockは`spec/skills/skills.qnt`から自動生成し、直接編集しません。
詳細・要件trace・digestは`spec/skills/skills.json`の同名契約を、契約の保守・監査時だけ参照します。
repository policyは導入先が所有します。非該当ならartifactやblocking判定を作りません。

- Skill: `maintain-canonical-requirements`
- 柱: requirements
- repository blocking: yes
- 既定portable: yes
- 適用条件: when-durable-obligation-changes-or-authority-is-initialized
- 起動context: `durable-requirement-change`
- 外部作用capability: no
- Authority: quint-requirements
- 副作用: repository-write
- 失敗状態: fail-on-invalid-catalog
<!-- END GENERATED QUINT CONTRACT -->
