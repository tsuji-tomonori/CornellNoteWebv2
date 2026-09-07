import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { Editor } from "./Editor";
import { blankNote, type Note } from "./domain";
const note = (): Note => ({
  ...blankNote(),
  id: "n",
  version: 1,
  updated_at: "2026-09-06",
  title: "講義",
  tasks: [
    { id: "a", text: "読む", done: false, due: null },
    { id: "b", text: "解く", done: true, due: "2026-09-10" },
  ],
});
test("三欄と科目を編集しタスクの追加・完了・期日・削除を保存する", async () => {
  const onSave = vi.fn().mockResolvedValue(undefined),
    onDirty = vi.fn();
  render(
    <Editor note={note()} onSave={onSave} onDirty={onDirty} busy={false} />,
  );
  for (const [label, value] of [
    ["ノートのタイトル", "復習"],
    ["コレクション", "数学"],
    ["問い・キーワード", "なぜ"],
    ["ノート本文", "証明"],
    ["まとめ", "理解"],
  ])
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  for (const tab of ["問い", "まとめ", "ノート"]) {
    fireEvent.click(screen.getByRole("tab", { name: tab }));
    expect(screen.getByRole("tab", { name: tab })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  }
  fireEvent.click(screen.getByLabelText("読むを完了"));
  fireEvent.change(screen.getByLabelText("読むの期日"), {
    target: { value: "2026-09-12" },
  });
  fireEvent.change(screen.getByLabelText("解くの期日"), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByLabelText("新しいアクション"), {
    target: { value: "  発表  " },
  });
  fireEvent.click(screen.getByLabelText("アクションを追加"));
  fireEvent.click(screen.getByLabelText("解くを削除"));
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({
      title: "復習",
      group: "数学",
      cue: "なぜ",
      content: "証明",
      summary: "理解",
      tasks: [
        { id: "a", text: "読む", done: true, due: "2026-09-12" },
        { id: expect.any(String), text: "発表", done: false, due: null },
      ],
    }),
  );
  expect(onDirty).toHaveBeenCalled();
});
test("空の入力と100件超のアクション追加を防ぐ", () => {
  const onSave = vi.fn(),
    onDirty = vi.fn();
  const { rerender } = render(
    <Editor note={note()} onSave={onSave} onDirty={onDirty} busy={false} />,
  );
  fireEvent.click(screen.getByLabelText("アクションを追加"));
  expect(onDirty).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("ノートのタイトル"), {
    target: { value: " " },
  });
  expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
  rerender(
    <Editor
      key="limit"
      note={{
        ...note(),
        tasks: Array.from({ length: 100 }, (_, i) => ({
          id: String(i),
          text: `項目${i}`,
          done: false,
          due: null,
        })),
      }}
      onSave={onSave}
      onDirty={onDirty}
      busy={false}
    />,
  );
  expect(screen.getByLabelText("アクションを追加")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("新しいアクション"), {
    target: { value: "追加" },
  });
  fireEvent.submit(screen.getByLabelText("新しいアクション").closest("form")!);
  expect(screen.queryByText("追加")).not.toBeInTheDocument();
});
test("保存ショートカットを処理し閲覧専用と保存中は変更しない", () => {
  const onSave = vi.fn();
  const { rerender, unmount } = render(
    <Editor note={note()} onSave={onSave} onDirty={vi.fn()} busy={false} />,
  );
  fireEvent.keyDown(window, { key: "x", ctrlKey: true });
  expect(onSave).not.toHaveBeenCalled();
  fireEvent.keyDown(window, { key: "s", metaKey: true });
  expect(onSave).toHaveBeenCalledOnce();
  rerender(<Editor note={note()} onSave={onSave} onDirty={vi.fn()} busy />);
  fireEvent.keyDown(window, { key: "s", ctrlKey: true });
  expect(screen.getByRole("button", { name: "保存中…" })).toBeDisabled();
  expect(onSave).toHaveBeenCalledOnce();
  rerender(
    <Editor
      note={note()}
      onSave={onSave}
      onDirty={vi.fn()}
      busy={false}
      readOnly
    />,
  );
  expect(
    screen.queryByRole("button", { name: "保存" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("ノート本文")).toHaveAttribute("readonly");
  expect(screen.getByLabelText("読むを完了")).toBeDisabled();
  fireEvent.keyDown(window, { key: "s", ctrlKey: true });
  unmount();
  fireEvent.keyDown(window, { key: "s", ctrlKey: true });
  expect(onSave).toHaveBeenCalledOnce();
});

test("タブを矢印とHome・Endで選びフォーカスを移動できる", () => {
  render(
    <Editor note={note()} onSave={vi.fn()} onDirty={vi.fn()} busy={false} />,
  );
  const content = screen.getByRole("tab", { name: "ノート" });
  content.focus();
  fireEvent.keyDown(content, { key: "ArrowRight" });
  const summary = screen.getByRole("tab", { name: "まとめ" });
  expect(summary).toHaveFocus();
  expect(summary).toHaveAttribute("aria-selected", "true");
  fireEvent.keyDown(summary, { key: "ArrowRight" });
  const cue = screen.getByRole("tab", { name: "問い" });
  expect(cue).toHaveFocus();
  fireEvent.keyDown(cue, { key: "ArrowLeft" });
  expect(summary).toHaveFocus();
  fireEvent.keyDown(summary, { key: "Home" });
  expect(cue).toHaveFocus();
  fireEvent.keyDown(cue, { key: "End" });
  expect(summary).toHaveFocus();
  fireEvent.keyDown(summary, { key: "Tab" });
  expect(summary).toHaveAttribute("tabindex", "0");
  expect(content).toHaveAttribute("tabindex", "-1");
});
