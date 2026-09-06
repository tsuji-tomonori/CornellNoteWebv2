import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api } from "./api";
beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());
test("認証済みの更新ではJWTとJSON本文を送り結果を受け取る", async () => {
  sessionStorage.setItem("access_token", "jwt");
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ id: "note" })),
  );
  expect(await api("/notes/n", "PUT", { title: "講義" })).toEqual({
    id: "note",
  });
  expect(fetch).toHaveBeenCalledWith(
    "/api/notes/n",
    expect.objectContaining({
      method: "PUT",
      body: '{"title":"講義"}',
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer jwt",
      },
    }),
  );
});
test("匿名の削除成功204は本文を解析しない", async () => {
  vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
  expect(await api("/notes/n", "DELETE")).toBeUndefined();
  expect(fetch).toHaveBeenCalledWith("/api/notes/n", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
});
test("認証切れではトークンを削除して画面へ通知する", async () => {
  sessionStorage.setItem("access_token", "expired");
  const expired = vi.fn();
  window.addEventListener("session-expired", expired);
  vi.mocked(fetch).mockResolvedValue(
    new Response('{"detail":"期限切れ"}', { status: 401 }),
  );
  await expect(api("/notes")).rejects.toThrow("期限切れ");
  expect(sessionStorage.getItem("access_token")).toBeNull();
  expect(expired).toHaveBeenCalledOnce();
  window.removeEventListener("session-expired", expired);
});
test("ログイン失敗は既存セッションの失効イベントを送らない", async () => {
  const expired = vi.fn();
  window.addEventListener("session-expired", expired);
  vi.mocked(fetch).mockResolvedValue(
    new Response('{"detail":"認証失敗"}', { status: 401 }),
  );
  await expect(api("/auth/local", "POST", {})).rejects.toThrow("認証失敗");
  expect(expired).not.toHaveBeenCalled();
  window.removeEventListener("session-expired", expired);
});
test("検証エラーとJSON以外の障害を日本語に変換する", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(new Response('{"detail":[]}', { status: 422 }))
    .mockResolvedValueOnce(new Response("upstream failure", { status: 502 }));
  await expect(api("/notes")).rejects.toThrow("入力内容");
  await expect(api("/notes")).rejects.toThrow("通信に失敗");
});
