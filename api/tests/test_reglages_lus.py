"""Un réglage déclaré écrivable est nommé par le code qui le lit (#2059).

`whatsapp_group_name` (« Nom du canal ») était écrit par l'onglet WhatsApp, déclaré dans la
liste blanche de `PUT /config`, et nommé par AUCUN code de l'API : un champ que l'on
renseigne et qui ne sert à rien. Le registre des réglages (`utils/reglages`) refuse
désormais une clé déclarée dont aucun module de l'API, hors le registre, le seed et la
carte, ne cite le nom.

Ce que le contrôle voit : la clé est NOMMÉE. Il ne prouve pas qu'elle est lue plutôt
qu'écrite — l'écriture passe par la route générique, qui ne cite aucune clé — mais un
réglage qu'aucun module ne cite ne peut, lui, être lu par personne.

Les clés de la famille `llm_<usage>_<champ>` se déduisent du registre des usages
(`utils/llm_usages`), lu par `llm_limites` et `llm_journal` : elles n'ont pas de littéral.
"""

from __future__ import annotations

import re

from app.utils import reglages
from app.utils.llm_usages import USAGES, champs
from tests.aides_sources import modules_app

#: Les modules qui DÉCLARENT les clés : les y trouver ne dit pas qu'elles servent.
_REGISTRES = {"reglages.py", "reglages_carte.py", "reglages_carte_rendu.py"}


def cles_sans_lecteur(cles: set[str], sources: dict[str, str]) -> list[str]:
    """PURE. Les clés qu'aucune source ne cite entre guillemets."""
    return sorted(
        cle
        for cle in cles
        if not any(re.search(r"""["']%s["']""" % re.escape(cle), t) for t in sources.values())
    )


def _sources_de_l_api() -> dict[str, str]:
    return {
        m.rel: m.source
        for m in modules_app()
        if m.rel.rsplit("/", 1)[-1] not in _REGISTRES and "seed" not in m.rel.split("/")
    }


def test_chaque_reglage_ecrivable_est_nomme_par_un_module_de_l_api():
    derivees = {u.cle(c) for u in USAGES.values() for c in champs(u)}
    cles = set(reglages.ECRIVABLES) - derivees
    sources = _sources_de_l_api()
    assert len(sources) > 100 and len(cles) > 40  # cas zéro : le balayage lit bien quelque chose
    assert cles_sans_lecteur(cles, sources) == [], (
        "réglages déclarés mais nommés par aucun module de l'API : faites-les lire "
        "(comme `whatsapp_group_name` par le journal des envois), ou retirez-les."
    )


def test_le_controle_voit_une_cle_que_personne_ne_cite():
    """Témoin : un corpus sans la clé la fait remonter, un corpus qui la cite la tait."""
    assert cles_sans_lecteur({"whatsapp_group_name"}, {"a.py": 'x = "site_email"'}) == [
        "whatsapp_group_name"
    ]
    assert cles_sans_lecteur({"whatsapp_group_name"}, {"b.py": "get('whatsapp_group_name')"}) == []
