"""Le front et l'API donnent la MÊME icône à un type d'évolution.

## Pourquoi ce garde-fou (19/08/2026, signalé à l'écran)

> *« Pourquoi mon commentaire sur un ticket a une icône de type relance et non
> commentaire ? »*

La même notion était écrite **quatre fois, avec trois valeurs** :

| Où | `commentaire` | `reponse` |
|---|---|---|
| le bouton qui ouvre le formulaire | 💬 | — |
| le fil (`RubriqueHistorique`) | 📝 | 💬 |
| le fil recomposé à la main dans `espace-cs` | 📝 | 💬 |
| le flux d'activité (`flux/tickets.py`) | 🔧 | 💬 |

On cliquait « 💬 Commenter » et l'entrée s'affichait en 📝 — un mémo, lu comme une
relance. Chacune de ces tables était cohérente **avec elle-même** : c'est ce qui
les rendait invisibles à la relecture (#415, #413).

Les trois écritures du front ont été réunies dans `#lib/evolutions.ts`. La
quatrième ne peut pas les rejoindre : **les contextes de build sont `./api` et
`./front`**, rien de la racine n'entre dans les images (mémoire projet du
14/08/2026). Deux écritures sont donc inévitables.

🔴 **Ce qui est inévitable se surveille, il ne se promet pas.** C'est ce test —
même remède que pour le motif de crontab, écrit deux fois lui aussi et divergent
pendant quatre jours (`lib-verdicts` / `lib-collecte`, corrigé le même jour).

⚠️ Le **libellé** n'est PAS comparé, et c'est délibéré : « Mise à jour » décrit
une carte de flux, « commentaire » une entrée de fil. Deux rendus du même fait
peuvent porter des mots différents — seul le **signe** doit être commun, parce
que c'est lui qu'on reconnaît sans lire.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.utils import evolutions
from app.utils.suivi_affaires.releve import MOTIF_NOUVELLE
from tests.aides_sources import modules_app
from tests.aides_tables_front import table_plate

_RACINE = Path(__file__).resolve().parents[2]
_API = _RACINE / "api" / "app" / "routers" / "flux" / "tickets.py"


def _icones_front() -> dict[str, str]:
    """`EVOLUTION_ICONE` de `#lib/evolutions.ts`, échappements `\\u{…}` résolus.

    Le front les écrit ainsi parce qu'un emoji hors BMP survit mal aux allers-retours
    d'encodage sous Windows (`standards/10`), alors que le Python les écrit
    littéralement. La lecture vit dans `aides_tables_front` (#2947).
    """
    return table_plate("evolutions.ts", "EVOLUTION_ICONE")


def _icones_api() -> dict[str, str]:
    """`_MISES_A_JOUR` de `flux/tickets.py` : (type, préfixe, libellé, icône)."""
    source = _API.read_text(encoding="utf-8")
    bloc = re.search(r"_MISES_A_JOUR\s*=\s*\((.*?)\n\)", source, re.S)
    assert bloc, "`_MISES_A_JOUR` est introuvable dans flux/tickets.py."
    return {
        t: icone
        for t, _prefixe, _libelle, icone in re.findall(
            r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', bloc.group(1)
        )
    }


def test_les_deux_tables_sont_lisibles():
    """Un test qui ne trouve pas ses tables échoue — il ne passe pas au vert.

    `standards/04` §1 : un contrôle qui ne peut pas mesurer rend INCONNU, jamais
    OK. Ici, INCONNU vaut échec.
    """
    front, api = _icones_front(), _icones_api()
    assert front, "table du front vide"
    assert api, "table de l'API vide"
    assert "commentaire" in front and "commentaire" in api


def test_les_icones_communes_sont_identiques():
    """🔴 Le cas exact du 19/08 : `commentaire` valait 📝 ici et 🔧 là.

    Seuls les types présents **des deux côtés** sont comparés : l'API ne rend pas
    de carte pour un changement d'état (`etat` a son propre libellé de flux), et
    exiger la symétrie complète interdirait à chaque écran d'avoir ses propres
    types.
    """
    front, api = _icones_front(), _icones_api()
    ecarts = {t: (front[t], api[t]) for t in set(front) & set(api) if front[t] != api[t]}
    assert not ecarts, (
        "Le front et l'API ne donnent pas la même icône à ces types : "
        + ", ".join(f"{t} → front={f!r} api={a!r}" for t, (f, a) in sorted(ecarts.items()))
        + ".\nUn utilisateur reconnaît un dessin, il ne relit pas une table : "
        "le geste et son résultat doivent porter le même signe."
    )


def test_le_commentaire_porte_la_bulle():
    """La valeur elle-même, pas seulement l'accord entre les deux.

    Deux tables d'accord sur une valeur fausse resteraient vertes au test
    précédent. Celui-ci fixe le fait constaté à l'écran : le bouton dit
    « 💬 Commenter », donc l'entrée qu'il produit porte 💬.
    """
    bulle = "💬"
    assert _icones_front().get("commentaire") == bulle
    assert _icones_api().get("commentaire") == bulle


# ── Ce que l'API ÉCRIT, et ce que le front sait rendre (#2947) ─────────────────
#
# 🔴 Le test ci-dessus ne compare que les types présents DES DEUX CÔTÉS : un type
# que l'API écrit et que le front ignore lui échappait. C'était le cas de
# `relance` (repli silencieux sur l'icône du commentaire) et de `synthese` dans
# `MOTIFS_EVOLUTION` (repli sur « Du nouveau ») — deux replis justes, mais que
# rien n'avait décidés. Le socle, `standards/11` §13 : un contrat producteur ⇆
# consommateur se contrôle dans les deux sens.
#
# Le producteur n'a pas de liste : les types sont des chaînes écrites à chaque
# `TicketEvolution(type=…)`. Ces tests les énumèrent sur l'arbre de `app/`.

#: Les écritures dont le type vient d'une VARIABLE, et la liste qui la borne.
_TYPES_BORNES = {
    #  `POST /tickets/{id}/evolutions` : `body.type`, refusé hors de `TYPES_SAISIS`.
    "routers/tickets/evolutions.py": "TYPES_SAISIS",
}

#: Les types que l'API écrit et qu'`EVOLUTION_ICONE` ne porte pas — le repli, voulu.
_SANS_ICONE_PROPRE = {
    "relance": "une relance au syndic s'inscrit au fil comme une suite (« Relance "
    "syndic n°N ») : la bulle du commentaire, par `evolutionIcone` (24/11/2026)",
}

#: Les types que l'API écrit et que `MOTIFS_EVOLUTION` ne porte pas.
_SANS_MOTIF_PROPRE = {
    "synthese": "le relevé du suivi ne liste que les affaires OUVERTES, et la synthèse "
    "s'écrit à la clôture ; une affaire rouverte reçoit d'abord un changement d'état",
}


def _constantes_chaines() -> dict[str, str]:
    """Les constantes `NOM = "valeur"` des modules de `app/` — pour `type=TYPE_SYNTHESE`."""
    vues: dict[str, str] = {}
    for m in modules_app(minimum=100):
        for n in m.arbre.body:
            if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)
            ):
                vues[n.targets[0].id] = n.value.value
    return vues


def _types_produits() -> set[str]:
    """Chaque type qu'une `TicketEvolution(type=…)` de `app/` peut écrire."""
    constantes = _constantes_chaines()
    produits: set[str] = set()
    inconnus: list[str] = []

    def lire(valeur: ast.expr, module: str, ligne: int) -> None:
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            produits.add(valeur.value)
        elif isinstance(valeur, ast.IfExp):
            lire(valeur.body, module, ligne)
            lire(valeur.orelse, module, ligne)
        elif isinstance(valeur, ast.Name) and valeur.id in constantes:
            produits.add(constantes[valeur.id])
        elif module in _TYPES_BORNES:
            produits.update(getattr(evolutions, _TYPES_BORNES[module]))
        else:
            inconnus.append(f"{module}:{ligne} — {ast.unparse(valeur)}")

    ecritures = 0
    for m in modules_app(minimum=100):
        for n in ast.walk(m.arbre):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "TicketEvolution"
            ):
                for k in n.keywords:
                    if k.arg == "type":
                        ecritures += 1
                        lire(k.value, m.rel, n.lineno)
    assert ecritures >= 10, f"{ecritures} écriture(s) de `TicketEvolution(type=…)` : portée cassée."
    assert not inconnus, (
        "Un type d'évolution vient d'une expression que ce test ne sait pas borner :\n  "
        + "\n  ".join(inconnus)
        + "\nLe dire dans `_TYPES_BORNES`, avec la liste qui le borne."
    )
    return produits


