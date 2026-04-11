"use strict";
/**
 * 05-checkout.spec.js — Flujo de checkout (Neki / transferencia)
 * ==============================================================
 * Valida que el formulario de checkout y la vista previa de totales
 * no introduzcan style= inválidos.
 *
 * Nota: no se completa la compra real (sin datos bancarios en tests).
 */

const { test, expect } = require("@playwright/test");
const { attachCspListener, runFullAudit, goto } = require("../helpers/csp");
const { skipIfNoCredentials, loginApi } = require("../helpers/auth");

// Helper: pone un producto en el carrito y navega al checkout Neki
async function goToCheckout(page) {
  await goto(page, "/");
  await page.waitForSelector(".product-card", { timeout: 15_000 });

  // Agregar primer producto al carrito
  await page.locator("[data-action='addToCart']").first().click();
  await page.waitForTimeout(500);

  // Abrir carrito y checkout
  await page.locator(
    "#cart-btn, .cart-btn, [data-action='openCart']"
  ).first().click();
  await page.waitForSelector("#cart-panel, .cart-panel", { state: "visible" }).catch(() => {});
  await page.waitForTimeout(300);

  const checkoutBtn = page.locator(
    "#cart-btn-checkout, [data-action='goToCheckout'], .checkout-btn"
  ).first();
  if (await checkoutBtn.isVisible().catch(() => false)) {
    await checkoutBtn.click();
    await page.waitForTimeout(500);
  }
}

test.describe("Checkout Neki — CSP + UI", () => {

  test("Formulario de checkout no tiene style= inválidos", async ({ page, browserName }, testInfo) => {
    skipIfNoCredentials(testInfo, "Checkout requiere sesión para ver totales completos");

    const cspViolations = attachCspListener(page);

    await loginApi(page);
    await goToCheckout(page);

    // Esperar a que el formulario de checkout esté visible
    await page.waitForSelector(
      "#checkout-form, .checkout-form, [id*='checkout']",
      { timeout: 8_000 }
    ).catch(() => {});
    await page.waitForTimeout(500);

    await runFullAudit(page, cspViolations, "formulario checkout Neki");
  });

  test("Vista previa de totales no usa style= (usa .summary-total-row--preview)", async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo);

    const cspViolations = attachCspListener(page);
    await loginApi(page);
    await goToCheckout(page);
    await page.waitForTimeout(600);

    // Verificar que las filas de totales no tienen style= de presentación
    const totalRows = await page.$$(".summary-total-row, .cart-total-row, .up-total-row");
    for (const row of totalRows) {
      const styleAttr = await row.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      expect(
        invalidRules.length,
        `Fila de totales tiene style= inválido: "${styleAttr}"`
      ).toBe(0);
    }

    await runFullAudit(page, cspViolations, "vista previa de totales");
  });

  test("Checkout sin sesión muestra formulario de auth sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await goToCheckout(page);
    await page.waitForTimeout(800);

    // Sin sesión, puede aparecer el modal de auth o redirect
    await runFullAudit(page, cspViolations, "checkout sin autenticación");
  });

  test("Etiqueta del demo Neki usa clase CSS (no style=font-family)", async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo);

    await loginApi(page);
    await goToCheckout(page);

    const demoLabel = await page.$("#checkout-demo-label");
    if (demoLabel) {
      const styleAttr = await demoLabel.getAttribute("style") || "";
      expect(styleAttr, "#checkout-demo-label no debe tener style=").toBe("");
    }
  });

  test("Botón de envío usa .checkout-submit-btn (no style=width)", async ({ page }, testInfo) => {
    skipIfNoCredentials(testInfo);

    await loginApi(page);
    await goToCheckout(page);

    const submitBtn = await page.$("#checkout-submit-btn");
    if (submitBtn) {
      const styleAttr = await submitBtn.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });
      expect(
        invalidRules.length,
        `#checkout-submit-btn tiene style= de presentación: "${styleAttr}"`
      ).toBe(0);
    }
  });

});
