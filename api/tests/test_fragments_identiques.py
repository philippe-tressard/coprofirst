"""Le texte des modèles d'e-mail ne bouge pas par accident (#959, 15/09/2026).

## Pourquoi une empreinte

`seed/emails/fragments.py` compose désormais la mise en forme des courriels :
les encarts, le cadre de commentaire, les boutons, les titres. C'est ce qui a
supprimé les **17 lignes de HTML** que `tickets.py` et `vie_collective.py`
portaient à l'identique.

🔴 **Mais la factorisation a déplacé le risque.** Avant, changer un encart
demandait de retoucher chaque modèle, un par un — pénible, donc visible. Après,
une ligne modifiée dans `fragments.py` change **tous** les modèles d'un coup.

Et ces modèles vivent **EN BASE**. Le seed ne repose que ce qui manque : un
texte modifié ici n'arrive jamais en production, sauf migration. Le code
afficherait alors une version, la production en enverrait une autre — c'est
exactement le modèle BOUCHON, qui a envoyé « Notification. » pendant des mois
(mémoire `project_modele_email_bouchon`).

## Ce que ce test demande

Qu'un changement de rendu soit **délibéré**. Si l'empreinte bouge :

1. c'est un accident → corriger `fragments.py` ;
2. c'est voulu → écrire la migration qui réécrit les modèles concernés en base
   (cf. 0192 et 0185), **puis** mettre à jour l'empreinte ci-dessous.

⚠️ Il ne remplace pas `test_email_templates.test_les_migrations_disent_la_meme_chose_que_le_seed`,
qui vérifie qu'une migration et le seed concordent. Celui-ci répond à l'autre
question : *« quelqu'un a-t-il changé le rendu sans s'en apercevoir ? »*
"""

from __future__ import annotations

import hashlib

from app.seed import EMAIL_TEMPLATES

#: L'empreinte des 27 modèles — code, objet et corps, dans l'ordre des codes.
#:
#: Posée le 15/09/2026, juste après la factorisation, sur un rendu vérifié
#: identique au caractère près à celui d'avant.
#:
#: ⬇️ Mise à jour le 22/09/2026 (#1101) : les modèles disent « affaire » et non
#: plus « ticket ». Le changement est accompagné de la migration **0203**, qui
#: le porte aux bases existantes — sans elle, le code montrerait une version et
#: la production en enverrait une autre, ce que ce test existe pour empêcher.
#: ⬇️ Mise à jour le 23/09/2026 : le bouton de `publication_syndic` suit le lien
#: fourni par l'appelant (`publication.lien`) — migration **0208**.
#: ⬇️ Mise à jour le 02/10/2026 (#1549) : un modèle AJOUTÉ, `adresse_changement_avis`,
#: posé par le seed ; l'empreinte des 29 autres est inchangée (vérifié en
#: l'écartant du calcul : b5f8b1b1…).
#: ⬇️ Mise à jour le 03/10/2026 : DEUX modèles AJOUTÉS, `ticket_copie_auteur` et
#: `publication_copie_auteur` (la copie à l'auteur cochée SEULE), posés par le seed ;
#: l'empreinte des 31 autres est inchangée (vérifié en les écartant : d1927163…).
#: ⬇️ Mise à jour le 04/10/2026 (#1580) : un modèle AJOUTÉ, `compte_inactif_avertissement`,
#: posé par le seed ; l'empreinte des 33 autres est inchangée (vérifié en
#: l'écartant : ca8db203…).
#: ⬇️ Mise à jour le 05/10/2026 : `ticket_syndic` et `ticket_copie_auteur` portent le
#: bloc des affaires liées sous leur historique — migration **0266**. Les autres
#: modèles sont inchangés (vérifié : seuls ces deux corps diffèrent de HEAD).
#: ⬇️ Mise à jour le 16/10/2026 (#2035) : `relance_syndic` dit le « Point de situation »
#: (résumé de l'assistant) et numérote la relance qui part — migration **0288**.
#: Seul ce corps diffère.
#: ⬇️ Mise à jour le 20/10/2026 (#2082) : `point_conseil_validation` marque les CR
#: « Modifié en révision N » (`a.marque`) — migration **0303** ; et un modèle AJOUTÉ,
#: `point_conseil_valide` (le CR validé, PDF joint), posé par le seed.
EMPREINTE = "a053eab180a4d83d4ff56be610f1a400d69898e4bb92c87782d7568d22e42413"
NOMBRE_ATTENDU = 36  # + ticket_partage, lien_partage (#1357), adresse_changement_avis (#1549),
#  synthese_a_valider (#1643), ticket_copie_auteur, publication_copie_auteur,
#  compte_inactif_avertissement (#1580), point_conseil_validation (#2042),
#  point_conseil_valide (#2082) — AJOUTÉS, donc
#  posés par le seed : aucune migration.


def _empreinte() -> str:
    #  \x1f (séparateur d'unités) : un caractère qui ne peut pas apparaître dans
    #  un gabarit, donc deux découpages différents ne peuvent pas produire la
    #  même chaîne — un `+` naïf le pourrait.
    tout = "\n".join(
        f"{code}\x1f{sujet}\x1f{corps}"
        for code, _libelle, sujet, corps, _desactivable in sorted(EMAIL_TEMPLATES)
    )
    return hashlib.sha256(tout.encode("utf-8")).hexdigest()


def test_le_nombre_de_modeles_est_celui_attendu():
    """🔴 Le cas zéro : une empreinte calculée sur une liste vide serait stable.

    Sans ce contrôle, un `EMAIL_TEMPLATES` qui ne se remplirait plus rendrait une
    empreinte constante — et le test d'à côté passerait au vert en ne mesurant
    rien (`standards/04` §2).
    """
    assert len(EMAIL_TEMPLATES) == NOMBRE_ATTENDU, (
        f"{len(EMAIL_TEMPLATES)} modèles au lieu de {NOMBRE_ATTENDU}. Si c'est "
        "voulu (ajout ou retrait d'un modèle), mets à jour NOMBRE_ATTENDU et "
        "EMPREINTE — et vérifie qu'un modèle AJOUTÉ est bien posé par le seed, "
        "tandis qu'un modèle MODIFIÉ exige une migration."
    )


def test_le_rendu_des_modeles_na_pas_change():
    """L'empreinte des 27 modèles, composée par `fragments.py`."""
    assert _empreinte() == EMPREINTE, (
        "Le texte d'au moins un modèle d'e-mail a changé.\n\n"
        "⚠️ Ces modèles vivent EN BASE, et le seed ne repose que ce qui manque : "
        "ce changement n'arrivera JAMAIS en production sans migration. Le code "
        "montrerait une version, la production en enverrait une autre.\n\n"
        "  • accident (une retouche de `fragments.py`) → corriger ;\n"
        "  • voulu → écrire la migration qui réécrit les modèles concernés "
        "(cf. 0192, 0185), puis mettre à jour EMPREINTE ici.\n\n"
        "Pour voir CE qui a changé : comparer les corps avant/après, le message "
        "d'un hash ne peut pas le dire."
    )
