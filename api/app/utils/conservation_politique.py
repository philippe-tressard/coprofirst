"""La politique de confidentialité ANNONCE la conservation des affaires (#2014).

Spec §11, arbitrage 1 : la phrase entre dans le texte servi **le jour où la case
« Conservation des affaires » est cochée**, pas avant — coupée, rien n'est appliqué
et les durées annoncées seraient fictives (`standards/14`). C'est `PUT /config` qui
l'appelle, au passage de la clé d'activation à « 1 ».

- **Idempotente** : déjà annoncée, rien ne change.
- **Jamais de réécriture à l'aveugle** : si le texte a été retouché et que son ancre
  a disparu, il n'est pas touché — le constat (`politique_annonce`) dit alors
  « non annoncée », au lieu de laisser croire le contraire.
- Décocher la case ne la retire pas : ce qui a été archivé reste vrai.
- Le texte modifié repasse « à relire » (`textes_legaux/relecture`, empreinte).
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.seed.contenus_legaux_conservation import AVANT_CONSERVATION, CONSERVATION_AFFAIRES
from app.utils.config_site import ecrire_cle
from app.utils.services import ACTIVE, SERVICE_CONSERVATION, SERVICE_DE_CLE

CLE = "politique_confidentialite"


def _texte_servi(session: Session) -> str:
    """Le texte de la copropriété, à défaut le gabarit (comme `relecture`)."""
    ligne = session.get(ConfigSite, CLE)
    return ligne.valeur if ligne else DEFAULT_LEGAL[CLE]


def politique_annonce(session: Session) -> bool:
    """La politique servie porte-t-elle la phrase ? Mesuré sur le texte, pas supposé."""
    return CONSERVATION_AFFAIRES in _texte_servi(session)


def annoncer(session: Session) -> bool:
    """Insère la phrase avant son ancre ; rend `True` si le texte la porte ensuite.

    Ne valide pas la transaction : l'appelant l'écrit avec la clé d'activation.
    """
    texte = _texte_servi(session)
    if CONSERVATION_AFFAIRES in texte:
        return True
    if AVANT_CONSERVATION not in texte:
        return False
    ecrire_cle(
        session, CLE, texte.replace(AVANT_CONSERVATION, CONSERVATION_AFFAIRES + AVANT_CONSERVATION)
    )
    return True


def apres_ecriture(session: Session, cle: str, valeur: str) -> None:
    """Appelée par `PUT /config` pour chaque clé écrite : coche → annonce."""
    if SERVICE_DE_CLE.get(cle) == SERVICE_CONSERVATION and valeur == ACTIVE:
        annoncer(session)
