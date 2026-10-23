"""Admin — Accueil d'un arrivant, baux locatifs et fiche d'arrivée.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    AgCsInfo,
    MembreCS,
    MembreSyndic,
    Notification,
    StatutUtilisateur,
    SyndicInfo,
    Utilisateur,
)

#  Importé sous un autre nom : plusieurs de ces fonctions affectent une variable
#  LOCALE `site_manager_user_id`, et l'import serait alors masqué. C'est la raison
#  d'être de l'ancien alias `_get_site_manager_user_id`, supprimé au découpage.
from app.utils.annuaire import membres_du_conseil, membres_du_syndic
from app.utils.destinataires import site_manager_user_id as _site_manager_user_id
from app.utils.destinataires import syndic_principal as _syndic_principal
from app.utils.syndic import nom_du_syndic
from app.utils.consignes_arrivant import (
    Consigne,
    Consignes,
    consignes_en_html,
    enregistrer_consignes,
    lire_consignes,
)
from html import escape
from typing import Optional
from app.utils.noms import nom_affiche
from app.utils.annonce_arrivee import creer_annonce_arrivee

#  Les trois gestes de l'accueil vivent côte à côte : le ticket de suivi,
#  l'annonce aux voisins, et le message d'arrivée avec ses consignes.
from app.utils.courriel_arrivee import FICHE_CONSIGNES, destinataires_arrivee
from app.utils.courriel_arrivee import envoyer as envoyer_message_arrivee
from app.utils.ticket_arrivant import creer_ticket_arrivant, ticket_arrivant_existant
from app.utils.recuperer import ou_404
from app.utils.cloche import sonner_systeme
from app.utils.config_site import config_site
from app.utils.liens import adresse_du_site, nom_site
from app.utils.logo import logo_televerse_png

router = APIRouter()


class AccueilArrivantBody(BaseModel):
    batiment: Optional[str] = None
    ancien_resident: Optional[str] = None
    ancien_resident_inconnu: bool = False


def _declencher_accueil_arrivant(
    user: Utilisateur,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session,
    allow_repeat: bool = False,
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel."""
    if not user.actif:
        raise HTTPException(400, "Le compte doit être actif pour déclarer un nouvel arrivant")

    statuts_residentiels = {
        StatutUtilisateur.copropriétaire_résident,
        StatutUtilisateur.copropriétaire_bailleur,
        StatutUtilisateur.locataire,
    }
    if user.statut not in statuts_residentiels:
        raise HTTPException(400, "Cette démarche est réservée aux profils résidentiels")

    if not allow_repeat:
        #  🔴 La notification seule ne suffisait pas (#2163) : son destinataire peut
        #  la supprimer (`DELETE /notifications/{id}`), puis redéclencher la démarche
        #  — et le syndic et le conseil recevaient à nouveau courriels et
        #  notifications. L'affaire de suivi, elle, n'est pas à lui : il ne
        #  l'efface pas. Le conseil garde la relance (`allow_repeat=True`).
        deja_declenche = (
            ticket_arrivant_existant(session, user.id)
            or session.exec(
                select(Notification).where(
                    Notification.destinataire_id == user.id,
                    Notification.titre == "Bienvenue dans la résidence !",
                )
            ).first()
        )
        if deja_declenche:
            raise HTTPException(
                409, "La démarche Nouvel Arrivant a déjà été déclarée pour ce compte"
            )

    nom_complet = nom_affiche(user.prenom, user.nom)
    bat = body.batiment or ""
    ancien = body.ancien_resident or ""
    bat_str = f", {bat}" if bat else ""
    ancien_str = f" (ancien résident : {ancien})" if ancien else ""
    nb_notifs = 0

    # ── A. Notification unique regroupée → arrivant ───────────────────────────
    demarches: list[str] = []

    # Syndic principal (pour l'email BAL)
    syndic_principal: MembreSyndic | None = _syndic_principal(session)
    if syndic_principal:
        demarches.append(
            f"• Demande d'étiquette boîte aux lettres transmise au syndic{bat_str}{ancien_str}."
        )

    # CS du bâtiment + gestionnaire du site (pour les notifs interphone)
    cs_query = select(MembreCS).where(MembreCS.user_id != None)  # noqa: E711
    site_manager_user_id = _site_manager_user_id(session)
    if user.batiment_id:
        cs_filters = MembreCS.batiment_id == user.batiment_id
        if site_manager_user_id is not None:
            cs_filters = cs_filters | (MembreCS.user_id == site_manager_user_id)
        cs_members = session.exec(cs_query.where(cs_filters)).all()
    else:
        if site_manager_user_id is not None:
            cs_members = session.exec(
                cs_query.where(MembreCS.user_id == site_manager_user_id)
            ).all()
        else:
            cs_members = []
    # Dédoublonner par user_id
    cs_seen: set[int] = set()
    cs_unique: list[MembreCS] = []
    for mc in cs_members:
        if mc.user_id not in cs_seen:
            cs_seen.add(mc.user_id)
            cs_unique.append(mc)

    if cs_unique:
        demarches.append(
            f"• Demande d'ajout sur l'interphone transmise au Conseil Syndical{bat_str}{ancien_str}."
        )

    # Corps en HTML : `safeRichContent()` côté front bascule en mode HTML dès qu'une
    # balise est détectée et ne convertit alors plus les `\n` en `<br>`. Tout le
    # corps doit donc être structuré, sinon l'ajout du lien écraserait la mise en
    # forme. Bénéfice au passage : les `**gras**` de l'ancienne version, qui
    # s'affichaient avec leurs astérisques (aucun rendu markdown côté front),
    # deviennent de vrais `<strong>`.
    demarches_html = ""
    if demarches:
        # Les puces arrivent préfixées « • » (format texte) — on les retire au
        # profit d'un vrai <ul>.
        items = "".join(f"<li>{escape(d.lstrip('• ').strip())}</li>" for d in demarches)
        demarches_html = f"<p><strong>Démarches initiées en votre nom</strong></p><ul>{items}</ul>"

    FICHE_URL = FICHE_CONSIGNES

    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre="Bienvenue dans la résidence !",
        corps=(
            f"<p>Bienvenue {escape(user.prenom)} ! Nous sommes heureux de vous "
            "accueillir dans notre résidence. Vous trouverez dans cette application "
            "toutes les informations pratiques : actualités, documents, contacts "
            "et services.</p>"
            "<p><strong>Consignes de la copropriété</strong><br>"
            "Règlement intérieur, consignes de tri, modalités d'accès, "
            "stationnement et contacts utiles sont réunis dans votre fiche "
            f'd\'accueil : <a href="{FICHE_URL}" target="_blank" rel="noopener">'
            "consulter les consignes de la copropriété</a>.</p>" + demarches_html
        ),
        lien=FICHE_URL,
    )
    nb_notifs += 1

    # ── B. Notification interphone → CS du bâtiment + gestionnaire du site ─────
    for mc in cs_unique:
        sonner_systeme(
            session,
            "tache_du_conseil",
            destinataire_id=mc.user_id,
            type="system",
            titre="Accueil — Demande d'ajout sur l'interphone",
            corps=(
                f"Merci d'ajouter le nom **{nom_complet}**{bat_str}{ancien_str} "
                "sur l'interphone du bâtiment concerné."
            ),
        )
        nb_notifs += 1

    # ── C. LE MESSAGE D'ARRIVÉE → syndic, arrivant, ET conseil du bâtiment ────
    #  Un seul modèle — `nouvel_arrivant_bal` — adapté à ses trois publics par
    #  `role_destinataire`. Le récit complet, et pourquoi un second modèle a
    #  failli naître, sont dans `utils/courriel_arrivee`.
    #
    #  ⚠️ Les membres passés ici sont ceux que la section B vient de notifier :
    #  le courriel ne doit atteindre personne d'autre.
    destinataires = destinataires_arrivee(
        session,
        user,
        syndic_principal=syndic_principal,
        membres_cs_notifies={mc.user_id for mc in cs_unique},
    )
    #  🔴 Ce booléen décide de la DIFFUSION du ticket ci-dessous : quand les
    #  consignes sont parties au résident ET au conseil, la diffusion ferait un
    #  second message disant la même chose, le même jour, aux mêmes personnes.
    consignes_transmises = envoyer_message_arrivee(
        session,
        background_tasks,
        destinataires,
        nom_complet=nom_complet,
        batiment=bat,
        ancien_resident=ancien,
    )

    # ── D. LE TICKET DE SUIVI ────────────────────────────────────────────────
    #  🔴 Signalé le 07/09/2026 : *« le syndic n'a rien fait depuis deux semaines
    #  et le locataire a créé lui-même un ticket »*.
    #
    #  Tout ce qui précède ENVOIE : une notification qui se lit une fois puis
    #  quitte la pile, un e-mail qui tombe dans une boîte. Rien ne mesurait le
    #  FAIT — la démarche réalisée — et personne ne voyait que ça traînait.
    #  C'est `standards/04` §14 : observer la chose, pas son enregistrement.
    #
    #  ⚠️ Les notifications restent : elles PRÉVIENNENT, le ticket SUIT. Retirer
    #  l'alerte immédiate au profit d'une ligne dans une liste aurait échangé un
    #  défaut contre un autre.
    ticket = creer_ticket_arrivant(
        session,
        user,
        nom_complet=nom_complet,
        batiment=bat,
        ancien=ancien,
        demarches=demarches,
        vers_syndic=bool(syndic_principal) and not consignes_transmises,
        vers_cs=bool(cs_unique) and not consignes_transmises,
    )

    # ── E. L'ANNONCE AUX VOISINS ─────────────────────────────────────────────
    #  Demandé le 07/09/2026 : une actualité de bienvenue, avec le bâtiment et
    #  l'étage — et SANS aucune donnée personnelle.
    #
    #  ⚠️ Ce qui n'y entre jamais est écrit noir sur blanc dans
    #  `utils/annonce_arrivee.CHAMPS_INTERDITS`, et un test construit l'annonce
    #  depuis un compte dont l'e-mail, le téléphone et le nom du propriétaire
    #  sont remplis de valeurs reconnaissables. Une intention ne survit pas au
    #  premier enrichissement du gabarit ; un contrôle, oui.
    annonce = creer_annonce_arrivee(session, user, nom_complet=nom_complet, ancien=ancien)

    # ── Persister le choix en base ───────────────────────────────────────────
    user.demarche_arrivant = "nouvel_arrivant"

    session.commit()
    return {
        "ok": True,
        "notifications_envoyees": nb_notifs,
        "email_syndic": bool(syndic_principal and syndic_principal.email),
        #  Le numéro, pas un booléen : l'écran peut y renvoyer, et le compte rendu
        #  d'une MEP peut le retrouver. `None` quand le ticket existait déjà.
        "ticket_suivi": ticket.numero if ticket else None,
        "annonce_publiee": bool(annonce),
        #  Le compte rendu dit si les consignes sont sorties de l'application —
        #  c'est ce fait, et lui seul, qui a coupé la diffusion du ticket.
        "consignes_transmises": consignes_transmises,
    }


