"""L'appairage d'un écran de hall, sans saisie sur la télévision (#2770, RFC 8628).

## Le parcours

1. L'écran demande, SANS être authentifié, un code d'appareil (secret, 256 bits) et un
   code court à afficher (`demander`). Les deux expirent au bout de `VALIDITE`.
2. Un membre du conseil, CONNECTÉ, saisit le code court sur le site et choisit le nom et
   le périmètre de l'écran (`confirmer`).
3. L'écran échange son code d'appareil contre son jeton (`echanger`), en interrogeant au
   plus toutes les `intervalle` secondes ; trop tôt, l'intervalle grandit (`ralentir`).
   L'écran naît à cet instant, avec l'empreinte de son jeton, et la demande disparaît.

## Ce qui protège

- **Le code court ne vaut rien sans le geste d'un conseil connecté** : il ne fait que
  désigner une demande. Sa saisie est plafonnée (`LIMITE_SECRET_EPROUVE`), et un code
  faux ne dit pas s'il a existé.
- **Le code d'appareil est un secret** de 256 bits ; il n'est jamais saisi.
- **Rien ne se garde en clair** : les deux codes et le jeton se gardent par leur
  empreinte (`auth/empreinte_jeton`, #1389).
- **L'appairage ne révèle rien de l'installation** (`multi-coproprietes.md` §4.1 bis) :
  ni nom, ni adresse, ni périmètre — l'écran connaît déjà l'adresse qu'on lui a saisie.
- **Une demande anonyme écrit une ligne** : la demande est plafonnée par visiteur
  (`LIMITE_APPAIRAGE`), les échues se purgent à chaque demande, et au-delà de
  `DEMANDES_EN_COURS_MAX` en attente, la demande est refusée.

🔒 `tests/test_ecrans.py`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, delete, func, select

from app.auth.empreinte_jeton import empreinte
from app.auth.jetons_appareil import echeance, nouveau_brut
from app.models.ecrans import AppairageEcran, Ecran

#: La vie d'une demande : le temps de prendre son téléphone et d'ouvrir le site.
VALIDITE = timedelta(minutes=10)
#: L'intervalle imposé entre deux interrogations, et ce qu'ajoute une interrogation pressée.
INTERVALLE = 5
#: Le code court : huit consonnes, sans voyelle (aucun mot), sans lettre ambiguë.
ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"
LONGUEUR_CODE = 8
#: Au-delà, une demande anonyme est refusée : la table ne se remplit pas.
DEMANDES_EN_COURS_MAX = 50


def normaliser_code_court(saisi: str) -> str:
    """`bcdf-ghjk`, `BCDF GHJK` → `BCDFGHJK` : la forme sous laquelle il s'écrit ET se cherche."""
    return "".join(c for c in (saisi or "").upper() if c in ALPHABET)


def presenter_code_court(code: str) -> str:
    """`BCDFGHJK` → `BCDF-GHJK`, tel que l'écran l'affiche."""
    return f"{code[:4]}-{code[4:]}"


def _code_court() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LONGUEUR_CODE))


@dataclass(frozen=True)
class Demande:
    """Une demande émise : les deux codes bruts, rendus UNE fois à l'écran."""

    code_appareil: str
    code_court: str
    expire_dans: int
    intervalle: int


def purger_demandes(session: Session, maintenant: datetime) -> int:
    """Supprime les demandes échues. Ne valide pas la transaction."""
    resultat = session.exec(delete(AppairageEcran).where(AppairageEcran.expire_le <= maintenant))
    return resultat.rowcount or 0


def demander(session: Session, maintenant: datetime) -> Optional[Demande]:
    """Une demande d'appairage neuve, ou `None` si trop sont en attente. Valide la transaction."""
    purger_demandes(session, maintenant)
    en_cours = session.exec(select(func.count()).select_from(AppairageEcran)).one()
    if en_cours >= DEMANDES_EN_COURS_MAX:
        session.commit()
        return None
    code_appareil = nouveau_brut()
    code_court = _code_court()
    while session.exec(
        select(AppairageEcran.id).where(
            AppairageEcran.empreinte_code_court == empreinte(code_court)
        )
    ).first():
        code_court = _code_court()
    session.add(
        AppairageEcran(
            empreinte_code_appareil=empreinte(code_appareil),
            empreinte_code_court=empreinte(code_court),
            cree_le=maintenant,
            expire_le=maintenant + VALIDITE,
            intervalle=INTERVALLE,
        )
    )
    session.commit()
    return Demande(
        code_appareil=code_appareil,
        code_court=presenter_code_court(code_court),
        expire_dans=int(VALIDITE.total_seconds()),
        intervalle=INTERVALLE,
    )


def confirmer(
    session: Session, code_court: str, nom: str, perimetre: str, maintenant: datetime
) -> Optional[AppairageEcran]:
    """Le geste du conseil : la demande de ce code court deviendra l'écran `nom`, sur
    `perimetre`. `None` si le code est inconnu, échu ou déjà confirmé — sans dire lequel.
    Valide la transaction."""
    code = normaliser_code_court(code_court)
    if len(code) != LONGUEUR_CODE:
        return None
    demande = session.exec(
        select(AppairageEcran).where(AppairageEcran.empreinte_code_court == empreinte(code))
    ).first()
    if demande is None or demande.expire_le <= maintenant or demande.confirme_le is not None:
        return None
    demande.nom = nom
    demande.perimetre = perimetre
    demande.confirme_le = maintenant
    session.add(demande)
    session.commit()
    session.refresh(demande)
    return demande


#: Les réponses d'une interrogation qui ne rend pas de jeton (RFC 8628 §3.5).
EN_ATTENTE = "en_attente"  # le conseil n'a pas encore confirmé
RALENTIR = "ralentir"  # trop tôt : l'intervalle a grandi
INCONNU = "inconnu"  # code inconnu ou échu : recommencer l'appairage


def echanger(
    session: Session, code_appareil: str, maintenant: datetime
) -> tuple[Optional[Ecran], Optional[str], Optional[str]]:
    """L'écran échange son code d'appareil. Rend `(écran, jeton brut, None)` une fois la
    demande confirmée — le brut n'est rendu qu'ici —, sinon `(None, None, raison)`.
    Valide la transaction."""
    if not code_appareil:
        return None, None, INCONNU
    demande = session.exec(
        select(AppairageEcran).where(
            AppairageEcran.empreinte_code_appareil == empreinte(code_appareil)
        )
    ).first()
    if demande is None or demande.expire_le <= maintenant:
        return None, None, INCONNU
    trop_tot = demande.interroge_le is not None and maintenant < demande.interroge_le + timedelta(
        seconds=demande.intervalle
    )
    demande.interroge_le = maintenant
    if trop_tot:
        demande.intervalle += INTERVALLE
    if trop_tot or demande.confirme_le is None:
        session.add(demande)
        session.commit()
        return None, None, RALENTIR if trop_tot else EN_ATTENTE
    brut = nouveau_brut()
    ecran = Ecran(
        nom=demande.nom or "",
        perimetre=demande.perimetre or "",
        cree_le=maintenant,
        empreinte=empreinte(brut),
        expire_le=echeance("ecran", maintenant),
    )
    session.add(ecran)
    session.delete(demande)
    session.commit()
    session.refresh(ecran)
    return ecran, brut, None
