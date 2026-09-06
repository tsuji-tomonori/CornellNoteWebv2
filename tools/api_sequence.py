import ast

from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    websocket_request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from starlette.exceptions import HTTPException


def verify_framework(app):
    expected = {
        HTTPException: http_exception_handler,
        RequestValidationError: request_validation_exception_handler,
        WebSocketRequestValidationError: websocket_request_validation_exception_handler,
    }
    if app.debug or app.user_middleware or app.exception_handlers != expected:
        raise ValueError("Custom error handling requires response-contract extraction support")


def schema_name(schema):
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if schema.get("type") == "array":
        return schema_name(schema["items"]) + "[]"
    if "anyOf" in schema:
        return " / ".join(schema_name(s) for s in schema["anyOf"])
    return schema.get("title", schema.get("type", "object"))


def success_response(definition):
    success = [(k, v) for k, v in definition["responses"].items() if k.startswith("2")]
    if len(success) != 1:
        raise ValueError("Multiple success responses require branch-specific extraction")
    status, response = success[0]
    content = response.get("content", {})
    if not content:
        return status, "本文なし"
    return status, " / ".join(
        f"{media}: {schema_name(value.get('schema', {}))}" for media, value in content.items()
    )


def response_cases(definition, errors):
    status, body = success_response(definition)
    rows = [(status, "API", "正常終了", body)]
    rows += [
        (str(code), "API / 認証", detail, 'application/json: {detail: "' + detail + '"}')
        for code, detail in sorted({(code, detail) for code, detail, _ in errors})
    ]
    if "422" in definition["responses"]:
        rows.append(
            (
                "422",
                "FastAPI入力検証",
                "パス・query・bodyの型/制約違反、必須項目不足、不正なJSON",
                "application/json: HTTPValidationError（detail配列）",
            )
        )
    rows.append(
        (
            "500",
            "FastAPI / Starlette共通処理",
            "未処理例外（DB接続・実行・結果変換など）。個別catchでHTTP応答に変換した例外はそのコードを返す",
            "text/plain: Internal Server Error",
        )
    )
    return rows


def routing_cases(redirect_slashes):
    rows = [
        (
            "404",
            "ルーティング",
            "URLが登録済みパスに一致しない（このAPIのハンドラには到達しない）",
            'application/json: {detail: "Not Found"}',
        ),
        (
            "405",
            "ルーティング",
            "URLは存在するがHTTPメソッドが許可されていない",
            'application/json: {detail: "Method Not Allowed"} / Allowヘッダー',
        ),
    ]
    if redirect_slashes:
        rows.append(
            (
                "307",
                "ルーティング",
                "末尾スラッシュの補正で既存パスへリダイレクトする",
                "本文なし / Locationヘッダー",
            )
        )
    return rows


def label(value):
    text = ast.unparse(value) if isinstance(value, ast.AST) else str(value)
    return (
        text.replace("\n", " ")
        .replace(";", "#59;")
        .replace('"', "#quot;")
        .replace("<", "#lt;")
        .replace(">", "#gt;")
    )


def sequence(node, queries, *, request, definition, auth_errors=()):
    by_name = {q["name"]: q for q in queries}
    status, body = success_response(definition)
    lines = [
        "sequenceDiagram",
        "    participant C as 呼び出し元",
        "    participant A as API",
        "    participant D as データベース",
        "    C->>A: " + label(request),
        "    critical リクエスト処理",
    ]

    def emit(text):
        lines.append("    " + text)

    def reply(code, value):
        emit(f"A-->>C: HTTP {code} / {label(value)}")

    def calls(expr):
        if expr is None:
            return
        if isinstance(
            expr,
            ast.BoolOp | ast.IfExp | ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        ):
            if any(
                isinstance(n, ast.Call) and ast.unparse(n.func).startswith("queries.")
                for n in ast.walk(expr)
            ):
                raise ValueError(
                    "Conditional/iterated SQL calls require sequence extraction support"
                )
            return
        for child in ast.iter_child_nodes(expr):
            calls(child)
        if isinstance(expr, ast.Call):
            name = ast.unparse(expr.func)
            if name.startswith("queries.") and name.split(".")[-1] in by_name:
                q = by_name[name.split(".")[-1]]
                emit(f"A->>D: {q['operation']} {q['table']} / {label(q['summary'])}")
                emit("D-->>A: " + ("行データ（0件以上）" if q["rows"] else "実行完了"))

    def block(nodes):
        for n in nodes:
            if isinstance(n, ast.If):
                calls(n.test)
                emit("alt " + label(n.test))
                yes = block(n.body)
                no = True
                if n.orelse:
                    emit("else 条件が偽")
                    no = block(n.orelse)
                emit("end")
                if not yes and not no:
                    return False
            elif isinstance(n, ast.Try):
                if n.finalbody:
                    raise ValueError("finally control flow requires explicit response extraction")
                emit("critical try")
                falls_through = block(n.body)
                if n.orelse and falls_through:
                    falls_through = block(n.orelse)
                for h in n.handlers:
                    emit("option catch " + label(h.type))
                    falls_through = block(h.body) or falls_through
                emit("end")
                if not falls_through:
                    return False
            elif isinstance(n, ast.With):
                if not block(n.body):
                    return False
            elif isinstance(n, ast.Return):
                calls(n.value)
                emit("break 正常終了")
                reply(status, body)
                emit("end")
                return False
            elif isinstance(n, ast.Raise):
                if not isinstance(n.exc, ast.Call) or ast.unparse(n.exc.func) != "HTTPException":
                    raise ValueError("Non-HTTP raise requires exception propagation extraction")
                values = dict(zip(["status_code", "detail"], n.exc.args, strict=False))
                values.update({k.arg: k.value for k in n.exc.keywords})
                code = ast.literal_eval(values["status_code"])
                detail = ast.literal_eval(values["detail"])
                emit("break 異常終了")
                reply(code, 'application/json: {detail: "' + detail + '"}')
                emit("end")
                return False
            elif isinstance(n, ast.Assign | ast.AnnAssign | ast.Expr):
                calls(n.value)
            elif not isinstance(n, ast.Pass):
                raise ValueError(f"Unsupported sequence statement: {type(n).__name__}:{n.lineno}")
        return True

    rejection_branches = 0
    if auth_errors:
        emit("alt 認証検証で拒否")
        for code in sorted({code for code, _, _ in auth_errors}):
            reply(code, "application/json: detail（理由は応答表を参照）")
        rejection_branches += 1
    if "422" in definition["responses"]:
        emit(("else" if rejection_branches else "alt") + " 入力検証で拒否")
        reply("422", "application/json: HTTPValidationError")
        rejection_branches += 1
    if rejection_branches:
        emit("else 検証通過")
    if block(node.body):
        reply(status, body)
    if rejection_branches:
        emit("end")
    emit("option 個別catchで処理されない例外")
    reply("500", "text/plain: Internal Server Error")
    emit("end")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n"
