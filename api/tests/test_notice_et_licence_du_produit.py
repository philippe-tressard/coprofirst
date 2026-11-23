"""`NOTICE.md` dit le projet tel qu'il est, et le code ne prête au produit aucune autre licence (#2916, #2958).

## Pourquoi (audit du 23/11/2026)

Trois textes publics avaient dérivé sans qu'un contrôle le voie :

- la section « Composants sous licence non permissive » de `NOTICE.md` RECOPIAIT
  quatre composants à la main, avec une date d'analyse — et ignorait les trois
  arrivés depuis (`psycopg`, `libheif`, `lightningcss`), alors que l'inventaire
  généré (`docs/licences-tierces.md`) les portait ;
- l'en-tête de `NOTICE.md` donnait pour site du projet l'installation d'une
  résidence, et non le site du logiciel (`utils/plateforme.SITE_PLATEFORME`) ;
- une docstring de test disait le produit « réutilisable sous licence MIT » : il
  ne l'a jamais été. `test_gouvernance_depot.py` ne lit que les cinq fichiers de
  gouvernance — le reste du dépôt, public lui aussi, n'était lu par personne.

La liste des exceptions vit en un seul endroit, `scripts/ci/licences_politique.py`,
d'où l'inventaire la tire : `NOTICE.md` y renvoie, il ne la recopie plus.
"""

from __future__ import annotations

import pathlib
import re
import sys

_RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "scripts" / "ci"))

from licences_politique import BIBLIOTHEQUES_SYSTEME, EXCEPTIONS  # noqa: E402
from tests.test_gouvernance_depot import LICENCES_NON_ACCORDEES  # noqa: E402

NOTICE = _RACINE / "NOTICE.md"
SECTION_NON_PERMISSIVE = "### Composants sous licence non permissive"
INVENTAIRE = "docs/licences-tierces.md"

#: Ce qui désigne le PRODUIT dans une phrase. Suivi, à moins de quarante
#: caractères, de « licence » et d'une licence que le dépôt n'accorde pas, c'est
#: le défaut de la docstring du 19/09/2026.
_PRODUIT = r"\b(?:produit|projet|d[ée]p[ôo]t|logiciel|CoproFirst)\b"
_LICENCE_ETRANGERE = (
    _PRODUIT
    + r"[^\n]{0,40}\blicence\s+(?:"
    + "|".join(re.escape(nom) for nom in LICENCES_NON_ACCORDEES)
    + r")\b"
)

#: Où le code et sa documentation parlent du produit.
_PORTEE = ("api/app", "api/tests", "scripts", "front/src", "deploiement", "docs")
_SUFFIXES = {".py", ".ts", ".svelte", ".sh", ".md", ".js", ".mjs", ".yml"}

#: Les fichiers qui nomment LÉGITIMEMENT une licence étrangère près du mot
#: « projet » ou « dépôt » : l'inventaire des tiers, et ce contrôle-ci (son témoin).
_EXCEPTIONS = {INVENTAIRE, "api/tests/test_notice_et_licence_du_produit.py"}


def _section(texte: str, titre: str) -> str:
    debut = texte.find(f"\n{titre}\n")
    assert debut >= 0, f"NOTICE.md n'a plus de section « {titre} » : INCONNU"
    fin = re.search(r"\n#{2,3} ", texte[debut + len(titre) + 2 :])
    return texte[debut : debut + len(titre) + 2 + fin.start()] if fin else texte[debut:]


def _paquets_declares() -> set[str]:
    """Les noms exacts des paquets que la politique déclare en exception."""
    noms = set()
    for entree in (*EXCEPTIONS, *BIBLIOTHEQUES_SYSTEME):
        noms.update(p for p in entree["paquets"] if "*" not in p)
    return noms


