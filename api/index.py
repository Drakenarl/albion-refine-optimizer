"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12.

Structure imposee par les contraintes Vercel :
1. L'analyseur statique de Vercel exige un ``app = FastAPI(...)`` litteral
   au top-level du module. Un import dans un try/except ne compte pas.
2. Le runtime demande a ce que l'app fonctionne vraiment. On tente d'importer
   la vraie app (``albion_refine.api``) et on la substitue au placeholder si
   ca marche.
3. Si l'import echoue, on garde le placeholder et on lui attache des
   endpoints ``/api/health`` et ``/api/debug`` qui reportent l'erreur en JSON,
   pour eviter les FUNCTION_INVOCATION_FAILED opaques.

``albion_refine`` est resolu localement : le buildCommand copie
``src/albion_refine`` dans ``api/albion_refine`` avant le packaging, et
``sys.path`` inclut le dossier de ce fichier.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI

# --- Etape 1 : placeholder litteral (obligatoire pour l'analyseur Vercel) ---
app: FastAPI = FastAPI(title="Albion Refine API — booting")

# --- Etape 2 : setup sys.path + tentative d'import de la vraie app ---
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_boot_error: BaseException | None = None
_boot_traceback: str | None = None

try:
    from albion_refine.api import app as _real_app  # noqa: E402

    app = _real_app  # remplace le placeholder par la vraie app
except BaseException as _exc:  # noqa: BLE001 (on veut vraiment tout attraper au boot)
    _boot_error = _exc
    _boot_traceback = traceback.format_exc()

    # Le placeholder reste actif : on lui attache des endpoints de diagnostic
    # accessibles en JSON via le navigateur, ce que Vercel ne fait pas nativement.

    @app.get("/api/health")
    def _health_fallback() -> dict[str, object]:
        return {
            "status": "boot_failed",
            "error": str(_boot_error),
            "hint": "GET /api/debug pour le traceback complet",
        }

    @app.get("/api/debug")
    def _debug_fallback() -> dict[str, object]:
        return {
            "error": str(_boot_error),
            "traceback": _boot_traceback,
            "cwd": os.getcwd(),
            "here": str(_HERE),
            "here_exists": _HERE.exists(),
            "here_contents": (
                sorted(p.name for p in _HERE.iterdir()) if _HERE.exists() else None
            ),
            "sys_path": sys.path,
            "python_version": sys.version,
        }


__all__ = ["app"]
