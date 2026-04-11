#!/usr/bin/env python3
"""
csp_audit.py — Analizador estático CSP para Franja Pixelada
============================================================
Detecta violaciones de inline styles en el SPA monolítico:

  ERRORES (rompen CSP style-src):
    E01 — style="" en HTML estático
    E02 — style="" en template literals JS (` `...style="${...}"...` `)
    E03 — style='...' (comillas simples)

  ADVERTENCIAS (calidad de código, no rompen CSP):
    W01 — el.style.<prop> = valor  (usar clases o CSS custom props)
    W02 — innerHTML con color/background hardcodeado

Uso:
    python scripts/audit/csp_audit.py [--file PATH] [--json] [--strict]

Salida:
    reports/csp-static-audit.json   (siempre)
    reports/csp-static-audit.md     (siempre)
    exit 0 si PASS, exit 1 si FAIL
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── Configuración ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SPA = ROOT / "backend" / "templates" / "store" / "index.html"
REPORTS_DIR = ROOT / "reports"

# Propiedades CSS que en JS deben ir via clases o CSS custom properties
JS_STYLE_PROPS_BANNED = [
    "display", "background", "color", "width", "height",
    "margin", "padding", "border", "opacity", "visibility",
    "overflow", "transform", "position", "top", "left", "right",
    "bottom", "font", "cursor", "flex", "grid", "gap",
    "text", "align", "justify", "line", "letter",
]

# ── Parsers ───────────────────────────────────────────────────────────────────

def find_style_block_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """
    Encuentra los rangos de líneas que pertenecen a bloques <style>...</style>.
    Retorna lista de (start_line, end_line) con índice base-1.
    """
    ranges = []
    start = None
    for i, line in enumerate(lines, 1):
        if re.search(r"<style[\s>]", line) and start is None:
            start = i
        if "</style>" in line and start is not None:
            ranges.append((start, i))
            start = None
    return ranges


def find_script_block_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Encuentra rangos de bloques <script>...</script>."""
    ranges = []
    start = None
    for i, line in enumerate(lines, 1):
        if re.search(r"<script[\s>]", line) and start is None:
            start = i
        if "</script>" in line and start is not None:
            ranges.append((start, i))
            start = None
    return ranges


def in_any_range(line_num: int, ranges: list[tuple[int, int]]) -> bool:
    return any(s <= line_num <= e for s, e in ranges)


def classify_line_context(line_num: int, style_ranges, script_ranges) -> str:
    if in_any_range(line_num, style_ranges):
        return "css"
    if in_any_range(line_num, script_ranges):
        return "js"
    return "html"


# ── Detectores ───────────────────────────────────────────────────────────────

def detect_inline_style_html(lines, style_ranges, script_ranges) -> list[dict]:
    """E01/E02/E03 — style= en HTML o template literals JS."""
    violations = []

    # Patrón: style="..." o style='...' como atributo HTML
    re_attr_double = re.compile(r'(?<!\bstyle=")style="([^"]*)"', re.IGNORECASE)
    re_attr_single = re.compile(r"style='([^']*)'", re.IGNORECASE)
    # style=" dentro de template literals JS: style="${...}" o style="valor"
    re_tpl_dyn   = re.compile(r'style="\$\{[^}]+\}"')
    re_tpl_static = re.compile(r'style="[^"]{1,200}"')

    for i, line in enumerate(lines, 1):
        ctx = classify_line_context(i, style_ranges, script_ranges)

        # Ignorar líneas que son sólo CSS (dentro de <style>)
        if ctx == "css":
            continue

        # Ignorar líneas que son comentarios CSS/JS
        stripped = line.strip()
        if stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("//"):
            continue

        matches_dbl = re_attr_double.findall(line)
        matches_sgl = re_attr_single.findall(line)
        has_tpl_dyn = bool(re_tpl_dyn.search(line))

        if matches_dbl or matches_sgl or has_tpl_dyn:
            code = "E02" if ctx == "js" else "E01"
            if matches_sgl:
                code = "E03"
            all_vals = matches_dbl + matches_sgl

            violations.append({
                "code": code,
                "line": i,
                "context": ctx,
                "snippet": line.strip()[:160],
                "values": all_vals,
                "is_dynamic": has_tpl_dyn,
                "severity": "error",
                "message": (
                    "style= dinámico en template literal JS"
                    if has_tpl_dyn else
                    f"style= inline en contexto {ctx}"
                ),
            })

    return violations


