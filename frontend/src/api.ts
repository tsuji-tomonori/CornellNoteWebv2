export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const token = sessionStorage.getItem("access_token");
  const response = await fetch("/api" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "通信に失敗しました" }));
    if (response.status === 401 && path !== "/auth/local") {
      sessionStorage.removeItem("access_token");
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "入力内容を確認してください",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}
