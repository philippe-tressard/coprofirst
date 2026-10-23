"""Router documents — bibliothèque documentaire avec contrôle d'accès 3 couches."""

import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.config_site import config_site
from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import est_moderateur, get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CategorieDocument,
    ContratEntretien,
    Document,
    ProfilAccesDocument,
    Utilisateur,
)
from app.routers.documents_schemas import DocumentRead
from app.utils.annexes import (
    PORTEURS,
    porteurs_demandes,
    retirer_fichier_principal,
    supprimer_annexes,
    verifier_porteur,
)
from app.utils.fichiers import enregistrer_televersement
from app.utils.stockage import stockage
from app.utils.html_sur import html_riche

# Toute règle de visibilité — documents compris — vient du module central.
from app.utils.visibility import document_visible, peut_ecrire_dans, profil_admet
from app.utils.liens import adresse_du_site
from app.utils.liens import nom_site
from app.utils.recuperer import connu_ou_404, fichier_ou_404, ou_404
from app.utils.cloche import sonner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# La règle d'accès aux documents est `document_visible` (app/utils/visibility.py),
# avec toutes les autres règles de visibilité. Ce router l'appelle, il ne la redéfinit
# pas et ne l'aliase pas : un seul nom, un seul endroit.


def _notifier_document_publie(
    doc: Document,
    auteur: Utilisateur,
    background_tasks: BackgroundTasks,
    session: Session,
) -> None:
    """Prévient les résidents qui ont le droit de voir ce document.

    Le modèle `document_publie` existait depuis l'origine sans qu'aucune ligne
    ne l'envoie. Ce n'était pas un modèle mort : le manuel recommande
    « documents = e-mail » et le profil affiche la ligne « Nouveaux documents
    ajoutés » avec ses deux cases. Les deux canaux étaient promis, aucun n'était
    branché — la préférence se réglait dans le vide.

    **Le périmètre de diffusion est celui de la lecture, pas un autre.** La
    liste des destinataires est filtrée par `document_visible`, la même
    fonction que l'endpoint de téléchargement : une notification qui annonce un
    document qu'on ne peut pas ouvrir est au mieux une frustration, au pire la
    divulgation d'un titre confidentiel. Réutiliser la règle plutôt que de la
    réécrire garantit qu'un durcissement ultérieur profite aux deux.

    Envois **individuels** et non groupés : `send_email_group` place tous les
    destinataires en TO, où ils se voient les uns les autres. Le dépôt ne s'en
    sert que pour des groupes internes de quelques personnes (syndic, conseil
    syndical) ; diffuser ainsi à toute la résidence exposerait le carnet
    d'adresses des copropriétaires à chacun d'eux.
    """
    from app.utils.email import send_email
    from app.utils.documents import lien_document

    # Une pièce jointe d'actualité et un document de contrat ne sont pas des
    # publications documentaires : la première est annoncée par l'e-mail de sa
    # publication, le second ne concerne que le CS, déjà à la manœuvre.
    if not doc.categorie_id:
        return

    cfg = config_site(session)
    site_nom = nom_site(cfg.get("site_nom"))
    site_url = adresse_du_site()

    destinataires = session.exec(
        select(Utilisateur).where(Utilisateur.actif == True)  # noqa: E712
    ).all()

    # Ni ici ni dans le modèle l'URL n'est écrite à la main : `/documents`
    # n'existe pas côté front, et c'est exactement la faute qui a produit un 404
    # en pleine page le 26/07/2026. La table `EMPLACEMENTS` sait où vit un
    # document, et `test_liens_front.py` vérifie qu'elle dit vrai.
    #
    #  🔴 `lien_element("doc", doc.id)` SANS CONDITION jusqu'au 09/09/2026 — et
    #  seules TROIS des dix catégories ont une rubrique sur /residence. Les sept
    #  autres — fiche synthétique, attestation, diagnostic, contrats, devis,
    #  document interne — partaient donc avec un lien vers une page où elles ne
    #  sont pas listées : la page bonne, l'élément invisible. C'est le défaut du
    #  28/07/2026 un cran plus loin, et le fil d'actualité savait déjà l'éviter.
    #
    #  ⚠️ PAR DESTINATAIRE, et non une fois pour toute la liste : `lien_document`
    #  dépend de qui regarde.
    for u in destinataires:
        if u.id == auteur.id or not document_visible(u, doc, session):
            continue
        lien_doc = lien_document(doc, u, session)
        sonner(
            session,
            destinataire_id=u.id,
            type="document",
            titre=f"Nouveau document : {doc.titre}",
            #  🔴 `corps=doc.titre` REPÉTAIT le titre, qui est déjà juste au-dessus :
            #  la notification occupait deux lignes pour dire une fois la même
            #  chose. La description, ajoutée le 08/09/2026, dit ce que le document
            #  couvre — c'est exactement ce qu'un corps doit porter. Le titre reste
            #  le repli quand elle est vide (09/09/2026).
            corps=doc.description or doc.titre,
            lien=lien_doc,
        )
        if not u.email:
            continue
        background_tasks.add_task(
            send_email,
            code="document_publie",
            to=u.email,
            context={
                #  `description` transmise depuis le 09/09/2026 : le modèle
                #  l'affiche sous le titre quand elle existe (migration 0185).
                "document": {
                    "titre": doc.titre,
                    "description": html_riche(doc.description),
                    "lien": lien_doc,
                },
                "residence": {"nom": site_nom},
                "app": {"url": site_url},
            },
            session=session,
            # Sans cet identifiant, le profil (`utils/preferences_mail`) ne serait
            # pas consulté : ses cases resteraient décoratives.
            destinataire_id=u.id,
        )
    session.commit()


