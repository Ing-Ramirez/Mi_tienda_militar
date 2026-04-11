"use strict";
/**
 * 02-catalog.spec.js — Catálogo de productos
 * ============================================
 * Valida el flujo completo del catálogo:
 *   - Carga inicial y renderizado de tarjetas
 *   - Búsqueda y filtros
 *   - Sin regresiones CSP durante interacciones
 */

const { test, expect } = require("@playwright/test");
const { attachCspListener, runFullAudit, goto } = require("../helpers/csp");

test.describe("Catálogo de productos — CSP + UI", () => {

  test.beforeEach(async ({ page }) => {
    // Cada test empieza desde el catálogo
    await goto(page, "/");
    await page.waitForSelector(".header", { timeout: 15_000 });
  });

  // ── Carga inicial ─────────────────────────────────────────────────────────

  test("Carga la página sin errores CSP", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1_000);

    await runFullAudit(page, cspViolations, "home / catálogo");
  });

  test("Grid de productos renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    // Esperar a que aparezcan tarjetas (o mensaje de catálogo vacío)
    await Promise.race([
      page.waitForSelector(".product-card",   { timeout: 12_000 }),
      page.waitForSelector(".catalog-empty",  { timeout: 12_000 }),
      page.waitForSelector(".products-empty", { timeout: 12_000 }),
    ]).catch(() => {});

    await runFullAudit(page, cspViolations, "grid de productos");
  });

  // ── Interacciones ─────────────────────────────────────────────────────────

  test("Buscar un producto no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    const searchInput = page.locator("input#search-input, input[placeholder*='Buscar'], .search-input").first();
    if (!(await searchInput.isVisible().catch(() => false))) {
      test.skip(true, "Campo de búsqueda no encontrado");
      return;
    }

    await searchInput.fill("uniforme");
    await searchInput.press("Enter");
    await page.waitForTimeout(1_500);

    await runFullAudit(page, cspViolations, "resultados de búsqueda");
  });

  test("Filtrar por categoría no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    const firstCatBtn = page.locator(".category-btn, [data-action='filterCategory']").first();
    if (!(await firstCatBtn.isVisible().catch(() => false))) {
      test.skip(true, "Botones de categoría no encontrados");
      return;
    }

    await firstCatBtn.click();
    await page.waitForTimeout(1_000);

    await runFullAudit(page, cspViolations, "filtro por categoría");
  });

  test("Ordenar productos no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    const sortSelect = page.locator("#sort-select, select[id*='sort'], .sort-select").first();
    if (!(await sortSelect.isVisible().catch(() => false))) {
      return; // Sort no visible — skip silencioso
    }

    await sortSelect.selectOption({ index: 1 });
    await page.waitForTimeout(800);

    await runFullAudit(page, cspViolations, "ordenamiento de productos");
  });

  test("Agregar a favoritos no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    const wishBtn = page.locator("[data-action='addToWish']").first();
    if (!(await wishBtn.isVisible().catch(() => false))) {
      return;
    }

    await wishBtn.click();
    await page.waitForTimeout(600);

    await runFullAudit(page, cspViolations, "toggle favoritos");
  });

  test("Animación de aparición de tarjetas usa CSS animation (no style=)", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    // Hacer scroll para activar animaciones de entrada
    await page.evaluate(() => window.scrollTo(0, 300));
    await page.waitForTimeout(800);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);

    await runFullAudit(page, cspViolations, "animaciones scroll");
  });

  // ── Landmark: tarjetas individuales ───────────────────────────────────────

  test("Las tarjetas de producto usan cursor:pointer via CSS (no style=)", async ({ page }) => {
    await page.waitForSelector(".product-card", { timeout: 12_000 }).catch(() => {});

    const cards = await page.$$(".product-card");
    if (cards.length === 0) return;

    // Verificar que .product-img-wrap y .product-name NO tienen style=cursor
    const violations = await page.evaluate(() => {
      const issues = [];
      document.querySelectorAll(".product-img-wrap, .product-name").forEach((el) => {
        const s = el.getAttribute("style") || "";
        if (s.includes("cursor")) {
          issues.push({ tag: el.tagName, style: s });
        }
      });
      return issues;
    });

    expect(violations.length, `Cursor via style= encontrado: ${JSON.stringify(violations)}`).toBe(0);
  });

});
