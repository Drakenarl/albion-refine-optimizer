"""Handler Vercel Python — expose l'API FastAPI en fonction serverless.

Vercel decouvre ce fichier grace au dossier ``api/`` et route ``/api/*`` vers
son runtime Python 3.12.

Comment ``albion_refine`` est resolu :
- Au build Vercel, le buildCommand copie ``src/albion_refine`` dans
  ``api/albion_refine``. Le paquet est donc physiquement a cote de ce fichier
  au moment ou la fonction est packagee.
- ``sys.path`` inclut le dossier de ce fichier (Python le fait automatiquement
  pour le module principal, et on l'ajoute explicitement pour etre defensif).
- L'import se resout localement, sans dependre de ``includeFiles`` ou d'un
  pip install du paquet local.

Contraintes runtime :
- Timeout 10 s (plan Hobby), suffisant pour un run AODP standard.
- Pas de systeme de fichiers persistant → le cache diskcache est recree a
  chaque cold start, ce qui n'est pas dramatique (l'AODP repond en < 1s).
- Cold start ~1-2 s a la premiere invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Le buildCommand Vercel copie src/albion_refine -> api/albion_refine.
# On s'assure que ce dossier est dans sys.path avant l'import.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from albion_refine.api import app  # noqa: E402

# Vercel Python runtime detecte l'attribut ``app`` (ASGI) et le sert directement.
__all__ = ["app"]
