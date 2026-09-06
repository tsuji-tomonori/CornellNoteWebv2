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
  await expect(navigation.locator("ul ul ul a")).toHaveCount(10);
  await expect(page.locator("article.case")).toHaveCount(10);
  await expect(page.locator("details")).toHaveCount(0);
  await expect(page.locator(".step img")).toHaveCount(32);
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