def detect_js_cssom_mutations(lines, script_ranges) -> list[dict]:
    """
    W01 — Detecta mutaciones CSSOM directas (no CSS custom properties).

    Permitido:    el.style.setProperty('--var', val)
    No permitido: el.style.display = 'none'
                  el.style.background = '#fff'
    """
    warnings = []

    # Patrón: .style.PROP = (sin setProperty, sin --)
    props_pattern = "|".join(JS_STYLE_PROPS_BANNED)
    re_cssom = re.compile(
        rf"\.style\.({props_pattern})\s*=(?!=)",
        re.IGNORECASE,
    )
    re_allowed = re.compile(r"\.style\.setProperty\s*\(")

    for i, line in enumerate(lines, 1):
        ctx = classify_line_context(i, [], script_ranges)
        if ctx not in ("js", "html"):
            continue

        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Saltar líneas que usan setProperty (permitido)
        if re_allowed.search(line):
            continue

        m = re_cssom.search(line)
        if m:
            warnings.append({
                "code": "W01",
                "line": i,
                "context": "js",
                "snippet": stripped[:160],
                "property": m.group(1),
                "severity": "warning",
                "message": (
                    f"el.style.{m.group(1)} = … detectado. "
                    "Usar clases CSS o CSS custom properties + setProperty()."
                ),
            })

    return warnings


def detect_hardcoded_colors_in_templates(lines, script_ranges) -> list[dict]:
    """
    W02 — background: o color: hardcodeado dentro de template literals JS.
    Estos no violan CSP pero son malas prácticas.
    """
    warnings = []
    re_hc = re.compile(r"(background|color)\s*:\s*(#[0-9a-fA-F]{3,6}|rgb\(|rgba\()", re.IGNORECASE)

    for i, line in enumerate(lines, 1):
        if not in_any_range(i, script_ranges):
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Solo en template literals (líneas con backtick o con `${`)
        if "`" not in line and "${" not in line:
            continue
        m = re_hc.search(line)
        if m:
            warnings.append({
                "code": "W02",
                "line": i,
                "context": "js_template",
                "snippet": stripped[:160],
                "severity": "warning",
                "message": (
                    f"Color hardcodeado '{m.group(0)}' en template literal. "
                    "Usar CSS custom property o clase."
                ),
            })

    return warnings


# ── Verificaciones de buenas prácticas ───────────────────────────────────────

def verify_swatch_pattern(lines, script_ranges) -> dict:
    """
    Verifica que los swatches usen el patrón correcto:
      data-swatch + CSS custom property (no style=background).
    """
    result = {
        "pattern": "data-swatch + CSS --swatch-bg",
        "old_pattern_found": False,
        "new_pattern_found": False,
        "setProperty_found": False,
        "lines": [],
    }

    for i, line in enumerate(lines, 1):
        # Patrón antiguo (violación)
        if "bgStyle" in line and ("style=" in line or "background:" in line):
            result["old_pattern_found"] = True
            result["lines"].append({"line": i, "type": "old", "snippet": line.strip()[:120]})
        # Patrón nuevo (correcto)
        if "data-swatch=" in line:
            result["new_pattern_found"] = True
            result["lines"].append({"line": i, "type": "new_data_attr", "snippet": line.strip()[:120]})
        if "setProperty" in line and "--swatch-bg" in line:
            result["setProperty_found"] = True
            result["lines"].append({"line": i, "type": "setProperty", "snippet": line.strip()[:120]})

    result["status"] = (
        "PASS"
        if result["new_pattern_found"]
        and result["setProperty_found"]
        and not result["old_pattern_found"]
        else "FAIL"
    )
    return result


# ── Reporte ───────────────────────────────────────────────────────────────────