@router.post("/utilisateurs/{user_id}/accueil-arrivant")
def accueil_arrivant(
    user_id: int,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel (CS/Admin)."""
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=True)


@router.post("/me/accueil-arrivant")
def accueil_arrivant_me(
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Self-service : l'utilisateur déclare lui-même son arrivée dans la résidence."""
    ancien = (body.ancien_resident or "").strip()
    if not ancien and not body.ancien_resident_inconnu:
        raise HTTPException(
            422, "Le nom de l'ancien résident est requis (ou cochez 'Je ne sais pas')."
        )
    if body.ancien_resident_inconnu:
        body.ancien_resident = "Ne sait pas"
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=False)


# ── Gestion manuelle des baux locatifs ────────────────────────────────────────

#  🔴 DEUX ENDPOINTS RETIRÉS LE 13/09/2026, SUR OBSERVATION (#808).
#
#  `POST /admin/baux/{id}/lier-locataire/{user}` — rattacher à la main un compte
#  locataire à son bail — et `GET /admin/baux` — la liste qui devait l'alimenter.
#
#  L'arbitrage du 06/09 était *« garder et observer »* : on ne savait pas si
#  l'auto-match échouait en pratique. Le relevé qui permet d'observer est livré
#  depuis le 07/09 (`GET /admin/audit/baux-sans-locataire`, onglet **Audit lots**),
#  et il a répondu : **tous les baux en cours ont leur locataire rattaché.**
#
#  Le cas ne s'est jamais présenté. Un endpoint d'écriture que rien n'appelle est
#  une surface exposée sans usage ; le garder « au cas où » revient à maintenir
#  une capacité que personne n'éprouve. L'historique git le rend en une commande
#  le jour où le besoin apparaît — et ce jour-là, le relevé dira AUSSI pourquoi
#  l'auto-match a échoué, ce qui est la vraie question (un écart d'orthographe,
#  un lot mal importé et une ambiguïté réelle n'appellent pas le même remède).
#
#  ⚠️ Le RELEVÉ reste, lui : c'est lui qui surveille, et c'est ce qui permet de
#  rouvrir la question sur un fait plutôt que sur une intuition.


