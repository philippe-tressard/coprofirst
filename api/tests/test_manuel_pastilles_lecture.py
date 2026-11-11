"""Les pastilles « qui la lit » du manuel disent ce que le site dit (27/09/2026).

Le manuel montre la VRAIE pastille, avec sa phrase au survol. Une phrase recopiée
dans un document diverge au premier changement de la règle — le manuel mentirait
alors en toute confiance. Chaque `<span … data-lecture="cas" title="…">` est donc
RECALCULÉ par la règle servie (`lecture_pastille.regle.lecture_de`), sur la nature
déclarée ci-dessous. Un cas du manuel inconnu d'ici, ou d'ici absent du manuel,
échoue aussi.

Porté de `front/scripts/check-manuel-pastilles.mjs` le 11/11/2026 (#2633) : la
règle a quitté le front, son contrôle la suit.
"""

from __future__ import annotations

import pathlib
import re

from app.utils.lecture_pastille.regle import lecture_de

MANUEL = pathlib.Path(__file__).resolve().parents[2] / "docs" / "manuel-utilisateur.html"

NATURE = dict(
    actualite=False,
    categorie="etude_travaux",
    confidentiel=False,
    public_cible=None,
    perimetre_restreint=False,
    reserve_perimetre=False,
)
ACTUALITE = dict(actualite=True, categorie="actualite")

#: Le cas du manuel → la nature d'objet qui produit sa pastille.
CAS = {
    #  Une Étude & travaux dont le conseil a CHOISI les copropriétaires : sans
    #  choix, elle est au conseil seul depuis le 29/09/2026 — le cas `cs` le dit.
    "copro": NATURE | dict(public_cible=["copropriétaires_occupants", "bailleurs"]),
    "occ": NATURE | ACTUALITE | dict(public_cible=["copropriétaires_occupants"]),
    "cad": NATURE
    | ACTUALITE
    | dict(public_cible=["résidents"], perimetre_restreint=True, reserve_perimetre=True),
    #  Une Étude & travaux sans choix : le conseil seul.
    "cs": NATURE,
    #  Une Nuisance sans choix du conseil : « Résident concerné » (#1436).
    "concerne": NATURE | dict(categorie="nuisance"),
    #  Une Panne sans choix, sur un bâtiment : les copropriétaires partout, les
    #  locataires du périmètre (standard du 30/09/2026).
    "panne": NATURE | dict(categorie="panne", perimetre_restreint=True),
}

_PASTILLE = re.compile(
    r'<span class="pastille-lecture-ex" data-lecture="(\w+)"[^>]*title="([^"]*)">'
    r"[\s\S]*?<span>([^<]*)</span>"
)


def test_les_pastilles_du_manuel_sont_celles_du_site():
    pastilles = _PASTILLE.findall(MANUEL.read_text(encoding="utf-8"))
    #  Cas zéro : un manuel sans pastille ne prouverait rien (`standards/04` §2).
    assert pastilles, "INCONNU : aucune pastille `data-lecture` dans le manuel"
    ecarts, vus = [], set()
    for cas, titre, texte in pastilles:
        vus.add(cas)
        if cas not in CAS:
            ecarts.append(f"cas « {cas} » inconnu du contrôle — le déclarer dans CAS")
            continue
        lecture = lecture_de(**CAS[cas])
        attendu = f"{lecture.titre} — {lecture.phrase} {lecture.exclus}".strip()
        if titre != attendu:
            ecarts.append(f"{cas} : survol\n  manuel : {titre}\n  site   : {attendu}")
        if texte != lecture.court:
            ecarts.append(f"{cas} : texte « {texte} », le site dit « {lecture.court} »")
    ecarts += [f"cas « {c} » absent du manuel" for c in CAS if c not in vus]
    assert not ecarts, "Pastilles du manuel ≠ site :\n" + "\n".join(ecarts)
