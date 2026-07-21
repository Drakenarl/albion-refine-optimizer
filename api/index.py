"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12. On importe l'app FastAPI existante (definie dans
``src/albion_refine/api.py``) sans dupliquer de code.

L'import ``app`` doit rester **au top-level du module** : le detecteur statique
de Vercel (build-time) parse le fichier sans l'executer et refuse un import
enferme dans ``try:`` (erreur "does not define a top-level app FastAPI
instance"). Le sys.path est configure AVANT l'import pour que ca fonctionne
meme si pip n'a pas installe le paquet local.

Contraintes runtime :
- Timeout 10 s (plan Hobby), suffisant pour un run AODP standard.
- Pas de systeme de fichiers persistant → le cache diskcache est recree a
  chaque cold start, ce qui n'est pas dramatique (l'AODP repond en < 1s).
- Cold start ~1-2 s a la premiere invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Fallback : ajoute src/ au path au cas ou pip n'aurait pas installe le paquet.
# Doit s'executer AVANT l'import ci-dessous.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from albion_refine.api import app  # noqa: E402  (import apres modif sys.path)

# Vercel Python runtime detecte l'attribut ``app`` (ASGI) et le sert directement.
__all__ = ["app"]
