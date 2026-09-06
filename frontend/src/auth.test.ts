import { beforeEach, afterEach, expect, test, vi } from "vitest";

let memory: Map<string, string>;
const assign = vi.fn();
const replaceState = vi.fn();
beforeEach(() => {
  memory = new Map();
  vi.resetModules();
  vi.stubEnv(
    "VITE_COGNITO_DOMAIN",
    "test.auth.ap-northeast-1.amazoncognito.com",
  );
  vi.stubEnv("VITE_COGNITO_CLIENT_ID", "test-client");
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => memory.set(key, value),
    removeItem: (key: string) => memory.delete(key),
  });
  vi.stubGlobal("location", {
    origin: "https://notes.example",
    search: "",
    assign,
  });
  vi.stubGlobal("history", { replaceState });
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

test("Cognitoへの遷移にランダムなstateとSHA-256のPKCEを付与する", async () => {
  const { loginCognito } = await import("./auth");
  await loginCognito();
  const url = new URL(assign.mock.calls[0][0]);
  expect(url.searchParams.get("code_challenge_method")).toBe("S256");
  expect(url.searchParams.get("state")).toBe(memory.get("oauth_state"));
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(memory.get("pkce")),
  );
  const expected = btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  expect(url.searchParams.get("code_challenge")).toBe(expected);
  expect(url.searchParams.get("redirect_uri")).toBe("https://notes.example/");
});
test("stateが一致しないコールバックを拒否し交換リクエストを送らない", async () => {
  location.search = "?code=code&state=attacker";
  memory.set("pkce", "verifier");
  memory.set("oauth_state", "expected");
  const { completeLogin } = await import("./auth");
  await expect(completeLogin()).rejects.toThrow("ログイン状態");
  expect(fetch).not.toHaveBeenCalled();
  expect(memory.has("pkce")).toBe(false);
});
test("正常なコールバックを一度だけ交換しアクセストークンを保存する", async () => {
  location.search = "?code=code&state=expected";
  memory.set("pkce", "verifier");
  memory.set("oauth_state", "expected");
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ access_token: "test-access-token" })),
  );
  const { completeLogin } = await import("./auth");
  await completeLogin();
  expect(memory.get("access_token")).toBe("test-access-token");
  expect(memory.has("oauth_state")).toBe(false);
  await expect(completeLogin()).rejects.toThrow("ログイン状態");
  expect(fetch).toHaveBeenCalledTimes(1);
});
test("キャンセルされたログインをエラーとして返す", async () => {
  location.search = "?error=access_denied";
  const { completeLogin } = await import("./auth");
  await expect(completeLogin()).rejects.toThrow("キャンセル");
  expect(replaceState).toHaveBeenCalledWith(null, "", "/");
});

test("設定不足ではCognitoへ遷移せずコールバックなしは何もしない", async () => {
  vi.stubEnv("VITE_COGNITO_DOMAIN", "");
  const { loginCognito, completeLogin } = await import("./auth");
  await expect(loginCognito()).rejects.toThrow("ログイン設定");
  await completeLogin();
  expect(fetch).not.toHaveBeenCalled();
});
test("トークン交換の失敗を表示して保存しない", async () => {
  location.search = "?code=code&state=expected";
  memory.set("pkce", "verifier");
  memory.set("oauth_state", "expected");
  vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 400 }));
  const { completeLogin } = await import("./auth");
  await expect(completeLogin()).rejects.toThrow("ログインに失敗");
  expect(memory.has("access_token")).toBe(false);
});
test("Cognitoログアウトではトークンを消してHosted UIへ遷移する", async () => {
  vi.stubEnv("VITE_AUTH_MODE", "cognito");
  memory.set("access_token", "jwt");
  const { logout } = await import("./auth");
  logout();
  expect(memory.has("access_token")).toBe(false);
  expect(assign).toHaveBeenCalledWith(expect.stringContaining("/logout?"));
});
test("ローカルログアウトはトップへ戻る", async () => {
  vi.stubEnv("VITE_AUTH_MODE", "local");
  const { logout } = await import("./auth");
  logout();
  expect(assign).toHaveBeenCalledWith("/");
});
