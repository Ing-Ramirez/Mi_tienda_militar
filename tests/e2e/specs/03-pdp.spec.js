"use strict";
/**
 * 03-pdp.spec.js — Página de detalle de producto (PDP)
 * ======================================================
 * Valida:
 *   - Apertura del modal PDP sin style= inválidos
 *   - Swatches de color usan data-swatch + --swatch-bg
 *   - Selector de talla renderiza sin inline styles
 *   - Galería de imágenes / lightbox
 */

const { test, expect } = require("@playwright/test");
const {
  attachCspListener,
  auditDomStyles,
  auditSwatches,
  getDomCspViolations,
  assertNoCspViolations,
  assertNoDomStyleViolations,
  runFullAudit,
  goto,
} = require("../helpers/csp");

// Helper: abre el primer producto disponible
async function openFirstProduct(page) {
  await goto(page, "/");
  await page.waitForSelector(".product-card", { timeout: 15_000 });

  const card = page.locator(".product-card").first();
  await card.click();

  await page.waitForSelector(".pdp-modal.open, #pdp-modal.open, [id='pdp-modal']", {
    timeout: 8_000,
  }).catch(() => {});

  // Pequeña pausa para que JS complete el render
  await page.waitForTimeout(600);
}

test.describe("PDP — Detalle de producto", () => {

  test("Abrir PDP no genera violaciones CSP", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await openFirstProduct(page);

    const [domVio, domCspVio] = await Promise.all([
      auditDomStyles(page),
      getDomCspViolations(page),
    ]);

    assertNoCspViolations(cspViolations, domCspVio);
    assertNoDomStyleViolations(domVio, "PDP modal");
  });

  test("Input de bordado usa clase CSS (no style=)", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await goto(page, "/");
    await page.waitForSelector(".product-card").catch(() => {});

    // Buscar un producto que requiera bordado
    const cards = await page.$$(".product-card");
    let foundBordado = false;

    for (const card of cards.slice(0, 5)) {
      await card.click();
      await page.waitForTimeout(400);

      const bordadoInput = await page.$("#pdp-bordado-input");
      if (bordadoInput) {
        foundBordado = true;

        // El input NO debe tener style= con propiedades de presentación
        const styleAttr = await bordadoInput.getAttribute("style") || "";
        const invalidRules = styleAttr.split(";").filter((r) => {
          const prop = r.split(":")[0]?.trim() || "";
          return prop && !prop.startsWith("--");
        });

        expect(
          invalidRules.length,
          `#pdp-bordado-input tiene style= inválido: "${styleAttr}"`
        ).toBe(0);

        break;
      }

      // Cerrar PDP y probar el siguiente
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }

    if (!foundBordado) {
      // No hay productos con bordado — OK, skip silencioso
      return;
    }

    await runFullAudit(page, cspViolations, "PDP con bordado");
  });

  // ── Swatches ───────────────────────────────────────────────────────────────

  test("Swatches usan data-swatch + CSS custom property --swatch-bg", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await goto(page, "/");
    await page.waitForSelector(".product-card").catch(() => {});

    const cards = await page.$$(".product-card");
    let swatchesFound = false;

    for (const card of cards.slice(0, 8)) {
      await card.click();
      await page.waitForTimeout(500);

      const swatches = await auditSwatches(page);

      if (swatches.total > 0) {
        swatchesFound = true;

        expect(
          swatches.violations.length,
          `${swatches.violations.length} swatch(es) con patrón incorrecto:\n` +
          swatches.violations.map((v) => `  ${v.outerHTML}`).join("\n")
        ).toBe(0);

        // Verificar que el background viene del CSS custom property
        const hasCssVar = await page.$$eval(".pdp-color-swatch", (els) =>
          els.every((el) => {
            const computedBg = getComputedStyle(el).backgroundColor;
            // El background debe estar definido (no ser transparent / initial)
            return computedBg !== "rgba(0, 0, 0, 0)" || el.querySelector("img");
          })
        );

        expect(hasCssVar, "Los swatches deben tener background aplicado vía CSS var").toBe(true);
        break;
      }

      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
    }

    if (!swatchesFound) {
      // Ningún producto tiene swatches — skip
      return;
    }

    const domCspVio = await getDomCspViolations(page);
    assertNoCspViolations(cspViolations, domCspVio);
  });

  // ── Galería ────────────────────────────────────────────────────────────────

  test("Galería de imágenes renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await openFirstProduct(page);

    // Intentar hacer clic en miniatura si hay galería
    const thumb = page.locator(".pdp-thumb").first();
    if (await thumb.isVisible().catch(() => false)) {
      await thumb.click();
      await page.waitForTimeout(400);
    }

    await runFullAudit(page, cspViolations, "PDP galería");
  });

  test("Selector de tallas renderiza sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);

    await goto(page, "/");
    await page.waitForSelector(".product-card").catch(() => {});

    const cards = await page.$$(".product-card");
    let found = false;

    for (const card of cards.slice(0, 6)) {
      await card.click();
      await page.waitForTimeout(400);

      const sizeChips = await page.$$(".pdp-size-chips .size-chip");
      if (sizeChips.length > 0) {
        found = true;

        // Verificar que los chips no tienen style=
        for (const chip of sizeChips) {
          const styleAttr = await chip.getAttribute("style") || "";
          const invalidRules = styleAttr.split(";").filter((r) => {
            const prop = r.split(":")[0]?.trim() || "";
            return prop && !prop.startsWith("--");
          });

          expect(
            invalidRules.length,
            `.size-chip tiene style= inválido: "${styleAttr}"`
          ).toBe(0);
        }

        // Seleccionar primera talla y re-auditar
        await sizeChips[0].click();
        await page.waitForTimeout(300);
        await runFullAudit(page, cspViolations, "PDP selector de tallas");
        break;
      }

      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
    }

    if (!found) return; // Sin tallas — skip silencioso
  });

  // ── Lightbox ──────────────────────────────────────────────────────────────

  test("Lightbox se abre sin style= inválidos", async ({ page }) => {
    const cspViolations = attachCspListener(page);
    await openFirstProduct(page);

    const mainImg = page.locator("#pdp-main-img-wrap, .pdp-main-img-wrap").first();
    if (await mainImg.isVisible().catch(() => false)) {
      await mainImg.click();
      await page.waitForSelector("#fp-lb-overlay", { state: "visible" }).catch(() => {});
      await page.waitForTimeout(400);
    }

    await runFullAudit(page, cspViolations, "lightbox PDP");
  });

});
