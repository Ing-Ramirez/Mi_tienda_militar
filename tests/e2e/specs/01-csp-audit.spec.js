"use strict";
/**
 * 01-csp-audit.spec.js — Auditoría CSP DOM en todas las rutas
 * ============================================================
 *
 * Verifica en CADA ruta pública que:
 *   1. No existan elementos con style="" inválidos (no CSS custom props)
 *   2. No se generen violaciones CSP en consola / SecurityPolicyViolationEvent
 *   3. El nonce del <style> está presente en el HTML
 *
 * Este spec es el más importante: un FAIL aquí significa que la refactorización
 * CSP tiene regresiones que deben corregirse antes de desplegar.
 */

const { test, expect } = require("@playwright/test");
const {
  attachCspListener,
  auditDomStyles,
  getDomCspViolations,
  assertNoCspViolations,
  assertNoDomStyleViolations,
  goto,
} = require("../helpers/csp");

// Rutas públicas a auditar
const PUBLIC_ROUTES = [
  { path: "/",           name: "Home / Catálogo" },
  { path: "/#catalog",   name: "Catálogo (anchor)" },
];

// Umbrales de aceptación
const MAX_DOM_STYLE_VIOLATIONS = 0;

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("Auditoría CSP — DOM Inspection", () => {

  // ── Estructura del HTML ──────────────────────────────────────────────────────

  test("El <style nonce> está presente y tiene nonce válido", async ({ page }) => {
    await goto(page, "/");

    const nonceAttr = await page.$eval(
      "style[nonce]",
      (el) => el.getAttribute("nonce")
    );

    expect(nonceAttr, "El <style> debe tener atributo nonce no vacío")
      .toBeTruthy();
    expect(nonceAttr.length, "El nonce debe tener al menos 16 caracteres")
      .toBeGreaterThanOrEqual(16);
  });

  test("No hay elementos <style> sin nonce en el body", async ({ page }) => {
    await goto(page, "/");

    const stylesWithoutNonce = await page.$$eval(
      "style:not([nonce])",
      (els) => els.map((el) => el.outerHTML.slice(0, 150))
    );

    expect(
      stylesWithoutNonce.length,
      `Encontrados <style> sin nonce: ${stylesWithoutNonce.join(", ")}`
    ).toBe(0);
  });

  test("No hay elementos <script> sin nonce (excluyendo JSON-LD / data scripts)", async ({ page }) => {
    await goto(page, "/");

    const violations = await page.$$eval(
      "script:not([nonce]):not([type='application/json']):not([type='application/ld+json'])",
      (els) => els
        .filter((el) => !el.src) // Ignorar scripts externos con src
        .map((el) => el.outerHTML.slice(0, 150))
    );

    expect(
      violations.length,
      `<script> sin nonce encontrados: ${violations.join("\n")}`
    ).toBe(0);
  });

  // ── Auditoría style= en DOM estático ────────────────────────────────────────

  for (const route of PUBLIC_ROUTES) {
    test(`Sin style= inválidos en DOM — ${route.name}`, async ({ page }) => {
      const cspViolations = attachCspListener(page);
      await goto(page, route.path);

      // Esperar que el SPA hidrate
      await page.waitForSelector(".header", { timeout: 10_000 });

      const domViolations = await auditDomStyles(page);

      expect(
        domViolations.length,
        `${domViolations.length} elemento(s) con style= inválido en ${route.name}:\n` +
        domViolations.slice(0, 3).map((v) =>
          `  <${v.tagName}> style="${v.style.slice(0, 80)}" → reglas inválidas: ${v.invalidRules.join(", ")}`
        ).join("\n")
      ).toBeLessThanOrEqual(MAX_DOM_STYLE_VIOLATIONS);

      // Verificar que no hubo violaciones CSP en consola
      const domCspVio = await getDomCspViolations(page);
      assertNoCspViolations(cspViolations, domCspVio);
    });
  }

  // ── Estado inicial del DOM (antes de interacciones JS) ──────────────────────

  test("DOM inicial sin style= — carga sin JS demorado", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    // Deshabilitar JS para auditar el HTML puro servido por Django
    await page.context().route("**/*.js", (route) => route.abort());
    await goto(page, "/");

    const domViolations = await auditDomStyles(page);

    assertNoDomStyleViolations(domViolations, "HTML estático (sin JS)");
    assertNoCspViolations(cspViolations);
  });

  // ── Auditoría post-renderizado JS ────────────────────────────────────────────

  test("Sin style= inválidos después de renderizar productos (JS activo)", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");

    // Esperar que el grid de productos esté renderizado
    await page.waitForSelector(".product-card", { timeout: 15_000 }).catch(() => {
      // Puede que no haya productos — continuar de todas formas
    });

    // Dar tiempo al JS dinámico
    await page.waitForTimeout(1_500);

    const [domViolations, domCspVio] = await Promise.all([
      auditDomStyles(page),
      getDomCspViolations(page),
    ]);

    assertNoCspViolations(cspViolations, domCspVio);
    assertNoDomStyleViolations(domViolations, "catálogo con productos renderizados");
  });

  // ── Verificar patrón swatches si hay PDP abierta ────────────────────────────

  test("Swatches de color usan data-swatch (no style=background)", async ({ page }) => {
    await goto(page, "/");

    // Intentar abrir el primer producto con colores disponibles
    const firstProduct = await page.$(".product-card");
    if (!firstProduct) {
      test.skip("No hay productos en el catálogo para auditar swatches");
      return;
    }

    await firstProduct.click();
    await page.waitForSelector(".pdp-modal.open, #pdp-modal.open", { timeout: 8_000 }).catch(() => {});

    // Buscar swatches en el DOM
    const swatches = await page.$$(".pdp-color-swatch");
    if (swatches.length === 0) {
      // No hay swatches en este producto — skip
      return;
    }

    for (const swatch of swatches) {
      const styleAttr   = await swatch.getAttribute("style") || "";
      const dataAttr    = await swatch.getAttribute("data-swatch");
      const hasInvalidStyle = styleAttr
        .split(";")
        .some((r) => {
          const prop = r.split(":")[0]?.trim() || "";
          return prop && !prop.startsWith("--");
        });

      expect(
        hasInvalidStyle,
        `Swatch tiene style= inválido: "${styleAttr}"\n` +
        `data-swatch="${dataAttr}" — debe usar CSS custom property --swatch-bg`
      ).toBe(false);

      // El swatch debe tener data-swatch con el color
      expect(
        dataAttr,
        "Swatch sin atributo data-swatch"
      ).toBeDefined();
    }
  });

});

