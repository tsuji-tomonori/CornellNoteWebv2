# 任意の検査runner

既存のtarget-owned registryで複数commandを機械実行する場合だけ読む。通常の検査は対象repositoryのcommandを直接実行できる。

複数commandを機械実行する場合だけ、対象repositoryが既に所有するcommand registryとrepository-confined planを渡し、`python <host-skill-path>/scripts/inspect.py --root . --registry <target-owned-checks.json> --plan <selected-checks.json>`を使う。`<host-skill-path>`はinstaller receiptとhost adapterが配置した、このSkillのhost-native rootへ解決する。registryがない導入先へ新しいregistryを要求せず、関連checkを通常の対象repository手順で実行する。

registry entryは`command_id`、shell文字列ではない`command` argv、許可する`acceptance_ids` / `risk_tags`、宣言`effect`、`authority` / `authority_reference`、`output_roots`だけを持つ。effectは`read-only`、`repository-build-artifacts`、`target-declared-external`のいずれかとする。read-onlyはoutput rootなし、build artifactは一つ以上のrepository-relative output rootを宣言する。external effectは現在の明示authority referenceがなければ実行前に拒否する。

planはtop-levelにbounded `scope`、`residual_risks`、`no_applicable_reason`と選択済み`checks`だけを持つ。各checkは`command_id`、関連する`acceptance_ids` / `risk_tags`、任意のbounded `timeout_seconds`を持ち、argv、cwd、envを上書きしない。該当checkがなければ`checks: []`と具体的な`no_applicable_reason`を返すno-opとし、checkがある場合は理由をnullにする。

runnerは`.git`、`.devflow/run`、宣言済みoutput root以外の全tree digestを実行前後で比較し、source、config、ignored fileを含む予期しないmutationを拒否する。registryとplanのsnapshotは全command後にも再検証し、`--json-out`のCAS read preconditionへも結合する。commandが除外領域内のregistry / planを変更してもresultを発行しない。primary executableは固定system pathへ解決してFD pinし、実行前後のidentity hashを照合する。開始不能時は`cannot-start`とし、実行していないcommandにeffectやdriftがなかったとは主張しない。

stdoutへraw outputを含まないbounded JSONを返し、明示した`--json-out`以外へsummaryを書かない。runner自身はGitHub APIや外部serviceを呼ばないが、任意のtarget commandが持つprocess外effectを隔離も完全検知もできない。このためeffect宣言がlocalであっても全commandへ`process-effect-not-isolated:<command_id>` residualを付ける。global resultは`process_effect_isolation_provided: false`と`process_effect_detection_provided: false`、各command resultは`process_effect_isolated: false`と`process_effect_detection: "not-provided"`を返し、宣言effect、authority、acceptance / riskとの関連、未検証範囲を伝播する。tree差分から判定できるのはrepository mutationであり、process外effectを検知したとは表現しない。
