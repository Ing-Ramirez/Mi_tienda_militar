# Security audit report

Static analysis only — review each finding manually.

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 17 |
| HIGH     | 61 |
| MEDIUM   | 40 |
| LOW      | 2 |

## Issues

### Secrets in file (CRITICAL) — `.env`:8

Environment file contains non-placeholder value for "SECRET_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env`:17

Environment file contains non-placeholder value for "DB_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env`:23

Environment file contains non-placeholder value for "REDIS_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.dev`:7

Environment file contains non-placeholder value for "SECRET_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.dev`:15

Environment file contains non-placeholder value for "ENCRYPTION_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.dev`:20

Environment file contains non-placeholder value for "DB_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.dev`:26

Environment file contains non-placeholder value for "REDIS_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (MEDIUM) — `.env.example`:9

Environment file contains non-placeholder value for "SECRET_KEY"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:16

Environment file contains non-placeholder value for "DB_PASSWORD"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:40

Environment file contains non-placeholder value for "REDIS_PASSWORD"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:62

Environment file contains non-placeholder value for "STRIPE_PUBLIC_KEY"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:63

Environment file contains non-placeholder value for "STRIPE_SECRET_KEY"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:64

Environment file contains non-placeholder value for "STRIPE_WEBHOOK_SECRET"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (MEDIUM) — `.env.example`:73

Environment file contains non-placeholder value for "EMAIL_HOST_PASSWORD"

**Recommendation:** Ensure .env.example only documents keys with dummy values; never real secrets.

---

### Secrets in file (CRITICAL) — `.env.prod`:8

Environment file contains non-placeholder value for "SECRET_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:17

Environment file contains non-placeholder value for "DB_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:23

Environment file contains non-placeholder value for "REDIS_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:39

Environment file contains non-placeholder value for "STRIPE_PUBLIC_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:40

Environment file contains non-placeholder value for "STRIPE_SECRET_KEY"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:41

Environment file contains non-placeholder value for "STRIPE_WEBHOOK_SECRET"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:43

Environment file contains non-placeholder value for "PAYPAL_SECRET"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Secrets in file (CRITICAL) — `.env.prod`:50

Environment file contains non-placeholder value for "EMAIL_HOST_PASSWORD"

**Recommendation:** Never commit .env to version control; rotate any exposed values.

---

### Unsafe JS (CRITICAL) — `audit-tools/security-audit.js`:202

Use of eval()

**Recommendation:** Avoid eval; parse JSON with JSON.parse, use safe alternatives.

---

### Unsafe JS (HIGH) — `audit-tools/security-audit.js`:214

new Function() dynamic code generation

**Recommendation:** Avoid compiling strings to code; refactor to static functions.

---

### Unsafe JS (CRITICAL) — `audit-tools/security_audit.py`:212

Use of eval()

**Recommendation:** Avoid eval; parse JSON with JSON.parse, use safe alternatives.

---

### Unsafe JS (HIGH) — `audit-tools/security_audit.py`:222

new Function() dynamic code generation

**Recommendation:** Avoid compiling strings to code; refactor to static functions.

---

### XSS (MEDIUM) — `backend/core/admin.py`:179

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### Hardcoded credential (MEDIUM) — `backend/proveedores/tests/test_integration_proveedores_orders.py`:71

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### Hardcoded credential (MEDIUM) — `backend/proveedores/tests/test_integration_proveedores_orders.py`:256

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### Hardcoded credential (MEDIUM) — `backend/returns/tests.py`:23

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### Hardcoded credential (MEDIUM) — `backend/returns/tests.py`:28

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:171

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:179

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:189

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:198

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:339

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:347

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:360

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:387

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:399

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:420

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:482

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:514

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:574

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:632

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/admin_productos.js`:692

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/fp_user_permissions.js`:56

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/fp_user_permissions.js`:118

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/fp_user_permissions.js`:231

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/fp_user_permissions.js`:245

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/franja_admin_global.js`:64

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/franja_admin_global.js`:131

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (MEDIUM) — `backend/static/js/franja_admin_global.js`:197

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### Hardcoded credential (MEDIUM) — `backend/static/js/i18n/es-co.js`:134

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### Hardcoded credential (MEDIUM) — `backend/static/js/i18n/es-co.js`:387

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### Hardcoded credential (MEDIUM) — `backend/static/js/i18n/es-co.js`:390

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---

### XSS / CSP (MEDIUM) — `backend/templates/store/index.html`:4397

Inline event handler attribute (e.g. onclick, onload)

**Recommendation:** Prefer addEventListener and keep logic in script files with a strict CSP.

---

### XSS / CSP (MEDIUM) — `backend/templates/store/index.html`:4408

Inline event handler attribute (e.g. onclick, onload)

**Recommendation:** Prefer addEventListener and keep logic in script files with a strict CSP.

---

### Validation (LOW) — `backend/templates/store/index.html`:4749

Form with user inputs may lack required/pattern client-side hints

**Recommendation:** Add server-side validation always; add required/pattern where appropriate (client is not sufficient).

---

### Maintainability / CSP (LOW) — `backend/templates/store/index.html`:3798

Inline style attributes detected (125 occurrence(s))

**Recommendation:** Prefer external CSS; inline styles complicate CSP style-src and maintenance.

---

### XSS (HIGH) — `backend/templates/store/index.html`:5337

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:5482

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:5653

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6092

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6158

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6243

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6262

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6489

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6682

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6690

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6785

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6803

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6822

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6833

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:6925

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7202

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7442

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7449

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7479

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7484

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7489

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7495

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7499

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7505

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7506

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7516

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7519

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7521

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7523

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7675

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7683

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7703

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7839

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7843

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7920

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:7997

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8024

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8028

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8043

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8059

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8067

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8075

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8077

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8088

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8089

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8097

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8119

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8126

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8132

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8150

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8156

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8157

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8948

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8951

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8974

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:8984

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:9004

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:9053

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### XSS (HIGH) — `backend/templates/store/index.html`:9133

Assignment to innerHTML (potential XSS if data is user-controlled)

**Recommendation:** Prefer textContent, or sanitize with a trusted library and encode output.

---

### Hardcoded credential (MEDIUM) — `backend/templates/store/index.html`:8543

Possible hardcoded secret or password string

**Recommendation:** Use environment variables; exclude placeholders in examples only.

---