def test_la_section_non_permissive_renvoie_a_l_inventaire_sans_le_recopier():
    """Le défaut exact : quatre composants recopiés, trois oubliés, une date figée."""
    section = _section(NOTICE.read_text(encoding="utf-8"), SECTION_NON_PERMISSIVE)
    paquets = _paquets_declares()
    assert len(paquets) >= 5, f"{len(paquets)} paquets lus dans la politique : INCONNU"

    assert f"]({INVENTAIRE})" in section, (
        f"la section ne renvoie plus à `{INVENTAIRE}`, seule liste à jour des exceptions"
    )
    recopies = sorted(p for p in paquets if re.search(rf"`{re.escape(p)}`", section))
    assert not recopies, (
        f"NOTICE.md recopie des exceptions ({', '.join(recopies)}) : la liste se périme au "
        f"premier composant ajouté — renvoyer à `{INVENTAIRE}`"
    )
    date = re.search(r"\b\d{2}/\d{2}/\d{4}\b", section)
    assert not date, (
        f"la section date une analyse ({date.group(0)}) : elle se périme au premier "
        "composant ajouté ; le statut de chacun vit dans `licences_politique.py`"
    )


def test_le_controle_refuse_la_section_d_avant():
    """Cas témoin : la section du 08/10/2026 est refusée (`standards/04` §2)."""
    fautive = (
        "- **`libsignal` (GPL-3.0)**, tiré par `baileys`.\n"
        "- Côté API : `certifi` (MPL-2.0) et `pyphen`.\n"
        "Leur compatibilité a été analysée le 08/10/2026."
    )
    assert any(re.search(rf"`{re.escape(p)}`", fautive) for p in _paquets_declares())
    assert re.search(r"\b\d{2}/\d{2}/\d{4}\b", fautive)


def test_notice_donne_le_site_du_logiciel():
    """L'en-tête nommait l'installation d'une résidence, pas le site du projet."""
    from app.utils.plateforme import SITE_PLATEFORME

    entete = NOTICE.read_text(encoding="utf-8").split("\n---", 1)[0]
    site = re.search(r"\*\*Site\*\* : <([^>]+)>", entete)
    assert site, "l'en-tête de NOTICE.md ne donne plus de site : INCONNU"
    assert site.group(1) == SITE_PLATEFORME, (
        f"NOTICE.md donne pour site « {site.group(1)} », le logiciel est à « {SITE_PLATEFORME} »"
    )


def _fichiers_portee():
    for dossier in _PORTEE:
        for chemin in (_RACINE / dossier).rglob("*"):
            relatif = chemin.relative_to(_RACINE).as_posix()
            if (
                chemin.suffix in _SUFFIXES
                and chemin.is_file()
                and "node_modules" not in chemin.parts
                and relatif not in _EXCEPTIONS
            ):
                yield relatif, chemin


def test_le_code_ne_prete_au_produit_aucune_autre_licence():
    """« Le PRODUIT, réutilisable sous licence MIT » : une docstring publique, et fausse."""
    lus, fautes = 0, []
    for relatif, chemin in _fichiers_portee():
        lus += 1
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        for trouve in re.finditer(_LICENCE_ETRANGERE, texte, re.I):
            ligne = texte.count("\n", 0, trouve.start()) + 1
            fautes.append(f"  {relatif}:{ligne} : …{trouve.group(0)}…")
    assert lus > 500, f"{lus} fichiers lus : la portée ne voit plus le dépôt (INCONNU)"
    assert not fautes, (
        "Le produit est sous AGPL-3.0-or-later ; ces lignes lui prêtent une autre licence :\n"
        + "\n".join(fautes)
    )


def test_le_motif_refuse_la_docstring_d_avant():
    """Cas témoin, et son contraire : une dépendance sous MIT reste permise."""
    assert re.search(
        _LICENCE_ETRANGERE, "le seed porte le PRODUIT, réutilisable sous licence MIT", re.I
    )
    assert not re.search(
        _LICENCE_ETRANGERE, "HTTP/2 : APNs n'accepte que lui (h2 sous licence MIT).", re.I
    )
