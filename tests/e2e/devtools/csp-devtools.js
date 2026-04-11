/**
 * csp-devtools.js — Script de auditoría CSP para DevTools
 * =========================================================
 *
 * Pegar y ejecutar directamente en la consola del navegador (F12).
 * No requiere instalación ni dependencias externas.
 *
 * Versión 1.0.0 — Franja Pixelada
 *
 * FUNCIONES:
 *   auditCSP()          — Auditoría completa (recomendada)
 *   auditStyles()       — Solo style= inválidos en DOM
 *   auditSwatches()     — Solo color swatches
 *   auditNonces()       — Verificar nonces <style> y <script>
 *   watchCSPViolations()— Monitor de violaciones en tiempo real
 */

(function () {
  "use strict";

  // ── Colores para la consola ────────────────────────────────────────────────
  const C = {
    error:   "color:#e74c3c;font-weight:bold",
    warn:    "color:#f39c12;font-weight:bold",
    ok:      "color:#27ae60;font-weight:bold",
    info:    "color:#3498db",
    bold:    "font-weight:bold",
    reset:   "",
    code:    "font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:2px 6px;border-radius:3px",
    header:  "font-size:14px;font-weight:bold;color:#8e44ad;border-bottom:2px solid #8e44ad",
  };

  function h(msg)    { console.log(`%c${msg}`, C.header); }
  function ok(msg)   { console.log(`%c✅ ${msg}`, C.ok); }
  function err(msg)  { console.log(`%c❌ ${msg}`, C.error); }
  function warn(msg) { console.log(`%c⚠️ ${msg}`, C.warn); }
  function info(msg) { console.log(`%cℹ️ ${msg}`, C.info); }
  function code(msg) { console.log(`%c${msg}`, C.code); }

  // ── 1. Auditoría de style= en DOM ─────────────────────────────────────────

  function auditStyles() {
    h("── Auditoría style= en DOM ─────────────────────────────");

    const allWithStyle = document.querySelectorAll("[style]");
    const violations   = [];
    const allowed      = [];

    allWithStyle.forEach((el) => {
      const styleAttr = el.getAttribute("style") || "";
      const rules     = styleAttr.split(";").map((r) => r.trim()).filter(Boolean);

      const invalid = rules.filter((rule) => {
        const prop = rule.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      const valid = rules.filter((rule) => {
        const prop = rule.split(":")[0]?.trim() || "";
        return prop && prop.startsWith("--");
      });

      if (invalid.length > 0) {
        violations.push({ el, styleAttr, invalidRules: invalid, validRules: valid });
      } else if (valid.length > 0) {
        allowed.push({ el, styleAttr });
      }
    });

    console.log(`   Total [style] en DOM: ${allWithStyle.length}`);
    console.log(`   CSS custom props (OK): ${allowed.length}`);
    console.log(`   Violaciones CSP:       ${violations.length}`);
    console.log("");

    if (violations.length === 0) {
      ok(`Sin violaciones CSP de inline styles. ✓`);
    } else {
      err(`${violations.length} violación(es) encontrada(s):`);
      violations.forEach(({ el, invalidRules, validRules }) => {
        const tag = el.tagName.toLowerCase();
        const id  = el.id ? `#${el.id}` : "";
        const cls = el.classList.length ? `.${Array.from(el.classList).slice(0, 2).join(".")}` : "";
        console.group(`%c<${tag}${id}${cls}>`, C.warn);
        console.log("  Reglas inválidas:", invalidRules.join(" | "));
        if (validRules.length) console.log("  Reglas OK (CSS vars):", validRules.join(" | "));
        console.log("  Elemento:", el);
        console.groupEnd();
      });
    }

    return { total: allWithStyle.length, violations: violations.length, allowed: allowed.length };
  }

  // ── 2. Auditoría de nonces ────────────────────────────────────────────────

  function auditNonces() {
    h("── Verificación de nonces ──────────────────────────────");

    const styleEls   = document.querySelectorAll("style");
    const scriptEls  = document.querySelectorAll("script:not([src]):not([type='application/json'])");
    let issues = 0;

    console.log(`   <style>  totales: ${styleEls.length}`);
    styleEls.forEach((el, i) => {
      const nonce = el.getAttribute("nonce");
      if (!nonce) {
        err(`<style>[${i}] sin nonce — contenido: "${el.textContent.slice(0, 60)}..."`);
        issues++;
      } else {
        ok(`<style>[${i}] nonce="${nonce.slice(0, 12)}..." ✓`);
      }
    });

    console.log(`   <script> inline totales: ${scriptEls.length}`);
    scriptEls.forEach((el, i) => {
      const nonce = el.getAttribute("nonce");
      if (!nonce) {
        err(`<script>[${i}] sin nonce — contenido: "${el.textContent.slice(0, 60)}..."`);
        issues++;
      } else {
        ok(`<script>[${i}] nonce="${nonce.slice(0, 12)}..." ✓`);
      }
    });

    if (issues === 0) ok("Todos los elementos inline tienen nonce válido. ✓");
    return { issues };
  }

  // ── 3. Auditoría de swatches ──────────────────────────────────────────────

  function auditSwatches() {
    h("── Auditoría color swatches ────────────────────────────");

    const swatches = document.querySelectorAll(".pdp-color-swatch");

    if (swatches.length === 0) {
      info("No hay swatches visibles en el DOM actual.");
      info("Abre un producto con colores disponibles y ejecuta de nuevo.");
      return { total: 0, violations: 0 };
    }

    let violations = 0;
    console.log(`   Swatches encontrados: ${swatches.length}`);

    swatches.forEach((el, i) => {
      const styleAttr   = el.getAttribute("style") || "";
      const dataAttr    = el.getAttribute("data-swatch");
      const cssVar      = el.style.getPropertyValue("--swatch-bg");
      const bgComputed  = getComputedStyle(el).backgroundColor;

      const hasInvalidStyle = styleAttr.split(";").some((r) => {
        const prop = r.split(":")[0]?.trim() || "";
        return prop && !prop.startsWith("--");
      });

      if (hasInvalidStyle) {
        violations++;
        err(`Swatch[${i}]: style= inválido: "${styleAttr}"`);
        warn(`  Debe usar: data-swatch="${dataAttr || "?"}" + style.setProperty("--swatch-bg", hex)`);
      } else {
        const status = dataAttr
          ? `data-swatch="${dataAttr}" | --swatch-bg="${cssVar}" | computed="${bgComputed}"`
          : "Sin data-swatch (imagen?)";
        ok(`Swatch[${i}]: ${status}`);
      }
    });

    if (violations === 0) ok(`Todos los swatches usan el patrón correcto. ✓`);
    return { total: swatches.length, violations };
  }

  // ── 4. Monitor de violaciones en tiempo real ─────────────────────────────

  function watchCSPViolations() {
    h("── Monitor CSP en tiempo real ──────────────────────────");
    info("Escuchando SecurityPolicyViolationEvent... (interactúa con la página)");
    info("Para detener: ejecuta window.__cspWatchOff()");

    let count = 0;

    const handler = (e) => {
      count++;
      console.group(`%c❌ CSP Violation #${count}`, C.error);
      console.log("Directiva violada:", e.violatedDirective);
      console.log("URI bloqueada:    ", e.blockedURI);
      console.log("Disposición:      ", e.disposition);
      console.log("Muestra:          ", e.sample || "(vacío)");
      console.log("Documento:        ", e.documentURI);
      console.log("Línea:            ", e.lineNumber);
      console.groupEnd();
    };

    document.addEventListener("securitypolicyviolation", handler);
    window.__cspWatchOff = () => {
      document.removeEventListener("securitypolicyviolation", handler);
      ok(`Monitor detenido. ${count} violación(es) detectada(s).`);
    };
  }

  // ── 5. Auditoría completa ─────────────────────────────────────────────────

  function auditCSP() {
    console.clear();

    console.log("%c╔══════════════════════════════════════════════════════╗", C.header);
    console.log("%c║   AUDITORÍA CSP — Franja Pixelada                   ║", C.header);
    console.log("%c╚══════════════════════════════════════════════════════╝", C.header);
    console.log("");
    info(`URL: ${window.location.href}`);
    info(`Timestamp: ${new Date().toISOString()}`);
    console.log("");

    const styleResults  = auditStyles();
    console.log("");

    const nonceResults  = auditNonces();
    console.log("");

    const swatchResults = auditSwatches();
    console.log("");

    // ── Resumen final ──────────────────────────────────────────────────────
    h("── RESUMEN ─────────────────────────────────────────────");

    const totalIssues = styleResults.violations + nonceResults.issues + swatchResults.violations;
    const status      = totalIssues === 0 ? "PASS ✅" : "FAIL ❌";

    console.log(`%cEstado global: ${status}`, totalIssues === 0 ? C.ok : C.error);
    console.log(`   style= inválidos:    ${styleResults.violations}`);
    console.log(`   Nonces faltantes:    ${nonceResults.issues}`);
    console.log(`   Swatches inválidos:  ${swatchResults.violations}`);
    console.log(`   style= con CSS var:  ${styleResults.allowed}  (OK)`);

    if (totalIssues > 0) {
      console.log("");
      warn("Para más detalle por sección:");
      code("  auditStyles()    → style= en DOM");
      code("  auditNonces()    → nonces de <style>/<script>");
      code("  auditSwatches()  → color swatches");
      code("  watchCSPViolations() → monitor en tiempo real");
    }

    return { status, styleViolations: styleResults.violations, nonceIssues: nonceResults.issues, swatchViolations: swatchResults.violations };
  }

  // ── Exponer funciones globalmente ─────────────────────────────────────────
  window.auditCSP          = auditCSP;
  window.auditStyles       = auditStyles;
  window.auditSwatches     = auditSwatches;
  window.auditNonces       = auditNonces;
  window.watchCSPViolations = watchCSPViolations;

  // ── Auto-ejecutar la auditoría completa ───────────────────────────────────
  auditCSP();

  console.log("");
  info("Funciones disponibles: auditCSP() | auditStyles() | auditSwatches() | auditNonces() | watchCSPViolations()");
})();
