"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12.

Comment ``albion_refine`` est resolu :
- Le buildCommand copie ``src/albion_refine`` dans ``api/albion_refine``, donc
  le paquet est physiquement a cote de ce fichier au moment du packaging.
- ``sys.path`` inclut explicitement le dossier de ce fichier.
- L'import se resout localement, sans dependre de includeFiles ni du pip
  install du paquet local.

En cas d'echec d'import, on expose un app FastAPI minimal qui reporte
l'erreur en JSON via GET /api/debug. Evite de boucler sur les
FUNCTION_INVOCATION_FAILED opaques de Vercel.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_boot_error: BaseException | None = None
_boot_traceback: str | None = None

try:
    from albion_refine.api import app  # noqa: E402
except BaseException as _e:  # noqa: BLE001 (on veut vraiment tout attraper)
    _boot_error = _e
    _boot_traceback = traceback.format_exc()

    # App de secours : renvoie 200 mais reporte l'erreur exacte au frontend.
    from fastapi import FastAPI  # noqa: E402

    app = FastAPI(title="Albion Refine API — boot failed")

    @app.get("/api/health")
    def _health_fallback() -> dict[str, object]:
        return {"status": "boot_failed", "error": str(_boot_error)}

    @app.get("/api/debug")
    def _debug() -> dict[str, object]:
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
