"""La clé de maintenance se compare à temps constant, et aucun secret ne se compare par `==`.

## Le défaut (audit de sécurité du 27/09/2026)

`exiger_cle_maintenance` comparait la clé reçue par `!=`. Une comparaison de
chaînes s'arrête au premier caractère qui diffère : sa durée dit combien de
caractères étaient justes, et une clé se devine alors caractère par caractère.
Le correctif est `hmac.compare_digest`. Le garde-fou refuse le motif partout.

## La portée du garde-fou, écrite pour qu'on ne la croie pas plus large

Il refuse un `==` ou un `!=` dont un opérande est un **réglage** secret :
`settings.<nom>` ou `get_settings().<nom>`, quand le nom finit par `key`,
`secret`, `password` ou `token`. Il ne voit pas un secret déjà copié dans une
variable locale, ni un secret lu dans la configuration du site
(`config.get("…")`). Un jeton cherché en base par `WHERE token = :x` n'est pas
concerné : la comparaison a lieu dans la base, derrière une recherche par index.
"""

from __future__ import annotations

import ast
import re

import pytest
from fastapi import HTTPException

from app.auth.cle_maintenance import exiger_cle_maintenance
from app.config import get_settings
from tests.aides_sources import modules_app

CLE = "cle-de-test-du-temps-constant"
SECRET = re.compile(r"(key|secret|password|token)$", re.IGNORECASE)
REGLAGES = {"settings", "_settings"}


@pytest.fixture()
def cle(monkeypatch):
    monkeypatch.setattr(get_settings(), "maintenance_key", CLE)


@pytest.mark.parametrize("recue", [None, "", "mauvaise", CLE[:-1], CLE + "x", "clé-accentuée"])
def test_une_cle_fausse_est_refusee_en_403(cle, recue):
    """Clé absente, vide, fausse, préfixe, et non ASCII : un 403, jamais un 500."""
    with pytest.raises(HTTPException) as refus:
        exiger_cle_maintenance(recue)
    assert refus.value.status_code == 403


def test_la_bonne_cle_passe(cle):
    exiger_cle_maintenance(CLE)


@pytest.mark.parametrize("recue", [None, ""])
def test_sans_cle_configuree_tout_est_refuse(monkeypatch, recue):
    """Une clé vide comparée à une clé vide serait égale : le canal reste fermé."""
    monkeypatch.setattr(get_settings(), "maintenance_key", "")
    with pytest.raises(HTTPException) as refus:
        exiger_cle_maintenance(recue)
    assert refus.value.status_code == 503


def _est_reglage_secret(noeud: ast.AST) -> bool:
    if not (isinstance(noeud, ast.Attribute) and SECRET.search(noeud.attr)):
        return False
    base = noeud.value
    if isinstance(base, ast.Name):
        return base.id in REGLAGES
    return isinstance(base, ast.Call) and getattr(base.func, "id", None) == "get_settings"


def _comparaisons_de_secret(source: str) -> list[int]:
    return [
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Compare)
        and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in n.ops)
        and any(_est_reglage_secret(o) for o in (n.left, *n.comparators))
    ]


def test_le_controle_voit_ce_qu_il_doit_refuser():
    """Un contrôle qui ne peut pas échouer ne prouve rien (`standards/04`)."""
    assert _comparaisons_de_secret("if cle != settings.maintenance_key: pass") == [1]
    assert _comparaisons_de_secret("ok = get_settings().secret_key == x") == [1]
    assert _comparaisons_de_secret("ok = settings.cookie_secure == True") == []
    assert _comparaisons_de_secret("ok = hmac.compare_digest(a, settings.maintenance_key)") == []


def test_aucun_secret_ne_se_compare_par_egalite():
    modules = modules_app()
    assert len(modules) > 100, "le contrôle ne voit presque rien : sa portée a changé"
    ecarts = [
        f"app/{m.rel}:{ligne}" for m in modules for ligne in _comparaisons_de_secret(m.source)
    ]
    assert not ecarts, (
        "Un secret comparé par `==` ou `!=` : la durée de la réponse trahit combien "
        "de caractères étaient justes. Utiliser `hmac.compare_digest` sur des octets :\n"
        + "\n".join(f"  • {e}" for e in ecarts)
    )
