"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12. On importe l'app FastAPI existante (definie dans
``src/albion_refine/api.py``) sans dupliquer de code.

Contraintes runtime :
- Timeout 10 s (plan Hobby), suffisant pour un run AODP standard.
- Pas de systeme de fichiers persistant → le cache diskcache est recree a
  chaque cold start, ce qui n'est pas dramatique (l'AODP repond en < 1s).
- Cold start ~1-2 s (importable, imports lourds font a la premiere invocation).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Le paquet ``albion_refine`` vit dans ``src/`` (layout src standard). On l'ajoute
# au sys.path avant l'import pour eviter de reempaqueter le code.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from albion_refine.api import app  # noqa: E402  (import apres modif sys.path)

# Vercel Python runtime detecte l'attribut ``app`` (ASGI) et le sert directement.
# Aucun handler custom a ecrire ; FastAPI/Starlette sont supportes nativement.
__all__ = ["app"]
