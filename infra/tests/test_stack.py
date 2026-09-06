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


def test_private_serverless_architecture():
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


def test_infrastructure_snapshot():
    _, t = synth()
    data = t.to_json()
    for resource in data["Resources"].values():
        if resource["Type"] == "AWS::Lambda::Function":
            resource["Properties"]["Code"] = {"Artifact": "uv.lock runtime bundle"}
    expected = Path("infra/tests/stack.snapshot.json")
    assert data == json.loads(expected.read_text())
