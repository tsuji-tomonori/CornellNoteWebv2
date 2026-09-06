import { describe, it, expect } from "vitest";
import {
  blankNote,
  editable,
  groupedNotes,
  progress,
  type Note,
} from "./domain";
const sample: Note = {
  ...blankNote(),
  id: "1",
  title: "分散システム",
  group: "情報工学",
  content: "DSQLのトランザクション",
  version: 1,
  updated_at: "2026-09-06T00:00:00Z",
};
describe("ノートの整理", () => {
  it("科目と本文を組み合わせて検索する", () => {
    expect(groupedNotes([sample], "dsql", "情報工学")["情報工学"]).toHaveLength(
      1,
    );
    expect(Object.keys(groupedNotes([sample], "dsql", "数学"))).toHaveLength(0);
    expect(Object.keys(groupedNotes([sample], "存在しない", ""))).toHaveLength(
      0,
    );
  });
  it("特殊な科目名を安全に扱う", () => {
    expect(
      groupedNotes([{ ...sample, group: "__proto__" }], "", "")["__proto__"],
    ).toHaveLength(1);
  });
  it("空ノートごとにタスク配列を分離する", () => {
    const a = blankNote(),
      b = blankNote();
    a.tasks.push({ id: "x", text: "復習", done: false, due: null });
    expect(b.tasks).toEqual([]);
  });
  it("編集用payloadに所有者やIDを混ぜない", () => {
    expect(Object.keys(editable(sample))).toEqual([
      "title",
      "group",
      "cue",
      "content",
      "summary",
      "tasks",
    ]);
  });
  it("完了件数を算出する", () => {
    expect(progress([])).toBe("0 / 0");
    expect(
      progress([
        { id: "a", text: "読む", done: true, due: null },
        { id: "b", text: "考える", done: false, due: null },
      ]),
    ).toBe("1 / 2");
  });
});
