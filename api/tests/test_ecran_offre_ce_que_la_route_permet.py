"""Un écran n'offre un geste qu'aux rôles que sa route accepte (#2096).

Relevé en générant la carte des réglages (#2061) : la fiche de la résidence
s'éditait pour `$isCS` — le conseil syndical ET l'administrateur — alors que
`PATCH /copropriete` exige `require_admin`. Un membre du conseil voyait le crayon,
saisissait, enregistrait… et recevait un 403. Rien ne confrontait l'écran à la
route : la règle d'affichage (`#lib/stores/auth`) et la règle d'accès
(`app/auth/deps.py`) sont deux textes.

Le contrôle lit les DEUX : les rôles qu'ouvre le prédicat qui garde le geste dans
le `.svelte` (`GESTES`, déclarés un par un avec leur marqueur), et ceux que la
dépendance de la route montée accepte. Offrir plus qu'elle n'accepte échoue.

⚠️ Il ne voit que ce qui est DÉCLARÉ : un geste neuf dont la route refuse un rôle
que son écran admet s'ajoute à `GESTES`. Le témoin ci-dessous prouve que le
contrôle refuse bien le cas fautif d'origine, et un marqueur introuvable échoue :
un geste retiré de l'écran sans l'être d'ici ne passe pas inaperçu.
"""

from __future__ import annotations

import pathlib
import re
from typing import NamedTuple

from app.main import app
from tests.aides_sources import operations_montees

FRONT = pathlib.Path(__file__).resolve().parents[2] / "front/src"
TOUS = frozenset({"*"})

#: Ce que chaque dépendance d'autorisation (`app/auth/deps.py`) laisse passer.
#: Une dépendance absente d'ici fait échouer le contrôle : elle se déclare.
ROLES_DE_LA_ROUTE = {
    "get_current_user": TOUS,
    "require_admin": frozenset({"admin"}),
    "require_cs_or_admin": frozenset({"conseil_syndical", "admin"}),
}


class Geste(NamedTuple):
    #: ce que l'utilisateur fait, pour le message
    libelle: str
    #: l'écran, sous `front/src`
    ecran: str
    #: l'attribut qui lance le geste, tel qu'il est écrit dans l'écran
    marqueur: str
    methode: str
    #: le chemin monté de la route, sans le préfixe de l'application
    chemin: str


GESTES = [
    Geste(
        "Modifier la fiche de la résidence",
        "routes/(app)/residence/+page.svelte",
        "on:click={startEdit}",
        "PATCH",
        "/copropriete",
    ),
]


def roles_du_magasin() -> dict[str, frozenset[str]]:
    """`$isCS` → {conseil_syndical, admin}, lu dans `#lib/stores/auth.ts`."""
    source = (FRONT / "lib/stores/auth.ts").read_text(encoding="utf-8")
    return {
        nom: frozenset(re.findall(r"'([a-z_]+)'", roles))
        for nom, roles in re.findall(
            r"export const (is\w+) = derived\(currentUser, \(\$u\) => aRole\(\$u, ([^)]*)\)\)",
            source,
        )
    }


def gardes_de(source: str, marqueur: str) -> list[str]:
    """Les conditions des `{#if}` encore ouverts devant `marqueur`."""
    pile: list[str] = []
    motif = r"\{(#if|:else if|:else|/if)\b([^}]*)\}|" + re.escape(marqueur)
    for balise in re.finditer(motif, source):
        if balise.group(0) == marqueur:
            return [c for c in pile if c]
        genre, condition = balise.group(1), balise.group(2).strip()
        if genre == "#if":
            pile.append(condition)
        elif genre == ":else if":
            pile[-1] = condition
        elif genre == ":else":
            pile[-1] = ""
        else:
            pile.pop()
    raise AssertionError(f"marqueur introuvable : {marqueur}")


