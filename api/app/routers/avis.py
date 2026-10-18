"""Les AVIS sur l'application — onglet « Avis » de la Communauté (#2075).

Un avis par compte : note, titre, description — une remarque sous 3 étoiles,
l'accord de l'auteur à partir de 4. Le gestionnaire du site y répond, retient
ceux qui paraîtront sur coprofirst.fr et les exporte. Les règles vivent dans
`utils/avis` ; ce routeur ne fait que les appliquer.

| Geste | Qui |
|---|---|
| lire | l'auteur et le conseil, toujours ; tout compte (syndic et mandataire compris, la seule rubrique de la Communauté qui leur est ouverte) si l'auteur l'a accepté — `avis_visible` ; un banni de la Communauté, non |
| déposer, corriger | l'auteur — un compte externe ne donne pas d'avis |
| retirer (📦) / ressortir (↩️) | l'auteur, le gestionnaire ; ce que le gestionnaire a retiré, lui seul le ressort |
| répondre, retenir, exporter | le gestionnaire du site (`est_gestionnaire_du_site`) |
| supprimer | l'auteur et l'administrateur, aux Archives seulement |

⚠️ L'avis n'est pas une idée : pas de vote, pas de périmètre, pas de réponses
des voisins. La seule réponse est celle du gestionnaire — d'où un champ, et
non la fabrique `reponses_communaute`.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.deps import exiger_non_externe, get_current_user
from app.database import get_session
from app.models.avis import Avis
from app.models.core import RoleUtilisateur, Utilisateur
from app.routers.avis_schemas import (
    AvisCreate,
    AvisListe,
    AvisRead,
    AvisUpdate,
    PublicationAvis,
    ReponseAvis,
)
from app.routers.prestataires_archivage import Archivage
from app.utils import horloge
from app.utils.avis import (
    auteurs_de,
    avis_visible,
    est_publiable,
    exiger_saisie_valide,
    exporter,
    signature,
)
from app.utils.cloche import sonner
from app.utils.communaute import exiger_acces
from app.utils.destinataires import est_gestionnaire_du_site
from app.utils.lecture import lire_objet
from app.utils.liens import lien_element
from app.utils.recuperer import ou_404, ou_rien

router = APIRouter(prefix="/avis", tags=["avis"])

PREFIXE_LIEN = "avis"


def _lire(avis: Avis, auteur, lecteur: Utilisateur, gestionnaire: bool) -> AvisRead:
    """L'avis tel que CE lecteur a le droit de le lire."""
    nom, role = signature(auteur)
    proche = gestionnaire or avis.auteur_id == lecteur.id
    prive = {} if proche else {"remarque": None, "consentement_publication": None}
    return lire_objet(
        AvisRead,
        avis,
        auteur_nom=nom,
        auteur_role=role,
        est_auteur=avis.auteur_id == lecteur.id,
        archivee=avis.archive_le is not None,
        lu_de_tous=avis.consentement_publication is True,
        #  L'auteur ressort ce qu'il a rangé ; ce que le gestionnaire a retiré,
        #  seul le gestionnaire le ressort.
        restaurable=avis.archive_le is not None
        and (gestionnaire or avis.archive_par_id == lecteur.id),
        publiable=proche and est_publiable(avis),
        publication_validee=proche and avis.publication_validee_le is not None,
        **prive,
    )


def _rendre(session: Session, avis: Avis, lecteur: Utilisateur) -> AvisRead:
    gestionnaire = est_gestionnaire_du_site(session, lecteur)
    return _lire(avis, ou_rien(session, Utilisateur, avis.auteur_id), lecteur, gestionnaire)


def _exiger_gestionnaire(session: Session, user: Utilisateur) -> None:
    if not est_gestionnaire_du_site(session, user):
        raise HTTPException(403, "Réservé au gestionnaire du site")


def _enregistrer(session: Session, avis: Avis) -> None:
    session.add(avis)
    session.commit()
    session.refresh(avis)


