import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { api } from "./api";
import { blankNote, type Note } from "./domain";
const auth = vi.hoisted(() => ({
  localMode: true,
  loginCognito: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("./auth", () => auth);
vi.mock("./api", () => ({ api: vi.fn() }));
const note = (id = "n", group = "数学"): Note => ({
  ...blankNote(),
  id,
  group,
  title: "講義" + id,
  content: "証明",
  version: 1,
  updated_at: "2026-09-06",
});
let notes: Note[];
beforeEach(() => {
  vi.clearAllMocks();
  auth.localMode = true;
  sessionStorage.clear();
  location.hash = "";
  notes = [note(), note("b", "英語")];
  vi.stubGlobal(
    "confirm",
    vi.fn(() => true),
  );
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
  vi.mocked(api).mockImplementation(async (path, method = "GET", body) => {
    if (path === "/auth/local") return { access_token: "jwt" };
    if (path === "/notes" && method === "GET") return notes;
    if (path === "/notes" && method === "POST") {
      const n = { ...note("new"), ...(body as object) };
      notes = [...notes, n];
      return n;
    }
    if (path.includes("/share") && method === "POST")
      return { token: "shared" };
    if (method === "PUT") {
      const n = { ...note(), ...(body as object) };
      notes = [n];
      return n;
    }
    if (method === "DELETE") {
      notes = [];
      return undefined;
    }
    if (path.startsWith("/shared/")) return note();
    throw new Error("未定義API: " + path);
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
});
async function workspace() {
  sessionStorage.setItem("access_token", "jwt");
  render(<App />);
  await screen.findByRole("heading", { name: "講義n" });
}
async function open() {
  fireEvent.click(screen.getByRole("heading", { name: "講義n" }));
  await screen.findByLabelText("ノートのタイトル");
}
test("ローカルログインで選択した本人の一覧を表示する", async () => {
  render(<App />);
  fireEvent.change(screen.getByLabelText("ユーザー"), {
    target: { value: "bob" },
  });
  fireEvent.change(screen.getByLabelText("パスワード"), {
    target: { value: "password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "ログイン" }));
  await screen.findByRole("heading", { name: "講義n" });
  expect(api).toHaveBeenCalledWith("/auth/local", "POST", {
    username: "bob",
    password: "password",
  });
  expect(sessionStorage.getItem("access_token")).toBe("jwt");
});
test("Cognitoログイン失敗と初期エラーを表示する", async () => {
  auth.localMode = false;
  auth.loginCognito.mockRejectedValue(new Error("認証できません"));
  render(<App initialError="キャンセルされました" />);
  expect(screen.getByRole("alert")).toHaveTextContent("キャンセル");
  fireEvent.click(screen.getByRole("button", { name: "ログイン" }));
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("認証できません"),
  );
  expect(screen.queryByLabelText("パスワード")).not.toBeInTheDocument();
});
test("一覧を科目と検索で絞り込み該当なしと全件復帰を表示する", async () => {
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "数学" }));
  expect(
    screen.queryByRole("heading", { name: "講義b" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("ノートを検索"), {
    target: { value: "存在しない" },
  });
  expect(screen.getByText("一致するノートはありません")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("ノートを検索"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: /すべてのノート/ }));
  expect(screen.getByRole("heading", { name: "講義b" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "ログアウト" }));
  expect(auth.logout).toHaveBeenCalledOnce();
});
test("未保存の離脱を確認し保存後は一覧と共有へ進める", async () => {
  await workspace();
  await open();
  fireEvent.change(screen.getByLabelText("ノート本文"), {
    target: { value: "追記" },
  });
  expect(screen.getByRole("button", { name: "共有" })).toBeDisabled();
  const unload = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(unload);
  expect(unload.defaultPrevented).toBe(true);
  vi.mocked(confirm).mockReturnValue(false);
  fireEvent.click(screen.getByRole("button", { name: "ノート一覧" }));
  expect(screen.getByLabelText("ノート本文")).toHaveValue("追記");
  fireEvent.click(screen.getByRole("button", { name: "数学" }));
  fireEvent.click(screen.getByRole("button", { name: /すべてのノート/ }));
  fireEvent.click(screen.getByRole("button", { name: "ログアウト" }));
  expect(auth.logout).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent("保存しました"),
  );
  expect(api).toHaveBeenCalledWith(
    "/notes/n",
    "PUT",
    expect.objectContaining({ content: "追記", version: 1 }),
  );
  fireEvent.click(screen.getByRole("button", { name: "ノート一覧" }));
  await screen.findByRole("heading", { name: "講義n" });
});
test("新規作成から保存競合・削除取消・削除成功を扱う", async () => {
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "新しいノート" }));
  await screen.findByLabelText("ノートのタイトル");
  expect(api).toHaveBeenCalledWith("/notes", "POST", blankNote());
  vi.mocked(api).mockRejectedValueOnce(new Error("更新が競合しました"));
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await screen.findByText("更新が競合しました");
  expect(screen.getByRole("status")).toHaveTextContent(
    "操作を完了できませんでした",
  );
  vi.mocked(confirm).mockReturnValue(false);
  fireEvent.click(screen.getByLabelText("ノートを削除"));
  expect(screen.getByLabelText("ノートのタイトル")).toBeInTheDocument();
  vi.mocked(confirm).mockReturnValue(true);
  fireEvent.click(screen.getByLabelText("ノートを削除"));
  await screen.findByText("最初の一枚から、はじめよう。");
  fireEvent.click(screen.getByRole("button", { name: "ノートを作成" }));
  await screen.findByLabelText("ノートのタイトル");
});
test("共有発行・コピー・解除と共有画面の閉じる操作を行う", async () => {
  await workspace();
  await open();
  fireEvent.click(screen.getByRole("button", { name: "共有" }));
  fireEvent.click(screen.getByLabelText("共有画面を閉じる"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "共有" }));
  fireEvent.click(screen.getByRole("button", { name: "閲覧リンクを発行" }));
  const link = await screen.findByLabelText("共有リンク");
  expect(link).toHaveValue(location.origin + "/#share=shared");
  fireEvent.click(screen.getByRole("button", { name: "リンクをコピー" }));
  await waitFor(() =>
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      location.origin + "/#share=shared",
    ),
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "共有を解除",
    }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("status")).toHaveTextContent("共有を解除しました");
});
test("共有ノートは読み込み後に閲覧専用となり取得失敗は表示する", async () => {
  location.hash = "share=token";
  const { unmount } = render(<App />);
  expect(screen.getByText("読み込み中…")).toBeInTheDocument();
  await screen.findByLabelText("ノート本文");
  expect(screen.getByLabelText("ノート本文")).toHaveAttribute("readonly");
  expect(
    screen.queryByRole("button", { name: "保存" }),
  ).not.toBeInTheDocument();
  unmount();
  vi.mocked(api).mockRejectedValueOnce(new Error("期限切れ"));
  render(<App />);
  await screen.findByText("期限切れ");
  expect(screen.queryByText("読み込み中…")).not.toBeInTheDocument();
});
test("一覧の取得失敗とセッション失効を利用者に通知する", async () => {
  sessionStorage.setItem("access_token", "jwt");
  vi.mocked(api).mockRejectedValueOnce(new Error("通信障害"));
  render(<App />);
  await screen.findByText("通信障害");
  act(() => window.dispatchEvent(new Event("session-expired")));
  expect(screen.getByRole("alert")).toHaveTextContent("セッションが切れました");
  expect(screen.getByLabelText("パスワード")).toBeInTheDocument();
});
