"""Admin — Commandes vigik / télécommande, et audit des liens utilisateur-lot.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

import json

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, NaiveDatetime
from sqlmodel import Session, select
from app.utils.batiments import libelle_batiment_ou, libelle_lot
from app.utils.libelles_lot import SANS_TYPE, libelle_type_lot
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    CommandeAcces,
    Lot,
    StatutCommande,
    TypeLien,
    UserLot,
    Utilisateur,
)
from app.utils import horloge
from app.utils.noms import nom_affiche
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur
from app.utils.types_acces import libelle_statut_commande, libelle_type_acces
from app.utils.cloche import sonner_systeme

router = APIRouter()


# ── Commandes d'accès (vigik / télécommande) ────────────────────────────────


class CommandeAccesEnAttente(BaseModel):
    """Une commande de badge en attente : la ligne, plus ce qui la rend lisible.

    Typée le 05/11/2026 (#2522) : le contrat la déclarait `{}`, et l'app iOS la
    relisait d'après le type du front (`types-administration.ts`).
    """

    id: int
    user_id: int
    lot_id: int
    #: `vigik` ou `telecommande`.
    type: str
    quantite: int
    motif: Optional[str] = None
    statut: StatutCommande
    traite_par_id: Optional[int] = None
    motif_refus: Optional[str] = None
    cree_le: NaiveDatetime
    traite_le: Optional[NaiveDatetime] = None
    #: « Prénom NOM », « ? » quand le compte a disparu.
    demandeur_nom: str
    #: « Parking 12 », « ? » quand le lot a disparu.
    lot: str
    #: « Bât. 4 », `None` pour un lot sans bâtiment.
    batiment: Optional[str] = None


class CommandeTraitee(BaseModel):
    """Ce que rend le traitement d'une commande : son nouvel état."""

    statut: StatutCommande


@router.get("/commandes-acces", response_model=list[CommandeAccesEnAttente])
def list_commandes_acces(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les commandes en attente : la ligne, plus ce qui la rend LISIBLE.

    🔴 Elle rendait la ligne brute (#1679), et l'espace CS lisait un
    demandeur et un lot qu'aucun serveur n'envoyait : une commande en attente
    y faisait tomber le rendu de l'onglet. Enrichie ICI, une fois — comme
    `GET /admin/demandes-profil` —, pour les deux écrans qui la lisent.
    """
    commandes = session.exec(
        select(CommandeAcces)
        .where(CommandeAcces.statut == StatutCommande.en_attente)
        .order_by(CommandeAcces.cree_le)
    ).all()
    result = []
    for cmd in commandes:
        demandeur = session.get(Utilisateur, cmd.user_id)
        lot = session.get(Lot, cmd.lot_id)
        bat = session.get(Batiment, lot.batiment_id) if lot and lot.batiment_id else None
        item = cmd.model_dump()
        item["demandeur_nom"] = nom_affiche(demandeur.prenom, demandeur.nom) if demandeur else "?"
        item["lot"] = libelle_lot(lot) if lot else "?"
        item["batiment"] = libelle_batiment_ou(bat, None)
        result.append(item)
    return result


class CommandeAction(BaseModel):
    action: str  # accepter | refuser
    motif_refus: str | None = None
    #: Les codes des badges remis, s'ils sont connus à l'acceptation (#1194).
    codes: list[str] = []


def _poser_les_badges(session: Session, cmd: CommandeAcces, codes: list[str]) -> None:
    """Une commande acceptée pose ses badges sur le lot commandé (#1194, V3).

    🔴 Elle n'en créait AUCUN : le badge remis au résident n'existait nulle part,
    ni dans sa liste, ni au parc — il fallait le déclarer une seconde fois. Les
    codes se saisissent à l'acceptation quand on les connaît ; sans code, rien
    n'est créé (un badge sans numéro ne désigne aucun objet).
    """
    from app.utils.acces_gestes import _acces_json
    from app.utils.resolution_acces import exiger_code_libre, synchroniser_import
    from app.utils.types_acces import TYPES_ACCES

    type_acces = TYPES_ACCES.get(cmd.type)
    if type_acces is None:
        return
    for code in {c.strip() for c in codes if c and c.strip()}:
        exiger_code_libre(session, type_acces, code)
        objet = type_acces.modele(
            code=code,
            lot_id=cmd.lot_id,
            user_id=cmd.user_id,
            perimetre_cible=_acces_json(session, type_acces, None, cmd.lot_id, cmd.user_id),
        )
        session.add(objet)
        session.flush()
        synchroniser_import(session, type_acces, objet)


@router.post("/commandes-acces/{cmd_id}/traiter", response_model=CommandeTraitee)
def traiter_commande(
    cmd_id: int,
    body: CommandeAction,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    cmd = ou_404(session, CommandeAcces, cmd_id, "Commande")

    cmd.statut = StatutCommande.acceptee if body.action == "accepter" else StatutCommande.refusee
    cmd.traite_par_id = admin.id
    cmd.traite_le = horloge.maintenant()
    cmd.motif_refus = body.motif_refus
    if cmd.statut == StatutCommande.acceptee:
        _poser_les_badges(session, cmd, body.codes)

    sonner_systeme(
        session,
        "sa_demande",
        destinataire_id=cmd.user_id,
        type="vigik",
        titre=f"Commande {libelle_type_acces(cmd.type)} : {libelle_statut_commande(cmd.statut)}",
        corps=body.motif_refus or "Votre demande a été traitée.",
        lien="/mon-lot",
    )
    session.add(cmd)

    # ── Email au demandeur ────────────────────────────────────────────────
    # Les modèles `vigik_accepte` / `vigik_refuse` existaient depuis l'origine
    # sans qu'aucun code ne les envoie : le demandeur n'était prévenu que par une
    # notification dans l'application, qu'il ne voit que s'il l'ouvre. Pour une
    # demande de badge ou de télécommande — un objet qu'il faut ensuite venir
    # retirer — l'e-mail est le canal qui atteint vraiment (01/08/2026).
    accepte = cmd.statut == StatutCommande.acceptee
    demandeur = session.get(Utilisateur, cmd.user_id)
    if demandeur and demandeur.email:
        from app.utils.email import send_email

        ctx_vigik: dict[str, Any] = {
            "destinataire": {"prenom": demandeur.prenom, "nom": demandeur.nom},
            "type": libelle_type_acces(cmd.type),
        }
        if not accepte:
            ctx_vigik["motif"] = body.motif_refus or "Aucun motif précisé."
        background_tasks.add_task(
            send_email,
            code="vigik_accepte" if accepte else "vigik_refuse",
            to=demandeur.email,
            context=ctx_vigik,
            destinataire_id=demandeur.id,
        )

    session.commit()
    return {"statut": cmd.statut}


# ── Audit associations user-lot ─────────────────────────────────────────────


@router.get("/audit/user-lots")
def audit_user_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste toutes les associations user-lot avec détails pour audit.
    Permet de repérer les affectations erronées."""
    rows = session.exec(
        select(UserLot).where(UserLot.actif == True).order_by(UserLot.user_id)  # noqa: E712
    ).all()
    result = []
    for ul in rows:
        user = session.get(Utilisateur, ul.user_id)
        lot = session.get(Lot, ul.lot_id)
        bat = session.get(Batiment, lot.batiment_id) if lot and lot.batiment_id else None
        result.append(
            {
                "user_lot_id": ul.id,
                "user_id": ul.user_id,
                "user_nom": nom_affiche(user.prenom, user.nom) if user else "?",
                "user_statut": valeur(user.statut) if user else "?",
                "lot_id": ul.lot_id,
                "lot_numero": lot.numero if lot else "?",
                "lot_type": valeur(lot.type) if lot else "?",
                #  Le type en clair (#2562) : l'écran d'audit rendait « appartement ».
                "lot_libelle_type": libelle_type_lot(lot.type) if lot else SANS_TYPE,
                "batiment": libelle_batiment_ou(bat, "—"),
                "type_lien": valeur(ul.type_lien),
            }
        )
    return result


# ── Baux dont le locataire n'a pas été rattaché ──────────────────────────────


@router.get("/audit/baux-sans-locataire")
def audit_baux_sans_locataire(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les baux en cours dont aucun COMPTE n'est rattaché au locataire.

    ## 🔴 Pourquoi ce relevé existe (#808, 07/09/2026)

    Le rattachement d'un compte locataire à son bail est automatique, et il se
    fait sur l'**e-mail exact** (`_auto_match_baux_locataire`) : le bail doit
    porter la même adresse que celle de l'inscription. Il échoue donc dès que le
    bailleur a saisi une autre adresse, ou aucune — et surtout **quand le bail
    est créé après l'inscription**, puisque le rapprochement n'a lieu qu'à la
    validation du compte.

    ⚠️ Et il échoue **en silence** : la fonction rend `0`, personne n'est
    prévenu. Côté locataire, cela se voit ainsi — son compte est actif, mais il
    ne voit ni son lot, ni ses badges, ni sa fiche de location.

    Arbitrage du 06/09/2026 : *garder et observer*. Ce relevé est le moyen
    d'observer, et il a répondu le **13/09/2026** : *« tous les baux ont leur
    locataire rattaché »*. Le geste de rattachement manuel et la liste qui devait
    l'alimenter ont donc été **retirés** — une capacité que personne n'éprouve
    n'est pas une capacité, c'est une surface.

    ⚠️ Ce relevé, lui, RESTE : c'est ce qui permettra de rouvrir la question sur
    un fait plutôt que sur une intuition. Et le jour venu, il dira aussi
    **pourquoi** l'auto-match a échoué — un écart d'orthographe, un lot mal
    importé et une vraie ambiguïté n'appellent pas le même remède.

    ## Deux catégories, et les confondre ferait crier sur le cas normal

    - **`compte_probable`** — un compte existe au nom du locataire : le
      rattachement MANQUE, il est rattrapable.
    - **`sans_compte`** — personne ne s'est inscrit sous ce nom. C'est le cas
      **normal** d'un locataire qui n'utilise pas le site, et il ne doit pas se
      lire comme un défaut.
    """
    from app.models.core import LocationBail, StatutBail

    baux = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_id.is_(None),  # type: ignore[union-attr]
            LocationBail.statut != StatutBail.termine,
        )
    ).all()

    #  Les comptes candidats : on cherche par NOM, pas par e-mail — c'est
    #  justement l'e-mail qui a échoué, le redemander ne trouverait rien.
    result = []
    for bail in baux:
        lot = session.get(Lot, bail.lot_id)
        bat = session.get(Batiment, lot.batiment_id) if lot and lot.batiment_id else None
        candidats = []
        if bail.locataire_nom:
            cible = bail.locataire_nom.strip().lower()
            for u in session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all():  # noqa: E712
                if u.nom and u.nom.strip().lower() == cible:
                    candidats.append(
                        {"id": u.id, "nom": nom_affiche(u.prenom, u.nom), "email": u.email}
                    )
        result.append(
            {
                "bail_id": bail.id,
                "lot": libelle_lot(lot) if lot else "?",
                "batiment": libelle_batiment_ou(bat, "—"),
                "locataire_nom": nom_affiche(bail.locataire_prenom, bail.locataire_nom)
                if (bail.locataire_nom or bail.locataire_prenom)
                else "—",
                "locataire_email": bail.locataire_email,
                "date_entree": bail.date_entree,
                #  🔴 La catégorie est calculée ICI, une fois : la laisser à l'écran
                #  en ferait une seconde règle, et deux vues du même relevé pourraient
                #  ranger le même bail dans deux cases.
                "categorie": "compte_probable" if candidats else "sans_compte",
                "candidats": candidats,
            }
        )
    #  Les rattachements manquants d'abord : c'est ce sur quoi on peut agir.
    result.sort(key=lambda r: (r["categorie"] != "compte_probable", r["locataire_nom"]))
    return result


@router.delete("/user-lots/{user_lot_id}")
def supprimer_user_lot(
    user_lot_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Supprime une association user-lot incorrecte.
    Nettoie aussi utilisateurs_json dans les LotImport correspondants pour
    éviter que l'auto-match recrée le lien au prochain passage."""
    ul = ou_404(session, UserLot, user_lot_id, "Association user-lot")
    uid_supprime = ul.user_id
    lot_id_supprime = ul.lot_id
    #  Un locataire qui s'était déclaré sur ce lot rend les badges qu'il s'était
    #  remis : défaire le lien sans eux laisserait le badge « chez le locataire »
    #  d'un lot qui n'en a plus (`utils/rattachement_locataire`).
    if valeur(ul.type_lien) == TypeLien.locataire.value:
        from app.utils.rattachement_locataire import rendre_acces_declares

        rendre_acces_declares(session, uid_supprime, lot_id_supprime)
    session.delete(ul)
    # Retirer ce user de l'utilisateurs_json de tout import lié à ce lot
    from app.models.core import LotImport

    imports_lies = session.exec(select(LotImport).where(LotImport.lot_id == lot_id_supprime)).all()
    for imp in imports_lies:
        users = json.loads(imp.utilisateurs_json or "[]")
        nouveau = [e for e in users if e.get("user_id") != uid_supprime]
        if len(nouveau) != len(users):
            imp.utilisateurs_json = json.dumps(nouveau, ensure_ascii=False)
            session.add(imp)
    session.commit()
    return {"ok": True, "deleted_id": user_lot_id}


@router.get("/audit/reclassement-tickets")
def audit_reclassement_tickets(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les tickets dont la catégorie pourrait être plus juste — PROPOSITION SEULE.

    ## 🔴 Pourquoi ce relevé (#821, 07/09/2026)

    Demandé : *« peux-tu regarder les tickets créés et leur affecter la catégorie
    la plus adéquate ? Me faire une synthèse et me valider avant application. »*

    Quatre catégories sont nées le même jour (Propreté, Espaces verts, Sinistre,
    Étude & travaux) et une a disparu. Les tickets déjà ouverts portent donc des
    catégories choisies dans une liste qui n'existe plus telle quelle — beaucoup
    sont en « Panne » faute de mieux.

    ⚠️ **Rien n'est écrit.** Une reclassification automatique est un pari sur du
    texte libre : ces règles lisent un titre et une description écrits par des
    humains, elles se trompent, et une catégorie fausse posée en silence est pire
    qu'une catégorie approximative assumée. Le relevé propose, quelqu'un tranche.

    C'est le même choix que pour les baux sans locataire ci-dessus — *garder et
    observer* avant d'automatiser.

    ## Ce que `confiance` distingue

    - **haute** — un indice qui ne désigne qu'une chose (« dégât des eaux »,
      « interphone », « élagage »).
    - **moyenne** — un indice qui peut appartenir ailleurs : « eau » se lit dans
      « fuite d'eau chaude », qui est une panne de chauffe-eau ; « badge » peut
      être une commande d'accès, qui a son propre circuit.

    Le tri met les hautes d'abord : ce sont celles qu'on valide d'un coup d'œil.
    """
    from app.models.core import Ticket
    from app.utils.categories_ticket import libelle_categorie
    from app.utils.reclassement_tickets import proposer

    propositions = []
    total = 0
    for tk in session.exec(select(Ticket).order_by(Ticket.cree_le.desc())).all():
        total += 1
        actuelle = str(valeur(tk.categorie))
        suggestion = proposer(tk.titre or "", tk.description or "", actuelle)
        if not suggestion:
            continue
        categorie, confiance, indice = suggestion
        propositions.append(
            {
                "ticket_id": tk.id,
                "numero": tk.numero,
                "titre": tk.titre,
                "statut": str(valeur(tk.statut)),
                "actuelle": actuelle,
                "actuelle_libelle": libelle_categorie(actuelle),
                "proposee": categorie,
                "proposee_libelle": libelle_categorie(categorie),
                "confiance": confiance,
                #  Le mot qui a déclenché la règle : sans lui, on valide à l'aveugle.
                #  C'est la différence entre « fais-moi confiance » et « voilà pourquoi ».
                "indice": indice,
            }
        )

    propositions.sort(key=lambda p: (p["confiance"] != "haute", p["numero"]))
    return {
        "total_tickets": total,
        "propositions": propositions,
        #  Le compte par catégorie proposée : la synthèse tient en une ligne.
        "par_categorie": {
            c: sum(1 for p in propositions if p["proposee"] == c)
            for c in sorted({p["proposee"] for p in propositions})
        },
    }
