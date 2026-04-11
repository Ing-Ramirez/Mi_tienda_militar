"use strict";
/**
 * helpers/csp.js — Utilidades de auditoría CSP para Playwright
 * =============================================================
 *
 * Provee:
 *   attachCspListener(page)      → acumula violaciones de consola
 *   auditDomStyles(page)         → inspecciona [style] inválidos en el DOM
 *   auditSwatches(page)          → verifica patrón data-swatch
 *   assertNoCspViolations(vio)   → lanza error si hay violaciones
 *   assertNoDomStyleViolations() → lanza error si hay style= inválidos
 */

const { expect } = require("@playwright/test");

// ── CSP Console Listener ──────────────────────────────────────────────────────

/**
 * Adjunta un listener que acumula cualquier mensaje de consola relacionado
 * con CSP. Retorna un array que se va llenando en tiempo real.
 *
 * Uso:
 *   const cspViolations = attachCspListener(page);
 *   // ... navegar, interactuar ...
 *   assertNoCspViolations(cspViolations);
 *
 * @param {import('@playwright/test').Page} page
 * @returns {{ type: string, text: string, url: string }[]}
 */
function attachCspListener(page) {
  const violations = [];

  // Mensajes de consola: Chromium reporta violaciones CSP aquí
  page.on("console", (msg) => {
    const text = msg.text();
    if (
      text.includes("Content Security Policy") ||
      text.includes("Content-Security-Policy") ||
      text.includes("Refused to apply inline style") ||
      text.includes("Refused to execute inline script") ||
      (msg.type() === "error" && text.toLowerCase().includes("csp"))
    ) {
      violations.push({
        type:     msg.type(),
        text:     text.slice(0, 500),
        url:      msg.location()?.url || "",
        lineNum:  msg.location()?.lineNumber || 0,
      });
    }
  });

  // Errores de página (excepciones no capturadas)
  page.on("pageerror", (err) => {
    if (err.message.includes("Content Security Policy")) {
      violations.push({
        type:    "pageerror",
        text:    err.message.slice(0, 500),
        url:     "",
        lineNum: 0,
      });
    }
  });

  // CSP violation via SecurityPolicyViolationEvent (más preciso que consola)
  // Inyectado antes de la navegación para capturar violaciones tempranas
  page.addInitScript(() => {
    window.__cspViolations = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      window.__cspViolations.push({
        directive:   e.violatedDirective,
        blockedURI:  e.blockedURI,
        disposition: e.disposition,
        sample:      e.sample?.slice(0, 200) || "",
      });
    });
  });

  return violations;
}

/**
 * Recupera violaciones capturadas vía SecurityPolicyViolationEvent.
 * Llamar DESPUÉS de la navegación y acciones.
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<object[]>}
 */
async function getDomCspViolations(page) {
  return page.evaluate(() => window.__cspViolations || []);
}

// ── DOM Style Auditor ─────────────────────────────────────────────────────────

/**
 * Inspecciona todos los elementos [style] del DOM.
 * Reporta como violación cualquier propiedad que no sea CSS custom property (--var).
 *
 * Permitido: style="--swatch-bg: #ff0000"  (setProperty de CSS var)
 * Violación: style="display: none"
 *            style="background: #fff"
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<Array<{tagName, id, classes, style, invalidRules, outerHTML}>>}
 */
async function auditDomStyles(page) {
  return page.evaluate(() => {
    const violations = [];

    document.querySelectorAll("[style]").forEach((el) => {
      const styleAttr = el.getAttribute("style") || "";
      if (!styleAttr.trim()) return;

      const rules = styleAttr
        .split(";")
        .map((r) => r.trim())
        .filter(Boolean);

      const invalid = rules.filter((rule) => {
        const prop = rule.split(":")[0]?.trim() || "";
        // Solo CSS custom properties son permitidas via CSSOM
        return prop && !prop.startsWith("--");
      });

      if (invalid.length > 0) {
        violations.push({
          tagName:      el.tagName.toLowerCase(),
          id:           el.id || null,
          classes:      Array.from(el.classList).join(" ") || null,
          style:        styleAttr,
          invalidRules: invalid,
          // Truncar para no sobrecargar el reporte
          outerHTML:    el.outerHTML.slice(0, 250),
        });
      }
    });

    return violations;
  });
}