def build_report(file_path: Path, violations: list, warnings: list, swatch_check: dict) -> dict:
    errors   = [v for v in violations if v["severity"] == "error"]
    warns    = [v for v in violations if v["severity"] == "warning"] + warnings

    e01 = [e for e in errors if e["code"] == "E01"]
    e02 = [e for e in errors if e["code"] == "E02"]
    e03 = [e for e in errors if e["code"] == "E03"]

    status = "PASS" if not errors and swatch_check["status"] == "PASS" else "FAIL"

    return {
        "meta": {
            "tool": "csp_audit.py",
            "version": "1.0.0",
            "file": str(file_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "status": status,
            "total_errors": len(errors),
            "total_warnings": len(warns),
            "E01_html_static": len(e01),
            "E02_js_templates": len(e02),
            "E03_single_quotes": len(e03),
            "W01_cssom_mutations": len([w for w in warnings if w["code"] == "W01"]),
            "W02_hardcoded_colors": len([w for w in warnings if w["code"] == "W02"]),
            "swatch_pattern": swatch_check["status"],
        },
        "errors": errors,
        "warnings": warns,
        "checks": {
            "swatch_pattern": swatch_check,
        },
    }


def write_json_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "csp-static-audit.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_markdown_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "csp-static-audit.md"

    s = report["summary"]
    icon = "✅" if s["status"] == "PASS" else "❌"
    lines = [
        f"# Auditoría CSP — Análisis Estático",
        f"",
        f"> Generado: {report['meta']['generated_at']}  ",
        f"> Archivo: `{report['meta']['file']}`",
        f"",
        f"## Estado global: {icon} {s['status']}",
        f"",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Errores totales (rompen CSP) | **{s['total_errors']}** |",
        f"| E01 — style= HTML estático | {s['E01_html_static']} |",
        f"| E02 — style= en template literals JS | {s['E02_js_templates']} |",
        f"| E03 — style= comillas simples | {s['E03_single_quotes']} |",
        f"| Advertencias totales | {s['total_warnings']} |",
        f"| W01 — CSSOM directo (el.style.prop=) | {s['W01_cssom_mutations']} |",
        f"| W02 — Colores hardcodeados en templates | {s['W02_hardcoded_colors']} |",
        f"| Patrón swatches | {s['swatch_pattern']} |",
        f"",
    ]

    if report["errors"]:
        lines += [f"## ❌ Errores CSP ({len(report['errors'])})", ""]
        for e in report["errors"]:
            lines += [
                f"### [{e['code']}] Línea {e['line']} — {e['message']}",
                f"```",
                e["snippet"],
                f"```",
                "",
            ]
    else:
        lines += ["## ✅ Sin errores CSP", ""]

    if report["warnings"]:
        lines += [f"## ⚠️ Advertencias ({len(report['warnings'])})", ""]
        for w in report["warnings"]:
            lines += [
                f"- **[{w['code']}] L{w['line']}**: {w['message']}",
                f"  `{w['snippet']}`",
                "",
            ]

    sc = report["checks"]["swatch_pattern"]
    lines += [
        f"## 🎨 Patrón swatches: {sc['status']}",
        f"",
        f"- Patrón antiguo (`style=background`) encontrado: {'⚠️ Sí' if sc['old_pattern_found'] else '✅ No'}",
        f"- `data-swatch=` encontrado: {'✅ Sí' if sc['new_pattern_found'] else '❌ No'}",
        f"- `style.setProperty(--swatch-bg)` encontrado: {'✅ Sí' if sc['setProperty_found'] else '❌ No'}",
        "",
        "---",
        "_Generado por `scripts/audit/csp_audit.py`_",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auditoría CSP estática — Franja Pixelada")
    parser.add_argument("--file",   default=str(DEFAULT_SPA), help="Ruta al SPA index.html")
    parser.add_argument("--json",   action="store_true",      help="Imprimir JSON en stdout")
    parser.add_argument("--strict", action="store_true",      help="Exit 1 si hay advertencias")
    parser.add_argument("--out",    default=str(REPORTS_DIR), help="Directorio de salida")
    args = parser.parse_args()

    spa_path = Path(args.file)
    if not spa_path.exists():
        print(f"❌ Archivo no encontrado: {spa_path}", file=sys.stderr)
        sys.exit(2)

    print(f"🔍 Analizando: {spa_path}")
    content   = spa_path.read_text(encoding="utf-8")
    lines     = content.splitlines()

    print(f"   Líneas totales: {len(lines)}")

    # Detectar bloques CSS y JS para contexto
    style_ranges  = find_style_block_ranges(lines)
    script_ranges = find_script_block_ranges(lines)

    css_lines = sum(e - s + 1 for s, e in style_ranges)
    js_lines  = sum(e - s + 1 for s, e in script_ranges)
    print(f"   CSS: {css_lines} líneas | JS: {js_lines} líneas | HTML: {len(lines) - css_lines - js_lines} líneas")

    # Ejecutar detectores
    violations   = detect_inline_style_html(lines, style_ranges, script_ranges)
    cssom_warns  = detect_js_cssom_mutations(lines, script_ranges)
    color_warns  = detect_hardcoded_colors_in_templates(lines, script_ranges)
    swatch_check = verify_swatch_pattern(lines, script_ranges)

    all_warnings = cssom_warns + color_warns
    report = build_report(spa_path, violations, all_warnings, swatch_check)

    # Escribir reportes
    out_dir  = Path(args.out)
    json_out = write_json_report(report, out_dir)
    md_out   = write_markdown_report(report, out_dir)

    # Salida en consola
    s = report["summary"]
    icon = "✅" if s["status"] == "PASS" else "❌"
    print(f"\n{icon} Estado: {s['status']}")
    print(f"   Errores CSP:      {s['total_errors']}")
    print(f"   Advertencias:     {s['total_warnings']}")
    print(f"   Patrón swatches:  {s['swatch_pattern']}")
    print(f"\n📄 JSON:     {json_out}")
    print(f"📄 Markdown: {md_out}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    # Fallar si hay errores (o advertencias en modo strict)
    has_errors = s["total_errors"] > 0 or s["swatch_pattern"] == "FAIL"
    has_warns  = s["total_warnings"] > 0
    if has_errors or (args.strict and has_warns):
        sys.exit(1)


if __name__ == "__main__":
    main()
