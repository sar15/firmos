import { expect, test } from "@playwright/test";

const privateRoutes = [
  "/", "/agent", "/audit", "/clients", "/connectors", "/documents",
  "/search", "/settings/profile", "/settings/security", "/settings/team",
  "/settings/billing", "/clients/test-client/purchase-register",
  "/clients/test-client/reconcile", "/documents/test-document", "/run/test-run",
];

test("anonymous users cannot render any private page", async ({ page }) => {
  for (const route of privateRoutes) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Sign in to firmOS" })).toBeVisible();
  }
});

test("public authentication controls have accessible names", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show password" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});