// ── Swatch Auditor ────────────────────────────────────────────────────────────

/**
 * Verifica que los color swatches del PDP usen el patrón correcto:
 *   - Atributo data-swatch="#hexcolor"
 *   - CSS custom property --swatch-bg aplicada via style.setProperty
 *   - Sin style="background:..." inline
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<{total, correct, violations}>}
 */
async function auditSwatches(page) {
  return page.evaluate(() => {
    const swatches = document.querySelectorAll(".pdp-color-swatch");
    const result = { total: swatches.length, correct: 0, violations: [] };

    swatches.forEach((el) => {
      const hasDataSwatch   = el.hasAttribute("data-swatch");
      const styleAttr       = el.getAttribute("style") || "";
      // Solo CSS custom properties son permitidas
      const hasInvalidStyle = styleAttr
        .split(";")
        .some((r) => {
          const prop = r.split(":")[0]?.trim() || "";
          return prop && !prop.startsWith("--");
        });

      if (hasDataSwatch && !hasInvalidStyle) {
        result.correct++;
      } else {
        result.violations.push({
          hasDataSwatch,
          hasInvalidStyle,
          styleAttr,
          outerHTML: el.outerHTML.slice(0, 200),
        });
      }
    });

    return result;
  });
}

// ── Assertions ────────────────────────────────────────────────────────────────

/**
 * Verifica que no haya violaciones CSP en el array acumulado.
 * Falla el test con mensaje descriptivo si las hay.
 *
 * @param {object[]} violations
 * @param {object[]} [domViolations]
 */
function assertNoCspViolations(violations, domViolations = []) {
  const all = [...violations, ...domViolations];
  if (all.length > 0) {
    const summary = all
      .slice(0, 5)
      .map((v) => `  [${v.type || v.directive}] ${v.text || v.blockedURI}`)
      .join("\n");
    throw new Error(
      `❌ ${all.length} violación(es) CSP detectada(s):\n${summary}\n` +
      (all.length > 5 ? `  ... y ${all.length - 5} más` : "")
    );
  }
}

/**
 * Verifica que no haya elementos con style= inválidos en el DOM.
 *
 * @param {object[]} violations
 * @param {string} [context] - Contexto para el mensaje de error
 */
function assertNoDomStyleViolations(violations, context = "") {
  if (violations.length > 0) {
    const summary = violations
      .slice(0, 5)
      .map((v) => {
        const id  = v.id ? `#${v.id}` : "";
        const cls = v.classes ? `.${v.classes.split(" ")[0]}` : "";
        return `  <${v.tagName}${id}${cls}> style="${v.style.slice(0, 80)}"`;
      })
      .join("\n");
    throw new Error(
      `❌ ${violations.length} elemento(s) con style= inválido(s)${context ? ` en ${context}` : ""}:\n` +
      `${summary}\n` +
      (violations.length > 5 ? `  ... y ${violations.length - 5} más` : "") +
      `\n\n💡 Usar clases CSS o CSS custom properties (--var) en lugar de style=`
    );
  }
}

// ── Helpers de navegación ─────────────────────────────────────────────────────

/**
 * Navega a una URL y espera que el DOM esté cargado.
 * Reintenta una vez si hay error de red.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} url
 */
async function goto(page, url) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20_000 });
  } catch (err) {
    // Un reintento para conexiones lentas / Docker startup
    console.warn(`⚠️ Primer intento falló (${err.message}), reintentando...`);
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20_000 });
  }
}

/**
 * Ejecuta una auditoría CSP completa en la página actual.
 * Útil al final de cada test como verificación final.
 *
 * @param {import('@playwright/test').Page} page
 * @param {object[]} cspViolations - Array del listener
 * @param {string} [context]
 */
async function runFullAudit(page, cspViolations, context = "") {
  const [domViolations, domCspViolations] = await Promise.all([
    auditDomStyles(page),
    getDomCspViolations(page),
  ]);

  assertNoCspViolations(cspViolations, domCspViolations);
  assertNoDomStyleViolations(domViolations, context);

  return { domViolations, domCspViolations, cspViolations };
}

module.exports = {
  attachCspListener,
  getDomCspViolations,
  auditDomStyles,
  auditSwatches,
  assertNoCspViolations,
  assertNoDomStyleViolations,
  runFullAudit,
  goto,
};
