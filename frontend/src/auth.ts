const domain = import.meta.env.VITE_COGNITO_DOMAIN as string | undefined;
const client = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined;
export const localMode = import.meta.env.VITE_AUTH_MODE === "local";
const b64 = (v: Uint8Array) =>
  btoa(String.fromCharCode(...v))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
export async function loginCognito(): Promise<void> {
  if (!domain || !client) throw new Error("ログイン設定がまだ完了していません");
  const verifier = b64(crypto.getRandomValues(new Uint8Array(32)));
  const state = b64(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem("pkce", verifier);
  sessionStorage.setItem("oauth_state", state);
  const challenge = b64(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)),
    ),
  );
  location.assign(
    `https://${domain}/oauth2/authorize?${new URLSearchParams({ client_id: client, response_type: "code", scope: "openid email profile", redirect_uri: location.origin + "/", state, code_challenge: challenge, code_challenge_method: "S256" })}`,
  );
}
export async function completeLogin(): Promise<void> {
  const p = new URLSearchParams(location.search);
  if (p.has("error")) {
    history.replaceState(null, "", "/");
    throw new Error("ログインがキャンセルされました");
  }
  const code = p.get("code");
  if (!code) return;
  const verifier = sessionStorage.getItem("pkce");
  const state = sessionStorage.getItem("oauth_state");
  history.replaceState(null, "", "/");
  sessionStorage.removeItem("pkce");
  sessionStorage.removeItem("oauth_state");
  if (!domain || !client || !verifier || !state || p.get("state") !== state)
    throw new Error("ログイン状態を確認できません。やり直してください");
  const res = await fetch(`https://${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: client,
      code,
      redirect_uri: location.origin + "/",
      code_verifier: verifier,
    }),
  });
  if (!res.ok) throw new Error("ログインに失敗しました");
  const result = await res.json();
  sessionStorage.setItem("access_token", result.access_token);
}
export function logout(): void {
  sessionStorage.removeItem("access_token");
  if (!localMode && domain && client)
    location.assign(
      `https://${domain}/logout?${new URLSearchParams({ client_id: client, logout_uri: location.origin + "/" })}`,
    );
  else location.assign("/");
}
