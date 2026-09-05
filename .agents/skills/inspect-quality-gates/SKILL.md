---
name: inspect-quality-gates
description: Select and run only the checks relevant to the current change, using local evidence or an existing project check without creating CI, merge rules, or review bureaucracy.
---

# Inspect Quality Gates

形式契約: `spec/skills/skills.qnt`の`name: "inspect-quality-gates"`（保守・監査時に参照）。

変更差分、受入条件、riskから、失敗を検出できる最小十分な検査を選ぶ。これは3本目のガードレールであり、別の統制層を追加しない。

## 検証

- 既存のtest、lint、type check、build、generatorから変更に関係するものを実行し、結果を直接確認する。CIがないこと自体を失敗にしない。
- 挙動を変えない低影響の文書修正等に、新しいtestや全suiteの反復を一律要求しない。恒久testは実際の回帰riskと既存の運用に応じて残す。
- 受入条件、生成drift、機密情報、権限境界に関する失敗を隠さない。失敗、新しい依存、未解決risk、既存の必須gateに根拠がある場合だけ検査を広げる。
- 検査対象がなければ理由を簡潔に返す。未選択の検査をN/Aで列挙せず、成功後に追加検査を繰り返さない。

検査と判定はsourceや設定を修正しない。失敗時はcheck、直接証拠、影響範囲を返す。元の開発依頼が修正を許可している場合、呼出元はその権限内で修正し再検証でき、別Skillの導入や再承認は不要である。レビューだけの依頼を変更へ拡張しない。

## 実行境界

commandが作るbuild artifact等は対象repositoryの通常の実行効果として扱う。外部作用は既存の明示権限を確認する。実行できなかったcheckを成功扱いせず、局所検査でprocess外の作用を隔離・完全検知したとは主張しない。

既存のtarget-owned command registryで複数commandを機械実行する場合だけ[runner-contract.md](references/runner-contract.md)を読み、任意runnerを使う。registryのない導入先へ新規作成を要求しない。

結果と未検証範囲は会話または既存のPR欄へ簡潔に記録する。CI workflow、required check、branch protection、merge rule、review YAML、生ログを新たに要求せず、対象repositoryの規則と権限を維持する。

<!-- BEGIN GENERATED QUINT CONTRACT -->
## Quint contract（自動生成）

このblockは`spec/skills/skills.qnt`から自動生成し、直接編集しません。
詳細・要件trace・digestは`spec/skills/skills.json`の同名契約を、契約の保守・監査時だけ参照します。
repository policyは導入先が所有します。非該当ならartifactやblocking判定を作りません。

- Skill: `inspect-quality-gates`
- 柱: checks
- repository blocking: yes
- 既定portable: yes
- 適用条件: when-change-relevant-checks-exist
- 起動context: `selected-checks`
- 外部作用capability: yes
- Authority: target-repository-and-selected-checks
- 副作用: target-command-effects
- 失敗状態: report-bounded
<!-- END GENERATED QUINT CONTRACT -->
