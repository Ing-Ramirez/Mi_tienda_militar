"use strict";
/**
 * 07-user-panel.spec.js — Panel de usuario
 * ==========================================
 * Valida que el panel de usuario (pedidos, devoluciones, perfil, seguridad)
 * no introduzca style= inválidos en sus renders dinámicos.
 *
 * Todos los tests en este archivo requieren autenticación.
 */

const { test, expect } = require("@playwright/test");
const {
  attachCspListener,
  runFullAudit,
  auditDomStyles,
  goto,
} = require("../helpers/csp");
const { skipIfNoCredentials, loginApi } = require("../helpers/auth");

// Helper: abre el panel de usuario
async function openUserPanel(page) {
  const userBtn = page.locator(
    "[data-action='openUserPanel'], #btn-user-panel, .user-btn"
  ).first();
  await userBtn.click();
  await page.waitForSelector("#up-panel, .up-panel", { state: "visible", timeout: 6_000 }).catch(() => {});
  await page.waitForTimeout(400);
}

// Helper: navega a una sección del panel
async function goToSection(page, section) {
  const navBtn = page.locator(
    `[data-action="upNav"][data-section="${section}"], .up-nav-item[data-section="${section}"]`
  ).first();
  if (await navBtn.isVisible().catch(() => false)) {
    await navBtn.click();
    await page.waitForTimeout(600);
  }
}

test.describe("Panel de usuario — CSP + UI", () => {

  test.beforeEach(async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo, "Panel de usuario requiere autenticación");
    await goto(page, "/");
    await loginApi(page);
    await page.waitForTimeout(400);
  });

  // ── Dashboard ─────────────────────────────────────────────────────────────

  test("Dashboard del panel no tiene style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);

    // Esperar a que cargue el dashboard
    await page.waitForSelector(".up-dash-section, #up-dash", { timeout: 8_000 }).catch(() => {});
    await page.waitForTimeout(600);

    await runFullAudit(page, cspViolations, "dashboard panel usuario");
  });

  // ── Pedidos ───────────────────────────────────────────────────────────────

  test("Lista de pedidos renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "orders");

    // Esperar a que carguen los pedidos
    await page.waitForSelector(
      ".up-orders-list, .up-empty, .up-loading",
      { timeout: 10_000 }
    ).catch(() => {});
    await page.waitForTimeout(500);

    await runFullAudit(page, cspViolations, "lista de pedidos");
  });

  test("Detalle de pedido renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "orders");

    await page.waitForSelector(".up-orders-list, .up-order-row", { timeout: 10_000 }).catch(() => {});

    // Abrir el primer pedido si existe
    const firstOrder = page.locator(".up-order-row").first();
    if (await firstOrder.isVisible().catch(() => false)) {
      await firstOrder.click();
      await page.waitForSelector("#up-order-detail-view", { state: "visible" }).catch(() => {});
      await page.waitForTimeout(700);
    }

    await runFullAudit(page, cspViolations, "detalle de pedido");
  });

  test("Número de pedido usa clase .up-order-detail-num (no style=font-family)", async ({ page }) => {
    await openUserPanel(page);
    await goToSection(page, "orders");

    await page.waitForSelector(".up-order-row", { timeout: 10_000 }).catch(() => {});

    const firstOrder = page.locator(".up-order-row").first();
    if (await firstOrder.isVisible().catch(() => false)) {
      await firstOrder.click();
      await page.waitForTimeout(500);

      const orderNum = await page.$(".up-order-detail-num");
      if (orderNum) {
        const styleAttr = await orderNum.getAttribute("style") || "";
        expect(styleAttr, ".up-order-detail-num no debe tener style=").toBe("");
      }
    }
  });

  // ── Devoluciones ──────────────────────────────────────────────────────────

  test("Sección de devoluciones renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "returns");

    await page.waitForSelector(
      ".up-orders-list, .up-empty, .up-loading, #up-returns-container",
      { timeout: 10_000 }
    ).catch(() => {});
    await page.waitForTimeout(700);

    await runFullAudit(page, cspViolations, "sección devoluciones");
  });

  test("Modal de devolución no tiene style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "returns");
    await page.waitForTimeout(600);

    // Intentar abrir el modal de política de devoluciones
    const policyBtn = page.locator(
      "[data-action='openReturnPolicyModal'], [data-action='upStartReturn']"
    ).first();
    if (await policyBtn.isVisible().catch(() => false)) {
      await policyBtn.click();
      await page.waitForSelector(
        "#fp-return-policy-overlay, .fp-rp-overlay",
        { state: "visible" }
      ).catch(() => {});
      await page.waitForTimeout(500);
    }

    await runFullAudit(page, cspViolations, "modal de política devoluciones");
  });

  // ── Perfil ────────────────────────────────────────────────────────────────

  test("Formulario de perfil no tiene style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "profile");
    await page.waitForTimeout(500);

    await runFullAudit(page, cspViolations, "formulario de perfil");
  });

  // ── Seguridad ─────────────────────────────────────────────────────────────

  test("Sección de seguridad (contraseña) no tiene style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openUserPanel(page);
    await goToSection(page, "security");
    await page.waitForTimeout(400);

    await runFullAudit(page, cspViolations, "sección seguridad / cambio contraseña");
  });

  test("Inputs de nueva contraseña usan clase .up-form-group--no-mb (no style=margin)", async ({ page }) => {
    await openUserPanel(page);
    await goToSection(page, "security");
    await page.waitForTimeout(400);

    const passGroups = await page.$$("#up-pass-new, #up-pass-confirm");
    for (const input of passGroups) {
      const parent = await input.evaluateHandle((el) => el.closest(".up-form-group"));
      if (!parent) continue;

      const styleAttr = await parent.evaluate((el) => el.getAttribute("style") || "");
      expect(
        styleAttr,
        "Los grupos de contraseña no deben tener margin via style="
      ).toBe("");
    }
  });

  test("Botón de cerrar sesión usa clase .btn-logout (no style=border-color)", async ({ page }) => {
    await openUserPanel(page);
    await goToSection(page, "security");
    await page.waitForTimeout(400);

    const logoutBtn = await page.$("[data-action='upLogout']");
    if (logoutBtn) {
      const styleAttr = await logoutBtn.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      expect(
        invalidRules.length,
        `Botón logout tiene style= inválido: "${styleAttr}"\n` +
        "Debe usar la clase .btn-logout que define border-color y color"
      ).toBe(0);
    }
  });

  // ── Cuadro de confirmación ────────────────────────────────────────────────

  test("Modal de confirmación no tiene style= en botones (usa .up-confirm-actions .btn)", async ({ page }) => {
    await openUserPanel(page);
    await page.waitForTimeout(300);

    // Verificar que los botones del modal ya definidos en HTML no tienen style=
    const confirmBtns = await page.$$("#up-confirm-cancel, #up-confirm-ok");
    for (const btn of confirmBtns) {
      const styleAttr = await btn.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      expect(
        invalidRules.length,
        `Botón de confirmación tiene style= de presentación: "${styleAttr}"`
      ).toBe(0);
    }
  });

});
