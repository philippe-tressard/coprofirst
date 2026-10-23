"""La FUSION d'affaires à la clôture (#1704) — la règle, écrite une fois.

## La demande (05/10/2026)

> « Pour une affaire liée, à la clôture, demander si ces affaires doivent être
> fusionnées (si les affaires liées sont non closes). Si oui (même besoin
> fonctionnel & périmètre) il y a fusion des affaires et suites dans l'ordre
> chronologique. Le bilan de clôture comprend alors la totalité des affaires
> liées. Les affaires fusionnées sont closes simultanément. »

## Arbitré le même jour — ne pas rouvrir (#1704)

* **Absorption** : l'affaire qu'on clôt est la PRINCIPALE. Les Suites, messages,
  documents et courriels des autres lui sont rattachés ; le fil se trie par
  date, l'ordre chronologique vient de lui-même.
* « Même besoin & périmètre » : **le conseil juge**. Aucun refus automatique
  sur la catégorie ou le périmètre — la question rappelle le critère.
* 🔒 **Fusion refusée** si un lecteur de la principale ne pouvait pas lire
  l'absorbée : ses Suites lui deviendraient lisibles. Comparé compte par compte,
  par `ticket_visible` — la règle de la fiche, jamais une recopie.
* La description d'une absorbée devient une **Suite d'ouverture** de la
  principale, datée de sa création et signée de son auteur.
* L'absorbée sort du **carnet** et des moyennes (`utils/affaire_absorbee`) ;
  la durée de la principale court depuis la plus ancienne ouverture.
* Le bilan est la **synthèse IA** de la principale (#1643) : elle lit le fil
  fusionné, rien de plus à écrire.
* Pas de défusion. L'absorbée garde son numéro, et son suivi est terminé : elle
  ne reçoit plus de Suite (`refuser_si_absorbee`).

## Ce qui ne bouge PAS

* La Suite `synthese` d'une absorbée (une clôture antérieure, puis une
  réouverture) : son texte vit dans `synthese_affaire`, rattaché à SON affaire.
* Ses affiches de hall : elles désignent l'absorbée, dont la fiche renvoie.

## ⚠️ Une transition d'absorbée devient un COMMENTAIRE

« Ouvert → Chez le syndic » de TK-B, versé tel quel dans le fil de TK-A, ferait
mentir le suivi de TK-A : `statuts_avant` et les métriques de la synthèse lisent
les transitions du fil comme les siennes. Elle y entre en commentaire qui la
RACONTE. Même raison pour la marque « Venue de TK-… » en tête de chaque Suite
versée : une correction d'absorbée (« État : A → B ») ne se lit plus comme une
correction de la principale (`corrections.est_correction` lit la tête).
"""

from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, or_, select

from app.auth.deps import est_moderateur
from app.models.affaires_liees import AffaireLiee
from app.models.core import STATUTS_TICKET_CLOS, Ticket, TicketEvolution, Utilisateur
from app.utils.recuperer import ou_rien
from app.models.courriel import CourrielReleve, FilCourriel, MessageVerse, VersementCourriel
from app.models.documents import Document
from app.models.tickets import MessageTicket
from app.utils import horloge

#  `_lue` : la forme d'une affaire NOMMÉE (numéro, titre, statut), écrite une fois.
from app.utils.affaires_liees import _lue, ids_lies
from app.utils.nature_affaire import est_actualite
from app.utils.photos import parse_photos, photos_json
from app.utils.synthese_affaire.lecture import TYPE_SYNTHESE
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible

#: Ce que dit une affaire liée qu'on ne peut pas absorber sans fuite — à la
#: clôture comme depuis la correction (#2173), d'où « qui l'absorberait » et
#: non plus « qu'on clôt ».
MOTIF_LECTEURS = "lue par moins de monde que l'affaire qui l'absorberait"

#: Les tables qui suivent l'affaire, par leur colonne `ticket_id`. La Suite et
#: le message ont leur traitement (marque, Suite d'ouverture) ; celles-ci
#: changent seulement de porteur.
_RATTACHEES = (Document, CourrielReleve, FilCourriel, MessageVerse, VersementCourriel)


def principale_lue(session: Session, ticket: Ticket, lecteur: Utilisateur | None):
    """L'affaire qui a absorbé celle-ci, si CE lecteur la lit — un lien ne
    révèle rien (`utils/affaires_liees`). `None` sinon."""
    if ticket.fusionnee_dans_id is None or lecteur is None:
        return None
    p = session.get(Ticket, ticket.fusionnee_dans_id)
    return _lue(p) if p is not None and ticket_visible(p, lecteur) else None


