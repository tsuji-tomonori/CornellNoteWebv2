import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk.assertions import Annotations, Match, Template

from infra.stack import CornellStack


def synth():
    app = cdk.App()
    stack = CornellStack(
        app, "CornellNote", env=cdk.Environment(account="111111111111", region="ap-northeast-1")
    )
    template = Template.from_stack(stack)
    return stack, template


def test_非公開かつサーバーレスの最小権限構成を維持する():
    stack, t = synth()
    t.resource_count_is("AWS::DSQL::Cluster", 1)
    t.resource_count_is("AWS::EC2::VPC", 0)
    t.resource_count_is("AWS::EC2::NatGateway", 0)
    t.resource_count_is("AWS::WAFv2::WebACL", 0)
    t.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    t.has_resource_properties(
        "AWS::Cognito::UserPoolClient", {"GenerateSecret": False, "AllowedOAuthFlows": ["code"]}
    )
    t.has_resource_properties("AWS::DSQL::Cluster", {"DeletionProtectionEnabled": True})
    for item in t.find_resources("AWS::IAM::Policy").values():
        for statement in item["Properties"]["PolicyDocument"]["Statement"]:
            assert statement["Action"] != "*"
            assert statement["Resource"] != "*"
    Annotations.from_stack(stack).has_no_error("*", Match.any_value())


def test_CDKテンプレートが承認済みスナップショットと一致する():
    _, t = synth()
    data = t.to_json()
    for resource in data["Resources"].values():
        if resource["Type"] == "AWS::Lambda::Function":
            resource["Properties"]["Code"] = {"Artifact": "uv.lock runtime bundle"}
    expected = Path("infra/tests/stack.snapshot.json")
    assert data == json.loads(expected.read_text())


def test_通常APIとマイグレーションのDSQL権限を分離する():
    _, t = synth()
    policies = t.find_resources("AWS::IAM::Policy")
    runtime = next(v for k, v in policies.items() if k.startswith("ApiRole"))
    migration = next(v for k, v in policies.items() if k.startswith("MigrationRole"))

    def actions(policy):
        return {
            a
            for s in policy["Properties"]["PolicyDocument"]["Statement"]
            for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])
        }

    assert "dsql:DbConnect" in actions(runtime)
    assert "dsql:DbConnectAdmin" not in actions(runtime)
    assert "dsql:DbConnectAdmin" in actions(migration)
    t.has_resource_properties(
        "AWS::CloudFront::OriginAccessControl",
        {
            "OriginAccessControlConfig": Match.object_like(
                {"SigningBehavior": "always", "SigningProtocol": "sigv4"}
            )
        },
    )
    t.has_resource_properties(
        "AWS::ApiGatewayV2::Route", {"RouteKey": "ANY /api/notes", "AuthorizationType": "JWT"}
    )


def test_CDK_nagの未抑制エラーがなく抑制理由が全て存在する():
    stack, t = synth()
    Annotations.from_stack(stack).has_no_error("*", Match.any_value())
    suppressions = [
        s
        for r in t.to_json()["Resources"].values()
        for s in r.get("Metadata", {}).get("cdk_nag", {}).get("rules_to_suppress", [])
    ]
    assert suppressions
    assert all(s["reason"] for s in suppressions)
    assert not any(s["id"] == "AwsSolutions-S10" for s in suppressions)
