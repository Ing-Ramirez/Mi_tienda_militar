// @ts-check
"use strict";

const { defineConfig, devices } = require("@playwright/test");

const BASE_URL   = process.env.BASE_URL   || "http://localhost";
const PW_JSON    = process.env.PW_JSON_OUTPUT
  || require("path").join(__dirname, "../../reports/playwright-results.json");

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: "./specs",

  // Tiempo máximo por test; los flujos de carrito/checkout pueden ser lentos
  timeout: 45_000,
  expect: { timeout: 8_000 },

  // Tests en paralelo sólo si no comparten estado de sesión
  fullyParallel: false,
  workers: 1,

  // Fallar inmediatamente en CI si hay un test marcado con .only
  forbidOnly: !!process.env.CI,

  // 1 reintento en CI para evitar flakiness de red
  retries: process.env.CI ? 1 : 0,

  reporter: [
    ["list"],
    ["html",  { outputFolder: "reports/playwright", open: "never" }],
    ["json",  { outputFile: PW_JSON }],
  ],

  use: {
    baseURL: BASE_URL,

    // Adjuntar traza sólo al primer reintento fallido (ahorra espacio)
    trace: "on-first-retry",

    // Capturar pantalla y video sólo en fallo
    screenshot: "only-on-failure",
    video: "retain-on-failure",

    // Cabeceras comunes (simula navegador real)
    extraHTTPHeaders: {
      "Accept-Language": "es-CO,es;q=0.9",
    },

    // Viewport estándar desktop
    viewport: { width: 1280, height: 800 },
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Chromium reporta violaciones CSP en console — crítico para auditoría
        launchOptions: {
          args: ["--enable-logging", "--v=1"],
        },
      },
    },
    // Opcional: Firefox (comentado por defecto para acelerar CI)
    // {
    //   name: "firefox",
    //   use: { ...devices["Desktop Firefox"] },
    // },
  ],

  // Directorio de artefactos (screenshots, videos, trazas)
  outputDir: "reports/playwright-artifacts",
});