def refuser_si_absorbee(ticket: Ticket) -> None:
    """Une absorbée ne reçoit plus de Suite ni d'état : son fil vit ailleurs (422)."""
    if ticket.fusionnee_dans_id is not None:
        raise HTTPException(
            422, "Cette affaire a été fusionnée : son suivi se poursuit dans l'affaire principale"
        )


def _sans_fuite(session: Session, principale: Ticket, absorbee: Ticket) -> bool:
    """Tout lecteur de la principale lisait déjà l'absorbée — compte par compte."""
    return all(
        ticket_visible(absorbee, u)
        for u in session.exec(select(Utilisateur)).all()
        if ticket_visible(principale, u)
    )


def candidates(session: Session, principale: Ticket, lecteur: Utilisateur) -> list[dict]:
    """Les affaires liées qu'on peut proposer à la fusion : non closes, lisibles
    par qui clôt, ni actualité ni déjà absorbées, ni écartées par le conseil
    (#2083) — chacune avec son verdict."""
    from app.utils.fusion_en_cours import liens_ecartes

    rendu = []
    #  Une fusion écartée par le conseil n'est plus proposée (#2083).
    ecartees = liens_ecartes(session, principale.id)
    for i in sorted(ids_lies(session, principale.id) - ecartees):
        t = session.get(Ticket, i)
        if (
            t is None
            or valeur(t.statut) in STATUTS_TICKET_CLOS
            or t.fusionnee_dans_id is not None
            or est_actualite(t)
            or not ticket_visible(t, lecteur)
        ):
            continue
        fusionnable = _sans_fuite(session, principale, t)
        rendu.append(
            {
                **_lue(t),
                "fusionnable": fusionnable,
                "motif": None if fusionnable else MOTIF_LECTEURS,
            }
        )
    return rendu


def _absorbables(session: Session, principale: Ticket, ids, lecteur: Utilisateur) -> list[Ticket]:
    """Les affaires demandées, chacune candidate ET fusionnable — sinon 422."""
    if not est_moderateur(lecteur):
        raise HTTPException(403, "Seul le conseil syndical fusionne des affaires")
    admises = {c["id"]: c for c in candidates(session, principale, lecteur)}
    rendu = []
    for i in sorted({int(x) for x in ids}):
        c = admises.get(i)
        if c is None:
            raise HTTPException(422, f"Affaire à fusionner introuvable (#{i})")
        if not c["fusionnable"]:
            raise HTTPException(422, f"Fusion refusée : {c['numero']} est {MOTIF_LECTEURS}")
        rendu.append(session.get(Ticket, i))
    return rendu


def _marque(numero: str) -> str:
    return f"<p><em>↪ Venue de {numero}</em></p>"


def _verser_suites(session: Session, absorbee: Ticket, principale: Ticket) -> None:
    """Les Suites de l'absorbée rejoignent la principale, marquées, à leur date."""
    from app.routers.tickets.commun import STATUT_LABELS  # libellés de l'écran

    for e in session.exec(
        select(TicketEvolution).where(
            TicketEvolution.ticket_id == absorbee.id, TicketEvolution.type != TYPE_SYNTHESE
        )
    ).all():
        recit = ""
        if e.type == "etat":
            avant = STATUT_LABELS.get(e.ancien_statut or "", e.ancien_statut or "—")
            apres = STATUT_LABELS.get(e.nouveau_statut or "", e.nouveau_statut or "—")
            recit = f"<p><em>État : {avant} → {apres}</em></p>"
            e.type, e.ancien_statut, e.nouveau_statut = "commentaire", None, None
        e.contenu = _marque(absorbee.numero) + recit + (e.contenu or "")
        e.ticket_id = principale.id
        session.add(e)


def _suite_d_ouverture(absorbee: Ticket, principale: Ticket) -> TicketEvolution:
    """Sa description devient une Suite de la principale, datée de sa création."""
    pieces = parse_photos(absorbee.photos_urls) + parse_photos(absorbee.fichiers_urls)
    return TicketEvolution(
        ticket_id=principale.id,
        type="commentaire",
        contenu=(
            f"<p><strong>Ouverture de {absorbee.numero} — {absorbee.titre}</strong></p>"
            + (absorbee.description or "")
        ),
        auteur_id=absorbee.auteur_id,
        cree_le=absorbee.cree_le,
        fichiers_urls=photos_json(pieces),
        assiste_ia=absorbee.assiste_ia,
    )


