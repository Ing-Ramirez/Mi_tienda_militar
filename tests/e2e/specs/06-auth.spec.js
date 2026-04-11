"use strict";
/**
 * 06-auth.spec.js — Flujo de autenticación (login / registro)
 * =============================================================
 * Valida que los formularios de auth no introduzcan style= inválidos
 * y que el modal de auth cumpla CSP en todos sus estados.
 */

const { test, expect } = require("@playwright/test");
const {
  attachCspListener,
  runFullAudit,
  auditDomStyles,
  goto,
} = require("../helpers/csp");
const { skipIfNoCredentials, loginApi, loginUi, logout } = require("../helpers/auth");

// Helper: abre el modal de autenticación
async function openAuthModal(page) {
  await goto(page, "/");
  await page.waitForSelector(".header", { timeout: 10_000 });

  const loginBtn = page.locator(
    "[data-action='openAuthModal'], #btn-login, .btn-login, [aria-label*='sesión']"
  ).first();
  await loginBtn.click();
  await page.waitForSelector("#auth-modal", { state: "visible", timeout: 5_000 }).catch(() => {});
  await page.waitForTimeout(300);
}

test.describe("Autenticación — CSP + UI", () => {

  test("Modal de login se abre sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openAuthModal(page);

    await runFullAudit(page, cspViolations, "modal de login");
  });

  test("Tab de registro no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openAuthModal(page);

    // Cambiar a tab de registro si existe
    const registerTab = page.locator(
      "[data-action='switchToRegister'], #tab-register, button:text('Registrarse'), button:text('Crear cuenta')"
    ).first();

    if (await registerTab.isVisible().catch(() => false)) {
      await registerTab.click();
      await page.waitForTimeout(400);
    }

    await runFullAudit(page, cspViolations, "formulario de registro");
  });

  test("Intentar login con credenciales inválidas no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openAuthModal(page);

    await page.fill('[id="auth-email"], input[type="email"]',     "test@invalido.com");
    await page.fill('[id="auth-password"], input[type="password"]', "claveIncorrecta123");
    await page.click('[data-action="submitLogin"], button[type="submit"]');
    await page.waitForTimeout(1_200);

    await runFullAudit(page, cspViolations, "error de login");
  });

  test("Login exitoso no introduce style= inválidos", async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo);

    const cspViolations = attachCspListener(page);

    await goto(page, "/");
    await loginApi(page);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(800);

    await runFullAudit(page, cspViolations, "post-login");
  });

  test("Formulario de login tiene campos sin style= de presentación", async ({ page }) => {
    await openAuthModal(page);

    // Verificar que los inputs no tienen style= heredados
    const inputs = await page.$$("#auth-email, #auth-password, #auth-modal input");
    for (const input of inputs) {
      const styleAttr = await input.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      expect(
        invalidRules.length,
        `Input de auth tiene style= inválido: "${styleAttr}"`
      ).toBe(0);
    }
  });

  test("Cerrar modal de auth no deja style= residuales en body", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openAuthModal(page);

    // Cerrar el modal
    await page.keyboard.press("Escape");
    await page.waitForSelector("#auth-modal", { state: "hidden" }).catch(() => {});
    await page.waitForTimeout(300);

    await runFullAudit(page, cspViolations, "post-cierre modal auth");
  });

  test("Panel de usuario post-login no tiene style= inválidos", async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo);

    const cspViolations = attachCspListener(page);

    await goto(page, "/");
    await loginApi(page);

    // Abrir panel de usuario
    const userBtn = page.locator(
      "[data-action='openUserPanel'], #btn-user-panel, .user-btn, [aria-label*='usuario']"
    ).first();
    if (await userBtn.isVisible().catch(() => false)) {
      await userBtn.click();
      await page.waitForSelector("#up-panel, .up-panel", { state: "visible" }).catch(() => {});
      await page.waitForTimeout(600);
    }

    await runFullAudit(page, cspViolations, "panel de usuario");
  });

});