@router.get("/categories")
def list_categories(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne les catégories de documents actives accessibles à l'utilisateur."""
    cats = session.exec(
        select(CategorieDocument)
        .where(CategorieDocument.actif == True)  # noqa: E712
        .order_by(CategorieDocument.libelle)
    ).all()

    # CS et admin voient toutes les catégories — sauf, pour le CS, celles que
    # l'administration seule lit (`CATEGORIES_ADMIN_SEUL`). Les autres : celles dont
    # le profil admet le lecteur — la règle de `document_visible`, appelée (#1551).
    def lisible(c: CategorieDocument) -> bool:
        if est_moderateur(user):
            return peut_ecrire_dans(user, c)
        return profil_admet(user, session.get(ProfilAccesDocument, c.profil_acces_id))

    return [{"id": c.id, "code": c.code, "libelle": c.libelle} for c in cats if lisible(c)]


@router.get("", response_model=list[DocumentRead])
def list_documents(
    categorie_id: int | None = None,
    #  …ou par son CODE : Ma résidence n'attend plus les catégories (#1841).
    categorie: str | None = None,
    contrat_id: int | None = None,
    ticket_id: int | None = None,
    evenement_id: int | None = None,
    #  Les annexes d'une fiche de Ma résidence (migration 0276, `utils/annexes`).
    document_parent_id: int | None = None,
    diagnostic_rapport_id: int | None = None,
    regle_residence_id: int | None = None,
    #  Toutes les annexes d'une RUBRIQUE (`document`, `diagnostic`, `regle`) en
    #  un appel : l'écran les range sous leurs fiches, au lieu d'un appel par carte.
    annexes_de: str | None = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Document)
    if annexes_de:
        colonne = connu_ou_404(PORTEURS, annexes_de, "Fiche inconnue")
        stmt = stmt.where(getattr(Document, colonne).is_not(None))
    fiches = porteurs_demandes(
        document_parent_id=document_parent_id,
        diagnostic_rapport_id=diagnostic_rapport_id,
        regle_residence_id=regle_residence_id,
    )
    for porteur, porteur_id in fiches.items():
        stmt = stmt.where(getattr(Document, PORTEURS[porteur]) == porteur_id)
    #  Une annexe n'est pas un document de la bibliothèque non plus : sans
    #  filtre sur sa fiche, elle n'apparaît pas — la même raison que ci-dessous.
    if not fiches and not annexes_de:
        stmt = stmt.where(*(getattr(Document, c).is_(None) for c in PORTEURS.values()))
    if categorie_id:
        stmt = stmt.where(Document.categorie_id == categorie_id)
    if categorie:
        stmt = stmt.join(CategorieDocument, CategorieDocument.id == Document.categorie_id)
        stmt = stmt.where(CategorieDocument.code == categorie)
    if contrat_id:
        stmt = stmt.where(Document.contrat_id == contrat_id)
    if ticket_id:
        stmt = stmt.where(Document.ticket_id == ticket_id)
    if evenement_id:
        stmt = stmt.where(Document.evenement_id == evenement_id)

    #  🔴 UNE PIÈCE JOINTE N'EST PAS UN DOCUMENT DE LA BIBLIOTHÈQUE (#390).
    #
    #  Cet endpoint SANS filtre rend toutes les lignes, et c'est ce que l'écran
    #  Résidence appelle pour son dépôt de plans et de règlements. Sans cette
    #  exclusion, chaque photo jointe à un ticket s'y afficherait dès le premier
    #  écran basculé — la faille exacte que #390 existe pour fermer, retournée.
    #
    #  ⚠️ On exclut au niveau de la REQUÊTE et non du filtrage par visibilité :
    #  `document_visible` répondrait « oui » pour l'auteur du ticket, ce qui est
    #  juste — la pièce jointe lui est bien lisible — mais elle n'a rien à faire
    #  dans la bibliothèque pour autant. Ce sont deux questions différentes.
    if not ticket_id and not evenement_id:
        stmt = stmt.where(Document.ticket_id.is_(None), Document.evenement_id.is_(None))

    docs = session.exec(stmt.order_by(Document.publie_le.desc())).all()

    #  Filtrage côté serveur selon profil d'accès — pour TOUS : un modérateur
    #  passe en tête de `document_visible`, sauf sur les catégories réservées à
    #  l'administration (`CATEGORIES_ADMIN_SEUL`, le texte du règlement).
    docs = [d for d in docs if document_visible(user, d, session)]

    return docs


@router.get("/{doc_id}/télécharger")
def download_document(
    doc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    doc = ou_404(session, Document, doc_id, "Document")
    if not document_visible(user, doc, session):
        raise HTTPException(403, "Accès refusé")
    return FileResponse(
        fichier_ou_404(stockage().fichier_de(doc)),
        filename=doc.fichier_nom,
        media_type=doc.mime_type,
    )


class DocumentUpdate(BaseModel):
    #  🔴 TROIS champs ajoutés le 08/09/2026 (#852). Signalé à l'écran :
    #  *« très peu de champs sont éditables »* — on ne pouvait corriger qu'un
    #  titre, une année et une date d'AG.
    #
    #  ⚠️ Ce n'est pas qu'un manque d'écran : `DocumentUpdate` ne les acceptait
    #  pas non plus. Les ouvrir côté front sans les ouvrir ici aurait donné des
    #  champs qui ne font rien — pire qu'absents, parce qu'ils promettent
    #  quelque chose (`ux-patterns` §0 : « avant de rouvrir un champ dans
    #  l'interface, vérifier que le serveur le CONSOMME »).
    titre: Optional[str] = None
    description: Optional[str] = None
    #  Le périmètre en CODES, comme partout ailleurs (#470). L'ancien
    #  `batiment_id` reste déprécié : on ne le rouvre pas.
    perimetre_cible: Optional[list[str]] = None
    annee: Optional[int] = None
    date_ag: Optional[str] = None  # ISO date string
    #  La date du document (migration 0280) — vide l'efface, comme `date_ag`.
    date_document: Optional[str] = None


def _jour(valeur: str | None) -> date | None:
    """Une date ISO reçue d'un formulaire — vide = aucune, illisible = 422.

    `date_ag` et `date_document` se lisent ainsi à la création et à la
    correction : quatre lectures, une règle.
    """
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        raise HTTPException(422, "Date invalide") from None


def _document_ecrivable(session: Session, doc_id: int, user: Utilisateur) -> Document:
    """Le document (404), si ce modérateur peut le corriger ou le retirer (403) —
    tous, sauf ceux d'une catégorie réservée à l'admin (`peut_ecrire_dans`)."""
    return exiger_objet_autorise(
        session,
        Document,
        doc_id,
        "Document",
        user,
        lambda doc, u: peut_ecrire_dans(u, doc.categorie),
        "Réservé à l'admin",
    )


@router.patch("/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int,
    body: DocumentUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    doc = _document_ecrivable(session, doc_id, user)
    if body.titre is not None:
        doc.titre = body.titre
    if body.description is not None:
        doc.description = body.description
    if body.perimetre_cible is not None:
        #  Même sérialisation que la création : du JSON de codes, jamais une
        #  quatrième forme (#316).
        doc.perimetre_cible = json.dumps(body.perimetre_cible, ensure_ascii=False)
    if body.annee is not None:
        doc.annee = body.annee
    if body.date_ag is not None:
        doc.date_ag = _jour(body.date_ag)
    if body.date_document is not None:
        doc.date_document = _jour(body.date_document)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{doc_id}/fichier", response_model=DocumentRead)
def retirer_fichier_document(
    doc_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Retire le fichier PRINCIPAL d'une fiche de Ma résidence : sa première annexe
    prend sa place (`utils/annexes`).

    Seul un document de la bibliothèque — une catégorie — porte un fichier
    principal : une pièce jointe d'affaire, de contrat ou une annexe se supprime.
    """
    doc = ou_404(session, Document, doc_id, "Document")
    if not doc.categorie_id:
        raise HTTPException(400, "Seul le fichier d'un document de Ma résidence se retire ainsi")
    retirer_fichier_principal(session, doc, "document")
    return doc


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    titre: str = Form(...),
    #  Section 6 du cadre — ce que le document couvre, d'où il vient, ce qu'il
    #  ne dit pas (#852). Vide par défaut : elle n'est jamais requise.
    description: str = Form(""),
    categorie_id: int | None = Form(None),
    contrat_id: int | None = Form(None),
    ticket_id: int | None = Form(None),
    evenement_id: int | None = Form(None),
    #  L'annexe d'une fiche de Ma résidence (migration 0276).
    document_parent_id: int | None = Form(None),
    diagnostic_rapport_id: int | None = Form(None),
    regle_residence_id: int | None = Form(None),
    perimetre: str = Form("résidence"),
    batiment_id: int | None = Form(None),
    lot_id: int | None = Form(None),
    annee: int | None = Form(None),
    date_ag: str | None = Form(None),
    date_document: str | None = Form(None),
    batiments_ids_json: str | None = Form(None),
    #  Codes de périmètre, ce que l'écran envoie depuis `PerimetrePicker` (#470).
    perimetre_cible: str | None = Form(None),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    #  🔴 L'INVARIANT : une ligne `document` porte TOUJOURS un rattachement.
    #  C'est lui qui garantit qu'aucune ligne orpheline n'existe, et donc que
    #  `document_visible` a toujours une source de protection à consulter. Il
    #  S'ÉTEND aux pièces jointes de ticket et d'événement (#390) plutôt que de se
    #  relâcher : le découpage d'origine proposait de créer la ligne « sans
    #  rattachement, rattachée ensuite », ce qui l'aurait violé le temps d'un
    #  formulaire abandonné — c'est-à-dire pour toujours.
    #  `publication_id` n'en est plus un depuis le 23/09/2026 : une actualité est
    #  une affaire (#1091), ses pièces jointes portent `ticket_id`.
    annexe = porteurs_demandes(
        document_parent_id=document_parent_id,
        diagnostic_rapport_id=diagnostic_rapport_id,
        regle_residence_id=regle_residence_id,
    )
    if annexe:
        #  🔴 UN SEUL rattachement pour une annexe : une catégorie lui donnerait
        #  sa propre règle de lecture et l'enverrait dans la bibliothèque, deux
        #  porteurs deux règles. Elle se lit comme SA fiche, et rien d'autre.
        if len(annexe) > 1 or categorie_id or contrat_id or ticket_id or evenement_id:
            raise HTTPException(400, "Une annexe se rattache à une seule fiche")
        [(porteur, porteur_id)] = annexe.items()
        verifier_porteur(session, porteur, porteur_id)
    elif not categorie_id and not contrat_id and not ticket_id and not evenement_id:
        raise HTTPException(
            400,
            "categorie_id, contrat_id, ticket_id, evenement_id ou une fiche obligatoire",
        )

    if categorie_id:
        categorie = session.get(CategorieDocument, categorie_id)
        if not categorie or not categorie.actif:
            raise HTTPException(400, "Catégorie invalide")
        if not peut_ecrire_dans(user, categorie):
            raise HTTPException(403, "Réservé à l'admin")

    #  Lues AVANT l'écriture du fichier : une date refusée ne laisse rien sur le disque.
    jour_ag, jour_document = _jour(date_ag), _jour(date_document)

    # Dans le dossier PRIVÉ (`enregistrer_televersement`) et non à la racine du
    # volume : `/uploads/*` est servi en statique, et le contrôle d'accès à trois
    # couches de `document_visible` serait contourné par la simple URL du fichier.
    # Assainissement et préfixe UUID : app/utils/fichiers.py, seul endroit où
    # cette règle est écrite. Le téléchargement passe par un endpoint
    # authentifié qui impose lui-même le `media_type`, l'extension d'origine
    # peut donc être conservée telle quelle.
    raw_name = file.filename or "document"
    #  🔴 Validation ET écriture en un seul geste (#825) : lire seize octets,
    #  rembobiner, vérifier la signature, journaliser, refuser, nommer, copier.
    #  Ces neuf lignes étaient recopiées dans trois routeurs — une copie qui
    #  oublie le `seek(0)` écrit un fichier tronqué sans que rien ne le dise.
    cle = enregistrer_televersement(file, raw_name, user)
    st = stockage()

    doc = Document(
        titre=titre,
        description=description,
        fichier_nom=file.filename,
        **st.colonnes(cle),
        taille_octets=st.chemin(cle).stat().st_size,
        mime_type=file.content_type or "application/octet-stream",
        categorie_id=categorie_id,
        contrat_id=contrat_id,
        ticket_id=ticket_id,
        evenement_id=evenement_id,
        document_parent_id=document_parent_id,
        diagnostic_rapport_id=diagnostic_rapport_id,
        regle_residence_id=regle_residence_id,
        perimetre=perimetre,
        batiment_id=batiment_id,
        lot_id=lot_id,
        publie_par_id=user.id,
        annee=annee,
        date_ag=jour_ag,
        date_document=jour_document,
        batiments_ids_json=batiments_ids_json,
        perimetre_cible=perimetre_cible,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # `background_tasks` est optionnel : un appel qui ne le fournit pas publie
    # le document sans notifier, plutôt que d'échouer en cours de route.
    if background_tasks is not None:
        _notifier_document_publie(doc, user, background_tasks, session)

    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    doc = _document_ecrivable(session, doc_id, user)
    #  🔴 UN CONTRAT PEUT CITER CE DOCUMENT, et rien ne le déliait (#546).
    #  `contrat_entretien.document_id` référence le document : sous les clés, la
    #  suppression échoue ; sans elles — le régime actuel — le contrat garde une
    #  référence vers un fichier disparu, et l'écran des prestataires affiche un
    #  lien mort.
    #
    #  ⚠️ Ici le parent SURVIT, contrairement au ticket ou à l'événement : un
    #  contrat d'entretien existe indépendamment du fichier scanné qu'on lui a
    #  joint. La décision dépend de ce que la ligne RACONTE, jamais de la
    #  nullabilité de sa colonne.
    for contrat in session.exec(
        select(ContratEntretien).where(ContratEntretien.document_id == doc_id)
    ).all():
        contrat.document_id = None
        session.add(contrat)
    #  Une fiche emporte ses annexes (migration 0276) : sans elle, elles
    #  n'auraient plus de règle de lecture (`utils/annexes`).
    supprimer_annexes(session, "document", doc_id)
    stockage().supprimer_de(doc)
    session.delete(doc)
    session.commit()
