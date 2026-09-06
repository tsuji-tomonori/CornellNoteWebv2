import { test, expect } from "@playwright/test";

test("トップは品質サマリーから各結果へ移動できる", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "品質の状態を、ひと目で。",
  );
  await expect(page.locator("article.case, [data-screenshot]")).toHaveCount(0);
  for (const [name, path] of [
    ["E2E", "e2e.html"],
    ["静的解析", "static.html"],
    ["単体・結合テスト", "tests.html"],
    ["カバレッジ", "coverage.html"],
  ]) {
    await page
      .getByRole("link", { name: `${name}の詳細を見る →`, exact: true })
      .click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByRole("link", { name: "サマリー", exact: true }).click();
  }
});

test("階層一覧からケースへ移動しGWTの画像だけを読める", async ({ page }) => {
  await page.goto("/e2e.html");
  const navigation = page.getByRole("navigation", { name: "テストケース一覧" });
  await expect(navigation.getByText("PC", { exact: true })).toBeVisible();
  await expect(
    navigation.getByText("スマートフォン", { exact: true }),
  ).toBeVisible();
  await expect(navigation.locator("ul ul ul a")).toHaveCount(12);
  await expect(page.locator("article.case")).toHaveCount(12);
  await expect(page.locator("details")).toHaveCount(0);
  await expect(page.locator(".step img")).toHaveCount(38);
  const target = navigation.getByRole("link").last();
  const fragment = await target.getAttribute("href");
  await target.click();
  await expect(page).toHaveURL(new RegExp(`${fragment}$`));
  await expect(page.locator(fragment!)).toBeInViewport();
  for (const caption of await page
    .locator(".step img")
    .evaluateAll((images) =>
      images.map((image) => image.getAttribute("alt")),
    )) {
    expect(caption).toMatch(/^(Given|When|Then):/);
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("画像を拡大してEscと閉じる操作で元に戻れる", async ({ page }) => {
  await page.goto("/e2e.html");
  const shot = page.locator("[data-screenshot]").first();
  await shot.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const image = dialog.locator("img");
  await expect(image).toHaveAttribute("src", /screenshots\/001.png$/);
  await expect(
    dialog.getByRole("link", { name: "原寸画像を開く" }),
  ).toHaveAttribute("href", /screenshots\/001.png$/);
  await expect(image).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(shot).toBeFocused();
  await shot.press("Enter");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "閉じる" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(shot).toBeFocused();
});

test("C0とC1の実測値と日本語の個別テスト結果を確認できる", async ({ page }) => {
  await page.goto("/coverage.html");
  await expect(
    page.getByRole("cell", { name: "TypeScript C0（命令）", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "TypeScript C1（分岐）", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("row").filter({ hasText: "TypeScript C0" }),
  ).toContainText(/\d+\.\d+% \(\d+\/\d+\)/);
  await page.goto("/tests.html");
  await expect(
    page.getByRole("heading", { name: "日本語のテスト一覧" }),
  ).toBeVisible();
  await expect(page.locator(".unit-suite")).not.toHaveCount(0);
  await expect(
    page.getByRole("cell", {
      name: "ローカルログインで選択した本人の一覧を表示する",
      exact: true,
    }),
  ).toBeVisible();
});

test("設計書はHTMLで読めて内部のCRUD図とAPIシーケンスが描画される", async ({
  page,
}) => {
  const base = process.env.DOCS_BASE || "/design";
  await page.goto(base + "/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "自動生成ドキュメント",
  );
  for (const [path, title] of [
    ["database/crud/", "CRUD"],
    ["database/er/", "ER"],
    ["apis/update_note/sequence/", "シーケンス"],
    ["infrastructure/topology/", "CDK"],
  ]) {
    await page.goto(base + "/" + path);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(title);
    await expect(page.locator(".mermaid svg").first()).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Syntax error");
  }
  await page.goto(base + "/infrastructure/");
  await expect(
    page.getByRole("link", { name: "設定・参照関係", exact: true }).first(),
  ).toBeVisible();
  await page.goto(base + "/apis/list_notes/detail-design/");
  await expect(
    page.getByRole("heading", { name: "4. 正常系レスポンス", exact: true }),
  ).toBeVisible();
  await expect(page.locator("main")).toContainText("DB: notes.title");
});

test("日本語の全文検索から設計書へ移動できる", async ({ page }) => {
  const base = process.env.DOCS_BASE || "/design";
  await page.goto(base + "/");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  const input = page.getByRole("textbox", { name: "検索", exact: true });
  await expect(input).toBeVisible();
  await input.fill("正常系リソース変更");
  const hit = page.locator(".pagefind-ui__result-link").first();
  await expect(hit).toBeVisible({ timeout: 15000 });
  await hit.click();
  await expect(page).toHaveURL(new RegExp("/apis/.+/detail-design/"));
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "詳細設計",
  );
});

test("全APIのシーケンス図を構文エラーなく描画する", async ({ page }) => {
  test.setTimeout(90000);
  const base = process.env.DOCS_BASE || "/design";
  await page.goto(base + "/");
  const urls = await page
    .locator('main a[href$="/sequence/"]')
    .evaluateAll((links) =>
      links.map((link) => (link as HTMLAnchorElement).href),
    );
  expect(urls).toHaveLength(11);
  for (const url of urls) {
    await page.goto(url);
    await expect(page.locator(".mermaid svg").first()).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Syntax error");
  }
});
