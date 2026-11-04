"""Admin — Annuaire public, composition du conseil syndical et du syndic.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    AgCsInfo,
    ConfigSite,
    MembreCS,
    MembreSyndic,
    SyndicInfo,
    Utilisateur,
)
from app.utils.annuaire import membres_du_conseil, membres_du_syndic, reconcilier_membres
from app.utils.syndic import nom_du_syndic, source_du_nom
from typing import Literal, Optional

router = APIRouter()


# ── Annuaire public ──────────────────────────────────────────────────────────
#
#  Typé le 04/11/2026 (#2505) : le contrat le déclarait `{}`, et l'app iOS le
#  décodait champ par champ d'après le front. Les schémas déclarent EXACTEMENT ce
#  que `utils/annuaire` rendait déjà, plus les règles d'affichage servies — aucune
#  donnée personnelle de plus : `nom_affiche`, `etage_libelle` et `telephones` se
#  déduisent de champs déjà rendus, sous le même droit (tout résident connecté).


class MembreConseilLu(BaseModel):
    """Un membre du conseil syndical, tel que l'annuaire des résidents le montre."""

    id: int
    genre: str
    prenom: str
    nom: str
    #: « Prénom NOM » — `utils/noms.nom_affiche`, la civilité à part (`genre`).
    nom_affiche: str
    batiment_id: Optional[int] = None
    #: Le NUMÉRO du bâtiment (« A »), pas son libellé.
    batiment_nom: Optional[str] = None
    etage: Optional[int] = None
    #: « RDC », « 2ème étage » — `""` sans étage (`utils/etages.etage_label`).
    etage_libelle: str
    est_gestionnaire_site: bool
    est_president: bool
    photo_url: Optional[str] = None


class MembreSyndicLu(BaseModel):
    """Un interlocuteur du syndic, tel que l'annuaire des résidents le montre."""

    id: int
    genre: str
    prenom: str
    nom: str
    nom_affiche: str
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    #: Les numéros du champ, découpés sur les virgules (`utils/telephones`).
    telephones: list[str]
    est_principal: bool
    photo_url: Optional[str] = None


class ConseilLu(BaseModel):
    ag_annee: Optional[int] = None
    #: La date de l'AG qui a élu le conseil, ISO.
    ag_date: Optional[str] = None
    #: Classés comme l'écran les montre : bâtiment, civilité, puis nom.
    membres: list[MembreConseilLu]


class SyndicLu(BaseModel):
    #: Celui du contrat désigné, sinon la saisie ; `""` si ni l'un ni l'autre.
    nom_syndic: str
    nom_syndic_source: Literal["contrat", "saisie", "aucune"]
    adresse: str
    site_web: Optional[str] = None
    membres: list[MembreSyndicLu]


class AnnuaireLu(BaseModel):
    """L'annuaire des résidents : le conseil, le syndic, le groupe WhatsApp."""

    cs: ConseilLu
    syndic: SyndicLu
    whatsapp_url: Optional[str] = None


