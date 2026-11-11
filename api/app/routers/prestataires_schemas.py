"""Schémas du prestataire et de la lecture d'un contrat — sortis de `routers/prestataires.py`.

Le routeur approchait les 500 lignes, et le contrôle de la création y ajoutait
un validateur : les schémas partent à côté, comme `annonces_hall_schemas` (#1229).
`ContratRead` les a rejoints le 04/11/2026 (#2507), avec ses champs DÉDUITS : la
liste, les archives et la synthèse le lisent. L'entrée d'un contrat et les
notations restent dans le routeur, qui les porte seul.
"""

import json
from datetime import date
from typing import Optional

from pydantic import BaseModel, computed_field, field_validator

from app.models.core import TypePrestataire
from app.schemas_nom_servi import NomServi
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree, AssisteIASortie
from app.utils.equipements import AUTRE
from app.utils.perimetres.arbre import parse_json_perimetres
from app.utils.telephones import telephones_de


class PrestataireContact(BaseModel):
    telephone: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    fonction: Optional[str] = None
    email: Optional[str] = None


class PrestataireContactLu(PrestataireContact, NomServi):
    """Un contact LU : son « Prénom NOM » servi (#2633). Jamais en entrée — le
    contact saisi s'écrit tel quel dans `contacts_json`, sans champ calculé."""


class PrestataireCreate(AssisteIAEntree):
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.maintenance_depannage
    telephone: Optional[str] = None
    email: Optional[str] = None
    #  🔴 FACULTATIFS depuis le 25/09/2026 (#1327) — revirement arbitré à l'écran :
    #  « le contact ne doit pas être obligatoire ». #1229 exigeait la veille un
    #  contact joignable à la création ; la règle et son validateur sont retirés.
    contacts: Optional[list[PrestataireContact]] = None
    adresse: Optional[str] = None
    description: Optional[str] = None


class PrestataireUpdate(AssisteIACorrection):
    nom: Optional[str] = None
    specialite: Optional[str] = None
    type_prestataire: Optional[TypePrestataire] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None
    adresse: Optional[str] = None
    description: Optional[str] = None


class PrestataireRead(AssisteIASortie):
    id: int
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.maintenance_depannage
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: list[PrestataireContactLu] = []
    adresse: Optional[str] = None
    description: Optional[str] = None
    actif: bool
    #: Calculé par `REGLES["prestataire"]` (#1538) — ce que lit l'écran.
    archivee: bool = False
    #  ── Servis au site et à l'app iOS (#2507) ───────────────────────────────
    #: La moyenne de ses avis, au dixième — `None` sans avis (`utils/notes_prestataires`).
    note_moyenne: Optional[float] = None
    nb_notations: int = 0
    #: La plus proche visite prévue de ses contrats en cours — `None` s'il n'en a pas.
    prochaine_visite: Optional[date] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def telephones(self) -> list[str]:
        """Les numéros du champ, découpés sur les virgules et sans doublon (#2633)."""
        return telephones_de(self.telephone)

    class Config:
        from_attributes = True

    @field_validator("contacts", mode="before")
    @classmethod
    def parse_contacts(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        if v is None:
            return []
        return v


class ContratRead(BaseModel):
    id: int
    copropriete_id: int
    #: Rendu tel quel — l'écran l'affiche par `perimetreLabel`, comme partout
    #: ailleurs. La chaîne JSON est parsée par le `field_validator` ci-dessous.
    perimetre_cible: Optional[list[str]] = None
    #: DÉRIVÉ, conservé pour les lectures qui s'y appuient encore.
    batiment_id: Optional[int] = None
    prestataire_id: int

    #  La colonne est du TEXTE, l'API rend une liste.
    #
    #  🔴 Elle DÉLÈGUE à `parse_json_perimetres` au lieu de refaire un
    #  `json.loads` avec son `try` : `schemas.py` en porte déjà deux, qui
    #  divergent **exprès** sur le cas illisible — un ticket retombe sur
    #  « résidence », un document ne rend plus de badge. Un contrat suit la règle
    #  canonique, celle de l'arbre : ce serait la QUATRIÈME écriture, et la
    #  première à oublier pourquoi les trois autres diffèrent.
    _perimetre = field_validator("perimetre_cible", mode="before")(
        classmethod(lambda cls, v: v if isinstance(v, list) else parse_json_perimetres(v))
    )
    type_equipement: str
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    actif: bool
    #: Calculé par `REGLES["contrat"]` (#1538) — ce que lit l'écran.
    archivee: bool = False
    notes: Optional[str] = None
    document_id: Optional[int] = None

    #: L'échéance DÉDUITE, et `reconduit` quand le terme initial est passé.
    #: Non stockées : elles se reportent avec le temps, et une colonne figerait
    #: la valeur au jour du calcul — c'est le défaut corrigé le 29/08/2026, où
    #: « échéance » désignait trois valeurs différentes selon l'écran.
    #: 📖 La règle, ses cas et son historique : `app/utils/echeance_contrat.py`.
    date_fin: Optional[date] = None
    reconduit: bool = False
    #: Terme passé sans reconduction — un mandat de syndic qui a CESSÉ.
    echu: bool = False
    #: 🔴 Le geste ✨ est-il proposable sur ce contrat ?
    #:
    #: C'est le SERVEUR qui répond, pas l'écran. La disponibilité dépend de la
    #: configuration de l'assistant — fournisseur actif, clé posée — et un membre
    #: du conseil syndical n'a aucun accès à cette configuration : lui faire lire
    #: `GET /config/admin` pour afficher une icône serait ouvrir l'administration
    #: pour un détail d'affichage (`standards/03` §1).
    synthese_disponible: bool = False
    #  ── Ce qui s'en DÉDUIT, servi au site et à l'app iOS (#2507) ───────────────
    #  Aucun des deux clients ne le compose (`standards/09` §8, règle 1).
    #: Le début du préavis — trois mois avant le terme (`echeance_contrat`).
    date_preavis: Optional[date] = None
    #: `preavis`, `annee` ou `futur` ; `None` sans terme connu.
    urgence_echeance: Optional[str] = None
    #: La visite prévue est passée — le jour même n'en est pas une.
    en_retard: bool = False
    #: « ↺ Mensuel », « ↺ 2×/an » — vide sans fréquence (`utils/frequence_contrat`).
    frequence_libelle: str = ""
    #: L'équipement que le contrat couvre : le sien, sinon (« autre ») la spécialité
    #: du prestataire (`carnet_entretien.type_equipement_resolu`).
    equipement_effectif: str = AUTRE

    class Config:
        from_attributes = True
