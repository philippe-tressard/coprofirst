"""Cycle de vie d'un sondage : lister, consulter, créer, modifier, clôturer.

Extrait de `sondages.py` le 17/08/2026 (cf. `__init__.py`). Porte son préfixe
lui-même — `participation`, dont les chemins sont nus, le reçoit du paquet.
"""

import json
from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import get_current_user, peut_editer, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommentaireSondage,
    OptionSondage,
    Sondage,
    Utilisateur,
    VoteSondage,
)
from app.schemas import liste_depuis_json
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.reponses import enrich_reponse, tri_reponses
from app.utils.visibility import resultats_sondage_visibles, sondage_accessible, sondage_clos
from app.utils.config_site import config_site
from app.utils.diffusion import config_diffusion

from .groupe import diffuser_le_sondage
from .commun import (
    SondageCreate,
    SondageRead,
    SondageUpdate,
)
from app.utils.communaute import exiger_acces
from app.utils.liens import adresse_du_site, nom_site, lien_sondage
from app.utils.noms import contexte_personne
from app.utils.assiste_ia import marquer as marquer_assiste_ia
from app.utils.recuperer import ou_404
from app.utils.cloche import sonner

router = APIRouter(prefix="/sondages", tags=["sondages"])


@router.get("", response_model=list[SondageRead])
def list_sondages(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    all_s = session.exec(select(Sondage).order_by(Sondage.cree_le.desc())).all()
    accessible = [s for s in all_s if sondage_accessible(s, user)]
    if not accessible:
        return []
    # Compter les votants distincts par sondage en une seule requête
    ids = [s.id for s in accessible]
    counts = session.exec(
        select(VoteSondage.sondage_id, func.count(func.distinct(VoteSondage.user_id)))
        .where(VoteSondage.sondage_id.in_(ids))
        .group_by(VoteSondage.sondage_id)
    ).all()
    count_map = {row[0]: row[1] for row in counts}
    #  UN seul instant pour toute la liste : douze sondages qui appelleraient
    #  `utcnow()` chacun ne dateraient plus la même clôture. Même raison que
    #  `ContexteFlux.now` — c'est d'ailleurs pourquoi `sondage_clos` prend
    #  `maintenant` en paramètre au lieu de le lire lui-même.
    maintenant = horloge.maintenant()
    seuil_jours = seuil_archivage_jours(session)
    result = []
    for s in accessible:
        d = SondageRead.model_validate(s)
        d.nb_votants = count_map.get(s.id, 0)
        #  La liste ne laisse plus l'écran conclure : c'est la MÊME fonction que
        #  la fiche, le vote, la modification et le fil (#468).
        d.cloture = sondage_clos(s, maintenant)
        #  Idem pour l'archivage : la règle du site, transportée. Le seuil est
        #  lu UNE fois hors de la boucle — deux sondages du même appel ne
        #  peuvent pas être tranchés sur des seuils différents.
        d.archivee = est_archivable("sondage", s, seuil_jours=seuil_jours)
        result.append(d)
    return result


@router.get("/{sondage_id}")
def get_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    s = exiger_objet_autorise(
        session,
        Sondage,
        sondage_id,
        "Sondage",
        user,
        sondage_accessible,
        "Vous n'êtes pas autorisé à accéder à ce sondage",
    )

    options_db = session.exec(
        select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)
    ).all()

    mon_vote = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()

    cloture = sondage_clos(s, horloge.maintenant())

    #  Le filtrage est ICI, pas côté front : un masquage d'affichage laisse les
    #  décomptes dans la réponse réseau. La règle elle-même vit dans
    #  `utils/visibility.py`, à côté de `sondage_accessible` — et elle y est
    #  testée (tests/test_resultats_sondage.py), point d'appel compris.
    resultats_visibles = resultats_sondage_visibles(s.resultats_publics, cloture)

    options_out = []
    for opt in sorted(options_db, key=lambda o: o.ordre):
        option = {
            "id": opt.id,
            "libelle": opt.libelle,
            "ordre": opt.ordre,
            "champ_libre": opt.champ_libre,
        }
        if resultats_visibles:
            votes_opt = session.exec(
                select(VoteSondage).where(VoteSondage.option_id == opt.id)
            ).all()
            option["nb_votes"] = len(votes_opt)
            option["reponses_libres"] = [
                v.reponse_libre for v in votes_opt if v.reponse_libre and v.reponse_libre.strip()
            ]
        #  Clés ABSENTES et non mises à zéro quand les résultats sont masqués :
        #  « 0 vote » se lirait comme « personne n'a voté », ce qui est une autre
        #  information, et fausse.
        options_out.append(option)

    # Enrichissement partagé (nom + bâtiment + rôle, CS mis en avant) — même helper
    # que idées/annonces pour une UX cohérente. CS/admin d'abord, puis chronologique.
    commentaires_db = session.exec(
        select(CommentaireSondage).where(CommentaireSondage.sondage_id == sondage_id)
    ).all()
    commentaires_out = tri_reponses([enrich_reponse(c, session) for c in commentaires_db])

    return {
        "id": s.id,
        "question": s.question,
        "description": s.description,
        "cloture_le": s.cloture_le,
        "resultats_publics": s.resultats_publics,
        "auteur_id": s.auteur_id,
        "cree_le": s.cree_le,
        #  Cette réponse est construite à la main (pas de `response_model`) : la
        #  conversion JSON → liste ne se fait donc pas toute seule. Même règle
        #  que `ListeJson`, appelée et non recopiée.
        "perimetre_cible": liste_depuis_json(s.perimetre_cible),
        "public_cible": liste_depuis_json(s.public_cible),
        "options": options_out,
        "mon_vote": mon_vote.option_id if mon_vote else None,
        "cloture": cloture,
        "cloture_forcee": s.cloture_forcee,
        "commentaires": commentaires_out,
        #  Source UNIQUE de la décision d'affichage. Le front recomposait la sienne
        #  à partir de `resultats_publics`, `cloture` et « ai-je voté » — et se
        #  contredisait d'une ligne à l'autre. Il ne la recompose plus : il ne peut
        #  de toute façon plus afficher ce qui n'est pas envoyé.
        "resultats_visibles": resultats_visibles,
    }