def _deplacer_liens(session: Session, absorbee: Ticket, principale: Ticket, lecteur) -> None:
    """Les autres liens de l'absorbée passent à la principale ; le sien reste."""
    for lg in session.exec(
        select(AffaireLiee).where(
            or_(AffaireLiee.affaire_id == absorbee.id, AffaireLiee.liee_id == absorbee.id)
        )
    ).all():
        autre = lg.liee_id if lg.affaire_id == absorbee.id else lg.affaire_id
        if autre == principale.id:
            continue
        session.delete(lg)
        if autre not in ids_lies(session, principale.id):
            a, b = sorted((principale.id, autre))
            session.add(AffaireLiee(affaire_id=a, liee_id=b, cree_par_id=lecteur.id))
    session.flush()


def fusionner(
    session: Session,
    principale: Ticket,
    ids,
    lecteur: Utilisateur,
    suite: TicketEvolution | None,
) -> list[tuple[Ticket, str]]:
    """Absorbe les affaires `ids` dans `principale`, qui vient d'être close par
    `suite` — elles prennent son état au même instant. Rend chacune avec l'état
    qu'elle quitte (l'avis à son auteur le dit). Sans `commit`."""
    absorbees = _absorbables(session, principale, ids or [], lecteur)
    statut = valeur(principale.statut)
    rendu = []
    for a in absorbees:
        rendu.append((a, valeur(a.statut)))
        _verser_suites(session, a, principale)
        session.add(_suite_d_ouverture(a, principale))
        for m in session.exec(select(MessageTicket).where(MessageTicket.ticket_id == a.id)).all():
            m.ticket_id = principale.id
            session.add(m)
        for modele in _RATTACHEES:
            for x in session.exec(select(modele).where(modele.ticket_id == a.id)).all():
                x.ticket_id = principale.id
                session.add(x)
        _deplacer_liens(session, a, principale, lecteur)
        session.add(
            TicketEvolution(
                ticket_id=a.id,
                type="etat",
                ancien_statut=valeur(a.statut),
                nouveau_statut=statut,
                contenu=f"<p><em>🔀 Fusionnée dans {principale.numero} : le suivi s'y poursuit.</em></p>",
                auteur_id=lecteur.id,
                cree_le=horloge.maintenant(),
            )
        )
        a.statut, a.ferme_le = principale.statut, principale.ferme_le
        a.fusionnee_dans_id = principale.id
        a.mis_a_jour_le = horloge.maintenant()
        session.add(a)
    if absorbees and suite is not None:
        numeros = ", ".join(a.numero for a in absorbees)
        suite.contenu = (suite.contenu or "") + f"<p><em>🔀 Fusion : {numeros}</em></p>"
        session.add(suite)
    return rendu


def prevenir_auteurs(
    session: Session,
    background_tasks: BackgroundTasks,
    absorbees: list[tuple[Ticket, str]],
    lecteur: Utilisateur,
    *,
    courriel: bool,
    deja: set[int],
) -> None:
    """L'auteur d'une absorbée apprend sa clôture — UNE fois, quel que soit le
    nombre de ses affaires absorbées, et jamais s'il est déjà prévenu (`deja`)
    ou s'il agit lui-même. Le lien mène à SON affaire : il ne lit peut-être pas
    la principale, et la fiche de l'absorbée dit où le suivi se poursuit."""
    from app.routers.tickets.commun import STATUT_LABELS, config_site, contexte_site
    from app.utils.cloche import sonner
    from app.utils.email import send_email
    from app.utils.liens import lien_ticket
    from app.utils.noms import contexte_personne

    cfg = config_site(session)
    prevenus = set(deja) | {lecteur.id}
    for a, avant in absorbees:
        if a.auteur_id in prevenus:
            continue
        prevenus.add(a.auteur_id)
        libelle = STATUT_LABELS.get(valeur(a.statut), valeur(a.statut))
        auteur = ou_rien(session, Utilisateur, a.auteur_id)
        if courriel and auteur and auteur.email:
            background_tasks.add_task(
                send_email,
                code="ticket_statut_change",
                to=auteur.email,
                context={
                    "ticket": {
                        "id": a.id,
                        "numero": a.numero,
                        "titre": a.titre,
                        "statut": libelle,
                        "ancien_statut": STATUT_LABELS.get(avant, avant),
                    },
                    "destinataire": {"prenom": auteur.prenom, "nom": auteur.nom},
                    "auteur_action": contexte_personne(lecteur),
                    **contexte_site(cfg),
                },
                destinataire_id=a.auteur_id,
            )
        sonner(
            session,
            destinataire_id=a.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{a.numero} — statut : {libelle} (fusionnée)",
            corps="Le suivi de votre affaire se poursuit dans l'affaire qui l'a absorbée.",
            lien=lien_ticket(a.id),
        )
