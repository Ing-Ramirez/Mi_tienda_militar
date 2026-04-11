#!/usr/bin/env node
/**
 * run_audit.js — Orquestador CLI de auditoría CSP
 * ================================================
 * Ejecuta en secuencia:
 *   1. Análisis estático Python  → reports/csp-static-audit.json
 *   2. Tests E2E Playwright       → reports/playwright-results.json
 *   3. Fusión de resultados       → reports/csp-full-report.{json,md}
 *
 * Uso:
 *   node scripts/audit/run_audit.js [--skip-e2e] [--strict]
 *   npm run audit:csp              (desde tests/e2e/)
 *
 * Variables de entorno:
 *   BASE_URL      URL base de la app (default: http://localhost)
 *   SKIP_E2E=1    Omitir tests Playwright
 *   STRICT=1      Fallar si hay advertencias (además de errores)
 */

"use strict";

const { spawnSync } = require("child_process");
const fs   = require("fs");
const path = require("path");

// ── Rutas ─────────────────────────────────────────────────────────────────────

const ROOT       = path.resolve(__dirname, "../..");
const REPORTS    = path.join(ROOT, "reports");
const E2E_DIR    = path.join(ROOT, "tests", "e2e");
const STATIC_JSON = path.join(REPORTS, "csp-static-audit.json");
const PW_JSON    = path.join(REPORTS, "playwright-results.json");
const FULL_JSON  = path.join(REPORTS, "csp-full-report.json");
const FULL_MD    = path.join(REPORTS, "csp-full-report.md");

// ── Argumentos ────────────────────────────────────────────────────────────────

const args     = process.argv.slice(2);
const skipE2e  = args.includes("--skip-e2e") || process.env.SKIP_E2E === "1";
const strict   = args.includes("--strict")   || process.env.STRICT   === "1";

// ── Helpers ───────────────────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function log(icon, msg) {
  console.log(`${icon} ${msg}`);
}

function separator(char = "─", len = 60) {
  console.log(char.repeat(len));
}

/**
 * Ejecuta un comando y muestra la salida en tiempo real.
 * Retorna el código de salida.
 */
function run(cmd, args, opts = {}) {
  const isWindows = process.platform === "win32";
  const shell = isWindows;

  log("▶", `${cmd} ${args.join(" ")}`);
  const result = spawnSync(cmd, args, {
    stdio: "inherit",
    shell,
    cwd: opts.cwd || ROOT,
    env: { ...process.env, ...opts.env },
  });
  return result.status ?? 1;
}

