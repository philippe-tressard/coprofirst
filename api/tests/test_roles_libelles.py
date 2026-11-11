"""Un rôle et un statut s'écrivent d'UNE façon — des deux côtés de la frontière.

## Pourquoi ce test (#801, 06/09/2026)

La table des libellés existait **sept fois** : trois dans
`routers/admin/utilisateurs.py` (`ajouter_role`, `retirer_role`, `changer_role`),
une dans `utils/reponses.py`, et trois côté front (`admin`, `profil`,
`tableau-de-bord`). Elles avaient dérivé.

    ajouter_role       conseil_syndical → « Membre du Conseil Syndical »
    retirer_role       conseil_syndical → « Conseil Syndical »
    front/admin        copropriétaire_résident → « Copropriétaire Résident »
    front/tableau      copropriétaire_résident → « Copropriétaire résident »

Le même rôle s'annonçait autrement selon qu'on l'attribuait ou qu'on le retirait,
dans deux notifications que **la même personne** reçoit.

🔴 **Chaque table était cohérente avec elle-même** — c'est pourquoi rien ne l'a
vu. Deux copies d'accord entre elles ne prouvent rien (`standards/02` §3 bis) :
il faut une référence, et il n'y en avait pas.

## Ce que ce fichier vérifie, et pourquoi il lit le TypeScript

La duplication front ⇄ API est inévitable (contextes de build disjoints, mémoire
`project_partage_front_api_impossible`). Le seul motif viable est **copie +
concordance exécutée** — celui de `noms.py` / `noms.ts`.

Ce test lit donc `front/src/lib/roles.ts` **en tant que texte** et compare ses
tables aux tables Python. Il échoue si l'une des deux bouge sans l'autre.

⚠️ Il échoue aussi s'il n'arrive pas à lire assez d'entrées : un extracteur qui
ne trouve plus rien conclurait au vert sur zéro comparaison — c'est le « cas
zéro » de `standards/04` §2.
"""

from __future__ import annotations

import re

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.utils.roles_libelles import (
    LIBELLES_ROLE,
    LIBELLES_STATUT,
    libelle_role,
    libelle_statut,
    libelle_statut_court,
)

#  🔴 La lecture du TypeScript vit dans le module PARTAGÉ, et n'est plus
#  recopiée ici : elle l'était — `_table_ts` et `aides_roles_libelles_lecture.table_ts`
#  étaient la même fonction —, dans le fichier même dont l'en-tête du module
#  partagé dit qu'il est né parce que « la lecture était elle-même dupliquée ».
from tests.aides_sources import modules_app
from tests.aides_roles_libelles_lecture import ROLES_TS, table_ts

#  Les chaînes qui ne doivent apparaître QUE dans le module source. Écrites ici
#  une fois, et employées par le garde-fou comme par son cas zéro.
CHAINES_CANONIQUES = (
    "Conseil syndical",
    "Membre du Conseil Syndical",
    "Copropriétaire résident",
    "Copropriétaire bailleur",
)


def _motif_valeur(chaine: str) -> re.Pattern:
    """La chaîne SEULE entre guillemets — `"Conseil syndical"`, pas une phrase.

    C'est ce resserrement qui distingue un libellé posé comme valeur d'une prose
    qui contient les mêmes mots.
    """
    return re.compile("[\"']" + re.escape(chaine) + "[\"']")


def test_les_deux_tables_couvrent_TOUTE_l_enumeration():
    """Un rôle ou un statut sans libellé s'afficherait avec son identifiant brut."""
    for role in RoleUtilisateur:
        assert role.value in LIBELLES_ROLE, f"rôle sans libellé : {role.value}"
    for statut in StatutUtilisateur:
        assert statut.value in LIBELLES_STATUT, f"statut sans libellé : {statut.value}"


def test_une_cle_inconnue_est_rendue_TELLE_QUELLE_jamais_vide():
    """Un libellé manquant doit se voir dans l'interface, pas s'effacer.

    Rendre `""` ferait disparaître l'information au lieu de signaler l'oubli —
    c'est la version « affichage » du faux vert.
    """
    assert libelle_role("role_invente") == "role_invente"
    assert libelle_statut("statut_invente") == "statut_invente"
    assert libelle_role(RoleUtilisateur.conseil_syndical) == "Conseil syndical"
    assert libelle_statut(StatutUtilisateur.copropriétaire_résident) == "Copropriétaire résident"


