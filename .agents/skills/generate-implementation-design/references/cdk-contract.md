# AWS CDK implementation-to-design contract

1. Build and test the CDK application.
2. Run `cdk synth`; AWS documents that this produces a CloudFormation template for each stack.
3. Feed the synthesized YAML/JSON, not handwritten architecture prose, to `designflow.py cdk`.
4. Generate resource type/logical-ID/Properties inventory and parameter type/default/allowed-values/description.
5. Put the applicable active canonical requirement IDs in synthesized resource `Metadata.RequirementIds`（または`Metadata.DevStandard.RequirementIds`）and trace each ID to the logical ID and a node in the generated portable pytest collection manifest.
6. Keep manual architecture decisions separate from generated implementation detail.

The manifest binds generated documentation to the exact template bytes. Logical-ID or property changes therefore invalidate `--check` until regeneration.

The command requires canonical requirements JSON, schema-v2 explicit trace JSON with `applicable_requirement_ids`, and a test root. A resource trace uses the same schema as the FastAPI contract with `{"kind": "resource", "id": "<LogicalId>"}`. Unknown or inactive requirements, unknown logical IDs, nodes absent from `TEST_MANIFEST.gen.json`, duplicate links, and differences among the applicable set, resource metadata, and explicit trace fail closed. Active requirements outside the declared applicable set are not implicitly required.

The bundled command supports a single synthesized template, resource and parameter catalogs, requirement trace, and deterministic generate/check. Multi-stack manifests, IAM/network/stateful catalogs, suppression extraction, and destructive-change classification are not bundled capabilities; use them only when the target repository explicitly selects and owns an adapter that provides them.

Run `python tools/portable_python.py setup` once in the target repository, then invoke `python tools/portable_python.py run <host-skill-path>/scripts/designflow.py -- cdk ...`. The runner keeps the exact-pinned YAML/SQL runtime isolated from the target's existing environment, passes arguments including `--repo-root` through unchanged, and resolves `<host-skill-path>` through the installed host adapter instead of assuming `.agents`.

Primary references: [AWS CDK synthesis](https://docs.aws.amazon.com/cdk/v2/guide/configure-synth.html) and [CloudFormation template sections](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html).
