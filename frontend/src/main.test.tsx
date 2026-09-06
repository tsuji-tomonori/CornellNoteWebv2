import { afterEach, expect, test, vi } from "vitest";
const mocks = vi.hoisted(() => ({ render: vi.fn(), completeLogin: vi.fn() }));
vi.mock("react-dom/client", () => ({
  createRoot: () => ({ render: mocks.render }),
}));
vi.mock("./auth", () => ({ completeLogin: mocks.completeLogin }));
vi.mock("./App", () => ({ App: () => null }));
afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});
test("起動時の認証完了後にアプリを描画する", async () => {
  mocks.completeLogin.mockResolvedValue(undefined);
  await import("./main");
  await vi.waitFor(() => expect(mocks.render).toHaveBeenCalledOnce());
  expect(mocks.render.mock.calls[0][0].props.initialError).toBeUndefined();
});
test("起動時の認証失敗を画面の初期エラーへ渡す", async () => {
  mocks.completeLogin.mockRejectedValue(new Error("認証失敗"));
  await import("./main");
  await vi.waitFor(() => expect(mocks.render).toHaveBeenCalledOnce());
  expect(mocks.render.mock.calls[0][0].props.initialError).toBe("認証失敗");
});
