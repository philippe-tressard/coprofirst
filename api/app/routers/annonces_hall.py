"""Router annonces hall — affiches PDF (A4/A5) du Conseil Syndical.

Deux usages :
  1. création d'une annonce → PDF généré à la charte + envoi par e-mail aux
     membres du CS du périmètre, le PDF en pièce jointe ;
  2. historique consultable, archivable (CS) et supprimable (admin).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import AnnonceHall, Document, Utilisateur
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.annonce_hall import (
    APERCU_MAX,
    FORMATS,
    MAX_PHOTOS,
    choisir_format,
    construire_html,
    format_libelle,
    generer_pdf,
    nom_fichier,
    texte_brut,
)
from app.routers.annonces_hall_courriels import (
    _envoyer_email_annonce,
    _partager_sur_le_groupe,
)
from app.utils.perimetres import (
    parse_json_perimetres,
    perimetre_defaut_liste,
    perimetre_label_liste,
)
from app.utils.config_site import config_site
from app.utils.photos import parse_photos
from app.utils.noms import nom_auteur

router = APIRouter(prefix="/annonces-hall", tags=["annonces-hall"])

#  L'aperçu avant envoi vit dans son propre module — même découpage que les
#  affaires (`tickets/apercu.py`) : il ne partage avec la création que les
#  fonctions de composition, et surtout pas son routeur (#480/#498).
from app.routers.annonces_hall_apercu import router as _router_apercu  # noqa: E402

router.include_router(_router_apercu)
#  Ce qu'une affiche peut reprendre du fil (`/sources`, `/depuis/…`) — extrait le
#  28/09/2026 (#779). Inclus ici, avant les routes à paramètre de ce routeur.
from app.routers.annonces_hall_sources import router as _router_sources  # noqa: E402

router.include_router(_router_sources)

from app.utils.stockage import DOSSIER_AFFICHES, cle_de_url, stockage

#  🔴 La racine venait d'un chemin écrit en dur, ici comme à cinq autres
#  endroits (#1026). Les affiches s'écrivent dans le stockage de la copropriété
#  (`utils/stockage`, #1748), sous ce dossier : un fichier écrit hors du volume
#  n'est ni répliqué vers le standby par `bascule.sh`, ni sauvegardé par
#  `backup.py` — il est perdu à la première bascule, sans aucun signal.
DOSSIER_PDF = DOSSIER_AFFICHES


#  Les schémas vivent dans `annonces_hall_schemas` (02/09/2026, plafond de
#  modularité) : ce qui DÉCLARE part, ce qui DÉCIDE reste.
from app.utils.liens import adresse_du_site, nom_site
from app.utils.logo import logo_televerse_png
from app.utils.recuperer import fichier_ou_404, ou_404, ou_rien
from app.routers.annonces_hall_schemas import (  # noqa: E402
    AnnonceHallArchive,
    AnnonceHallBase,
    AnnonceHallCreate,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

#  🔴 `_config_site` A ÉTÉ RETIRÉ (18/09/2026) : c'était une recopie de la
#  lecture partagée, avec un écart — elle rendait `""` là où l'originale rend
#  `None`. Sans conséquence ici, les deux valeurs passant par `nom_site()` et
#  `base_site()` qui traitent l'absence ; mais c'est par cet écart-là qu'une
#  copie devient un jour un comportement différent.
#  La lecture vit dans `app/utils/config_site.py`.


#  ⚠️ `_batiments()` a disparu avec `perimetre_libelle` (27/08/2026) : il ne
#  servait qu'à fabriquer « Bât. {numero} » en dehors de l'arbre. Le libellé d'un
#  bâtiment vient désormais de la table `perimetre`, donc de l'administration —
#  un renommage l'atteint, ce que cette table-là ne permettait pas.


def _valider(body: AnnonceHallBase) -> None:
    if not body.titre.strip():
        raise HTTPException(422, "Le titre est obligatoire")
    #  Une photo seule fait une affiche (24/10/2026) : elle occupe alors le feuillet.
    if not texte_brut(body.message) and not body.images:
        raise HTTPException(
            422, "Le message est obligatoire, sauf pour une affiche faite d'une photo"
        )
    if (body.format_demande or "auto").lower() not in ("auto", *FORMATS):
        raise HTTPException(422, "Format invalide (auto, a4 ou a5)")
    if len(body.images) > MAX_PHOTOS:
        raise HTTPException(422, f"{MAX_PHOTOS} photos au maximum")
    if any(cle_de_url(u) is None for u in body.images):
        raise HTTPException(422, "Photo invalide")


def _html_params(
    body: AnnonceHallBase, session: Session, *, format_effectif: str, date_affichage: datetime
) -> dict:
    cfg = config_site(session)
    return {
        "titre": body.titre.strip(),
        "message_html": body.message,
        "perimetre_label": perimetre_label_liste(body.perimetre_cible),
        "format_effectif": format_effectif,
        "site_nom": nom_site(cfg.get("site_nom")),
        "site_url": adresse_du_site(),
        "logo_png": logo_televerse_png(session),
        "images": body.images,
        "date_affichage": date_affichage,
    }


def _to_read(annonce: AnnonceHall, session: Session) -> dict:
    auteur = ou_rien(session, Utilisateur, annonce.auteur_id)
    perimetres = parse_json_perimetres(annonce.perimetre_cible)
    return {
        "id": annonce.id,
        "titre": annonce.titre,
        "message": annonce.message,
        "assiste_ia": annonce.assiste_ia,
        "apercu": texte_brut(annonce.message)[:APERCU_MAX],
        "perimetre_cible": perimetres,
        "perimetre_label": perimetre_label_liste(perimetres),
        "format_demande": annonce.format_demande,
        "format_effectif": annonce.format_effectif,
        "format_label": format_libelle(annonce.format_effectif),
        "images": json.loads(annonce.images_json or "[]"),
        "pdf_nom": annonce.pdf_nom,
        "taille_octets": annonce.taille_octets,
        "destinataires": json.loads(annonce.destinataires or "[]"),
        "envoye_le": annonce.envoye_le.isoformat() if annonce.envoye_le else None,
        #  🔴 EFFECTIF, et non la colonne : la règle du site archive une affiche
        #  30 jours après son envoi, que personne n'ait rien coché.
        "archivee": est_archivable(
            "annonce_hall", annonce, seuil_jours=seuil_archivage_jours(session)
        ),
        "archivee_manuellement": annonce.archivee,
        "ticket_id": annonce.ticket_id,
        "cree_le": annonce.cree_le.isoformat(),
        "auteur_nom": nom_auteur(auteur),
    }


def images_de(ticket, session: Session) -> list[str]:
    """Photos exploitables d'une affaire « Actualité », limitées à `MAX_PHOTOS`.

    Ses photos d'abord, puis ses pièces jointes de type image, puis les images
    de la bibliothèque rattachées (`Document.ticket_id`). Elle remplace
    `images_de_publication`, retirée avec l'entité (#1091).
    """
    urls: list[str] = [
        u
        for u in parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
        if cle_de_url(u) is not None
    ]
    docs = session.exec(
        select(Document).where(Document.ticket_id == ticket.id).order_by(Document.publie_le)  # type: ignore[arg-type]
    ).all()
    st = stockage()
    for doc in docs:
        if not (doc.mime_type or "").startswith("image/"):
            continue
        cle = st.cle_de(doc)
        if cle is None or not st.existe(cle):
            continue
        url = st.url(cle)
        if url not in urls:
            urls.append(url)
    return urls[:MAX_PHOTOS]


def _supprimer_fichier(annonce: AnnonceHall) -> None:
    """Supprime le PDF d'une affiche du volume uploads (jamais hors de ce volume)."""
    try:
        stockage().supprimer_de(annonce, "pdf")
    except OSError:
        pass


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", summary="Historique des annonces de hall (CS/Admin)")
def list_annonces_hall(
    archivees: bool = False,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    #  🔴 LE TRI SE FAIT EN PYTHON, plus en SQL (#515, 02/09/2026).
    #
    #  La colonne `archivee` ne porte que la décision HUMAINE. La règle du site en
    #  ajoute une seconde — 30 jours après l'envoi — que SQL ne sait pas exprimer
    #  sans recopier le calcul en SQL, c'est-à-dire sans en faire une deuxième
    #  écriture de la règle. C'est exactement ce que ce lot supprime ailleurs.
    #
    #  ⚠️ Le coût est assumé : la table des affiches de hall compte quelques
    #  dizaines de lignes, et l'écran est réservé au CS. À revoir si elle grossit,
    #  et à MESURER avant d'optimiser.
    seuil_jours = seuil_archivage_jours(session)
    toutes = session.exec(
        select(AnnonceHall).order_by(AnnonceHall.cree_le.desc())  # type: ignore[arg-type]
    ).all()
    retenues = [
        a for a in toutes if est_archivable("annonce_hall", a, seuil_jours=seuil_jours) == archivees
    ]
    return [_to_read(a, session) for a in retenues]


@router.post("/previsualiser", summary="Aperçu HTML de l'annonce avant envoi (CS/Admin)")
def previsualiser_annonce(
    body: AnnonceHallCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend l'annonce en HTML sans rien enregistrer ni envoyer."""
    _valider(body)
    fmt = choisir_format(
        body.message,
        body.format_demande,
        titre=body.titre,
        avec_photos=bool(body.images),
    )
    params = _html_params(body, session, format_effectif=fmt, date_affichage=horloge.maintenant())
    return {
        "format_effectif": fmt,
        "format_label": format_libelle(fmt),
        "perimetre_label": params["perimetre_label"],
        "html": construire_html(**params),
    }


def creer_annonce_hall(
    *,
    session: Session,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    titre: str,
    message: str,
    perimetre_cible: list[str],
    format_demande: str = "auto",
    images: Optional[list[str]] = None,
    ticket_id: Optional[int] = None,
    #  Décoché par défaut : la valeur par défaut d'un envoi est « ne pas envoyer ».
    #  Les autres appelants (pré-remplissage depuis une actualité) n'envoient donc
    #  rien sans le demander.
    envoyer_cs: bool = False,
    #  🔴 Les DEUX autres canaux de la Diffusion (#480, 01/09/2026). Ils
    #  s'affichaient dans `CanauxNotification` partout ailleurs et n'existaient pas
    #  ici : l'écran portait une case unique, et le cadre interdit d'ouvrir un
    #  champ que le serveur ne consomme pas. Les voici consommés.
    envoyer_syndic: bool = False,
    partager_whatsapp: bool = False,
    envoyer_auteur: bool = False,
    #  La section Description a l'assistant IA, et sa marque (#1089).
    assiste_ia: bool = False,
) -> AnnonceHall:
    """Génère le PDF et l'enregistre dans l'historique.

    ⚠️ Plus aucun envoi depuis le 18/08/2026 : cet écran fabrique un document à
    imprimer, et sa diffusion appartient à celui qui le génère.

    Point d'entrée unique : utilisé par l'onglet Annonces Hall **et** par l'option
    « Annonce Hall » d'une actualité (`tickets/actualite.generer_affiche`).
    """
    body = AnnonceHallCreate(
        titre=titre,
        message=message,
        perimetre_cible=perimetre_cible or perimetre_defaut_liste(),
        format_demande=format_demande,
        images=(images or [])[:MAX_PHOTOS],
    )
    _valider(body)
    maintenant = horloge.maintenant()
    fmt = choisir_format(
        body.message,
        body.format_demande,
        titre=body.titre,
        avec_photos=bool(body.images),
    )
    params = _html_params(body, session, format_effectif=fmt, date_affichage=maintenant)

    try:
        pdf = generer_pdf(**params)
    except Exception as exc:  # pragma: no cover - dépend de l'environnement de rendu
        raise HTTPException(500, f"Génération du PDF impossible : {exc}") from exc

    st = stockage()
    cle_pdf = f"{DOSSIER_PDF}/{uuid.uuid4().hex}.pdf"
    st.ecrire(cle_pdf, pdf)

    annonce = AnnonceHall(
        titre=body.titre.strip(),
        message=body.message,
        perimetre_cible=json.dumps(body.perimetre_cible, ensure_ascii=False),
        format_demande=(body.format_demande or "auto").lower(),
        format_effectif=fmt,
        images_json=json.dumps(body.images, ensure_ascii=False),
        **st.colonnes(cle_pdf, "pdf"),
        pdf_nom=nom_fichier(body.titre, maintenant),
        taille_octets=len(pdf),
        ticket_id=ticket_id,
        auteur_id=user.id,
        cree_le=maintenant,
        assiste_ia=assiste_ia,
    )
    session.add(annonce)
    session.commit()
    session.refresh(annonce)

    #  🔴 L'ENVOI EST UN CHOIX, jamais un automatisme (18/08/2026).
    #
    #  Il était automatique le matin — « ce menu ne doit pas envoyer de mail au CS,
    #  juste générer un PDF » —, supprimé dans la foulée, puis rendu au CADRE : la
    #  Diffusion est la section 9, elle se coche, et elle n'agit que cochée.
    #
    #  Cet écran FABRIQUE un document à imprimer. Qui l'imprime, quand, et à qui il
    #  l'envoie sont des décisions qui appartiennent à celui qui le génère — les
    #  prendre à sa place expédiait un courriel à tout le conseil syndical au moindre
    #  essai de mise en page, pièce jointe comprise.
    #
    #  ⚠️ Le bouton dit « Générer une affiche », et c'est vrai dans les deux cas :
    #  l'affiche est produite, l'envoi est une option qu'on ajoute. C'est ce qui
    #  distingue cette section 9 d'un bouton « Envoyer » — le geste principal reste
    #  la génération.
    #
    #  Sans la case, `destinataires` et `envoye_le` restent vides : l'historique dit
    #  qu'une affiche a été générée, et rien de plus — ce qui est exactement le fait.
    diffuse = False
    if envoyer_cs or envoyer_syndic:
        emails = _envoyer_email_annonce(
            annonce,
            user,
            background_tasks,
            session,
            syndic=envoyer_syndic,
            cs=envoyer_cs,
            auteur=envoyer_auteur,
        )
        if emails:
            annonce.destinataires = json.dumps(emails, ensure_ascii=False)
            diffuse = True
    if partager_whatsapp and _partager_sur_le_groupe(annonce, background_tasks, session):
        diffuse = True

    #  ⚠️ `envoye_le` est posé si UN canal a réellement été programmé — pas si une
    #  case était cochée. Un WhatsApp éteint ou un périmètre sans conseiller ne
    #  doivent pas inscrire dans l'historique une diffusion qui n'a pas eu lieu.
    if diffuse:
        annonce.envoye_le = horloge.maintenant()
        session.add(annonce)
        session.commit()
        session.refresh(annonce)

    return annonce


@router.post("", status_code=201, summary="Créer une annonce de hall (CS/Admin)")
def create_annonce_hall(
    body: AnnonceHallCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Génère le PDF et l'archive dans l'historique — sans aucun envoi (18/08/2026)."""
    annonce = creer_annonce_hall(
        session=session,
        user=user,
        background_tasks=background_tasks,
        titre=body.titre,
        message=body.message,
        perimetre_cible=body.perimetre_cible,
        format_demande=body.format_demande,
        images=body.images,
        envoyer_cs=body.envoyer_cs,
        envoyer_syndic=body.envoyer_syndic,
        partager_whatsapp=body.partager_whatsapp,
        envoyer_auteur=body.envoyer_auteur,
        assiste_ia=body.assiste_ia,
    )
    return _to_read(annonce, session)


@router.get("/{annonce_id}/pdf", summary="Télécharger le PDF d'une annonce (CS/Admin)")
def download_pdf(
    annonce_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = ou_404(session, AnnonceHall, annonce_id, "Annonce")
    return FileResponse(
        fichier_ou_404(stockage().fichier_de(annonce, "pdf"), "PDF"),
        media_type="application/pdf",
        filename=annonce.pdf_nom or f"annonce-{annonce_id}.pdf",
    )


@router.post(
    "/{annonce_id}/renvoyer-email",
    status_code=204,
    summary="Renvoyer l'annonce au CS du périmètre (CS/Admin)",
)
def renvoyer_email(
    annonce_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = ou_404(session, AnnonceHall, annonce_id, "Annonce")
    #  Le renvoi manuel vise le CS du périmètre, comme avant : c'est un geste de
    #  rattrapage sur un envoi qui a déjà eu lieu, pas une nouvelle diffusion.
    emails = _envoyer_email_annonce(annonce, user, background_tasks, session)
    if not emails:
        raise HTTPException(
            422,
            "Aucun membre du CS rattaché à ce périmètre ne dispose d'un compte avec e-mail",
        )
    annonce.destinataires = json.dumps(emails, ensure_ascii=False)
    annonce.envoye_le = horloge.maintenant()
    session.add(annonce)
    session.commit()


@router.patch("/{annonce_id}", summary="Archiver / désarchiver une annonce (CS/Admin)")
def archiver_annonce(
    annonce_id: int,
    body: AnnonceHallArchive,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = ou_404(session, AnnonceHall, annonce_id, "Annonce")
    annonce.archivee = body.archivee
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _to_read(annonce, session)


@router.delete(
    "/{annonce_id}", status_code=204, summary="Supprimer définitivement une annonce (Admin)"
)
def delete_annonce_hall(
    annonce_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Suppression définitive : la ligne et son PDF partent — ses images restent.

    🔴 Les images d'une affiche ne lui appartiennent pas (#1828) : reprise d'une
    affaire, elle porte les photos de l'affaire (`images_de`) ; reprise d'une autre
    affiche, les mêmes adresses. Les effacer laissait l'affaire avec des photos
    disparues. Comme partout ailleurs, supprimer un objet ne supprime pas les
    photos qu'il référence. 🔒 `test_annonce_hall_suppression.py`.
    """
    annonce = ou_404(session, AnnonceHall, annonce_id, "Annonce")
    _supprimer_fichier(annonce)
    session.delete(annonce)
    session.commit()
