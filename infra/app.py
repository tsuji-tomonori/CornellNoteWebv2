import aws_cdk as cdk

from infra.stack import CornellStack

app = cdk.App(outdir="cdk.out")
CornellStack(
    app,
    "CornellNote",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or "111111111111",
        region=app.node.try_get_context("region") or "ap-northeast-1",
    ),
)
app.synth()