def roles_offerts(conditions: list[str], magasin: dict[str, frozenset[str]]) -> frozenset[str]:
    """Les rôles qui voient le geste : l'intersection des prédicats POSITIFS qui le gardent.

    Un prédicat inconnu ou une condition composée (`||`) n'est pas analysable : le
    contrôle échoue plutôt que de deviner.
    """
    offerts: frozenset[str] | None = None
    for condition in conditions:
        assert "||" not in condition, f"condition non analysable : {condition}"
        for negation, nom in re.findall(r"(!?)\$(is\w+)", condition):
            if negation:
                continue
            assert nom in magasin, f"prédicat inconnu du magasin : ${nom}"
            offerts = magasin[nom] if offerts is None else offerts & magasin[nom]
    assert offerts is not None, "le geste n'est gardé par aucun prédicat de rôle"
    return offerts


def _noms_des_dependances(dependant) -> list[str]:
    noms: list[str] = []
    for d in dependant.dependencies:
        noms.append(getattr(d.call, "__name__", ""))
        noms.extend(_noms_des_dependances(d))
    return noms


def roles_de_la_route(methode: str, chemin: str) -> frozenset[str]:
    routes = [
        route
        for m, chemin_monte, route in operations_montees(app)
        if m == methode and chemin_monte.removeprefix("/api").rstrip("/") == chemin
    ]
    assert len(routes) == 1, f"{methode} {chemin} : {len(routes)} route(s) montée(s)"
    noms = _noms_des_dependances(routes[0].dependant)
    connus = [n for n in noms if n in ROLES_DE_LA_ROUTE]
    assert connus, f"{methode} {chemin} : aucune dépendance d'autorisation connue ({noms})"
    acceptes = TOUS
    for nom in connus:
        r = ROLES_DE_LA_ROUTE[nom]
        acceptes = r if acceptes == TOUS else (acceptes if r == TOUS else acceptes & r)
    return acceptes


def ecart(geste: Geste, magasin: dict[str, frozenset[str]]) -> frozenset[str]:
    """Les rôles à qui l'écran offre le geste et que la route refusera."""
    source = (FRONT / geste.ecran).read_text(encoding="utf-8")
    offerts = roles_offerts(gardes_de(source, geste.marqueur), magasin)
    acceptes = roles_de_la_route(geste.methode, geste.chemin)
    return frozenset() if acceptes == TOUS else offerts - acceptes


def test_le_controle_refuse_le_cas_fautif_d_origine():
    """Le cas fautif d'abord : `$isCS` devant une route réservée à l'administrateur."""
    magasin = roles_du_magasin()
    marqueur = "on:click={startEdit}"
    fautif = "{#if $isCS && !editing}<button on:click={startEdit}></button>{/if}"
    offerts = roles_offerts(gardes_de(fautif, marqueur), magasin)
    assert offerts - ROLES_DE_LA_ROUTE["require_admin"] == {"conseil_syndical"}
    juste = "{#if $isAdmin && !editing}<button on:click={startEdit}></button>{/if}"
    assert roles_offerts(gardes_de(juste, marqueur), magasin) <= ROLES_DE_LA_ROUTE["require_admin"]


def test_le_magasin_et_la_route_sont_lus():
    magasin = roles_du_magasin()
    assert magasin["isCS"] == {"conseil_syndical", "admin"}
    assert magasin["isAdmin"] == {"admin"}
    assert roles_de_la_route("PATCH", "/copropriete") == {"admin"}


def test_aucun_ecran_n_offre_un_geste_que_sa_route_refuse():
    magasin = roles_du_magasin()
    ecarts = {g.libelle: sorted(ecart(g, magasin)) for g in GESTES if ecart(g, magasin)}
    assert not ecarts, (
        "Un écran offre un geste à un rôle que sa route refuse (403 à l'enregistrement) : "
        f"{ecarts}. Aligner l'écran sur la route (`#lib/stores/auth`), jamais la route sur l'écran."
    )
