"""Un mot de passe TEMPORAIRE se change avant tout autre geste (#3019, décidé le 23/11/2026).

## Pourquoi

Au premier démarrage, le seed crée l'administrateur et l'opérateur de l'installation avec
un mot de passe tiré au sort, écrit au journal du conteneur — la seule voie par laquelle
l'installateur se connecte la première fois (#2973). Un journal se lit par d'autres que
lui, et se conserve : ce mot de passe ne doit servir qu'à en choisir un autre.

## La règle — défaut fermé

Le compte porte `mot_de_passe_a_changer` (posé par le seed, retiré par
`utils/mots_de_passe.poser_mot_de_passe`). Tant qu'il tient, toute route authentifiée
refuse — 403, `detail = {"code": MOTIF, "message": …}` — sauf celles de
`ROUTES_ADMISES` : lire son profil (qui sert le drapeau, et mène l'écran au changement)
et changer son mot de passe. Se déconnecter et renouveler sa session ne prennent pas la
dépendance d'auth : ils restent ouverts sans figurer ici.

La table se lit sur le chemin DEMANDÉ (`chemin_demande`), comme celle des jetons
d'appareil (`auth/jetons_appareil.PORTEES`) : une route absente est refusée. Aucun
routeur ne décide : `auth/deps.get_current_user` — et la cloche, qui lit aussi le cookie
— appelle `exiger_mot_de_passe_change`.

`MOTIF` est publié aux apps (`contrat/constantes_clients`) : le site et les apps
reconnaissent le refus par lui, jamais par le texte du message.

🔒 `tests/test_mot_de_passe_a_changer.py` balaie toutes les routes montées avec un
compte initial du seed ; `tests/test_seed.py` tient le drapeau posé.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

#: Le motif du refus, stable : le site et les apps le reconnaissent.
MOTIF = "mot_de_passe_a_changer"
MESSAGE = "Votre mot de passe est temporaire : choisissez-en un nouveau pour continuer."

#: 🔴 Ce qu'un compte au mot de passe temporaire peut appeler — `(méthode, chemin servi)`.
#: Ajouter une ligne ouvre une route à un mot de passe lu dans un journal.
ROUTES_ADMISES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/auth/me"),
        ("POST", "/auth/change-password"),
    }
)


def chemin_demande(request: Request) -> str:
    """Le chemin DEMANDÉ, tel que l'API le sert — pas celui que déclare le routeur, que
    l'inclusion d'un routeur dans un autre raccourcit."""
    chemin = request.scope.get("path", "")
    racine = request.scope.get("root_path", "")
    return chemin[len(racine) :] if racine and chemin.startswith(racine) else chemin


def exiger_mot_de_passe_change(user, request: Request):
    """Rend le compte, ou lève 403 (`MOTIF`) si son mot de passe est encore temporaire
    et que la route demandée n'est pas de celles qui servent à en changer."""
    if user.mot_de_passe_a_changer and (
        (request.method, chemin_demande(request)) not in ROUTES_ADMISES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"code": MOTIF, "message": MESSAGE}
        )
    return user
