import { test, expect, type Page, type TestInfo } from "@playwright/test";
async function step(
  page: Page,
  info: TestInfo,
  kind: string,
  text: string,
  work: () => Promise<void>,
) {
  await test.step(`${kind}: ${text}`, async () => {
    try {
      await work();
    } finally {
      if (!page.isClosed()) {
        const filename = info.outputPath(`${kind}-${Date.now()}.png`);
        await page.screenshot({ path: filename, fullPage: true });
        await info.attach(`${kind}: ${text}`, {
          path: filename,
          contentType: "image/png",
        });
      }
    }
  });
}
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("パスワード").fill("cornell-local");
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "新しいノート" }),
  ).toBeVisible();
}
async function field(page: Page, label: string, tab: string, value: string) {
  const button = page.getByRole("tab", { name: tab, exact: true });
  if (await button.isVisible()) await button.click();
  await page.getByLabel(label, { exact: true }).fill(value);
}
async function create(page: Page, title: string) {
  await page.getByRole("button", { name: "新しいノート" }).click();
  await page.getByLabel("ノートのタイトル").fill(title);
  await page.getByLabel("コレクション", { exact: true }).fill("情報工学");
}
async function save(page: Page) {
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("保存しました");
}

test("ログインして自分の一覧を見る", async ({ page }, info) => {
  await step(page, info, "Given", "ログイン画面を開いている", async () => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "おかえりなさい。" }),
    ).toBeVisible();
  });
  await step(
    page,
    info,
    "When",
    "Aliceのアカウントでログインする",
    async () => {
      await page.getByLabel("パスワード").fill("cornell-local");
      await page.getByRole("button", { name: "ログイン", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "新しいノート" }),
      ).toBeVisible();
    },
  );
  await step(
    page,
    info,
    "Then",
    "自分のノート一覧と作成ボタンが表示される",
    async () => {
      await expect(
        page.getByRole("heading", { name: "マイノート." }),
      ).toBeVisible();
    },
  );
});
test("講義ノートを作成し三つの欄とタスクを保存する", async ({ page }, info) => {
  const title = `分散システムの基礎 ${info.project.name}`;
  await step(
    page,
    info,
    "Given",
    "ログインしてノート一覧を表示している",
    async () => {
      await login(page);
    },
  );
  await step(
    page,
    info,
    "When",
    "講義の問い・記録・要約と復習タスクを入力する",
    async () => {
      await create(page, title);
      await field(page, "問い・キーワード", "問い", "なぜ整合性が必要なのか？");
      await field(
        page,
        "ノート本文",
        "ノート",
        "複数の利用者が同時に更新する。\nトランザクションで一貫性を保つ。",
      );
      await field(
        page,
        "まとめ",
        "まとめ",
        "更新競合を検知し、学びの記録を守る。",
      );
      await page.getByLabel("新しいアクション").fill("教科書の第3章を復習する");
      await page.getByRole("button", { name: "アクションを追加" }).click();
      await page.getByLabel("教科書の第3章を復習するの期日").fill("2026-09-15");
      await save(page);
    },
  );
  await step(
    page,
    info,
    "Then",
    "一覧から開き直すと内容と期限付きタスクが保持される",
    async () => {
      await page
        .getByRole("button", { name: "ノート一覧", exact: true })
        .click();
      await page
        .getByRole("button")
        .filter({
          has: page.getByRole("heading", { name: title, exact: true }),
        })
        .click();
      const tab = page.getByRole("tab", { name: "まとめ", exact: true });
      if (await tab.isVisible()) await tab.click();
      await expect(page.getByLabel("まとめ", { exact: true })).toHaveValue(
        "更新競合を検知し、学びの記録を守る。",
      );
      await expect(
        page.getByLabel("教科書の第3章を復習するの期日"),
      ).toHaveValue("2026-09-15");
      await page.getByLabel("教科書の第3章を復習するを完了").check();
      await save(page);
    },
  );
});
test("科目別一覧を検索する", async ({ page }, info) => {
  const title = `検索対象 ${info.project.name}`;
  await step(
    page,
    info,
    "Given",
    "情報工学のノートを作成している",
    async () => {
      await login(page);
      await create(page, title);
      await save(page);
      await page
        .getByRole("button", { name: "ノート一覧", exact: true })
        .click();
    },
  );
  await step(page, info, "When", "タイトルの語句で検索する", async () => {
    await page.getByLabel("ノートを検索").fill(title);
  });
  await step(
    page,
    info,
    "Then",
    "一致するノートが科目ごとに表示される",
    async () => {
      await expect(
        page.getByRole("heading", { name: title, exact: true }),
      ).toBeVisible();
      await expect(page.locator(".note-card")).toHaveCount(1);
    },
  );
});
test("共有リンクで閲覧し共有解除後はアクセスできない", async ({
  page,
  browser,
}, info) => {
  let url = "";
  await step(
    page,
    info,
    "Given",
    "保存したノートの共有画面を開いている",
    async () => {
      await login(page);
      await create(page, `共有する講義 ${info.project.name}`);
      await field(
        page,
        "ノート本文",
        "ノート",
        "この記録を共有して一緒に振り返る。",
      );
      await save(page);
      await page.getByRole("button", { name: "共有", exact: true }).click();
    },
  );
  await step(page, info, "When", "閲覧リンクを発行する", async () => {
    await page.getByRole("button", { name: "閲覧リンクを発行" }).click();
    await expect(page.getByLabel("共有リンク", { exact: true })).toBeVisible();
    url = await page.getByLabel("共有リンク", { exact: true }).inputValue();
  });
  const context = await browser.newContext({
    viewport: info.project.use.viewport,
    locale: "ja-JP",
  });
  const guest = await context.newPage();
  await step(
    guest,
    info,
    "Then",
    "ログインしていない人も編集せずに閲覧できる",
    async () => {
      await guest.goto(url);
      await expect(guest.getByLabel("ノートのタイトル")).toHaveValue(
        `共有する講義 ${info.project.name}`,
      );
      await expect(guest.getByLabel("ノートのタイトル")).toHaveAttribute(
        "readonly",
        "",
      );
      await expect(
        guest.getByRole("button", { name: "保存", exact: true }),
      ).toHaveCount(0);
    },
  );
  await page.getByRole("button", { name: "共有を解除", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("共有を解除しました");
  await step(
    guest,
    info,
    "Then",
    "所有者が共有を解除すると古いリンクは無効になる",
    async () => {
      await guest.reload();
      await expect(guest.getByRole("alert")).toContainText(
        "無効または期限切れ",
      );
    },
  );
  await context.close();
});
test("誤ったパスワードでログインできない", async ({ page }, info) => {
  await step(page, info, "Given", "ログイン画面を表示している", async () => {
    await page.goto("/");
  });
  await step(page, info, "When", "誤ったパスワードを送信する", async () => {
    await page.getByLabel("パスワード").fill("wrong-password");
    await page.getByRole("button", { name: "ログイン", exact: true }).click();
  });
  await step(
    page,
    info,
    "Then",
    "エラーを表示しノートは開かれない",
    async () => {
      await expect(page.getByRole("alert")).toContainText("違います");
      await expect(
        page.getByRole("button", { name: "新しいノート" }),
      ).toHaveCount(0);
    },
  );
});

test("全ノートのタスクを状態別に探して編集結果を確認する", async ({
  page,
}, info) => {
  const title = `横断タスク ${info.project.name}`;
  await step(
    page,
    info,
    "Given",
    "未完了と完了のタスクを持つノートが保存されている",
    async () => {
      await login(page);
      await create(page, title);
      await page.getByLabel("新しいアクション").fill("横断一覧で復習する");
      await page.getByRole("button", { name: "アクションを追加" }).click();
      await page.getByLabel("新しいアクション").fill("資料を読み終えた");
      await page.getByRole("button", { name: "アクションを追加" }).click();
      await page.getByLabel("資料を読み終えたを完了").check();
      await save(page);
    },
  );
  await step(
    page,
    info,
    "When",
    "全タスクを開いてノート名で検索し完了状態を切り替える",
    async () => {
      await page.getByRole("button", { name: "すべてのタスク" }).click();
      await page.getByRole("textbox", { name: "タスクを検索" }).fill(title);
      await expect(
        page.getByText("横断一覧で復習する", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("資料を読み終えた", { exact: true }),
      ).not.toBeVisible();
      await page.getByRole("button", { name: "完了", exact: true }).click();
      await expect(
        page.getByText("資料を読み終えた", { exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: "すべて", exact: true }).click();
      await expect(
        page.getByText("横断一覧で復習する", { exact: true }),
      ).toBeVisible();
    },
  );
  await step(
    page,
    info,
    "Then",
    "所属ノートで復習を完了すると一覧の完了側に反映される",
    async () => {
      await page
        .getByRole("button", { name: `ノートを開く: ${title}`, exact: true })
        .first()
        .click();
      await page.getByLabel("横断一覧で復習するを完了").check();
      await save(page);
      await page.getByRole("button", { name: "すべてのタスク" }).click();
      await page.getByRole("textbox", { name: "タスクを検索" }).fill(title);
      await page.getByRole("button", { name: "完了", exact: true }).click();
      await expect(
        page.getByText("横断一覧で復習する", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("資料を読み終えた", { exact: true }),
      ).toBeVisible();
    },
  );
});
