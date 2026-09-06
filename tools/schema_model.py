from pathlib import Path

import sqlglot
from sqlglot import exp


def ddl_state(root: Path):
    tables, comments, indexes = {}, {}, []
    for path in sorted((root / "backend/migrations").glob("*.sql")):
        for node in sqlglot.parse(path.read_text(), dialect="postgres"):
            if isinstance(node, exp.Create) and node.kind == "TABLE":
                tables[node.this.this.name] = (path, node)
            elif isinstance(node, exp.Create) and node.kind == "INDEX":
                indexes.append((path, node))
            elif isinstance(node, exp.Comment):
                comments[node.this.sql(dialect="postgres")] = node.expression.this
            elif isinstance(node, exp.Alter):
                table = tables[node.this.name][1].this
                for action in node.args["actions"]:
                    if isinstance(action, exp.Drop) and action.kind == "COLUMN":
                        table.set(
                            "expressions",
                            [c for c in table.expressions if c.name != action.this.name],
                        )
                        indexes = [
                            (p, i)
                            for p, i in indexes
                            if not (
                                i.this.args["table"].name == node.this.name
                                and any(c.name == action.this.name for c in i.find_all(exp.Column))
                            )
                        ]
                    elif isinstance(action, exp.AddConstraint):
                        table.set("expressions", [*table.expressions, *action.expressions])
                    else:
                        raise ValueError("Unsupported ALTER: " + action.sql())
            else:
                raise ValueError("Unsupported DDL: " + str(node))
    return tables, comments, indexes


def primary_columns(table):
    return {c.name for c in table.find_all(exp.PrimaryKey) for c in c.expressions} | {
        c.name
        for c in table.expressions
        if isinstance(c, exp.ColumnDef)
        and any(isinstance(k.kind, exp.PrimaryKeyColumnConstraint) for k in c.constraints)
    }


def references(table):
    result = []
    for c in table.expressions:
        if isinstance(c, exp.ColumnDef):
            for ref in c.find_all(exp.Reference):
                result.append(
                    ([c.name], ref.this.this.name, [n.name for n in ref.this.expressions])
                )
        else:
            for fk in c.find_all(exp.ForeignKey):
                ref = fk.args["reference"].this
                result.append(
                    (
                        [n.name for n in fk.expressions],
                        ref.this.name,
                        [n.name for n in ref.expressions],
                    )
                )
    return result