def test_la_forme_COURTE_ne_dit_pas_si_le_coproprietaire_habite_ou_loue():
    """La divergence assumée de `LIBELLES_STATUT_COURT`, verrouillée.

    Elle n'est pas un oubli : à côté d'une réponse dans un fil, préciser
    « résident » ou « bailleur » révélerait si la personne habite son lot ou le
    loue — sans rapport avec le message. Si quelqu'un « corrige » un jour la
    table courte pour l'aligner sur la longue, ce test le dit.
    """
    assert libelle_statut_court(StatutUtilisateur.copropriétaire_résident) == "Copropriétaire"
    assert libelle_statut_court(StatutUtilisateur.copropriétaire_bailleur) == "Copropriétaire"
    assert libelle_statut(StatutUtilisateur.copropriétaire_résident) != libelle_statut_court(
        StatutUtilisateur.copropriétaire_résident
    )


def test_le_front_ecrit_EXACTEMENT_les_memes_chaines():
    """La moitié qui tient les deux implémentations ensemble."""
    assert ROLES_TS.exists(), f"jumeau front introuvable : {ROLES_TS}"
    source = ROLES_TS.read_text(encoding="utf-8")

    ts_roles = table_ts(source, "ATTRIBUTS_ROLE", "libelle")
    ts_statuts = table_ts(source, "ATTRIBUTS_STATUT", "libelle")

    #  🔴 Cas zéro : sans ce garde, un extracteur cassé rendrait deux dictionnaires
    #  vides et le test passerait au vert en ne comparant rien.
    assert len(ts_roles) >= 5, f"extraction des rôles incomplète : {ts_roles}"
    assert len(ts_statuts) >= 7, f"extraction des statuts incomplète : {ts_statuts}"

    assert ts_roles == LIBELLES_ROLE, (
        "les libellés de RÔLES divergent entre le front et l'API :\n"
        f"  front : {ts_roles}\n  api   : {LIBELLES_ROLE}"
    )
    assert ts_statuts == LIBELLES_STATUT, (
        "les libellés de STATUTS divergent entre le front et l'API :\n"
        f"  front : {ts_statuts}\n  api   : {LIBELLES_STATUT}"
    )


def test_aucun_libelle_de_role_n_est_REECRIT_ailleurs():
    """Le garde-fou contre la huitième écriture.

    ⚠️ **La portée fait partie du contrôle** (`standards/05` §9). Ce test ne
    cherche pas « une table de libellés » en général : il cherche la chaîne
    canonique **posée comme une valeur**, c'est-à-dire seule entre guillemets.

    Sans ce resserrement, il criait sur quatre PHRASES qui contiennent les mêmes
    mots — « Conseil syndical, syndic et admin uniquement » (une description de
    profil), « À la demande du Conseil syndical… » (un texte de la fiche
    arrivant). Un contrôle qui crie sur de la prose finit désarmé, et il aurait
    fallu quatre dérogations pour zéro défaut réel.
    """
    source_unique = "utils/roles_libelles.py"
    motifs = [_motif_valeur(c) for c in CHAINES_CANONIQUES]

    fautifs = []
    for m in modules_app():
        if m.rel == source_unique:
            continue
        for numero, ligne in enumerate(m.lignes, 1):
            nue = ligne.strip()
            #  Un commentaire ne pose pas de libellé — celui qui explique la
            #  suppression de `changer-role` cite justement l'ancienne chaîne.
            if nue.startswith("#") or nue.startswith('"""') or nue.startswith("*"):
                continue
            if any(m.search(ligne) for m in motifs):
                fautifs.append(f"{m.rel}:{numero} — {nue[:80]}")

    assert not fautifs, (
        "un libellé de rôle est réécrit hors de `app/utils/roles_libelles.py` :\n  "
        + "\n  ".join(fautifs)
        + "\n  → employer `libelle_role()` / `libelle_statut()`."
    )


def test_le_garde_fou_REFUSE_bien_une_reecriture():
    """Cas zéro : sans lui, un motif cassé rendrait un vert parfait.

    Les deux sens sont vérifiés — la valeur seule est refusée, la prose qui
    contient les mêmes mots passe.
    """
    motif = _motif_valeur("Conseil syndical")
    assert motif.search('    role = "Conseil syndical"')
    assert motif.search("    badge = 'Conseil syndical'")
    assert not motif.search('    "description": "Conseil syndical, syndic et admin uniquement",')
    assert not motif.search("    À la demande du Conseil syndical, il est rappelé")
