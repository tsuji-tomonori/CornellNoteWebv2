# FastAPI implementation-to-design contract

## Operation layout

- `router.py`: path-operation declaration and ordered orchestration only. It may validate/construct narrow typed inputs and call named functions, but must not contain domain algorithms or persistence details.
- `functions.py`: concrete application/domain operations. Prefer three or fewer arguments; introduce a narrowly scoped Pydantic input model beyond that and explain the grouping in its docstring.
- Return the final response-producing call directly. A route ending with `response = ...; return response` is a contract violation.
- Put `/health` under a `system` domain router, not in `main.py`.
- Examples declared in schemas/OpenAPI are executable unit-test expectations, not decorative documentation.
- Declare `APIRouter(prefix=...)` with a literal string. The effective route identity is prefix + decorator path; duplicate effective method/path pairs are invalid.
- Calls from `router.py` into sibling `functions.py` are expanded recursively in evaluation order. The bundled CFG supports simple expression/assignment/return/raise/assert statements and explicit `if`/`else`; generated sequence diagrams retain each branch. Loops, comprehensions, `try`, `with`, `match`, short-circuit/conditional expressions, nested definitions, local recursion, dynamic route paths/metadata, and dynamic dispatch fail closed instead of being linearized.

## Generated artifacts

| Source | Generated design |
|---|---|
| `router.py` AST | operation flow and Mermaid sequence diagrams |
| application `openapi.json`、handler metadata、`samples.py` | API catalog、API details、path/query/header parameters、request/response interface、global error case JSON |
| raw `.sql` parsed with SQLGlot and explicit handler string references | query-object catalog、table×API CRUD、external destination×API |
| authoritative DDL | table、column、constraint、ER relationship、column-writing API |
| E2E test source | ordered Given/When/Then scenario |
| generator tool AST and docstrings | CLI、control flow、function responsibility |
| external result reference JSON | status and evidence links only; result bodies remain external |
| canonical requirements JSON、artifact metadata、explicit applicable-ID set、trace JSON、test source | applicable active requirement ID→operation→portable pytest collection node trace and generated test manifest |
| source bytes | manifest SHA-256 used by `--check` |

OpenAPI operationとeffective handler routeは1対1でなければならない。duplicate route・operation ID、handlerとOpenAPIのoperation IDまたは同名`x-*` metadataの競合、inline解析できないpath referenceを拒否する。path/query/header parameterをpath-levelとoperation-levelからOpenAPIの上書き規則で導出し、path template変数とrequired path parameterの集合を完全一致させる。OpenAPIの各operationは空でない`x-requirement-ids`を持ち、explicit traceの同じoperationに対するID集合と完全一致させる。

Trace JSONは次の形を使う。`applicable_requirement_ids`は、この生成scopeに適用されるactive requirementだけを明示する。全catalog active要件を過剰要求せず、この集合、artifact metadataの和集合、trace linkの集合を完全一致させる。test nodeはrepository相対のpytest node IDであり、生成する`TEST_MANIFEST.gen.json`のportable static collection subset（top-level test functionまたはcollectable test class method、非parametrize）に実在しなければならない。

```json
{
  "schema_version": 2,
  "applicable_requirement_ids": ["REQ-ITEM-001"],
  "links": [
    {
      "requirement_id": "REQ-ITEM-001",
      "artifact": {"kind": "operation", "id": "getItem"},
      "tests": ["tests/test_items.py::test_get_item"]
    }
  ]
}
```

SQL sourceはhandlerまたは到達可能なhelperのliteral repository-relative `.sql` pathへ明示対応させる。basename参照はSQL root内で一意の場合だけ許可し、未対応source、複数operationへの対応、basename衝突を拒否する。bundled SQL projectionは`SELECT` / `INSERT` / `UPDATE` / `DELETE`だけを扱い、`MERGE`その他のstatementはSELECTへ読み替えずbounded errorにする。

Error case IDはhandler名ではなくliteral `code` / `case_id`から`ERR-<NORMALIZED-CODE>`として導出し、生成scope全体で一意にする。

`FAST-017`はsample keyの文字列参照だけではpassにしない。client invocationからbranch-aware data-flowで導出された値とのassertを要求し、再代入時にprovenanceをkillする。adapterは`@trusted_runtime_response_adapter("<authority-id>")`を持ち、その関数自身が認識済みruntime clientを呼ぶ場合だけ信頼する。`FAST-018`はSQLのC/U/Dに`assert_db_state`、変更を伴う外部client callに`assert_external_state`を個別に要求する。異常系も`assert_<effect>_state_unchanged`または理由付き`assert_allowed_<effect>_state_change`をeffect別に要求する。

Static analysis must reject missing direct returns, unparseable Python/SQL/DDL, unsupported structures, lexical symlinks, unmanaged or escaped output paths, and generated drift. Manifest source pathとdrift pathはrepository相対にする。`--check`は候補をOS temporary directoryに構築し、repositoryを変更しない。FAST-016〜022とAUD-008は`scripts/qualityflow.py`の個別commandで実行する。選択結果の集約は3本目の`inspect-quality-gates`へ一本化し、portable runtimeはGitHub Actions等のCI固有pathへ直接書き込まない。

Target repositoryで初回だけ`python tools/portable_python.py setup`を実行し、以後は`python tools/portable_python.py run <host-skill-path>/scripts/designflow.py -- <args...>`（品質checkは同じ形で`qualityflow.py`）を使う。runnerはSkillのexact-pinned依存をtargetの既存venv/global環境から隔離し、`--`以後の`--repo-root`を含む引数を透過する。`<host-skill-path>`はinstallerが選んだhost-native Skill rootであり、`.agents`を固定しない。

Primary references: [FastAPI OpenAPI generation](https://fastapi.tiangolo.com/how-to/extending-openapi/), [OpenAPI Specification](https://spec.openapis.org/oas/latest.html), and [SQLGlot AST documentation](https://sqlglot.com/sqlglot.html).
