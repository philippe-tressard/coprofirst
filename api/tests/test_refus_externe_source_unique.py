# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Garde-fou : « un compte externe ne contribue pas » ne s'écrit qu'à UN endroit.

## Le défaut (06/09/2026)

La règle « externe **sauf** conseil syndical ou admin » existait en **cinq
exemplaires**, mot pour mot, au message d'erreur près :

    routers/idees.py                  soumettre une idée
    routers/idees.py                  voter pour une idée
    routers/reponses_communaute.py    répondre
    routers/sondages/participation.py voter à un sondage
    routers/tickets/crud.py           ouvrir un ticket

🔴 **Une règle d'autorisation en cinq exemplaires se durcit une fois sur cinq.**
Le jour où un sixième rôle devra être écarté, où la dérogation du conseil
syndical devra tomber, ou simplement où l'on voudra journaliser ces refus, il
faudra retrouver les cinq — et un oubli ne se voit **jamais** à l'écran : un
refus qui n'a pas lieu ressemble à un accès légitime.

⚠️ Le dépôt a déjà payé ce prix deux fois : `utils/destinataires.py` (quatre
copies jusqu'au 31/08, dont une qui affirmait par écrit être la seule) et
`_require_bailleur`, doublon exact de `require_proprietaire` posé hors du module
central, avec dix-sept endpoints dessus — que la spec documentait comme officiel.

## Ce que ce test vérifie, et ce qu'il ne peut pas vérifier

Il vérifie la **forme** : plus aucun fichier hors du module central ne compose
lui-même la condition. Il ne peut pas vérifier qu'un appelant emploie
`exiger_non_externe` au bon endroit du corps — c'est le rôle des tests de chaque
entité.

Il cherche la **cooccurrence** de `RoleUtilisateur.externe` et de `has_role` dans
un même fichier hors exception : c'est la forme que prend cette règle, et la
chercher ligne à ligne raterait les copies coupées sur plusieurs lignes — ce que
trois des cinq étaient.
"""

from __future__ import annotations

from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#  🔴 Les exceptions sont NOMMÉES, avec leur raison — une tolérance sans raison
#  devient un dépotoir. Le test échoue si l'une cesse de servir (voir plus bas).
EXCEPTIONS = {
    #  Le seul endroit où la règle a le droit de s'écrire.
    "auth/deps.py": "la source unique elle-même",
    #  L'énumération des rôles et leur ordre de priorité : elle NOMME `externe`
    #  sans rien en déduire. La confondre avec la règle d'accès reviendrait à
    #  interdire au modèle de connaître ses propres valeurs.
    #
    #  ⚠️ Le fichier a CHANGÉ le 15/09/2026 : `core.py` a rendu les rôles à
    #  `models/roles.py` (modularité), et l'exception a suivi — parce que ce test
    #  a refusé, en annonçant « exception devenue inutile ». C'est ce qu'on lui
    #  demande : une tolérance nominative doit mourir avec son objet, sans quoi
    #  elle finit par couvrir un fichier qu'elle n'a jamais examiné.
    "models/roles.py": "la définition du rôle et sa priorité, pas une décision",
    #  La règle « statut → rôles » POSE le rôle externe (inscription et changement de
    #  statut, #2161) ; elle n'oppose aucun refus.
    "utils/roles_du_statut.py": "attribution du rôle selon le statut, pas un contrôle",
}


def _sans_commentaires(source: str) -> str:
    """Retire les commentaires : expliquer la règle ne doit pas la violer.

    Ce test-ci en est le premier bénéficiaire — le commentaire posé dans
    `reponses_communaute.py` cite la règle qu'il décrit.
    """
    return "\n".join(ligne for ligne in source.splitlines() if not ligne.lstrip().startswith("#"))


def test_le_refus_des_comptes_externes_ne_se_recopie_pas():
    coupables = []
    for m in modules_app():
        rel = m.rel
        if rel in EXCEPTIONS:
            continue
        source = _sans_commentaires(m.source)
        #  La condition complète, pas la simple mention du rôle : c'est la
        #  DÉCISION qu'on interdit de recopier, pas le vocabulaire.
        if "RoleUtilisateur.externe" in source and "has_role" in source:
            coupables.append(rel)

    assert not coupables, (
        "Le refus opposé aux comptes externes est réécrit dans "
        f"{coupables} — il vit dans `auth/deps.py` (`exiger_non_externe`). "
        "Une règle d'autorisation recopiée se durcit une fois sur N."
    )


def test_la_source_unique_porte_bien_la_regle():
    """⚠️ Le cas zéro : sans lui, supprimer `exiger_non_externe` rendrait le test
    ci-dessus vert par vacuité — plus aucune copie, et plus aucune règle."""
    source = (RACINE / "auth" / "deps.py").read_text(encoding="utf-8")
    assert "def exiger_non_externe(" in source
    assert "RoleUtilisateur.externe" in source
    assert "RoleUtilisateur.conseil_syndical" in source


def test_chaque_exception_sert_encore():
    """Une exception qui ne correspond plus à rien est un oubli, pas une décision."""
    inutiles = []
    for rel, raison in EXCEPTIONS.items():
        chemin = RACINE / rel
        if not chemin.is_file():
            inutiles.append(f"{rel} (fichier absent) — {raison}")
            continue
        if "RoleUtilisateur.externe" not in chemin.read_text(encoding="utf-8"):
            inutiles.append(f"{rel} (ne mentionne plus le rôle) — {raison}")
    assert not inutiles, (
        f"Exceptions devenues inutiles : {inutiles}. Les retirer d'`EXCEPTIONS` — "
        "une tolérance qui ne sert plus finit par en couvrir une qui compte."
    )


def test_les_appelants_emploient_la_fonction():
    """La règle ne doit pas avoir disparu des endroits qui la posaient.

    🔴 Retirer une copie **sans** appeler la fonction laisserait le premier test
    vert et **ouvrirait l'accès** : c'est exactement le mode d'échec qu'une
    factorisation d'autorisation peut produire, et il est silencieux.
    """
    attendus = {
        "routers/idees.py",
        "routers/reponses_communaute.py",
        "routers/sondages/participation.py",
        "routers/tickets/crud.py",
    }
    manquants = [
        rel
        for rel in sorted(attendus)
        if "exiger_non_externe(" not in (RACINE / rel).read_text(encoding="utf-8")
    ]
    assert not manquants, (
        f"{manquants} n'appellent plus `exiger_non_externe` : soit le geste a "
        "disparu, soit le refus avec — et le second ne se voit pas à l'écran."
    )
