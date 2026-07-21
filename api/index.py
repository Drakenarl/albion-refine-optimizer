"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12. On importe l'app FastAPI existante (definie dans
``src/albion_refine/api.py``) sans dupliquer de code.

Import strategy (deux niveaux) :
1. Path standard, apres que Vercel ait fait ``pip install -r requirements.txt``
   (qui inclut ``.`` en fin de fichier → installe le package local via son
   pyproject.toml).
2. Fallback sys.path si l'install pip n'a pas ramene notre package (par ex.
   probleme avec hatchling / layout src).

Contraintes runtime :
- Timeout 10 s (plan Hobby), suffisant pour un run AODP standard.
- Pas de systeme de fichiers persistant → le cache diskcache est recree a
  chaque cold start, ce qui n'est pas dramatique (l'AODP repond en < 1s).
- Cold start ~1-2 s a la premiere invocation.
"""

from __future__ import annotations

try:
    from albion_refine.api import app
except ImportError:
    # Fallback : le package n'a pas ete installe par pip, on ajoute src/ au path.
    import sys
    from pathlib import Path

    _SRC = Path(__file__).resolve().parent.parent / "src"
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))

    from albion_refine.api import app  # noqa: E402  (fallback import)

# Vercel Python runtime detecte l'attribut ``app`` (ASGI) et le sert directement.
__all__ = ["app"]
