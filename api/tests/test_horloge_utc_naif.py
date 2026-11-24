"""Un instant conscient se ramène en UTC naïf par `horloge.utc_naif`, une fois (#2949).

`.astimezone(timezone.utc).replace(tzinfo=None)` s'écrivait cinq fois hors de
`horloge` — deux fonctions au corps identique (`inscription/constat._utc_naif`,
`registre/alertes._naif`), trois en ligne —, et `utils/courriel_fil` réécrivait
mot pour mot `horloge.de_paris`. Une conversion de fuseau recopiée diverge au
premier changement d'heure mal traité (`test_horloge.py`, #1617).

Le contrôle cherche la CHAÎNE `….astimezone(…).replace(tzinfo=None)` dans l'AST
de `app/` : `astimezone` seul est banal (afficher à Paris), `replace(tzinfo=None)`
seul aussi (un instant déjà en UTC) ; c'est leur enchaînement qui est la notion.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone

from app.utils import horloge
from tests.aides_sources import module_app, modules_app

_HORLOGE = "utils/horloge.py"

#: Modules qui ont le droit d'écrire la conversion, avec leur raison. Le contrôle
#: échoue si l'un d'eux cesse de l'écrire : l'exception ne sert plus.
EXCEPTIONS = {
    #  Lancé hors de l'API par `scripts/ci/purge-paquets.sh` : il n'importe que la
    #  bibliothèque standard, et `app.utils.horloge` lui coûterait le paquet `app`.
    "registre/versions.py": "bibliothèque standard seulement (purge-paquets.sh)",
}


def _est_sans_fuseau(appel: ast.AST) -> bool:
    """`x.replace(tzinfo=None)`."""
    return (
        isinstance(appel, ast.Call)
        and isinstance(appel.func, ast.Attribute)
        and appel.func.attr == "replace"
        and any(
            k.arg == "tzinfo" and isinstance(k.value, ast.Constant) and k.value.value is None
            for k in appel.keywords
        )
    )


def conversions(arbre: ast.AST) -> list[int]:
    """Les lignes où `….astimezone(…).replace(tzinfo=None)` s'écrit. PURE."""
    return sorted(
        n.lineno
        for n in ast.walk(arbre)
        if _est_sans_fuseau(n)
        and isinstance(n.func.value, ast.Call)
        and isinstance(n.func.value.func, ast.Attribute)
        and n.func.value.func.attr == "astimezone"
    )


def test_le_controle_sait_REFUSER():
    cas = {
        "d.astimezone(timezone.utc).replace(tzinfo=None)": 1,
        "d.replace(tzinfo=P).astimezone(utc).replace(tzinfo=None)": 1,
        "d.astimezone(TZ_PARIS)": 0,
        "d.replace(tzinfo=None)": 0,
        "d.astimezone(utc).replace(hour=0)": 0,
    }
    for source, attendu in cas.items():
        assert len(conversions(ast.parse(source))) == attendu, source


def test_la_conversion_s_ecrit_dans_horloge_seulement():
    fautes, servies = [], set()
    for m in modules_app(minimum=100):
        lignes = conversions(m.arbre)
        if not lignes or m.rel == _HORLOGE:
            continue
        if m.rel in EXCEPTIONS:
            servies.add(m.rel)
            continue
        fautes += [f"{m.rel}:{ligne}" for ligne in lignes]
    assert not fautes, (
        "UTC naïf recomposé hors de `horloge` — appeler `horloge.utc_naif(instant)` "
        f"(ou `horloge.de_paris` pour une heure murale de Paris) : {fautes}"
    )
    assert servies == set(EXCEPTIONS), (
        f"exception qui ne sert plus : {set(EXCEPTIONS) - servies} — la retirer d'EXCEPTIONS"
    )
    assert conversions(module_app(_HORLOGE).arbre), "le témoin a disparu : contrôle vide"


def test_utc_naif():
    ete = datetime(2026, 7, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    assert horloge.utc_naif(ete) == datetime(2026, 7, 1, 12, 0)
    assert horloge.utc_naif(ete).tzinfo is None
    naif = datetime(2026, 7, 1, 12, 0)
    assert horloge.utc_naif(naif) is naif, "un instant naïf est déjà de l'UTC de la base"
