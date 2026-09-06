from pathlib import Path

from aws_cdk import (
    Aspects,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_apigatewayv2 as apigw,
)
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import (
    aws_apigatewayv2_integrations as integrations,
)
from aws_cdk import (
    aws_cloudfront as cf,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_dsql as dsql,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct

ROOT = Path(__file__).resolve().parents[1]


class CornellStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)
        bucket = s3.Bucket(
            self,
            "Frontend",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
        )
        database = dsql.CfnCluster(self, "Database", deletion_protection_enabled=True)
        database.apply_removal_policy(RemovalPolicy.RETAIN)
        pool = cognito.UserPool(
            self,
            "Users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )
        domain = pool.add_domain(
            "Login",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"cornell-{self.account}-{self.region}"
            ),
        )
        log_group = logs.LogGroup(
            self,
            "ApiLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        role = iam.Role(self, "ApiRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        log_group.grant_write(role)
        role.add_to_policy(
            iam.PolicyStatement(actions=["dsql:DbConnect"], resources=[database.attr_resource_arn])
        )
        code = lambda_.Code.from_asset(str(ROOT / "build/lambda"))
        fn = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.main.handler",
            code=code,
            role=role,
            log_group=log_group,
            timeout=Duration.seconds(28),
            reserved_concurrent_executions=0
            if self.node.try_get_context("maintenance") == "true"
            else None,
            memory_size=256,
            environment={"AUTH_MODE": "cognito", "DSQL_HOST": database.attr_endpoint},
        )
        api = apigw.HttpApi(self, "HttpApi", create_default_stage=True)
        integration = integrations.HttpLambdaIntegration("FastApiIntegration", fn)
        headers = cf.ResponseHeadersPolicy(
            self,
            "Headers",
            security_headers_behavior=cf.ResponseSecurityHeadersBehavior(
                content_type_options=cf.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cf.ResponseHeadersFrameOptions(
                    frame_option=cf.HeadersFrameOption.DENY, override=True
                ),
                referrer_policy=cf.ResponseHeadersReferrerPolicy(
                    referrer_policy=cf.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=cf.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365),
                    include_subdomains=True,
                    override=True,
                ),
            ),
        )
        distribution = cf.Distribution(
            self,
            "Web",
            default_root_object="index.html",
            minimum_protocol_version=cf.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=headers,
            ),
            additional_behaviors={
                "/api/*": cf.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        f"{api.api_id}.execute-api.{self.region}.{self.url_suffix}"
                    ),
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    response_headers_policy=headers,
                )
            },
            price_class=cf.PriceClass.PRICE_CLASS_100,
        )
        url = f"https://{distribution.distribution_domain_name}/"
        client = pool.add_client(
            "Browser",
            generate_secret=False,
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[url],
                logout_urls=[url],
            ),
            access_token_validity=Duration.hours(1),
        )
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoJwt", pool.user_pool_provider_url, jwt_audience=[client.user_pool_client_id]
        )
        api.add_routes(
            path="/api/notes",
            methods=[apigw.HttpMethod.ANY],
            integration=integration,
            authorizer=jwt_authorizer,
        )
        api.add_routes(
            path="/api/notes/{proxy+}",
            methods=[apigw.HttpMethod.ANY],
            integration=integration,
            authorizer=jwt_authorizer,
        )
        api.add_routes(
            path="/api/shared/{token}", methods=[apigw.HttpMethod.GET], integration=integration
        )
        api.add_routes(path="/api/health", methods=[apigw.HttpMethod.GET], integration=integration)
        api.add_routes(
            path="/api/tasks",
            methods=[apigw.HttpMethod.GET],
            integration=integration,
            authorizer=jwt_authorizer,
        )
        stage = api.default_stage.node.default_child
        stage.default_route_settings = apigw.CfnStage.RouteSettingsProperty(
            throttling_burst_limit=20, throttling_rate_limit=10
        )
        NagSuppressions.add_resource_suppressions(
            stage,
            [
                {
                    "id": "AwsSolutions-APIG1",
                    "reason": "ログ保存費と共有URLの記録を避ける。アプリの例外ログは7日保持する。",
                }
            ],
        )
        for route in api.node.find_all():
            if isinstance(route, apigw.CfnRoute) and route.route_key in [
                "GET /api/health",
                "GET /api/shared/{token}",
            ]:
                NagSuppressions.add_resource_suppressions(
                    route,
                    [
                        {
                            "id": "AwsSolutions-APIG4",
                            "reason": "ヘルスチェックと期限付き共有リンクの閲覧のみ公開する。ノートAPIはJWT必須。",
                        }
                    ],
                )
        fn.add_environment("COGNITO_ISSUER", pool.user_pool_provider_url)
        fn.add_environment("COGNITO_CLIENT_ID", client.user_pool_client_id)
        migration_logs = logs.LogGroup(
            self,
            "MigrationLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        migration_role = iam.Role(
            self, "MigrationRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        migration_logs.grant_write(migration_role)
        migration_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dsql:DbConnectAdmin"], resources=[database.attr_resource_arn]
            )
        )
        migration = lambda_.Function(
            self,
            "Migration",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.migration_handler.handler",
            code=code,
            role=migration_role,
            log_group=migration_logs,
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "DSQL_HOST": database.attr_endpoint,
                "APP_ROLE_ARN": role.role_arn,
                "MIGRATIONS_DIR": "migrations",
            },
        )
        for name, value in {
            "SiteUrl": url,
            "BucketName": bucket.bucket_name,
            "DistributionId": distribution.distribution_id,
            "CognitoDomain": f"{domain.domain_name}.auth.{self.region}.amazoncognito.com",
            "CognitoClientId": client.user_pool_client_id,
            "MigrationFunction": migration.function_name,
        }.items():
            CfnOutput(self, name, value=value)
        NagSuppressions.add_resource_suppressions(
            bucket,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "個人ノート初期構築の費用を抑えるためS3アクセスログを省略。非公開・TLSは強制。",
                }
            ],
        )
        NagSuppressions.add_resource_suppressions(
            distribution,
            [
                {
                    "id": "AwsSolutions-CFR1",
                    "reason": "地域制限の要件なし。日本から利用可能な公開入口。",
                },
                {
                    "id": "AwsSolutions-CFR2",
                    "reason": "固定費のあるWAFは初期構築では使わない。JWTと所有者認可で保護。",
                },
                {
                    "id": "AwsSolutions-CFR3",
                    "reason": "アクセスログ保存費を抑える。API例外はCloudWatchへ記録。",
                },
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "CloudFront標準ドメイン証明書。カスタム証明書は不要。HTTPSを強制。",
                },
            ],
        )
        NagSuppressions.add_resource_suppressions(
            pool,
            [
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "初期構築はメール認証。MFAを強制せず利用者負担を抑える。",
                },
                {
                    "id": "AwsSolutions-COG8",
                    "reason": "高度な脅威保護の追加費用を避ける。標準のCognito認証を利用。",
                },
            ],
        )
        for target in [fn, migration]:
            NagSuppressions.add_resource_suppressions(
                target,
                [
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "全実行環境をPython 3.12に統一。サポート中のランタイム。",
                    }
                ],
            )
        for target in [role, migration_role]:
            NagSuppressions.add_resource_suppressions(
                target,
                [
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "ログストリームの自動生成名に限ったワイルドカード。対象ロググループARNで制限。",
                        "appliesTo": [
                            "Resource::<ApiLogs5D0D1BC0.Arn>:*",
                            "Resource::<MigrationLogsC70063D7.Arn>:*",
                        ],
                    }
                ],
                apply_to_children=True,
            )
        Aspects.of(self).add(AwsSolutionsChecks(verbose=True))
