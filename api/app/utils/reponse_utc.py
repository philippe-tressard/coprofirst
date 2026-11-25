"""La sérialisation UTC des réponses : toute datetime naïve sort avec « Z ».

Extrait de `main.py` le 07/10/2026 (#1725), au fil de l'eau : le module touchait
son plafond de 500 lignes, et cette notion — comment une date QUITTE l'API — n'a
rien à voir avec le montage de l'application. L'import a un effet voulu :
il enregistre l'encodeur de `datetime` auprès de FastAPI (`ENCODERS_BY_TYPE`).
"""

import json as _json
import re as _re
from datetime import datetime
from typing import Any

from fastapi.responses import JSONResponse

# ── Sérialisation UTC : toutes les datetime naïves sortent avec "Z" ───────────
# Problème : FastAPI 0.115+ / Pydantic v2 appelle model_dump(mode="json")
# qui convertit les datetime en chaînes ISO AVANT que ENCODERS_BY_TYPE ne
# puisse ajouter le suffixe "Z". Résultat : "2026-04-10T00:00:00" sans "Z"
# → le navigateur interprète comme heure locale au lieu d'UTC.
#
# Solution : UTCJSONResponse post-traite le JSON pour ajouter "Z" à toute
# chaîne ISO datetime naïve (sans timezone). Le _UTCEncoder reste en place
# pour les cas où un dict brut contient des objets datetime Python.

from fastapi.encoders import ENCODERS_BY_TYPE  # noqa: E402

ENCODERS_BY_TYPE[datetime] = lambda dt: (
    dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()
)

# Regex : "2026-04-10T00:00:00" ou "2026-04-10T00:00:00.123456" (sans suffixe TZ)
_NAIVE_DT_RE = _re.compile(r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"')


class _UTCEncoder(_json.JSONEncoder):
    """Filet de sécurité : si un datetime arrive directement dans le JSON
    (retour de dict brut), on ajoute Z aussi."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                return obj.isoformat() + "Z"
            return obj.isoformat()
        return super().default(obj)


class UTCJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        body = _json.dumps(
            content,
            cls=_UTCEncoder,
            ensure_ascii=False,
        )
        # Post-traitement : ajouter "Z" aux datetime ISO naïves
        # (Pydantic v2 les a déjà converties en chaînes sans timezone)
        body = _NAIVE_DT_RE.sub(r'"\1Z"', body)
        return body.encode("utf-8")