function readJsonSafe(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

// ── Paso 1: Análisis estático ─────────────────────────────────────────────────

function runStaticAudit() {
  separator();
  log("🔍", "PASO 1 — Análisis estático (csp_audit.py)");
  separator();

  const python = process.platform === "win32" ? "python" : "python3";
  const script = path.join(__dirname, "csp_audit.py");

  const code = run(python, [script, "--out", REPORTS]);
  return { exitCode: code, reportPath: STATIC_JSON };
}

// ── Paso 2: Tests E2E Playwright ──────────────────────────────────────────────

function runE2eTests() {
  separator();
  log("🎭", "PASO 2 — Tests E2E Playwright");
  separator();

  if (!fs.existsSync(path.join(E2E_DIR, "node_modules"))) {
    log("📦", "Instalando dependencias Playwright...");
    run("npm", ["install"], { cwd: E2E_DIR });
  }

  const playwrightArgs = [
    "test",
    "--reporter=list,json",
    `--output=${REPORTS}/playwright-artifacts`,
  ];

  const code = run("npx", ["playwright", ...playwrightArgs], {
    cwd: E2E_DIR,
    env: {
      BASE_URL:        process.env.BASE_URL || "http://localhost",
      PW_JSON_OUTPUT:  PW_JSON,
    },
  });
  return { exitCode: code, reportPath: PW_JSON };
}

// ── Paso 3: Fusión y reporte final ────────────────────────────────────────────

function mergeReports(staticResult, e2eResult) {
  separator();
  log("📊", "PASO 3 — Generando reporte consolidado");
  separator();

  const staticData = readJsonSafe(staticResult.reportPath);
  const e2eData    = readJsonSafe(e2eResult?.reportPath);

  // Extraer métricas E2E
  let e2eSummary = null;
  if (e2eData) {
    const suites = e2eData.suites || [];
    let passed = 0, failed = 0, skipped = 0;
    const cspViolations = [];

    function walkSuites(suitesArr) {
      for (const suite of suitesArr) {
        for (const spec of suite.specs || []) {
          for (const test of spec.tests || []) {
            const status = test.results?.[0]?.status;
            if (status === "passed") passed++;
            else if (status === "failed") {
              failed++;
              // Recopilar mensajes de violación CSP de los resultados
              const errMsg = test.results?.[0]?.error?.message || "";
              if (errMsg.includes("CSP") || errMsg.includes("Content-Security-Policy")) {
                cspViolations.push({ test: spec.title, error: errMsg.slice(0, 200) });
              }
            }
            else if (status === "skipped") skipped++;
          }
        }
        walkSuites(suite.suites || []);
      }
    }
    walkSuites(suites);

    e2eSummary = { passed, failed, skipped, csp_runtime_violations: cspViolations };
  }

  const staticSummary = staticData?.summary || {};
  const overallStatus =
    staticResult.exitCode !== 0 ||
    (e2eResult && e2eResult.exitCode !== 0)
      ? "FAIL"
      : "PASS";

  const fullReport = {
    meta: {
      tool: "run_audit.js",
      version: "1.0.0",
      generated_at: new Date().toISOString(),
      base_url: process.env.BASE_URL || "http://localhost",
    },
    status: overallStatus,
    static_audit: {
      status: staticResult.exitCode === 0 ? "PASS" : "FAIL",
      ...staticSummary,
      errors: staticData?.errors || [],
      warnings: staticData?.warnings || [],
    },
    e2e_audit: e2eSummary
      ? { status: e2eResult.exitCode === 0 ? "PASS" : "FAIL", ...e2eSummary }
      : { status: "SKIPPED" },
    checks: staticData?.checks || {},
  };

  ensureDir(REPORTS);
  fs.writeFileSync(FULL_JSON, JSON.stringify(fullReport, null, 2), "utf8");
  writeMarkdownFull(fullReport);

  return fullReport;
}

function writeMarkdownFull(report) {
  const icon  = report.status === "PASS" ? "✅" : "❌";
  const sa    = report.static_audit;
  const e2e   = report.e2e_audit;
  const sw    = report.checks?.swatch_pattern || {};

  const lines = [
    `# Auditoría CSP Completa — Franja Pixelada`,
    ``,
    `> Generado: ${report.meta.generated_at}  `,
    `> App: \`${report.meta.base_url}\``,
    ``,
    `## ${icon} Estado Global: ${report.status}`,
    ``,
    `### Análisis Estático (código fuente)`,
    ``,
    `| Verificación | Resultado |`,
    `|---|---|`,
    `| Estado | ${sa.status === "PASS" ? "✅ PASS" : "❌ FAIL"} |`,
    `| Errores CSP totales | **${sa.total_errors ?? "—"}** |`,
    `| E01 — style= HTML estático | ${sa.E01_html_static ?? "—"} |`,
    `| E02 — style= en JS templates | ${sa.E02_js_templates ?? "—"} |`,
    `| E03 — style= comillas simples | ${sa.E03_single_quotes ?? "—"} |`,
    `| W01 — CSSOM directo | ${sa.W01_cssom_mutations ?? "—"} |`,
    `| W02 — Colores hardcodeados | ${sa.W02_hardcoded_colors ?? "—"} |`,
    `| Patrón swatches | ${sa.swatch_pattern ?? "—"} |`,
    ``,
    `### Tests E2E (runtime)`,
    ``,
    e2e.status === "SKIPPED"
      ? `> ⚠️ Tests E2E omitidos (\`--skip-e2e\` o \`SKIP_E2E=1\`)`
      : [
          `| Verificación | Resultado |`,
          `|---|---|`,
          `| Estado | ${e2e.status === "PASS" ? "✅ PASS" : "❌ FAIL"} |`,
          `| Tests pasados | ${e2e.passed} |`,
          `| Tests fallidos | ${e2e.failed} |`,
          `| Tests omitidos | ${e2e.skipped} |`,
          `| Violaciones CSP runtime | **${e2e.csp_runtime_violations?.length ?? 0}** |`,
        ].join("\n"),
    ``,
  ];

  // Errores estáticos detallados
  if ((sa.errors || []).length) {
    lines.push(`### ❌ Errores CSP (${sa.errors.length})`, ``);
    for (const e of sa.errors.slice(0, 30)) {
      lines.push(`- **[${e.code}] L${e.line}**: ${e.message}`);
      lines.push(`  \`${e.snippet?.slice(0, 120)}\``);
    }
    if (sa.errors.length > 30) {
      lines.push(`  _... y ${sa.errors.length - 30} más. Ver \`csp-static-audit.json\`_`);
    }
    lines.push(``);
  }

  // Violaciones CSP runtime
  const runtimeVio = e2e.csp_runtime_violations || [];
  if (runtimeVio.length) {
    lines.push(`### ❌ Violaciones CSP Runtime (${runtimeVio.length})`, ``);
    for (const v of runtimeVio) {
      lines.push(`- **${v.test}**: ${v.error}`);
    }
    lines.push(``);
  }

  lines.push(
    `### 🎨 Patrón swatches`,
    ``,
    `- Patrón antiguo (\`style=background\`): ${sw.old_pattern_found ? "⚠️ Sí" : "✅ No"}`,
    `- \`data-swatch=\` presente: ${sw.new_pattern_found ? "✅ Sí" : "❌ No"}`,
    `- \`style.setProperty(--swatch-bg)\`: ${sw.setProperty_found ? "✅ Sí" : "❌ No"}`,
    ``,
    `---`,
    `_Generado por \`scripts/audit/run_audit.js\`_`,
  );

  fs.writeFileSync(FULL_MD, lines.join("\n"), "utf8");
}

// ── Main ──────────────────────────────────────────────────────────────────────

function main() {
  console.log("\n╔══════════════════════════════════════════════════════════╗");
  console.log("║        AUDITORÍA CSP — FRANJA PIXELADA                   ║");
  console.log("╚══════════════════════════════════════════════════════════╝\n");

  ensureDir(REPORTS);

  // Paso 1: Análisis estático
  const staticResult = runStaticAudit();
  if (staticResult.exitCode !== 0) {
    log("⚠️", "El análisis estático encontró errores CSP.");
  }

  // Paso 2: Tests E2E (opcional)
  let e2eResult = null;
  if (!skipE2e) {
    if (!fs.existsSync(E2E_DIR)) {
      log("⚠️", `Directorio E2E no encontrado: ${E2E_DIR}. Omitiendo tests.`);
    } else {
      e2eResult = runE2eTests();
    }
  } else {
    log("⏭", "Tests E2E omitidos.");
  }

  // Paso 3: Reporte consolidado
  const fullReport = mergeReports(staticResult, e2eResult);

  // Resumen final
  separator("═");
  const icon = fullReport.status === "PASS" ? "✅" : "❌";
  log(icon, `RESULTADO FINAL: ${fullReport.status}`);
  separator("═");
  console.log(`\n📄 Reporte JSON: ${FULL_JSON}`);
  console.log(`📄 Reporte MD:   ${FULL_MD}\n`);

  const exitCode = fullReport.status === "FAIL" ? 1 : 0;
  process.exit(exitCode);
}

main();
