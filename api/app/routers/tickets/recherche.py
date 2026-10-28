"""Recherche libre dans les affaires — ce que le lecteur a le droit de lire, et rien d'autre.

La règle de correspondance vit dans `app/utils/recherche_affaires.py` ; ce module
ne fait que rassembler, pour CE lecteur, les textes qu'il pourrait lire à l'écran :

- les affaires : `ticket_visible`, la règle de la liste ;
- leur fil de suivi : la même règle que l'affaire — `GET /{id}/evolutions`
  applique `ticket_visible` depuis le 29/09/2026 ;
- leurs messages : les notes internes selon `lit_les_notes_internes`, la règle de
  `GET /{id}/messages` ;
- leurs documents : `document_visible`, la règle du téléchargement.

🔴 Aucune de ces quatre règles n'est réécrite ici. Une recherche qui lirait plus
large que l'écran révélerait, par un simple compte de résultats, qu'un mot existe
dans une note interne ou le fil d'une affaire voisine.

⚠️ Coût assumé, comme la liste (`crud.list_tickets`) : toutes les affaires puis
leurs suites, messages et documents en TROIS requêtes, et non une par affaire.
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.auth.deps import get_current_user, lit_les_notes_internes
from app.database import get_session
from app.models.core import MessageTicket, Ticket, TicketEvolution, Utilisateur
from app.models.documents import Document
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.fichiers import nom_lisible
from app.utils.noms import nom_auteur
from app.utils.perimetres import parse_json_perimetres, perimetre_label
from app.utils.photos import parse_photos
from app.utils.recherche_affaires import Texte, correspondance, termes
from app.utils.saisi_pour import noms_derives
from app.utils.visibility import ticket_visible
from app.utils.visibility.documents import document_visible

from .commun import nom_prestataire, trier_par_activite

router = APIRouter()


class Segment(BaseModel):
    texte: str
    surligne: bool


class CorrespondanceAffaire(BaseModel):
    """Une affaire trouvée : où, et le passage qui l'a fait trouver."""

    ticket_id: int
    ou: str
    extrait: list[Segment] = []
    date: Optional[datetime] = None
    auteur: Optional[str] = None


def _pieces(urls: list[str], champ_date: Optional[datetime] = None) -> list[Texte]:
    return [Texte("piece_jointe", nom_lisible(u), date=champ_date) for u in urls]


def _par_affaire(lignes) -> dict[int, list]:
    groupes: dict[int, list] = defaultdict(list)
    for ligne in lignes:
        groupes[ligne.ticket_id].append(ligne)
    return groupes


@router.get("/recherche", response_model=list[CorrespondanceAffaire])
def rechercher(
    q: str = Query(..., min_length=2, max_length=200),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Les affaires lisibles qui contiennent TOUS les mots de `q`, les plus pertinentes d'abord.

    Archives comprises : c'est l'écran qui décide de les montrer.
    """
    mots = termes(q)
    if not mots:
        return []
    affaires = [
        t
        for t in trier_par_activite(session, session.exec(select(Ticket)).all())
        if ticket_visible(t, user)
    ]
    ids = [t.id for t in affaires]
    suites = _par_affaire(
        session.exec(
            select(TicketEvolution)
            .where(col(TicketEvolution.ticket_id).in_(ids))
            .order_by(TicketEvolution.cree_le)
        ).all()
    )
    requete_messages = select(MessageTicket).where(col(MessageTicket.ticket_id).in_(ids))
    if not lit_les_notes_internes(user):
        requete_messages = requete_messages.where(MessageTicket.interne == False)  # noqa: E712
    messages = _par_affaire(session.exec(requete_messages.order_by(MessageTicket.cree_le)).all())
    documents = _par_affaire(
        d
        for d in session.exec(select(Document).where(col(Document.ticket_id).in_(ids))).all()
        if document_visible(user, d, session)
    )
    noms: dict[tuple[Optional[int], Optional[str]], str] = {}

    def nom(porteur) -> str:
        #  Sans compte (supprimé, #1688) : « Ancien résident », comme à l'écran ;
        #  détaché par la conservation (#2014) : sa qualité.
        uid, qualite = porteur.auteur_id, porteur.auteur_qualite
        if (uid, qualite) not in noms:
            auteur = session.get(Utilisateur, uid) if uid is not None else None
            noms[(uid, qualite)] = nom_auteur(auteur, qualite)
        return noms[(uid, qualite)]

    trouves = []
    for rang, t in enumerate(affaires):
        proprietaire, _ = noms_derives(session, t)
        textes = [
            Texte("numero", t.numero),
            Texte("titre", t.titre),
            Texte("categorie", libelle_categorie(t.categorie)),
            Texte("lieu", perimetre_label(parse_json_perimetres(t.perimetre_cible))),
            Texte("personne", nom(t)),
            Texte("personne", proprietaire or ""),
            Texte("prestataire", nom_prestataire(session, t.prestataire_id) or ""),
            #  Le libellé de l'équipement n'existe qu'au front (`#lib/prestataires`) :
            #  la valeur, soulignés en espaces, suffit à « vmc », « porte parking ».
            Texte("equipement", (t.equipement or "").replace("_", " ")),
            Texte("description", texte_brut(t.description)),
            *_pieces(parse_photos(t.photos_urls) + parse_photos(t.fichiers_urls)),
        ]
        for e in suites.get(t.id, []):
            textes.append(
                Texte(
                    "suite",
                    texte_brut(e.contenu or ""),
                    date=e.cree_le,
                    auteur=nom(e),
                )
            )
            textes += _pieces(parse_photos(e.fichiers_urls), e.cree_le)
        for m in messages.get(t.id, []):
            textes.append(Texte("message", texte_brut(m.contenu), date=m.cree_le, auteur=nom(m)))
            textes += _pieces(parse_photos(m.fichiers_urls), m.cree_le)
        for d in documents.get(t.id, []):
            textes.append(Texte("piece_jointe", f"{d.titre} {d.fichier_nom}", date=d.publie_le))
        r = correspondance(textes, mots)
        if r:
            trouves.append((-r.score, rang, t.id, r))
    #  Le score d'abord ; à score égal, l'ordre de la liste (l'activité).
    return [
        CorrespondanceAffaire(
            ticket_id=tid, ou=r.ou, extrait=r.extrait, date=r.date, auteur=r.auteur
        )
        for _, _, tid, r in sorted(trouves, key=lambda x: (x[0], x[1]))
    ]