@router.get("/annuaire", response_model=AnnuaireLu)
def annuaire(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Équipe accessible à tous les résidents : membres CS + syndic depuis les tables dédiées."""
    # ── CS ──
    ag = session.exec(select(AgCsInfo)).first()
    #  La composition vient de `utils/annuaire` : elle était écrite ici ET dans
    #  la fiche d'accueil, à trente et une lignes identiques — et les deux avaient
    #  déjà divergé (#852). Le module dit sur quoi.
    cs_out = membres_du_conseil(session)

    # ── Syndic ──
    syndic_info = session.exec(select(SyndicInfo)).first()
    syndic_membres_out = membres_du_syndic(session)

    return {
        "cs": {
            "ag_annee": ag.ag_annee if ag else None,
            "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
            "membres": cs_out,
        },
        "syndic": {
            #  🔴 Le CONTRAT fait foi (#535) : le nom vivait ici en texte libre
            #  ET dans `syndic_contrat_id → ContratEntretien → Prestataire.nom`.
            #  Changer de syndic dans Prestataires ne mettait à jour ni cet
            #  écran ni la fiche arrivant. Une seule source désormais.
            "nom_syndic": nom_du_syndic(session),
            #  L'écran doit savoir si la saisie sert encore : un champ sans
            #  effet qui ne le dit pas fait corriger un texte que personne ne lit.
            "nom_syndic_source": source_du_nom(session),
            "adresse": syndic_info.adresse if syndic_info else "",
            "site_web": syndic_info.site_web if syndic_info else None,
            "membres": syndic_membres_out,
        },
        "whatsapp_url": (
            session.exec(
                select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")
            ).first()
            or ConfigSite(cle="", valeur="")
        ).valeur
        or None,
    }


# ── Annuaire CS — gestion (CS + admin) ──────────────────────────────────────


class MembreCSIn(BaseModel):
    #  🔴 L'IDENTIFIANT, ajouté le 31/08/2026. Le front le renvoyait DÉJÀ — il
    #  repasse la liste telle que le GET la lui a donnée — et ce schéma le jetait
    #  en silence. Sans lui, le PUT ne peut pas savoir qui est qui, et il ne lui
    #  reste qu'à tout supprimer puis tout recréer. Voir `put_composition_cs`.
    id: Optional[int] = None
    genre: str
    prenom: str
    nom: str
    batiment_id: Optional[int] = None
    etage: Optional[int] = None
    est_president: bool = False
    user_id: Optional[int] = None


class CompositionCSIn(BaseModel):
    ag_annee: Optional[int] = None
    ag_date: Optional[str] = None  # ISO "YYYY-MM-DD" ou None
    whatsapp_url: Optional[str] = None
    membres: list[MembreCSIn] = []


@router.get("/annuaire/cs")
def get_composition_cs(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    ag = session.exec(select(AgCsInfo)).first()
    return {
        "ag_annee": ag.ag_annee if ag else None,
        "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
        "whatsapp_url": (
            session.exec(
                select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")
            ).first()
            or ConfigSite(cle="", valeur="")
        ).valeur
        or "",
        #  La composition vient de `utils/annuaire`, comme pour l'écran des
        #  résidents six lignes plus haut. Elle était REFAITE ici — avec son
        #  propre cache de bâtiments et sa propre écriture de la règle du
        #  gestionnaire de site — dans le fichier même qui importe la fonction
        #  et qui explique pourquoi elle existe (#779, 18/09/2026).
        "membres": membres_du_conseil(session, pour_administration=True),
    }


@router.put("/annuaire/cs")
def put_composition_cs(
    body: CompositionCSIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Valider qu'il y a au maximum 1 président
    presidents_count = sum(1 for mb in body.membres if mb.est_president)
    if presidents_count > 1:
        raise HTTPException(
            status_code=400, detail="Il ne peut y avoir qu'un seul président du Conseil Syndical."
        )

    # Upsert AgCsInfo
    from datetime import date as date_type

    ag = session.exec(select(AgCsInfo)).first()
    if ag is None:
        ag = AgCsInfo()
        session.add(ag)
    ag.ag_annee = body.ag_annee
    ag.ag_date = date_type.fromisoformat(body.ag_date) if body.ag_date else None

    # WhatsApp URL
    wa_cfg = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")
    ).first()
    if wa_cfg is None:
        wa_cfg = ConfigSite(cle="whatsapp_community_url", valeur="")
        session.add(wa_cfg)
    wa_cfg.valeur = body.whatsapp_url or ""

    #  ── RÉCONCILIER, et surtout pas remplacer ────────────────────────────
    #
    #  🔴 Ce bloc supprimait les sept lignes et les recréait à chaque
    #  enregistrement (31/08/2026) : *« je n'ai modifié que Christine VERDIÈRE
    #  et ça a ajouté tous les membres du CS qui n'ont pas été modifiés »*. La
    #  règle vit dans `utils/annuaire.reconcilier_membres`, prise aussi par le
    #  syndic — qui avait gardé le remplacement jusqu'au 09/10/2026.
    reconcilier_membres(session, MembreCS, body.membres)

    session.commit()
    return {"ok": True}


# ── Annuaire Syndic — gestion (CS + admin) ──────────────────────────────────


class MembreSyndicIn(BaseModel):
    #  L'identifiant, comme `MembreCSIn` : sans lui le PUT ne sait pas qui est
    #  qui et recrée tout le monde (09/10/2026, voir `reconcilier_membres`).
    id: Optional[int] = None
    genre: str
    prenom: str
    nom: str
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    est_principal: bool = False
    user_id: Optional[int] = None


class SyndicIn(BaseModel):
    nom_syndic: str = ""
    adresse: str = ""
    site_web: Optional[str] = None
    membres: list[MembreSyndicIn] = []


@router.get("/annuaire/syndic")
def get_syndic_info(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    syndic = session.exec(select(SyndicInfo)).first()
    return {
        "nom_syndic": nom_du_syndic(session),
        "nom_syndic_source": source_du_nom(session),
        "adresse": syndic.adresse if syndic else "",
        "site_web": syndic.site_web if syndic else None,
        "membres": membres_du_syndic(session, pour_administration=True),
    }


@router.put("/annuaire/syndic")
def put_syndic_info(
    body: SyndicIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Upsert SyndicInfo
    syndic = session.exec(select(SyndicInfo)).first()
    if syndic is None:
        syndic = SyndicInfo()
        session.add(syndic)
    #  🔴 La saisie n'écrase PAS le repli quand le contrat fait foi (#535).
    #
    #  L'écran désactive le champ dans ce cas, et renvoie donc la valeur qu'il a
    #  reçue — celle du CONTRAT. L'enregistrer ici remplacerait la saisie
    #  d'origine par le nom du contrat : le repli cesserait d'être un repli, et
    #  retirer le contrat plus tard ferait réapparaître une valeur qui n'a jamais
    #  été saisie.
    #
    #  ⚠️ La règle vit ICI et pas dans l'écran : un second écran, ou un appel
    #  direct, contournerait un garde posé côté front. C'est le serveur qui
    #  décide de ce qu'il écrit.
    if source_du_nom(session) != "contrat":
        syndic.nom_syndic = body.nom_syndic
    syndic.adresse = body.adresse
    syndic.site_web = body.site_web

    #  Réconcilier, jamais remplacer : un membre inchangé garde son `cree_le`,
    #  et le fil n'annonce que les vraies arrivées (09/10/2026).
    reconcilier_membres(session, MembreSyndic, body.membres)

    session.commit()
    return {"ok": True}