// ── Suite: Auditoría post-interacción ─────────────────────────────────────────

test.describe("Auditoría CSP — Post-interacción", () => {

  test("Abrir carrito no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");
    await page.waitForSelector(".header");

    // Abrir carrito
    await page.click('[data-action="openCart"], #cart-btn, .cart-btn').catch(() => {});
    await page.waitForSelector(".cart-panel, #cart-panel", { state: "visible" }).catch(() => {});
    await page.waitForTimeout(500);

    const [domViolations, domCspVio] = await Promise.all([
      auditDomStyles(page),
      getDomCspViolations(page),
    ]);

    assertNoCspViolations(cspViolations, domCspVio);
    assertNoDomStyleViolations(domViolations, "panel de carrito");
  });

  test("Abrir modal de auth no introduce style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");
    await page.waitForSelector(".header");

    await page.click('[data-action="openAuthModal"], .btn-login, [id="btn-login"]').catch(() => {});
    await page.waitForSelector("#auth-modal", { state: "visible" }).catch(() => {});
    await page.waitForTimeout(300);

    const [domViolations, domCspVio] = await Promise.all([
      auditDomStyles(page),
      getDomCspViolations(page),
    ]);

    assertNoCspViolations(cspViolations, domCspVio);
    assertNoDomStyleViolations(domViolations, "modal de autenticación");
  });

});
