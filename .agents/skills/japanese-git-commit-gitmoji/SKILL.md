---
name: japanese-git-commit-gitmoji
description: Create a concise Japanese Gitmoji Conventional Commit message when the user or target repository has selected that commit style.
---

# Japanese Git Commit with Gitmoji

形式契約: `spec/skills/skills.qnt`の`name: "japanese-git-commit-gitmoji"`（保守・監査時に参照）。

利用者または対象repositoryがこの形式を選択している場合だけ使用する。portable default、commit gate、merge条件にはしない。

## Format

```text
<gitmoji> <type>(<scope>): <日本語の要約>

目的:
- <達成する結果>

変更内容:
- <主要変更>

要件影響:
- <あり / なし、ID、理由>

設計影響:
- <あり / なし、対象、理由>

検証:
- <実行したローカル検査、または既存CIへの参照>

互換性・残存リスク:
- <既知事項>
```

代表typeは`feat`、`fix`、`refactor`、`docs`、`test`、`build`、`ci`、`chore`、`revert`、`release`とする。破壊的変更では`!`または`BREAKING CHANGE:`を使用する。

## Rules

- staged diffまたは対象差分から、一つの主目的を選ぶ。
- 実行していない検査をPassと書かない。
- 生ログ、coverage全文、scanner全文を貼り付けない。
- review YAML、required check、特定CI、特定merge方式を必須項目にしない。
- 対象repositoryが別形式を採用している場合は、その形式を優先する。

## Completion

- 1行目が一つの主目的を表す。
- 要件・設計への影響と検証範囲が誤解なく読める。
- 互換性と残存riskを隠していない。

<!-- BEGIN GENERATED QUINT CONTRACT -->
## Quint contract（自動生成）

このblockは`spec/skills/skills.qnt`から自動生成し、直接編集しません。
詳細・要件trace・digestは`spec/skills/skills.json`の同名契約を、契約の保守・監査時だけ参照します。
repository policyは導入先が所有します。非該当ならartifactやblocking判定を作りません。

- Skill: `japanese-git-commit-gitmoji`
- 柱: auxiliary
- repository blocking: no
- 既定portable: no
- 適用条件: when-user-or-target-selects-style
- 起動context: `target-commit-style`
- 外部作用capability: no
- Authority: explicit-user-or-target-repository-style
- 副作用: none
- 失敗状態: no-op-unless-selected
<!-- END GENERATED QUINT CONTRACT -->
