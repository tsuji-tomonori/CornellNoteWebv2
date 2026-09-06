import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { TaskList, type TaskOverview } from "./TaskList";
import { api } from "./api";
vi.mock("./api", () => ({ api: vi.fn() }));
const tasks: TaskOverview[] = [
  {
    id: "one",
    note_id: "first",
    title: "数学",
    group_name: "学習",
    text: "復習する",
    done: false,
    due: "2026-09-20",
  },
  {
    id: "two",
    note_id: "second",
    title: "英語",
    group_name: "語学",
    text: "音読する",
    done: true,
    due: null,
  },
];
beforeEach(() => {
  vi.clearAllMocks();
});
test("未完了と完了を横断表示し検索して所属ノートを開く", async () => {
  vi.mocked(api).mockResolvedValue(tasks);
  const onOpen = vi.fn();
  render(<TaskList onOpen={onOpen} />);
  expect(screen.getByRole("status")).toHaveTextContent("読み込み中");
  expect(await screen.findByText("復習する")).toBeVisible();
  expect(screen.queryByText("音読する")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "完了" }));
  expect(screen.getByText("音読する")).toBeVisible();
  expect(screen.getByText("期日: 未設定")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "すべて" }));
  expect(screen.getByText("復習する")).toBeVisible();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "数学" } });
  expect(screen.queryByText("音読する")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "ノートを開く: 数学" }));
  expect(onOpen).toHaveBeenCalledWith("first");
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "存在しない" },
  });
  expect(screen.getByText("該当するタスクはありません。")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "未完了" }));
  expect(api).toHaveBeenCalledWith("/tasks");
});
test("取得失敗は空一覧と区別して表示する", async () => {
  vi.mocked(api).mockRejectedValue(new Error("取得に失敗しました"));
  render(<TaskList onOpen={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "取得に失敗しました",
  );
  expect(
    screen.queryByText("該当するタスクはありません。"),
  ).not.toBeInTheDocument();
});
test("移動後に完了した通信ではアンマウント済み画面を更新しない", async () => {
  let resolve!: (value: TaskOverview[]) => void;
  vi.mocked(api).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const view = render(<TaskList onOpen={vi.fn()} />);
  view.unmount();
  await act(async () => resolve(tasks));
  await waitFor(() =>
    expect(screen.queryByText("復習する")).not.toBeInTheDocument(),
  );
  let reject!: (error: Error) => void;
  vi.mocked(api).mockReturnValue(
    new Promise((_r, e) => {
      reject = e;
    }),
  );
  const second = render(<TaskList onOpen={vi.fn()} />);
  second.unmount();
  await act(async () => reject(new Error("移動後の失敗")));
});