# ── Fiche arrivant (génération dynamique) ────────────────────────────────────


@router.get("/fiche-arrivant")
def get_fiche_arrivant(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Génère la fiche arrivant HTML à partir des données annuaire actuelles."""
    from app.utils import horloge
    from fastapi.responses import HTMLResponse
    from app.utils.fiche_arrivant import generer_fiche_arrivant

    #  🔴 « même logique que GET /admin/annuaire » : c'était vrai, et c'était le
    #  problème (#852). Trente et une lignes identiques, et deux divergences déjà
    #  installées — dont `est_gestionnaire_site`, qui ne disait pas la même chose
    #  ici et là pour l'identifiant 0. La composition vit dans `utils/annuaire`.
    ag = session.exec(select(AgCsInfo)).first()
    cs_membres = membres_du_conseil(session)
    syndic_info = session.exec(select(SyndicInfo)).first()
    syndic_membres = membres_du_syndic(session)

    #  Une lecture de la configuration pour les trois réglages : le nom et
    #  l'adresse du site n'étaient pas lus du tout (#1725), et la fiche imprimait
    #  ceux de cette résidence, en dur.
    site = config_site(session, "whatsapp_community_url")
    whatsapp_url = (site.get("whatsapp_community_url") or "").strip() or None

    html = generer_fiche_arrivant(
        cs_data={
            "ag_annee": ag.ag_annee if ag else None,
            "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
            "membres": cs_membres,
        },
        syndic_data={
            #  🔴 Le CONTRAT fait foi (#535). C'est le consommateur qui compte le
            #  plus : la fiche arrivant est REMISE aux nouveaux résidents, et ils
            #  n'ont aucun moyen de savoir qu'elle nomme l'ancien syndic.
            "nom_syndic": nom_du_syndic(session),
            "adresse": syndic_info.adresse if syndic_info else "",
            "site_web": syndic_info.site_web if syndic_info else None,
            "membres": syndic_membres,
        },
        site_nom=nom_site(site.get("site_nom")),
        site_url=adresse_du_site(),
        logo_png=logo_televerse_png(session),
        whatsapp_url=whatsapp_url,
        #  Éditables par le CS, rendues échappées ; le syndic y est NOMMÉ par le
        #  contrat, comme dans l'encart ci-dessus (#1727).
        consignes=consignes_en_html(lire_consignes(session), nom_du_syndic(session)),
        annee=horloge.aujourd_hui().year,
    )
    # Jamais de cache : la fiche est régénérée à chaque appel depuis l'annuaire
    # (membres du CS, syndic, date d'AG). Sans ces en-têtes, un navigateur pouvait
    # garder une copie et afficher une fiche périmée après une modification de
    # l'annuaire — ou après un correctif, ce qui a semé la confusion le 26/07/2026.
    # Le document contient en outre des données personnelles : on évite qu'il
    # traîne dans un cache partagé.
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
    )


# ── Les consignes de la fiche, éditables par le conseil syndical (#1727) ────


class _ConsignesSaisies(BaseModel):
    """Le corps de l'enregistrement : les rubriques, rien d'autre."""

    consignes: list[Consigne] = Field(min_length=1, max_length=12)


@router.get("/consignes-arrivant", response_model=Consignes)
def get_consignes_arrivant(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les consignes de la résidence — le gabarit tant que rien n'est saisi."""
    return lire_consignes(session)


@router.put("/consignes-arrivant", response_model=Consignes)
def put_consignes_arrivant(
    body: _ConsignesSaisies,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Enregistre les consignes de la résidence. Du texte : la fiche l'échappe."""
    return enregistrer_consignes(session, body.consignes)
