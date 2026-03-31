---
name: auditor-inteligente-codigo
description: Audita código fuente de forma integral (seguridad, rendimiento, arquitectura y calidad) y produce hallazgos priorizados con correcciones accionables. Usar cuando el usuario pida auditoría técnica, revisión de vulnerabilidades, estandarización, hardening, refactor guiado por riesgos o cumplimiento de buenas prácticas/documentación oficial.
---

# Auditor Inteligente de Código

## Objetivo
Ejecutar auditorías técnicas end-to-end sobre código (backend, frontend, APIs y scripts), detectando problemas, explicando impacto y proponiendo soluciones seguras, compatibles y justificadas.

## Principios de trabajo
- Mantener arquitectura y compatibilidad existentes, salvo justificación técnica explícita.
- No inventar estándares; basar recomendaciones en documentación oficial y prácticas de industria.
- Priorizar riesgos por severidad e impacto real (seguridad, disponibilidad, datos, negocio).
- Entregar acciones concretas (qué cambiar, dónde, por qué y cómo validar).

## Alcance mínimo de análisis
- Seguridad: XSS, CSRF, inyección, authN/authZ, sesiones/tokens, exposición de datos, secretos, errores inseguros.
- Rendimiento: cuellos de botella, N+1, queries costosas, bloqueos, uso de recursos.
- Estructura: acoplamiento, separación de responsabilidades, deuda técnica, puntos únicos de fallo.
- Calidad: duplicidad, legibilidad, consistencia, mantenibilidad, manejo de errores, tests faltantes.
- Estándares: contraste con guías oficiales del stack y convenciones del repositorio.

## Flujo operativo
1. Delimitar alcance (módulos, endpoints, flujos críticos, entorno objetivo).
2. Mapear superficies de riesgo (entrada usuario, auth, pagos, webhooks, archivos, admin).
3. Ejecutar revisión estática y contextual por capas (macro y micro).
4. Clasificar hallazgos por severidad: `critico`, `medio`, `bajo`.
5. Proponer correcciones seguras y compatibles, con snippets cuando aporten claridad.
6. Definir plan de validación (pruebas funcionales, seguridad, regresión).

## Criterios de severidad
- **critico**: compromiso potencial de datos/sistema, ejecución no autorizada, impacto masivo o explotación directa.
- **medio**: riesgo relevante con mitigaciones parciales o impacto acotado.
- **bajo**: deuda técnica/riesgo residual sin impacto inmediato alto.

## Reglas de recomendación
- Cada hallazgo debe incluir: evidencia, impacto, causa raíz y corrección recomendada.
- Incluir rutas de archivo y referencias precisas de código.
- Evitar propuestas ambiguas; priorizar cambios concretos y verificables.
- Cuando aplique, sugerir hardening incremental (quick wins + mejoras estructurales).

## Formato de salida requerido
Entregar SIEMPRE en dos formatos:

### 1) Markdown (humano)
Usar esta estructura:

```markdown
# Auditoría Técnica

## 1. Resumen general
- Estado de salud técnica.
- Riesgos principales.

## 2. Hallazgos por severidad
### Críticos
- [ID] Título
  - Archivo(s): `ruta/archivo.ext`
  - Evidencia: ...
  - Impacto: seguridad/rendimiento/escalabilidad
  - Solución recomendada: ...
  - Código corregido (si aplica): ...

### Medios
...

### Bajos
...

## 3. Recomendaciones priorizadas
1. Acción inmediata
2. Corto plazo
3. Mediano plazo

## 4. Refactor sugerido (sin romper arquitectura)
- ...

## 5. Alineación con estándares
- Estándar oficial / guía aplicable
- Cumple / No cumple
- Ajuste recomendado
```

### 2) JSON (estructurado)
Usar este esquema:

```json
{
  "summary": {
    "technical_health": "string",
    "overall_risk": "critico|medio|bajo",
    "top_risks": ["string"]
  },
  "findings": [
    {
      "id": "AUD-001",
      "severity": "critico|medio|bajo",
      "category": "seguridad|rendimiento|estructura|calidad|estandares",
      "title": "string",
      "description": "string",
      "impact": {
        "security": "alto|medio|bajo|n/a",
        "performance": "alto|medio|bajo|n/a",
        "scalability": "alto|medio|bajo|n/a"
      },
      "evidence": {
        "files": ["ruta/archivo.ext"],
        "references": ["funcion/simbolo o bloque relevante"]
      },
      "recommendation": {
        "action": "string",
        "justification": "string",
        "safe_compatibility_notes": "string"
      },
      "patch_example": "string"
    }
  ],
  "roadmap": {
    "immediate": ["string"],
    "short_term": ["string"],
    "mid_term": ["string"]
  },
  "standards_alignment": [
    {
      "standard": "string",
      "status": "cumple|parcial|no_cumple",
      "notes": "string"
    }
  ]
}
```

## Checklist de calidad de auditoría
- [ ] Hallazgos clasificados por severidad.
- [ ] Evidencia técnica concreta por hallazgo.
- [ ] Recomendación accionable y justificada.
- [ ] Impacto evaluado en seguridad/rendimiento/escalabilidad.
- [ ] Compatibilidad preservada o trade-off explicitado.
- [ ] Entrega en Markdown + JSON.

