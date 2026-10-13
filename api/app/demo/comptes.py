"""Les comptes de la démo : les quatre personnages et les habitants de la résidence.

Noms INVENTÉS, tous déclarés dans `tests/test_identites_fictives.py` (`FICTIFS`) ;
`app/demo/` est lu comme un jeu de données par ce contrôle. Adresses en
`.invalid` (RFC 2606) : rien ne peut y être livré.

Chaque compte est actif, son adresse vérifiée, et porte un mot de passe ALÉATOIRE
haché qui n'est affiché nulle part : on entre par un personnage (`routers/demo.py`),
jamais par un formulaire.
"""

from __future__ import annotations

import secrets
import unicodedata
from dataclasses import dataclass

from sqlmodel import Session

from app.auth.adresse_compte import normaliser_adresse
from app.auth.jwt import hash_password
from app.demo.patrimoine import Patrimoine
from app.demo.personnages import DOMAINE, PERSONNAGES
from app.models.core import TypeLien, UserLot, Utilisateur
from app.models.roles import RoleUtilisateur, StatutUtilisateur, role_principal

_OCCUPANT = (
    StatutUtilisateur.copropriétaire_résident,
    (RoleUtilisateur.propriétaire, RoleUtilisateur.résident),
)
_BAILLEUR = (StatutUtilisateur.copropriétaire_bailleur, (RoleUtilisateur.propriétaire,))
_LOCATAIRE = (StatutUtilisateur.locataire, (RoleUtilisateur.résident,))


@dataclass(frozen=True)
class Habitant:
    prenom: str
    nom: str
    profil: tuple  #: (statut, rôles) — `_OCCUPANT`, `_BAILLEUR`, `_LOCATAIRE`
    lots: tuple[str, ...]  #: appartements puis parkings, par numéro
    conseil: bool = False


#: Les habitants qui ne sont pas des personnages. Le locataire du lot B21 est le
#: personnage « Locataire » ; son bailleur figure ici.
HABITANTS: tuple[Habitant, ...] = (
    Habitant(prenom="Alice", nom="Mercier", profil=_OCCUPANT, lots=("A01",)),
    Habitant(prenom="Jean", nom="Dupont", profil=_OCCUPANT, lots=("A02", "P03"), conseil=True),
    Habitant(prenom="Odile", nom="Perrin", profil=_OCCUPANT, lots=("A12",)),
    Habitant(prenom="Luc", nom="Faure", profil=_OCCUPANT, lots=("A22",)),
    Habitant(prenom="Nadia", nom="Rossi", profil=_OCCUPANT, lots=("A31",)),
    Habitant(prenom="Paul", nom="Morel", profil=_OCCUPANT, lots=("A32",)),
    Habitant(prenom="Camille", nom="Robin", profil=_OCCUPANT, lots=("B01",)),
    Habitant(prenom="Hélène", nom="Caron", profil=_OCCUPANT, lots=("B02",)),
    Habitant(prenom="Christophe", nom="Renard", profil=_OCCUPANT, lots=("B11", "P04")),
    Habitant(prenom="Élodie", nom="Sorel", profil=_OCCUPANT, lots=("B12",)),
    Habitant(prenom="Marcel", nom="Roy", profil=_OCCUPANT, lots=("C01",)),
    Habitant(prenom="Catherine", nom="Blondel", profil=_OCCUPANT, lots=("C02",), conseil=True),
    Habitant(prenom="Inès", nom="Zeller", profil=_OCCUPANT, lots=("C11",)),
    Habitant(prenom="Pierre", nom="Leroy", profil=_BAILLEUR, lots=("B21",)),
    Habitant(prenom="Anne", nom="Collard", profil=_BAILLEUR, lots=("C21",)),
    Habitant(prenom="Zoé", nom="Dupré", profil=_LOCATAIRE, lots=("C21",)),
)

#: Les lots des personnages (le locataire loue B21, l'administrateur n'en a pas).
LOTS_DES_PERSONNAGES: dict[str, tuple[str, ...]] = {
    "resident": ("A11", "P01"),
    "locataire": ("B21",),
    "conseil-syndical": ("A21", "P02"),
    "administrateur": (),
}


def _adresse(prenom: str, nom: str) -> str:
    brut = f"{prenom}.{nom}".replace(" ", "-")
    sans_accent = unicodedata.normalize("NFD", brut).encode("ascii", "ignore").decode()
    return normaliser_adresse(f"{sans_accent}@{DOMAINE}")


def _lien(statut: StatutUtilisateur) -> TypeLien:
    if statut == StatutUtilisateur.locataire:
        return TypeLien.locataire
    if statut == StatutUtilisateur.copropriétaire_bailleur:
        return TypeLien.bailleur
    return TypeLien.propriétaire


def _compte(session, pat: Patrimoine, *, prenom, nom, adresse, statut, roles, lots) -> Utilisateur:
    valeurs = [r.value for r in roles]
    appartement = next((pat.appartements[n] for n in lots if n in pat.appartements), None)
    habite = statut in (StatutUtilisateur.copropriétaire_résident, StatutUtilisateur.locataire)
    user = Utilisateur(
        prenom=prenom,
        nom=nom,
        email=adresse,
        statut=statut,
        role=role_principal(valeurs, defaut=RoleUtilisateur.résident.value),
        roles_json=",".join(valeurs),
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        actif=True,
        email_verifie=True,
        consentement_rgpd=True,
        onboarding_complete=True,
        batiment_id=appartement.batiment_id if appartement and habite else None,
        etage=appartement.etage if appartement and habite else None,
    )
    session.add(user)
    session.flush()
    numeros = {**pat.appartements, **{p.numero: p for p in pat.parkings}}
    for numero in lots:
        session.add(UserLot(user_id=user.id, lot_id=numeros[numero].id, type_lien=_lien(statut)))
    return user


def poser(session: Session, pat: Patrimoine) -> dict[str, Utilisateur]:
    """Rend les comptes par clé : le code du personnage, ou « Prénom Nom »."""
    comptes = {}
    for code, p in PERSONNAGES.items():
        comptes[code] = _compte(
            session,
            pat,
            prenom=p.prenom,
            nom=p.nom,
            adresse=normaliser_adresse(p.adresse),
            statut=p.statut,
            roles=p.roles,
            lots=LOTS_DES_PERSONNAGES[code],
        )
    for h in HABITANTS:
        statut, roles = h.profil
        if h.conseil:
            roles = (*roles, RoleUtilisateur.conseil_syndical)
        comptes[f"{h.prenom} {h.nom}"] = _compte(
            session,
            pat,
            prenom=h.prenom,
            nom=h.nom,
            adresse=_adresse(h.prenom, h.nom),
            statut=statut,
            roles=roles,
            lots=h.lots,
        )
    session.flush()
    return comptes