@router.post("", status_code=201)
def create_sondage(
    body: SondageCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    #  Sérialisation JSON, comme les publications. `None` quand la liste est vide :
    #  un `"[]"` et un `None` répondraient à la même question de deux façons.
    perimetre_json = (
        json.dumps(body.perimetre_cible, ensure_ascii=False) if body.perimetre_cible else None
    )
    public_json = json.dumps(body.public_cible, ensure_ascii=False) if body.public_cible else None

    s = Sondage(
        question=body.question,
        description=body.description,
        cloture_le=body.cloture_le,
        resultats_publics=body.resultats_publics,
        auteur_id=user.id,
        perimetre_cible=perimetre_json,
        public_cible=public_json,
        partager_whatsapp=body.partager_whatsapp,
        envoyer_syndic=body.envoyer_syndic,
        envoyer_cs=body.envoyer_cs,
        assiste_ia=body.assiste_ia,
    )
    session.add(s)
    session.flush()

    for opt in body.options:
        session.add(OptionSondage(sondage_id=s.id, **opt.model_dump()))

    #  Notifier exactement ceux qui PEUVENT le voir. Cette boucle réappliquait à
    #  la main les deux filtres de ciblage — une seconde écriture de la règle
    #  d'accès, qui ne connaissait donc ni les périmètres transverses ni le CS.
    #  `sondage_accessible` est désormais la seule à en décider.
    q = select(Utilisateur).where(Utilisateur.actif == True, Utilisateur.id != user.id)  # noqa: E712
    residents = session.exec(q).all()
    for r in residents:
        if not sondage_accessible(s, r):
            continue
        sonner(
            session,
            destinataire_id=r.id,
            type="sondage",
            titre=f"📊 Nouveau sondage : {s.question[:60]}",
            corps="Votre avis compte — participez au sondage.",
            lien=lien_sondage(s.id),
        )

    session.commit()
    session.refresh(s)

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    if body.partager_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        #  Deux lectures, deux notions (#1060) : la configuration du CANAL pour
        #  diffuser, celle du SITE pour les courriels — une seule variable les
        #  confondait, si bien que les courriels lisaient la configuration WhatsApp.
        if body.partager_whatsapp:
            cfg_canal = config_diffusion(session, "reference_copro", "site_nom")
            if cfg_canal is not None:
                diffuser_le_sondage(background_tasks, cfg_canal, s)
        cfg_map = config_site(session, "reference_copro")

        if body.envoyer_syndic or body.envoyer_cs:
            from app.utils.email import send_email_group
            from app.utils.copie_auteur import copie_demandee
            from app.utils.destinataires import destinataires_syndic_cs

            destinataires = destinataires_syndic_cs(
                session, syndic=body.envoyer_syndic, cs=body.envoyer_cs
            )

            # Le template `publication_syndic` déréférence `publication.titre`,
            # `publication.contenu` et `publication.id` : avec la clé `ticket`
            # reprise du mail de ticket, l'envoi échouait à tous les coups en
            # `'publication' is undefined`. Bug LATENT — invisible dans
            # `historique_email` faute d'un sondage créé avec « envoyer au CS »
            # depuis sa mise en place ; trouvé le 01/08/2026 par
            # `tests/test_email_contexte_appel.py`, pas par le pré-check.
            ctx = {
                "publication": {
                    "id": s.id,
                    "titre": s.question,
                    "contenu": s.description or "",
                    #  Le bouton du gabarit : il menait à `/actualites#pub-<id du
                    #  SONDAGE>`, c'est-à-dire à une autre actualité (23/09/2026).
                    "lien": lien_sondage(s.id),
                },
                "auteur": contexte_personne(user),
                "residence": {"nom": nom_site(cfg_map.get("site_nom"))},
                "app": {"url": adresse_du_site()},
                "reference_copro": cfg_map.get("reference_copro", ""),
                # Un sondage n'a pas de pièce jointe, mais le modèle
                # `publication_syndic` teste `fichiers` : Jinja évalue un
                # indéfini à faux sans rien dire, donc le rendu était correct
                # par chance. La clé manquante est précisément ce que
                # `test_email_contexte_appel.py` cherche — on la fournit.
                "fichiers": False,
            }
            if destinataires:
                background_tasks.add_task(
                    send_email_group,
                    code="publication_syndic",
                    to_recipients=destinataires,
                    context=ctx,
                    session=session,
                    #  La copie à l'auteur du sondage — règle commune dans
                    #  `app/utils/copie_auteur.py`. Elle n'existait pas ici,
                    #  alors que la case s'affichait sur cet écran.
                    bcc=copie_demandee(
                        session,
                        s.auteur_id,
                        (e for _, e in destinataires),
                        demandee=bool(body.envoyer_auteur),
                    ),
                )

    return s


# ── Édition / suppression / clôture anticipée ──────────────────────────────


@router.patch("/{sondage_id}")
def modifier_sondage(
    sondage_id: int,
    body: SondageUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Modifier un sondage (auteur ou admin)."""
    s = ou_404(session, Sondage, sondage_id, "Sondage")
    #  L'auteur ou un admin — `peut_editer`, du module central.
    if not peut_editer(s, user):
        raise HTTPException(403, "Seul l'auteur ou un admin peut modifier ce sondage")
    if sondage_clos(s, horloge.maintenant()):
        raise HTTPException(400, "Ce sondage est clôturé et ne peut plus être modifié")

    #  Y a-t-il DÉJÀ des votes ? Tout ce qui suit en dépend : avant le premier
    #  vote un sondage se corrige librement, après il engage des gens.
    deja_vote = (
        session.exec(
            select(VoteSondage.id).where(VoteSondage.sondage_id == sondage_id).limit(1)
        ).first()
        is not None
    )

    donnees = body.model_dump(exclude_unset=True)
    #  La marque « assistant IA » ne s'écrit que dans UN sens (`utils/assiste_ia`).
    marquer_assiste_ia(s, body)
    donnees.pop("assiste_ia", None)

    #  ── La clôture recule, elle n'avance jamais (#467) ──────────────────────
    #  Prolonger n'invalide rien ; raccourcir prive de leur voix ceux qui n'ont
    #  pas encore voté. Poser une échéance là où il n'y en avait aucune est un
    #  raccourcissement : le sondage n'avait pas de fin.
    if "cloture_le" in donnees and deja_vote:
        avant, apres = s.cloture_le, donnees["cloture_le"]
        if apres is None:
            pass  # retirer l'échéance = prolonger indéfiniment, donc reculer
        elif avant is None or apres < avant:
            raise HTTPException(
                400,
                "Des votes ont déjà été exprimés : la date de clôture peut être "
                "reculée, jamais avancée.",
            )

    #  ── Les options : le LIBELLÉ se corrige, la liste ne bouge pas ───────────
    #  Le schéma l'impose déjà (un `id` obligatoire, pas de liste complète) ;
    #  ici on vérifie que l'`id` appartient bien À CE sondage — sans quoi on
    #  renommerait l'option d'un autre.
    corrections = donnees.pop("options", None)
    if corrections:
        siennes = {
            o.id: o
            for o in session.exec(
                select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)
            ).all()
        }
        for corr in corrections:
            option = siennes.get(corr["id"])
            if option is None:
                raise HTTPException(400, "Option inconnue pour ce sondage")
            libelle = (corr["libelle"] or "").strip()
            if not libelle:
                raise HTTPException(400, "Le libellé d'une option ne peut pas être vide")
            option.libelle = libelle
            session.add(option)

    for field, val in donnees.items():
        setattr(s, field, val)
    session.add(s)
    session.commit()
    session.refresh(s)
    return {
        "id": s.id,
        "question": s.question,
        "description": s.description,
        "cloture_le": s.cloture_le,
        "resultats_publics": s.resultats_publics,
        #  Les libellés corrigés, dans l'ordre d'affichage : l'écran relit ce
        #  qu'il vient d'écrire sans redemander la fiche entière.
        "options": [
            {"id": o.id, "libelle": o.libelle, "ordre": o.ordre}
            for o in sorted(s.options, key=lambda o: o.ordre)
        ],
    }


@router.delete("/{sondage_id}", status_code=204)
def supprimer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Supprimer un sondage et toutes ses données (auteur ou admin)."""
    s = ou_404(session, Sondage, sondage_id, "Sondage")
    #  L'auteur ou un admin — `peut_editer`, du module central.
    if not peut_editer(s, user):
        raise HTTPException(403, "Seul l'auteur ou un admin peut supprimer ce sondage")
    # Suppression en cascade
    for c in session.exec(
        select(CommentaireSondage).where(CommentaireSondage.sondage_id == sondage_id)
    ).all():
        session.delete(c)
    for v in session.exec(select(VoteSondage).where(VoteSondage.sondage_id == sondage_id)).all():
        session.delete(v)
    for o in session.exec(
        select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)
    ).all():
        session.delete(o)
    session.delete(s)
    session.commit()


@router.patch("/{sondage_id}/cloturer", status_code=200)
def cloturer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Stopper un sondage immédiatement (auteur ou admin)."""
    s = ou_404(session, Sondage, sondage_id, "Sondage")
    #  L'auteur ou un admin — `peut_editer`, du module central.
    if not peut_editer(s, user):
        raise HTTPException(403, "Seul l'auteur ou un admin peut clôturer ce sondage")
    s.cloture_forcee = True
    session.add(s)
    session.commit()
    return {"message": "Sondage clôturé"}
