"""La règle de robustesse d'un mot de passe — écrite une fois.

Extraite de `routers/auth.py` le 14/08/2026 avec le bloc « mot de passe » : trois
routes l'appellent, et deux d'entre elles vivent désormais dans un autre fichier.
La laisser dans `auth.py` aurait obligé le second module à importer un nom privé
d'un router, ou — bien pire — à recopier les quatre critères.

Un critère recopié diverge : c'est exactement ce qui produirait un mot de passe
accepté à l'inscription et refusé au changement, sans que rien ne le signale.
"""

import re

from fastapi import HTTPException

#: Publiée aux apps (`contrat/constantes_clients`, #2755) : elles disent ce qui manque
#: avant l'envoi. Le site en tient une copie, `front/src/lib/mots-de-passe.ts`, comparée
#: à celle-ci par `tests/test_longueur_mot_de_passe_front.py` (#2763).
LONGUEUR_MIN_MOT_DE_PASSE = 8

#: Le refus d'un mot de passe actuel faux — changer son mot de passe, changer son
#: adresse : la même épreuve, le même message (#2949).
MOT_DE_PASSE_INCORRECT = "Mot de passe actuel incorrect."


def verifier_robustesse(password: str) -> None:
    """Vérifie la complexité du mot de passe. Lève HTTPException 400 si les critères ne sont pas satisfaits."""
    errors = []
    if len(password) < LONGUEUR_MIN_MOT_DE_PASSE:
        errors.append(f"au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("une lettre majuscule")
    if not re.search(r"\d", password):
        errors.append("un chiffre")
    if not re.search(r"[@$!%*?&#._\-+]", password):
        errors.append("un caractère spécial (@$!%*?&#._-+)")
    if errors:
        raise HTTPException(400, "Le mot de passe doit contenir : " + ", ".join(errors) + ".")


def _est_le_mot_de_passe(saisi: str, condense: str | None) -> bool:
    """`saisi` est-il le mot de passe de ce condensé ? Un condensé absent ou illisible
    ne reconnaît rien : il n'y a pas d'ancien mot de passe à refuser de reprendre."""
    from app.auth.jwt import verify_password

    try:
        return bool(condense) and verify_password(saisi, condense)
    except ValueError:
        return False


def poser_mot_de_passe(
    session,
    utilisateur,
    nouveau: str,
    *,
    jeton_courant: str | None = None,
) -> int:
    """Pose un nouveau mot de passe **et** ferme les sessions qu'il ouvrait.

    🔴 Les deux portes divergeaient jusqu'au 19/09/2026 (#1027). « Mot de passe
    oublié » révoquait toutes les sessions actives ; « changer mon mot de passe »
    ne révoquait rien. Un attaquant qui détenait une session ouverte la
    conservait **sept jours** après que la victime avait changé son mot de passe
    — et la victime croyait avoir refermé la porte.

    Les deux gestes sont le même : *poser un mot de passe*. Ils s'écrivent donc
    ici une fois. C'est l'écriture la plus **stricte** qui l'emporte, et non la
    plus répandue : en sécurité, la minorité prudente gagne
    (`standards/02` §4 bis).

    :param jeton_courant: le jeton de rafraîchissement porté par la requête, s'il
        y en a un. La session qui le présente **survit** ; toutes les autres
        tombent. Sans lui — cas de la réinitialisation, où l'appelant n'est pas
        authentifié — **tout** tombe, ce qui est le comportement voulu : on
        réinitialise parce qu'on craint que quelqu'un d'autre soit entré.
    :return: le nombre de sessions révoquées.

    Les jetons d'accès du compte tombent aussi, sans geste de plus : ils portent
    l'empreinte du condensé, que le nouveau mot de passe change (#1063,
    `jwt.empreinte_du_compte`).

    Un mot de passe posé n'est plus temporaire : le drapeau `mot_de_passe_a_changer`
    tombe ici (#3019) — ailleurs, seulement dans la démo, qui ferme le changement de
    mot de passe (`demo/administrateur.fixer_mot_de_passe`).
    """
    from app.auth.jetons_rafraichissement import revoquer_sessions
    from app.auth.jwt import hash_password

    verifier_robustesse(nouveau)
    #  Un mot de passe TEMPORAIRE (#3019) ne se repose pas tel quel : lu dans un journal,
    #  il resterait valide, drapeau levé.
    if utilisateur.mot_de_passe_a_changer and _est_le_mot_de_passe(
        nouveau, utilisateur.hashed_password
    ):
        raise HTTPException(400, "Choisissez un mot de passe différent du mot de passe temporaire.")
    utilisateur.hashed_password = hash_password(nouveau)
    utilisateur.mot_de_passe_a_changer = False
    #  Une révocation SANS `remplace_le` : l'ancien jeton de l'autre appareil,
    #  s'il revient, est une session fermée, pas un vol (27/09/2026).
    revoquees = revoquer_sessions(session, utilisateur.id, sauf=jeton_courant)
    session.add(utilisateur)
    return revoquees
