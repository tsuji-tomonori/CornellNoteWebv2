import hashlib
import json
from collections import Counter


def references(value):
    found = set()
    if isinstance(value, dict):
        if "Ref" in value:
            found.add(value["Ref"])
        if "Fn::GetAtt" in value:
            target = value["Fn::GetAtt"]
            found.add(target[0] if isinstance(target, list) else target.split(".")[0])
        for child in value.values():
            found |= references(child)
    elif isinstance(value, list):
        for child in value:
            found |= references(child)
    return found


def flatten(value, path=""):
    if isinstance(value, dict) and not any(k.startswith("Fn::") or k == "Ref" for k in value):
        for key, child in sorted(value.items()):
            yield from flatten(child, f"{path}.{key}".strip("."))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from flatten(child, f"{path}[{i}]")
    else:
        sensitive = "Environment.Variables." in path and any(
            word in path.upper()
            for word in ("PASSWORD", "SECRET", "CREDENTIAL", "ACCESS_KEY", "TOKEN")
        )
        yield path, "[非公開]" if sensitive else value


def infrastructure_docs(template, page, table):
    resources = template["Resources"]
    digest = hashlib.sha256(
        json.dumps(template, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    by_type = {}
    for logical, resource in sorted(resources.items()):
        by_type.setdefault(resource["Type"], []).append((logical, resource))
    paths = {kind: "types/" + kind.replace("::", "-").lower() + ".gen.md" for kind in by_type}

    def link(logical, prefix=""):
        return f"[{logical}]({prefix}{paths[resources[logical]['Type']]}#{logical.lower()})"

    def readable(value, prefix="../"):
        if isinstance(value, dict) and "Ref" in value:
            target = value["Ref"]
            return link(target, prefix) if target in resources else "Ref: " + target
        if isinstance(value, dict) and "Fn::GetAtt" in value:
            target, attr = value["Fn::GetAtt"]
            return (link(target, prefix) if target in resources else target) + "." + attr
        if isinstance(value, dict):
            return "; ".join(k + ": " + readable(v, prefix) for k, v in value.items())
        if isinstance(value, list):
            return ", ".join(readable(v, prefix) for v in value)
        return str(value)

    counts = Counter(r["Type"].split("::")[1] for r in resources.values())
    files = {
        "infrastructure/index.gen.md": page(
            "AWS リソースインベントリ",
            "Python CDKのsynth結果 `CornellNote.template.json` を静的解析する。AWSへのデプロイ完了や実在を示す台帳ではない。\n\n"
            + f"対象スタック: CornellNote / リソース総数: {len(resources)}\n\n正規化テンプレートSHA-256: `{digest}`。Lambda Codeの環境依存S3キーは正規化し、ソースとuv.lockを別途manifestで追跡する。\n\n## 全体サマリー\n\n"
            + table(["サービス領域", "件数"], sorted(counts.items()))
            + "## リソース種類別詳細\n\n"
            + table(
                ["CloudFormation Type", "件数", "詳細"],
                (
                    (kind, len(items), f"[設定・参照関係]({paths[kind]})")
                    for kind, items in sorted(by_type.items())
                ),
            )
            + "[構成・依存図](topology.gen.md) · [IAM](iam.gen.md) · [cdk-nag抑制](nag.gen.md) · [パラメーター](parameters.gen.md) · [出力](outputs.gen.md)\n",
        )
    }
    for kind, items in sorted(by_type.items()):
        body = (
            "[インベントリへ戻る](../index.gen.md)\n\n"
            + f"リソース数: {len(items)}\n\n## Logical ID 一覧\n\n"
        )
        body += table(
            ["Logical ID", "CDKパス", "保持方針"],
            (
                (
                    f"[{key}](#{key.lower()})",
                    r.get("Metadata", {}).get("aws:cdk:path", ""),
                    r.get("DeletionPolicy", "CloudFormation既定"),
                )
                for key, r in items
            ),
        )
        for key, r in items:
            body += f"## {key}\n\n### 設定項目\n\n" + table(
                ["項目", "値"],
                ((name, readable(value)) for name, value in flatten(r.get("Properties", {}))),
            )
            deps = sorted(
                (references(r.get("Properties", {})) | set(r.get("DependsOn", [])))
                & resources.keys()
            )
            body += "### 参照・明示依存\n\n" + table(
                ["リソース", "種類"], ((link(d, "../"), resources[d]["Type"]) for d in deps)
            )
            reverse = [
                k
                for k, v in resources.items()
                if key in references(v.get("Properties", {})) or key in v.get("DependsOn", [])
            ]
            body += "### 参照元\n\n" + table(
                ["リソース", "種類"], ((link(d, "../"), resources[d]["Type"]) for d in reverse)
            )
        files["infrastructure/" + paths[kind]] = page(kind, body)
    edges = sorted(
        (a, b)
        for a, r in resources.items()
        for b in (references(r.get("Properties", {})) | set(r.get("DependsOn", [])))
        if b in resources
    )
    services = sorted(counts)
    service_edges = sorted(
        {
            (resources[a]["Type"].split("::")[1], resources[b]["Type"].split("::")[1])
            for a, b in edges
            if resources[a]["Type"].split("::")[1] != resources[b]["Type"].split("::")[1]
        }
    )
    diagram = "flowchart TD\n" + "\n".join(
        f'  S{i}["{s} ({counts[s]})"]' for i, s in enumerate(services)
    )
    diagram += "\n" + "\n".join(
        f"  S{services.index(a)} -->|参照| S{services.index(b)}" for a, b in service_edges
    )
    files["infrastructure/topology.gen.md"] = page(
        "CDK構成・参照依存図",
        "テンプレート中のRef・GetAtt・DependsOnから生成した依存関係。矢印は設定の参照方向であり、通信方向ではない。\n\n```mermaid\n"
        + diagram
        + "\n```\n\n## リソース間の参照\n\n"
        + table(["参照元", "参照先"], ((link(a), link(b)) for a, b in edges)),
    )
    files["infrastructure/parameters.gen.md"] = page(
        "CDKパラメーター",
        table(
            ["名前", "型", "既定値", "許容値", "説明"],
            (
                (
                    k,
                    v.get("Type"),
                    "[非公開]" if v.get("NoEcho") else v.get("Default", "なし"),
                    v.get("AllowedValues", "制約なし"),
                    v.get("Description", ""),
                )
                for k, v in sorted(template.get("Parameters", {}).items())
            ),
        ),
    )
    policy_rows = []
    for key, r in sorted(resources.items()):
        for name, policy in r.get("Properties", {}).items():
            if name in {"PolicyDocument", "AssumeRolePolicyDocument"}:
                for statement in policy.get("Statement", []):
                    policy_rows.append(
                        (
                            link(key),
                            name,
                            statement.get("Effect"),
                            statement.get("Action"),
                            readable(statement.get("Resource", "なし"), ""),
                            statement.get("Principal", "なし"),
                            statement.get("Condition", "なし"),
                        )
                    )
    files["infrastructure/iam.gen.md"] = page(
        "IAM・リソースポリシー",
        table(
            ["リソース", "種別", "効果", "Action", "Resource", "Principal", "Condition"],
            policy_rows,
        ),
    )
    return files
