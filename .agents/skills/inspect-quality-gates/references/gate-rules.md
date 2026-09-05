# Selected check rules

検査順序と実行場所は対象repositoryへ委任し、このSkillは変更と受入条件に関係する最小の検査だけを選ぶ。

## 選択

- changed path、挙動、risk、生成対象から、失敗を検出できる検査を選ぶ。
- 未選択の検査をN/Aとして列挙しない。
- まずtargeted test、lint、type check、build、generator check等のローカルcommandを使う。
- 既存CIがある場合は同じcommandの追加証拠として参照できる。

## Verdict

- Passは実行command、対象範囲、直接証拠を持つ。
- N/Aは選択後に判明した具体的な適用外理由を持つ。
- blocking Failは直接証拠と最小修正handoffを返し、別途権限を持つ実装後に影響する検査だけを再実行する。
- Advisoryは修正handoff、対象repositoryが採用するIssue、残存riskのいずれかへ収束させる。

## Boundary

固定phase、専用review YAML、work item、CI workflow、required check、branch protection、ruleset、merge strategy、PR template、commit formatをこのSkillのために追加または要求しない。

機械runnerは対象repositoryが既に所有するregistryのargvだけをshellなしで実行する。planからargv、cwd、envを指定できない。registryは各commandのacceptance / risk、`read-only` / `repository-build-artifacts` / `target-declared-external` effect、authority、許可output rootを宣言する。external effectは明示authority referenceなしに実行しない。どのeffect宣言でもsubprocess外のeffectを隔離・完全検知できないため、全commandへ`process-effect-not-isolated:<command_id>`を付ける。resultはglobalなisolation / detectionを`false`、commandごとのisolationを`false`、detectionを`not-provided`と明示する。

`.git`、`.devflow/run`、宣言済みbuild output以外のtree mutationは失敗とする。registry / plan自体は除外領域にあっても実行後snapshotとJSON result CASのread preconditionへ結合し、途中変更時はresultを発行しない。primary executableも固定system pathからFD pinしてidentityを前後照合し、開始不能を「変更なし」の証拠にしない。結果はraw stdout / stderrを含めず、stdoutまたは明示されたrepository-confined JSONへbounded summaryだけを返す。該当checkがない場合は空のcheck集合と具体的な`no_applicable_reason`を返し、新しいblocking failureを作らない。
