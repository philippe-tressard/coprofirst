"""Le bail du lot B21 et le badge que le bailleur y confie à son locataire (#2027).

Le compte public `user-loc` loue B21 à un habitant du jeu (`comptes.HABITANTS`,
le bailleur de B21) : sans bail, son onglet Badges était vide, et la démo ne
montrait pas « les badges que votre bailleur vous confie », que le site vitrine
annonce au compte Locataire.

Le badge passe par `utils/acces_bail.remettre`, la porte du geste du bailleur
(`routers/bailleur/acces.py`) : jamais un `chez_locataire = True` écrit à la main,
qui laisserait le détenteur et le bail en désaccord. Le bailleur garde l'autre
badge du lot, comme dans la vie.

Le bail est posé sans `adopter_declares` : aucun badge déclaré par le locataire
ne l'attend, le jeu n'en crée pas.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.demo.dates import il_y_a, jour
from app.demo.patrimoine import Patrimoine
from app.models.acces import Vigik
from app.models.core import LocationBail, StatutBail, Utilisateur
from app.utils.acces_bail import remettre

#: Le lot loué au compte public, et la clé de son bailleur dans les comptes du jeu.
LOT_LOUE = "B21"
BAILLEUR = "Pierre"
LOCATAIRE = "user-loc"


def poser(session: Session, pat: Patrimoine, comptes: dict[str, Utilisateur]) -> LocationBail:
    """Après les badges (`acces.poser`) : le bail ne confie que ce qui existe."""
    lot = pat.appartements[LOT_LOUE]
    entree = il_y_a(400)
    bail = LocationBail(
        lot_id=lot.id,
        bailleur_id=comptes[BAILLEUR].id,
        locataire_id=comptes[LOCATAIRE].id,
        date_entree=jour(-400),
        statut=StatutBail.actif,
        cree_le=entree,
        mis_a_jour_le=entree,
    )
    session.add(bail)
    session.flush()
    badge = session.exec(select(Vigik).where(Vigik.lot_id == lot.id).order_by(Vigik.code)).first()
    remettre(badge, bail)
    session.add(badge)
    return bail
