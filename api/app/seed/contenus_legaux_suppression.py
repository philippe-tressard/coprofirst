"""La phrase du point 6 de la politique : ce qu'un compte fait depuis son profil (#2699).

Il y exporte et efface sa télémétrie, et, depuis #2699, y DEMANDE la suppression
de son compte — en plus de la voie écrite, qui reste ouverte même sans compte.

`DROITS_DEPUIS_LE_PROFIL_ANCIEN` est la phrase d'avant, écrite ici pour que la
migration 0332 la remplace EXACTEMENT dans le texte servi (`utils/textes_livres`).
Le délai se compose de la constante que l'API sert (`utils/delais_rgpd`).
"""

from app.utils.delais_rgpd import DELAI_TRAITEMENT_DEMANDE_JOURS

DROITS_DEPUIS_LE_PROFIL_ANCIEN = (
    "Les titulaires d'un compte peuvent aussi passer par la messagerie de "
    "l'application, ou exporter et effacer leurs données depuis leur profil."
)

DROITS_DEPUIS_LE_PROFIL = (
    "Les titulaires d'un compte peuvent aussi passer par la messagerie de "
    "l'application, exporter et effacer leurs données depuis leur profil, et y "
    "<strong>demander la suppression de leur compte</strong>, que l'administration de "
    f"la résidence traite sous {DELAI_TRAITEMENT_DEMANDE_JOURS}\xa0jours au plus."
)