def _couverture(produits: set[str], front: dict[str, str], replis: dict[str, str]) -> list[str]:
    """Les écarts entre ce qui est produit et ce que la table rend, replis compris."""
    ecarts = []
    if manquants := produits - set(front) - set(replis):
        ecarts.append(f"produits sans entrée ni repli déclaré : {sorted(manquants)}")
    if morts := set(front) - produits:
        ecarts.append(f"entrées que l'API ne produit jamais : {sorted(morts)}")
    if inutiles := set(replis) - (produits - set(front)):
        ecarts.append(f"replis déclarés qui ne servent plus : {sorted(inutiles)}")
    return ecarts


def test_les_types_ecrits_par_l_api_sont_enumeres():
    """Le témoin : les cinq types connus au 24/11/2026 sont vus — sinon l'énumération ment."""
    assert {"commentaire", "etat", "reponse", "relance", "synthese"} <= _types_produits()


def test_chaque_type_ecrit_a_son_icone_ou_son_repli_declare():
    """Un type écrit par l'API sans icône prendrait la bulle sans que personne l'ait décidé."""
    ecarts = _couverture(_types_produits(), _icones_front(), _SANS_ICONE_PROPRE)
    assert not ecarts, (
        "`EVOLUTION_ICONE` et les types que l'API écrit divergent — "
        + " ; ".join(ecarts)
        + ". Donner son icône au type, ou déclarer le repli dans `_SANS_ICONE_PROPRE`."
    )


def test_chaque_motif_du_releve_a_son_texte_ou_son_repli_declare():
    """Un motif servi sans texte se lirait « Du nouveau » sans que personne l'ait décidé."""
    produits = _types_produits() | {MOTIF_NOUVELLE}
    ecarts = _couverture(
        produits, table_plate("reporting.ts", "MOTIFS_EVOLUTION"), _SANS_MOTIF_PROPRE
    )
    assert not ecarts, (
        "`MOTIFS_EVOLUTION` et les motifs que le relevé sert divergent — "
        + " ; ".join(ecarts)
        + ". Donner son texte au motif, ou déclarer le repli dans `_SANS_MOTIF_PROPRE`."
    )