@router.get("", response_model=AvisListe)
def lister(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user, profil=False)
    gestionnaire = est_gestionnaire_du_site(session, user)
    tous = session.exec(select(Avis).order_by(Avis.cree_le.desc())).all()
    #  🔒 Sans l'accord de son auteur, un avis ne se lit que de lui et du conseil
    #  (`avis_visible`) : le filtre est ICI, jamais dans l'écran — une carte
    #  masquée par le navigateur resterait dans la charge utile.
    lisibles = [a for a in tous if avis_visible(a, user)]
    auteurs = auteurs_de(session, lisibles)
    mien = next((a.id for a in tous if a.auteur_id == user.id), None)
    return AvisListe(
        avis=[_lire(a, auteurs.get(a.auteur_id), user, gestionnaire) for a in lisibles],
        gestionnaire=gestionnaire,
        mon_avis_id=mien,
    )


#  ⚠️ Les routes à segment FIXE avant celles à paramètre (#1151).
@router.get("/export")
def exporter_avis(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Les avis retenus, en JSON, pour le site vitrine — un fichier à télécharger."""
    _exiger_gestionnaire(session, user)
    contenu = exporter(session, list(session.exec(select(Avis).order_by(Avis.note.desc()))))
    nom = f"avis-coprofirst-{horloge.aujourd_hui().isoformat()}.json"
    return JSONResponse(
        {"genere_le": horloge.aujourd_hui().isoformat(), "avis": contenu},
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.post("", response_model=AvisRead, status_code=201)
def deposer(
    body: AvisCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user, profil=False)
    exiger_non_externe(user, "donner un avis")
    titre, description = body.titre.strip(), body.description.strip()
    if not titre or not description:
        raise HTTPException(422, "Le titre et la description sont obligatoires")
    remarque, accord = exiger_saisie_valide(body.note, body.remarque, body.consentement_publication)
    if session.exec(select(Avis).where(Avis.auteur_id == user.id)).first():
        raise HTTPException(409, "Vous avez déjà donné votre avis : modifiez-le plutôt")
    avis = Avis(
        auteur_id=user.id,
        note=body.note,
        titre=titre,
        description=description,
        remarque=remarque,
        consentement_publication=accord,
    )
    try:
        _enregistrer(session, avis)
    except IntegrityError:
        #  Deux envois simultanés : la base tient « un avis par compte ».
        session.rollback()
        raise HTTPException(409, "Vous avez déjà donné votre avis : modifiez-le plutôt") from None
    return _rendre(session, avis, user)


@router.patch("/{avis_id}", response_model=AvisRead)
def corriger(
    avis_id: int,
    body: AvisUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """L'auteur corrige son avis — lui seul : on ne réécrit pas le témoignage d'un autre."""
    exiger_acces(user, profil=False)
    avis = ou_404(session, Avis, avis_id, "Avis")
    if avis.auteur_id != user.id:
        raise HTTPException(403, "Seul son auteur peut modifier un avis")
    if avis.archive_le is not None:
        raise HTTPException(400, "Cet avis est retiré : ressortez-le des Archives pour le modifier")
    donnees = body.model_dump(exclude_unset=True)
    for champ in ("titre", "description"):
        if champ in donnees:
            valeur = (donnees[champ] or "").strip()
            if not valeur:
                raise HTTPException(422, f"Le champ « {champ} » ne peut pas être vide")
            donnees[champ] = valeur
    note = donnees.get("note", avis.note)
    remarque, accord = exiger_saisie_valide(
        note,
        donnees.get("remarque", avis.remarque),
        donnees.get("consentement_publication", avis.consentement_publication),
    )
    avant = (avis.note, avis.titre, avis.description, avis.consentement_publication)
    avis.note = note
    avis.titre = donnees.get("titre", avis.titre)
    avis.description = donnees.get("description", avis.description)
    avis.remarque, avis.consentement_publication = remarque, accord
    if avant != (avis.note, avis.titre, avis.description, avis.consentement_publication):
        #  Ce que le gestionnaire a relu a changé : il le relira avant que
        #  coprofirst.fr n'affiche la nouvelle version.
        avis.publication_validee_le = None
        avis.mis_a_jour_le = horloge.maintenant()
    _enregistrer(session, avis)
    return _rendre(session, avis, user)


@router.patch("/{avis_id}/archivage", status_code=204)
def archiver(
    avis_id: int,
    corps: Archivage,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """📦 Retirer un avis, ↩️ le ressortir — un seul geste, comme ailleurs (#1538)."""
    exiger_acces(user, profil=False)
    avis = ou_404(session, Avis, avis_id, "Avis")
    gestionnaire = est_gestionnaire_du_site(session, user)
    if not gestionnaire and avis.auteur_id != user.id:
        raise HTTPException(
            403, "Seuls son auteur et le gestionnaire du site peuvent retirer un avis"
        )
    if corps.archivee:
        if avis.archive_le is None:
            avis.archive_le, avis.archive_par_id = horloge.maintenant(), user.id
            #  Retiré, il quitte l'export : le ressortir ne le republie pas.
            avis.publication_validee_le = None
    elif avis.archive_le is not None:
        if not gestionnaire and avis.archive_par_id != user.id:
            raise HTTPException(403, "Cet avis a été retiré par le gestionnaire du site")
        avis.archive_le, avis.archive_par_id = None, None
    _enregistrer(session, avis)


@router.delete("/{avis_id}", status_code=204)
def supprimer(
    avis_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Suppression définitive, aux Archives seulement — son auteur ou l'administrateur.

    L'auteur efface ce qu'il a écrit et signé : c'est son témoignage, et
    retirer son accord ne suffit pas toujours (RGPD, droit à l'effacement).
    """
    avis = ou_404(session, Avis, avis_id, "Avis")
    if avis.auteur_id != user.id and not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(403, "Seuls son auteur et l'administrateur suppriment un avis")
    if avis.archive_le is None:
        raise HTTPException(400, "Retirez d'abord l'avis : la suppression se fait aux Archives")
    session.delete(avis)
    session.commit()


@router.put("/{avis_id}/reponse", response_model=AvisRead)
def repondre(
    avis_id: int,
    body: ReponseAvis,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """La réponse du gestionnaire du site ; vide, elle se retire."""
    _exiger_gestionnaire(session, user)
    avis = ou_404(session, Avis, avis_id, "Avis")
    texte = body.reponse.strip() or None
    nouvelle = texte is not None and avis.reponse is None
    avis.reponse = texte
    avis.reponse_par_id = user.id if texte else None
    avis.reponse_le = horloge.maintenant() if texte else None
    _enregistrer(session, avis)
    if nouvelle and avis.auteur_id != user.id:
        sonner(
            session,
            destinataire_id=avis.auteur_id,
            type="communaute_reponse",
            titre="Réponse à votre avis",
            corps=avis.titre[:200],
            lien=lien_element(PREFIXE_LIEN, avis.id),
        )
        session.commit()
    return _rendre(session, avis, user)


@router.patch("/{avis_id}/publication", response_model=AvisRead)
def retenir(
    avis_id: int,
    body: PublicationAvis,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retenir un avis pour coprofirst.fr — seulement s'il est publiable."""
    _exiger_gestionnaire(session, user)
    avis = ou_404(session, Avis, avis_id, "Avis")
    if body.validee and not est_publiable(avis):
        raise HTTPException(
            400,
            "Seul un avis de 4 étoiles ou plus, dont l'auteur a accepté la publication, se retient",
        )
    avis.publication_validee_le = horloge.maintenant() if body.validee else None
    _enregistrer(session, avis)
    return _rendre(session, avis, user)
