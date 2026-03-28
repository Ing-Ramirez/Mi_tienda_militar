"""
Valida guardas basicas de idioma para la UI:
- No permitir terminos visibles en ingles definidos como prohibidos.
"""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STORE_FILE = ROOT / "backend" / "templates" / "store" / "index.html"

FORBIDDEN_VISIBLE_TERMS = [
    "BESTSELLER",
    "MISSION",
    ">HOT<",
    ">NEW<",
]


def main() -> int:
    if not STORE_FILE.exists():
        print(f"[ERROR] No existe {STORE_FILE}")
        return 1

    content = STORE_FILE.read_text(encoding="utf-8", errors="ignore")
    found = [term for term in FORBIDDEN_VISIBLE_TERMS if term in content]
    if found:
        print("[ERROR] Se encontraron terminos visibles prohibidos en ingles:")
        for term in found:
            print(f" - {term}")
        return 1

    print("[OK] Guardas de idioma UI superadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
