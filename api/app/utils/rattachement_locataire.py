"""Le LOCATAIRE dit lui-même ce qu'il loue — d'après le fichier des lots du syndic.

## Pourquoi (signalé à l'écran le 04/10/2026)

Un locataire nomme son propriétaire à l'inscription (`nom_proprietaire`).
`utils/rattachement_bailleur` s'en sert, mais seulement si ce propriétaire a un
**compte** : la plupart n'en ont pas. Le locataire restait alors sans lot ni
badge, son écran lui disant d'attendre un rattachement qui ne viendrait jamais —
alors que le fichier des lots du syndic porte le nom du copropriétaire, et donc
son appartement, sa cave et son parking.

Arbitré le 04/10/2026 : dans « Mes lots », le locataire répond à trois
questions — l'appartement, une cave, un parking — et chaque « oui » le
rattache **immédiatement** au lot, avec **tous** les badges qui vont avec
(Vigik de l'appartement, télécommandes du parking).

## 🔴 Le risque accepté, et ce qui le borne

Se dire locataire d'un lot ouvre ses badges (`utils/porteurs_acces`). Ce module
le borne sans le refuser :

- on ne propose que les lots du copropriétaire **nommé à l'inscription** — un
  nom que l'administration a vu en validant le compte —, désigné par la règle
  des noms des imports (`lot_des_imports.lots_du_nom`, homonymes refusés) ;
- les appartements se limitent au **bâtiment** du profil quand il en reste un ;
- un locataire déjà rattaché (lien ou bail) n'a plus de questions ;
- la réponse ne peut désigner QUE des lots proposés
  (`auth/appartenance.exiger_lots_proposes_au_locataire`) ;
- chaque rattachement est **journalisé** et **signalé** au gestionnaire du
  site, qui le défait d'un geste (`rendre_acces_declares` remet alors les
  badges chez le propriétaire).

## Les badges : « chez le locataire », et en main du locataire

Comme la remise par un bail (`utils/acces_bail.remettre`) : `chez_locataire`
vrai et `user_id` le locataire, mais **sans** `bail_id` — il n'y a pas de bail.
C'est ce qui les reconnaît plus tard : si le propriétaire s'inscrit et pose un
bail pour ce locataire, le bail les **adopte** (`acces_bail.adopter_declares`)
et les rendra à sa fin, comme ceux qu'il aurait remis lui-même.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.copropriete import Lot
from app.models.core import (
    LocationBail,
    StatutAcces,
    StatutBail,
    StatutUtilisateur,
    TypeLien,
    UserLot,
    Utilisateur,
)
from app.utils.journal_securite import journaliser_securite
from app.utils.lot_des_imports import lots_du_nom
from app.utils.mes_batiments import batiments_de_l_utilisateur, invalider_cache
from app.utils.noms import nom_affiche
from app.utils.rattachement_bailleur import deja_rattache, prevenir_gestionnaire
from app.utils.types_acces import TYPES_ACCES
from app.utils.valeurs import valeur

#: Les trois questions, dans l'ordre où elles se posent.
NATURES = ("appartement", "cave", "parking")


def lots_proposes(user: Utilisateur, session: Session) -> dict[str, list[Lot]]:
    """Les lots que ce locataire peut se dire louer, rangés par nature.

    Vide pour tout autre profil, pour un locataire déjà rattaché, et pour un
    nom de propriétaire qui ne désigne personne au fichier des lots.
    """
    vide: dict[str, list[Lot]] = {n: [] for n in NATURES}
    if valeur(user.statut) != StatutUtilisateur.locataire.value or deja_rattache(user, session):
        return vide
    ids = lots_du_nom(session)(user.nom_proprietaire)
    if not ids:
        return vide
    lots = session.exec(select(Lot).where(Lot.id.in_(ids))).all()  # type: ignore[union-attr]
    par_nature = {
        n: sorted((lot for lot in lots if valeur(lot.type) == n), key=lambda lot: lot.numero)
        for n in NATURES
    }
    #  Le bâtiment du profil départage les appartements — sauf s'il n'en laisse
    #  aucun : un bâtiment mal saisi ne doit pas cacher le seul logement.
    batiments = batiments_de_l_utilisateur(user)
    dans_le_batiment = [lot for lot in par_nature["appartement"] if lot.batiment_id in batiments]
    if dans_le_batiment:
        par_nature["appartement"] = dans_le_batiment
    return par_nature


def acces_des_lots(session: Session, lot_ids: list[int]) -> dict[int, dict[str, int]]:
    """Combien de badges de chaque type chaque lot fait remettre — `{lot: {clé: n}}`."""
    compte: dict[int, dict[str, int]] = {
        i: {t.cle: 0 for t in TYPES_ACCES.values()} for i in lot_ids
    }
    for t, objet in _acces_remissibles(session, lot_ids):
        compte[objet.lot_id][t.cle] += 1
    return compte


def _acces_remissibles(session: Session, lot_ids: list[int]):
    """Les badges que la location de ces lots met en main du locataire.

    Un badge perdu n'est chez personne ; un badge déjà remis par un BAIL
    appartient à ce bail, qui le rendra à sa fin.
    """
    if not lot_ids:
        return
    natures = {
        lot.id: valeur(lot.type)
        for lot in session.exec(select(Lot).where(Lot.id.in_(lot_ids))).all()
    }  # type: ignore[union-attr]
    for t in TYPES_ACCES.values():
        for objet in session.exec(
            select(t.modele).where(
                t.modele.lot_id.in_(lot_ids),  # type: ignore[attr-defined]
                t.modele.statut != StatutAcces.perdu,
                t.modele.bail_id == None,  # noqa: E711
            )
        ).all():
            if natures.get(objet.lot_id) in t.types_lot:
                yield t, objet


def lier_locataire(session: Session, user_id: int, lots: list[Lot]) -> dict[str, int]:
    """LA porte qui lie un locataire à des lots : le lien, puis les badges en main.

    ## 🔴 Pourquoi une seule porte (signalé le 27/10/2026)

    Quatre chemins posaient un lien `locataire` — sa déclaration, le nom de son
    bailleur, la résolution d'un import par l'administration, et la validation
    d'office —, et seul le premier remettait les badges : rattaché par un autre,
    le locataire avait son lot mais ni Vigik ni télécommande, et la remise se
    faisait à la main. 🔒 `test_lier_locataire_source_unique.py` refuse un lien
    `locataire` écrit ailleurs.

    Un lien déjà présent n'est pas dupliqué. Ne committe pas.
    """
    for lot in lots:
        existant = session.exec(
            select(UserLot).where(UserLot.user_id == user_id, UserLot.lot_id == lot.id)
        ).first()
        if existant is None:
            session.add(
                UserLot(user_id=user_id, lot_id=lot.id, type_lien=TypeLien.locataire, actif=True)
            )
    #  Ses bâtiments viennent de changer : ce qu'il lit en dépend (`mes_batiments`).
    invalider_cache(user_id)
    remis = {t.cle: 0 for t in TYPES_ACCES.values()}
    for t, objet in _acces_remissibles(session, [lot.id for lot in lots]):
        if objet.chez_locataire and objet.user_id == user_id:
            continue
        objet.chez_locataire = True
        objet.user_id = user_id
        session.add(objet)
        remis[t.cle] += 1
    return remis


def rattacher_lots_declares(
    user: Utilisateur, lots: list[Lot], session: Session, *, d_office: bool = False
) -> dict[str, int]:
    """Rattache le locataire à ces lots — déjà vérifiés comme proposés — et lui en remet les badges.

    `d_office` : c'est la validation du compte qui l'a fait, pas sa réponse
    (`rattacher_d_office`). Ne committe pas : l'appelant le fait.
    """
    remis = lier_locataire(session, user.id, lots)

    numeros = ", ".join(lot.numero for lot in lots)
    #  Des IDENTIFIANTS, jamais un nom : le journal ne porte aucune donnée
    #  personnelle (`test_journal_securite.py`).
    journaliser_securite(
        "rattachement_declare",
        acteur_id=user.id,
        cible_id=user.id,
        detail="lots " + ",".join(str(lot.id) for lot in lots) + (" d'office" if d_office else ""),
    )
    qui = nom_affiche(user.prenom, user.nom)
    if d_office:
        titre = "Locataire rattaché à la validation de son compte"
        phrase = f"{qui} a été rattaché d'office aux lots {numeros} de {user.nom_proprietaire}"
    else:
        titre = "Locataire rattaché sur sa déclaration"
        phrase = f"{qui} s'est déclaré locataire des lots {numeros} de {user.nom_proprietaire}"
    prevenir_gestionnaire(
        session,
        titre,
        f"{phrase}, d'après le fichier des lots, et en a reçu les badges. À défaire si c'est faux.",
    )
    return {"lots": len(lots), **remis}


def _deja_loue(session: Session, lot_ids: list[int], user_id: int) -> bool:
    """Un de ces lots a-t-il déjà un AUTRE locataire — lien actif ou bail en cours ?"""
    autre = session.exec(
        select(UserLot).where(
            UserLot.lot_id.in_(lot_ids),  # type: ignore[union-attr]
            UserLot.user_id != user_id,
            UserLot.type_lien == TypeLien.locataire,
            UserLot.actif == True,  # noqa: E712
        )
    ).first()
    bail = session.exec(
        select(LocationBail).where(
            LocationBail.lot_id.in_(lot_ids),  # type: ignore[union-attr]
            LocationBail.statut != StatutBail.termine,
        )
    ).first()
    return autre is not None or bail is not None


def rattacher_d_office(user: Utilisateur, session: Session) -> int:
    """À la validation du compte : la déclaration se fait seule quand rien n'est ambigu.

    ## Pourquoi (signalé le 27/10/2026)

    Les questions de « Mes lots » attendaient la réponse du locataire, qui ne
    venait pas : les quatre derniers locataires sont restés sans lot ni badge
    jusqu'à un rattachement à la main — que la règle des noms aurait trouvé à
    l'identique. Arbitré : quand le fichier des lots ne désigne qu'UN
    appartement, le locataire est rattaché d'office à tout ce que ce
    copropriétaire possède (appartement, caves, parkings), avec leurs badges.

    Restent aux questions : plusieurs appartements, aucun, ou un lot déjà loué à
    un autre (lien actif ou bail en cours) — on ne retire rien à personne.
    Rend le nombre de lots rattachés. Ne committe pas.
    """
    proposes = lots_proposes(user, session)
    if len(proposes["appartement"]) != 1:
        return 0
    lots = [lot for n in NATURES for lot in proposes[n]]
    if _deja_loue(session, [lot.id for lot in lots], user.id):
        return 0
    rattacher_lots_declares(user, lots, session, d_office=True)
    return len(lots)


def remettre_badges_manquants(user: Utilisateur, session: Session) -> dict[str, int]:
    """Un locataire déjà lié à ses lots, sans bail : les badges qu'il n'a pas encore en main.

    Le rattrapage de « Relancer l'appariement » (#2267) : avant la porte
    unique, un lien posé à la main ou par le bailleur laissait les badges chez
    le propriétaire. Un lot sous bail en cours n'est pas touché — c'est le bail
    qui remet les siens (`acces_bail`). Ne committe pas.
    """
    if valeur(user.statut) != StatutUtilisateur.locataire.value:
        return {}
    sous_bail = {
        b.lot_id
        for b in session.exec(
            select(LocationBail).where(
                LocationBail.locataire_id == user.id, LocationBail.statut != StatutBail.termine
            )
        ).all()
    }
    lot_ids = [
        ul.lot_id
        for ul in session.exec(
            select(UserLot).where(
                UserLot.user_id == user.id,
                UserLot.type_lien == TypeLien.locataire,
                UserLot.actif == True,  # noqa: E712
            )
        ).all()
        if ul.lot_id not in sous_bail
    ]
    if not lot_ids:
        return {}
    lots = session.exec(select(Lot).where(Lot.id.in_(lot_ids))).all()  # type: ignore[union-attr]
    remis = lier_locataire(session, user.id, list(lots))
    if any(remis.values()):
        journaliser_securite(
            "rattachement_declare",
            cible_id=user.id,
            detail="badges remis sur les lots " + ",".join(str(i) for i in sorted(lot_ids)),
        )
    return remis


def rendre_acces_declares(session: Session, user_id: int, lot_id: int) -> None:
    """Défaire : les badges que ce locataire s'était remis sur ce lot reviennent au propriétaire.

    Ceux qui sont en main de ce locataire, hors de tout bail : un badge qu'un
    bail a remis n'est pas touché, c'est la fin du bail qui le rend.
    """
    for t in TYPES_ACCES.values():
        for objet in session.exec(
            select(t.modele).where(
                t.modele.lot_id == lot_id,
                t.modele.user_id == user_id,
                t.modele.chez_locataire == True,  # noqa: E712
                t.modele.bail_id == None,  # noqa: E711
            )
        ).all():
            objet.chez_locataire = False
            objet.user_id = None
            session.add(objet)


__all__ = [
    "NATURES",
    "acces_des_lots",
    "lier_locataire",
    "lots_proposes",
    "rattacher_d_office",
    "rattacher_lots_declares",
    "remettre_badges_manquants",
    "rendre_acces_declares",
]
