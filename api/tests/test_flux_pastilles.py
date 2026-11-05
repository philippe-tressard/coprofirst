"""Le fil rend la MÊME ligne de pastilles qu'une carte d'affaire (27/09/2026).

Arbitré à l'écran : la dernière ligne d'une carte d'affaire fait la norme —
catégorie, état, 🔹 périmètre, qui la lit, ⚡ urgence, marqueurs, numéro,
✍️ auteur, ✨ IA —, et le fil doit la rendre à l'identique. Il ne recevait que
le numéro, le périmètre et l'auteur : il ne POUVAIT pas.

`pastilles_affaire` rend ce qu'il faut au composant partagé (`PastillesAffaire`,
côté front), en passant par `TicketRead` — mêmes validateurs que l'API, rien
de recopié : `public_cible` et `perimetre_cible` y sont décodés de leur JSON.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.models.core import Ticket
from app.routers.flux.commun import CHAMPS_PASTILLES, pastilles_affaire

_FLUX = Path(__file__).resolve().parents[1] / "app" / "routers" / "flux"


def _affaire(**kwargs) -> Ticket:
    """Affaire en mémoire — aucune session, aucune base ouverte."""
    defauts = dict(
        id=7,
        numero="TK-109008",
        titre="Porte du hall",
        description="Elle ne ferme plus",
        auteur_id=1,
        categorie="panne",
        statut="en_cours",
        priorite="haute",
        epingle=True,
        confidentiel=False,
        perimetre_cible='["bat:1"]',
        public_cible='["residents"]',
        assiste_ia=True,
    )
    defauts.update(kwargs)
    return Ticket(**defauts)


def test_les_champs_de_la_ligne_sont_TOUS_rendus():
    rendu = pastilles_affaire(_affaire())
    assert set(rendu) == set(CHAMPS_PASTILLES) | {"natures"}


def test_la_ligne_sert_le_libelle_de_la_categorie():
    """Le pied de carte du fil lit le libellé servi, sans table à lui (#2511)."""
    from app.utils.categories_ticket import libelle_categorie

    assert pastilles_affaire(_affaire())["categorie_libelle"] == libelle_categorie("panne")
    assert libelle_categorie("panne") != "panne"


def test_la_nature_suit_la_date_de_l_affaire():
    """Une affaire à laquelle on ajoute une date devient « Calendrier » : le fil
    doit le dire comme la liste des affaires (4/11/2026, « AFF. » restait au fil)."""
    from datetime import datetime

    assert pastilles_affaire(_affaire())["natures"] == ["activite"]
    datee = _affaire(debut=datetime(2026, 11, 9, 14, 30))
    assert pastilles_affaire(datee)["natures"] == ["calendrier"]


def test_les_listes_sont_DECODEES_comme_par_l_API():
    """Un JSON brut arriverait au front en chaîne : `perimetreRestreint` et la
    pastille de lecture le liraient comme un seul code illisible."""
    rendu = pastilles_affaire(_affaire())
    assert rendu["perimetre_cible"] == ["bat:1"]
    assert rendu["public_cible"] == ["residents"]
    assert rendu["priorite"] == "haute" and rendu["assiste_ia"] is True


def test_affaires_ET_actualites_du_fil_portent_la_ligne():
    """Les deux collecteurs qui rendent une affaire l'appellent — sinon l'un des
    deux fils resterait sur l'ancienne ligne, sans que rien ne le signale."""
    for nom in ("tickets.py", "publications.py"):
        arbre = ast.parse((_FLUX / nom).read_text(encoding="utf-8"))
        appels = {
            n.func.id
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "pastilles_affaire" in appels, f"{nom} ne rend pas la ligne de pastilles"


def test_chaque_carte_de_la_communaute_porte_la_marque_IA():
    """✨ se voyait sur l'actualité et nulle part dans le fil (27/09/2026, signalé
    à l'écran). Sondage, annonce et idée portent `assiste_ia` : chacune de leurs
    cartes le rend. Compté sur les `meta=` réels — un cinquième `FluxItem` qui
    l'oublierait échoue ici."""
    arbre = ast.parse((_FLUX / "communaute.py").read_text(encoding="utf-8"))
    metas = [
        kw.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "FluxItem"
        for kw in n.keywords
        if kw.arg == "meta"
    ]
    assert metas, "aucune carte trouvée — le contrôle ne mesure plus rien"
    sans = [
        m.lineno
        for m in metas
        if not (
            isinstance(m, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "assiste_ia" for k in m.keys)
        )
    ]
    assert not sans, f"cartes sans « assiste_ia » (lignes {sans})"
