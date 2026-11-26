"""Ce que la personne lit avant de demander l'effacement dit ce que fait la purge (#3134).

POURQUOI CE TEST — `CONSEQUENCES` (`utils/demande_suppression.py`) disait les
« badges » effacés, alors que la purge les garde sur leur lot et ne délie que le
nom (étape 8 de `supprimer_compte`, #1194). Il taisait aussi les signalements, les
masques, les baux et l'historique de navigation, qui partent, ainsi que les règles,
les annonces du hall et les questions au règlement, qui restent sans nom. Le texte
est lu au moment où la personne décide.

🔒 Chaque entrée de `CONTENUS_PERSONNELS` (ce qui part) et de `CONTENUS_GARDES`
(ce qui reste sans nom) se rapproche d'un mot du texte, ou se déclare omise avec sa
raison. Une table neuve classée dans l'une des deux fait échouer ce test tant
qu'elle n'est ni dite ni déclarée ; une déclaration qui ne sert plus aussi.
"""

import inspect

from app.utils import suppression_compte
from app.utils.demande_suppression import CONSEQUENCES
from app.utils.suppression_compte import CONTENUS_GARDES, CONTENUS_PERSONNELS

EFFACE, BADGES, GARDE = CONSEQUENCES[0], CONSEQUENCES[1], CONSEQUENCES[2]

#: Ce qui PART → le mot qui le dit dans la première phrase.
DIT_EFFACE: dict[tuple[str, str], str] = {
    ("user_lot", "user_id"): "liens à vos lots",
    ("refresh_token", "user_id"): "sessions",
    ("notification", "destinataire_id"): "notifications",
    ("appareil", "utilisateur_id"): "appareils",
    ("jeton_montre", "utilisateur_id"): "appareils",
    ("commande_acces", "user_id"): "demandes de badge",
    ("demande_modification_profil", "utilisateur_id"): "de modification",
    ("delegation", "mandant_id"): "délégations",
    ("delegation", "aidant_id"): "délégations",
    ("mandat", "bailleur_id"): "mandats",
    ("mandat", "mandataire_id"): "mandats",
    ("location_bail", "bailleur_id"): "baux de vos lots",
    ("petite_annonce", "auteur_id"): "petites annonces",
    ("signalement", "signale_par_id"): "signalements",
    ("masquage_auteur", "masque_par_id"): "masques",
    ("masquage_auteur", "auteur_id"): "masques",
    ("avis", "auteur_id"): "avis",
}

#: Ce qui RESTE sans nom → le mot qui le dit dans la troisième phrase.
DIT_GARDE: dict[tuple[str, str], str] = {
    ("ticket", "auteur_id"): "affaires",
    ("ticket_evolution", "auteur_id"): "affaires",
    ("message_ticket", "auteur_id"): "messages",
    ("document", "publie_par_id"): "documents",
    ("diagnostic_rapport", "publie_par_id"): "rapports",
    ("regle_residence", "cree_par_id"): "règles de la résidence",
    ("annonce_hall", "auteur_id"): "annonces du hall",
    ("sondage", "auteur_id"): "consultations",
    ("vote_sondage", "user_id"): "votes",
    ("commentaire_sondage", "auteur_id"): "réponses dans les échanges",
    ("idee", "auteur_id"): "idées",
    ("question_reglement", "auteur_id"): "questions au règlement",
    ("vote_idee", "user_id"): "soutiens",
    ("reponse_communaute", "auteur_id"): "réponses dans les échanges",
    ("notation_prestataire", "auteur_id"): "évaluations des prestataires",
}

#: Omis à dessein, avec la raison — un résumé n'énumère pas ce qui ne se décide pas.
OMIS: dict[tuple[str, str], str] = {
    ("password_reset_token", "user_id"): "un lien à usage unique, sans contenu",
    ("email_verification_token", "user_id"): "un lien à usage unique, sans contenu",
    ("demande_suppression_compte", "utilisateur_id"): "la demande même que la personne confirme",
    ("evenement", "auteur_id"): "table ancienne, migrée dans les affaires (0212)",
    ("evenement_evolution", "auteur_id"): "table ancienne, migrée dans les affaires (0212)",
    ("delegation", "cree_par_id"): (
        "qui a créé une délégation : la délégation elle-même est dite effacée"
    ),
}


def test_chaque_contenu_est_dit_ou_declare_omis():
    personnels, gardes = set(CONTENUS_PERSONNELS), set(CONTENUS_GARDES)
    non_classes = (personnels | gardes) - set(DIT_EFFACE) - set(DIT_GARDE) - set(OMIS)
    assert not non_classes, f"à dire dans CONSEQUENCES, ou à déclarer dans OMIS : {non_classes}"
    perimes = (set(DIT_EFFACE) - personnels) | (set(DIT_GARDE) - gardes)
    perimes |= set(OMIS) - personnels - gardes
    assert not perimes, f"déclarations qui ne servent plus : {perimes}"


def test_ce_qui_part_est_dit_efface():
    absents = {cle: mot for cle, mot in DIT_EFFACE.items() if mot not in EFFACE}
    assert not absents, absents


def test_ce_qui_reste_est_dit_garde_sans_nom():
    absents = {cle: mot for cle, mot in DIT_GARDE.items() if mot not in GARDE}
    assert not absents, absents
    assert "Ancien résident" in GARDE


def test_les_badges_ne_sont_jamais_dits_effaces():
    """Étape 8 de la purge : les badges restent sur leur lot, seul le nom est délié."""
    assert "badges" not in EFFACE
    assert "restent" in BADGES and "lot" in BADGES
    assert "Les badges RESTENT sur leur lot" in inspect.getsource(suppression_compte)


def test_l_historique_de_navigation_est_dit_efface():
    """`effacer_telemetrie` est la première étape de la purge."""
    assert "effacer_telemetrie(session, user_id)" in inspect.getsource(
        suppression_compte.supprimer_compte
    )
    assert "historique de navigation" in EFFACE
