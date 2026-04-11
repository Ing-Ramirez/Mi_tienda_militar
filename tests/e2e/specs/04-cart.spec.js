"use strict";
/**
 * 04-cart.spec.js — Carrito de compras
 * =====================================
 * Valida que el panel de carrito y el resumen de orden no introduzcan
 * style= inválidos al renderizar, modificar cantidades o aplicar cupones.
 */

const { test, expect } = require("@playwright/test");
const { attachCspListener, runFullAudit, auditDomStyles, goto } = require("../helpers/csp");

// Helper: abre el primer producto y lo agrega al carrito
async function addFirstProductToCart(page) {
  await goto(page, "/");
  await page.waitForSelector(".product-card", { timeout: 15_000 });

  // Clic en "Agregar al carrito" de la primera tarjeta
  const addBtn = page.locator("[data-action='addToCart']").first();
  await addBtn.click();
  await page.waitForTimeout(600);
}

// Helper: abre el panel de carrito
async function openCart(page) {
  const cartBtn = page.locator(
    "#cart-btn, .cart-btn, [data-action='openCart'], [aria-label*='carrito']"
  ).first();
  await cartBtn.click();
  await page.waitForSelector("#cart-panel, .cart-panel", { state: "visible", timeout: 5_000 }).catch(() => {});
  await page.waitForTimeout(400);
}

test.describe("Carrito — CSP + UI", () => {

  test("Panel de carrito vacío no tiene style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");
    await page.waitForSelector(".header");

    await openCart(page);

    await runFullAudit(page, cspViolations, "carrito vacío");
  });

  test("Agregar producto al carrito no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await addFirstProductToCart(page);
    await openCart(page);

    await runFullAudit(page, cspViolations, "carrito con producto");
  });

  test("Panel de resumen (summary) renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await addFirstProductToCart(page);
    await openCart(page);

    // Abrir el resumen de productos (edición de cantidades)
    const viewEditBtn = page.locator("[data-action='openCartSummary'], .edit-products-btn").first();
    if (await viewEditBtn.isVisible().catch(() => false)) {
      await viewEditBtn.click();
      await page.waitForSelector("#summary-modal, .summary-modal", { state: "visible" }).catch(() => {});
      await page.waitForTimeout(500);
    }

    await runFullAudit(page, cspViolations, "modal de resumen de carrito");
  });

  test("Modificar cantidad en resumen no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await addFirstProductToCart(page);
    await openCart(page);

    const viewEditBtn = page.locator("[data-action='openCartSummary'], .edit-products-btn").first();
    if (await viewEditBtn.isVisible().catch(() => false)) {
      await viewEditBtn.click();
      await page.waitForTimeout(400);

      // Intentar aumentar cantidad
      const plusBtn = page.locator(".summary-qty-btn[data-delta='1']").first();
      if (await plusBtn.isEnabled().catch(() => false)) {
        await plusBtn.click();
        await page.waitForTimeout(300);
      }
    }

    await runFullAudit(page, cspViolations, "modificar cantidad en resumen");
  });

  test("Aplicar cupón inválido no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await addFirstProductToCart(page);
    await openCart(page);

    const couponInput = page.locator("#coupon-input, .coupon-input").first();
    if (await couponInput.isVisible().catch(() => false)) {
      await couponInput.fill("INVALIDO123");
      const applyBtn = page.locator("[data-action='applyCoupon'], .coupon-btn").first();
      await applyBtn.click();
      await page.waitForTimeout(800);
    }

    await runFullAudit(page, cspViolations, "error de cupón");
  });

  test("El elemento 'ver y editar' usa clase CSS (no style=margin)", async ({ page }) => {
    await addFirstProductToCart(page);
    await openCart(page);

    // El span "Ver y editar →" debe usar .cart-view-edit (no style=)
    const viewEditSpan = await page.$(".cart-view-edit");
    if (viewEditSpan) {
      const styleAttr = await viewEditSpan.getAttribute("style") || "";
      expect(styleAttr, ".cart-view-edit no debe tener style= de presentación").toBe("");
    }
  });

  test("Botones de qty deshabilitados usan :disabled CSS (no style=opacity)", async ({ page }) => {
    await addFirstProductToCart(page);
    await openCart(page);

    const viewEditBtn = page.locator("[data-action='openCartSummary']").first();
    if (await viewEditBtn.isVisible().catch(() => false)) {
      await viewEditBtn.click();
      await page.waitForTimeout(400);
    }

    // Buscar botones + qty en el resumen
    const plusBtns = await page.$$(".summary-qty-btn[data-delta='1']");
    for (const btn of plusBtns) {
      const styleAttr = await btn.getAttribute("style") || "";
      const invalidRules = styleAttr.split(";").filter((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      expect(
        invalidRules.length,
        `Botón qty+ tiene style= de presentación: "${styleAttr}"\n` +
        `Debe usar la regla CSS .summary-qty-btn:disabled { opacity: 0.35 }`
      ).toBe(0);
    }
  });

});
