"""Les erreurs vues par les résidents — comptées, jamais rattachées à un compte (#1631).

## Pourquoi (02/10/2026)

Une erreur JavaScript chez un résident ne laissait AUCUNE trace côté serveur.
Le 16/09/2026, une clé `{#each}` répétée a figé un écran pendant que le serveur
était entièrement vert : la cause ne se lisait que dans la console du
navigateur de qui la subissait.

## Ce qui arrive, et par où

Le navigateur signale, par la file de la mesure d'audience (même route, même
plafond, même refus du profil — `routers/telemetry_collecte.py`), un événement
`action = ACTION_ERREUR` dont `detail` est un CODE court produit par
`codeErreur` (`front/src/lib/telemetry.ts`) : `svelte:each_key_duplicate`,
`HTTP 502 /tickets/#`, `TypeError: Cannot read properties of undefined (…)`.
Jamais un message brut ni une pile d'appels : un message peut porter une saisie.

## Ce qui est stocké

Un COMPTEUR par jour (de Paris), page et code — pas un événement, et sans
identifiant de compte : savoir qu'un écran casse ne demande pas de savoir chez
qui. Il vit dans sa propre table, et non dans `telemetry_event` : toutes les
lectures du tableau de bord y comptent chaque ligne comme une page vue, et un
signalement d'erreur les aurait faussées sans un mot.

Le navigateur ne signale un même couple (page, code) qu'UNE fois par onglet
ouvert : `total` compte donc des onglets touchés, pas des répétitions.

## Durée

`CONSERVATION_JOURS`, purgés par l'agrégation quotidienne
(`telemetry_aggregation`) — ce que dit la politique de confidentialité
(`seed/contenus_legaux.TELEMETRIE_ERREURS`).
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, SQLModel, delete, select

from app.models.telemetrie import ErreurNavigateur
from app.utils import horloge

#: L'action d'un signalement. ⚠️ Tenue à la main avec `ACTION_ERREUR` de
#: `front/src/lib/telemetry.ts` : le front et l'API ne partagent aucun fichier.
ACTION_ERREUR = "erreur"

#: Le code d'un signalement arrivé sans `detail` — le client du site en envoie
#: toujours un ; ce qui arrive vide vient d'ailleurs, et se compte quand même.
CODE_INCONNU = "inconnu"

CONSERVATION_JOURS = 30

#: Les lignes rendues au tableau de bord, les plus fréquentes d'abord.
LIGNES_AFFICHEES = 50


def enregistrer_erreur(session: Session, page: str, code: str | None, instant: datetime) -> None:
    """Compte un signalement — sans `commit`, que fait l'appelant pour tout son lot."""
    jour = horloge.jour_civil(instant).isoformat()
    code = code or CODE_INCONNU
    ligne = session.exec(
        select(ErreurNavigateur).where(
            ErreurNavigateur.jour == jour,
            ErreurNavigateur.page == page,
            ErreurNavigateur.code == code,
        )
    ).first()
    if ligne is None:
        ligne = ErreurNavigateur(
            jour=jour, page=page, code=code, premiere_le=instant, derniere_le=instant
        )
    ligne.total += 1
    ligne.derniere_le = instant
    session.add(ligne)


def synthese_erreurs(session: Session, depuis: date) -> list[dict]:
    """Les erreurs signalées depuis `depuis` (inclus), par page et code.

    ⚠️ Somme, minimum et maximum par couple, jamais une ligne lue telle quelle :
    deux collectes simultanées peuvent créer deux lignes pour le même jour, et
    la synthèse doit les compter ensemble.
    """
    lignes = session.exec(
        select(
            ErreurNavigateur.page,
            ErreurNavigateur.code,
            func.sum(ErreurNavigateur.total).label("total"),
            func.min(ErreurNavigateur.premiere_le),
            func.max(ErreurNavigateur.derniere_le),
        )
        .where(ErreurNavigateur.jour >= depuis.isoformat())
        .group_by(ErreurNavigateur.page, ErreurNavigateur.code)
        .order_by(func.sum(ErreurNavigateur.total).desc())
        .limit(LIGNES_AFFICHEES)
    ).all()
    return [
        {
            "page": page,
            "code": code,
            "total": total,
            "premiere_le": premiere.isoformat(),
            "derniere_le": derniere.isoformat(),
        }
        for page, code, total, premiere, derniere in lignes
    ]


def purger_releves_du_navigateur(session: Session, modele: type[SQLModel], aujourd_hui: date) -> int:
    """Retire les lignes de plus de `CONSERVATION_JOURS` d'un relevé ; rend leur nombre.

    Une règle pour les trois relevés du navigateur — erreurs (`ErreurNavigateur`),
    durées d'affichage (`MesureAffichage`), gestes de formulaire
    (`GesteFormulaire`) : même durée, même colonne `jour` (« AAAA-MM-JJ »). Elle
    s'écrivait trois fois, au modèle près (#2949).
    """
    limite = (aujourd_hui - timedelta(days=CONSERVATION_JOURS)).isoformat()
    resultat = session.exec(delete(modele).where(modele.jour < limite))
    session.commit()
    return resultat.rowcount
