"""Les pièces jointes d'un courriel versé dans une affaire (31/10/2026, #2388).

Jusque-là, la relève de la boîte des affaires ne gardait que le TEXTE : le devis
ou la photo qu'un syndic joignait à sa réponse restait dans la boîte, et le
conseil devait l'aller chercher pour le téléverser à la main.

## Deux temps, comme le reste de la relève

1. **`trier(message)`** — pur, sans base ni disque : quelles parties sont des
   pièces, lesquelles s'écartent et pourquoi. Il est appelé à la lecture du
   message, AVANT de savoir s'il sera versé.
2. **`verser(...)`** — n'écrit que si le message est versé : chaque pièce passe
   par la porte unique du téléversement (`fichiers.enregistrer_fichier_recu`,
   `images.enregistrer_image_recue`), avec la famille `document` ou `image` —
   types, plafond et signature du contenu, exactement comme au formulaire.
   Les URLs vont dans `TicketEvolution.fichiers_urls` : une pièce se lit donc par
   qui lit la suite (`visibility/fichiers.PORTEURS`).

## Ce qui n'est pas une pièce

- **La signature du message** : un logo, une icône de réseau social, un pixel de
  suivi — des images de moins de `COTE_MIN_SIGNATURE` pixels de côté, qu'elles
  soient jointes ou intégrées au corps (`Content-ID`). Une photo intégrée par
  l'iPhone ou Mail est grande, et elle reste une pièce : c'est la taille qui
  tranche, pas la façon dont le client l'a jointe. Les fichiers de signature
  électronique et les cartes de visite (`TYPES_DE_SIGNATURE`) aussi. Tout cela
  s'écarte EN SILENCE : le signaler ferait du bruit à chaque message.
- **Un type que les familles n'acceptent pas** (archive, exécutable, invitation…) :
  écarté, et la suite le DIT, nom et raison.
- **Au-delà de `MAX_PIECES`** : les premières sont gardées, les suivantes
  écartées, et le conseil est prévenu (`courriel_boite`).

Un même fichier joint deux fois (le logo d'un fil cité, un envoi doublé) ne
compte qu'une fois : les pièces se dédoublonnent par empreinte.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.utils.courriel_decodage import _parties, _texte
from app.utils.fichiers import FAMILLES, type_annonce
from app.utils.images import dimensions

#: Le nombre de pièces versées pour un message (demandé le 31/10/2026).
MAX_PIECES = 10

#: En deçà, sur son plus grand côté, une image est un élément de signature.
COTE_MIN_SIGNATURE = 300

#: Des fichiers que les clients de messagerie ajoutent d'eux-mêmes à la signature.
TYPES_DE_SIGNATURE = frozenset(
    {
        "application/pkcs7-signature",
        "application/x-pkcs7-signature",
        "application/pgp-signature",
        "application/pgp-keys",
        "text/vcard",
        "text/x-vcard",
        "text/directory",
    }
)

MOTIF_TYPE = "type de fichier non accepté"
MOTIF_AU_DELA = f"au-delà de {MAX_PIECES} pièces jointes"


@dataclass(frozen=True)
class Piece:
    nom: str
    type: str
    famille: str  # « image » ou « document »
    octets: bytes = field(repr=False)


@dataclass(frozen=True)
class Ecart:
    nom: str
    motif: str


@dataclass
class Tri:
    pieces: list[Piece] = field(default_factory=list)
    ecarts: list[Ecart] = field(default_factory=list)

    @property
    def au_dela(self) -> list[Ecart]:
        return [e for e in self.ecarts if e.motif == MOTIF_AU_DELA]


def _nom(partie, rang: int) -> str:
    """Le nom affiché d'une pièce — jamais un saut de ligne ni un chemin."""
    nom = _texte(partie.get_filename() or "") or f"piece-{rang}"
    return re.sub(r"[\r\n\t/\\]", "_", nom).strip()[:120] or f"piece-{rang}"


def _est_le_corps(partie) -> bool:
    """La partie texte ou HTML qui EST le message, et non une pièce jointe."""
    return (
        partie.get_content_type() in ("text/plain", "text/html")
        and not partie.get_filename()
        and partie.get_content_disposition() != "attachment"
    )


def _famille(type_: str, nom: str) -> tuple[str, str] | None:
    """`(famille, type à juger)` d'une pièce, ou None si aucune ne l'accepte."""
    for famille in ("image", "document"):
        juge = type_annonce(type_, nom, famille)
        if juge in FAMILLES[famille].types:
            return famille, juge
    return None


def _de_signature(type_: str, famille: str | None, octets: bytes) -> bool:
    if type_ in TYPES_DE_SIGNATURE:
        return True
    if famille != "image":
        return False
    taille = dimensions(octets)
    return taille is not None and max(taille) < COTE_MIN_SIGNATURE


def trier(message) -> Tri:
    """Les pièces du message, dans l'ordre où il les porte. Sans écriture."""
    tri = Tri()
    vues: set[str] = set()
    propres, _joints = _parties(message)
    for rang, partie in enumerate(propres, start=1):
        if _est_le_corps(partie) or partie.get_content_maintype() == "multipart":
            continue
        octets = partie.get_payload(decode=True) or b""
        if not octets:
            continue
        empreinte = hashlib.sha256(octets).hexdigest()
        if empreinte in vues:
            continue
        vues.add(empreinte)
        type_, nom = partie.get_content_type(), _nom(partie, rang)
        reconnue = _famille(type_, nom)
        if _de_signature(type_, reconnue[0] if reconnue else None, octets):
            continue
        if reconnue is None:
            tri.ecarts.append(Ecart(nom, MOTIF_TYPE))
        elif len(tri.pieces) >= MAX_PIECES:
            tri.ecarts.append(Ecart(nom, MOTIF_AU_DELA))
        else:
            tri.pieces.append(Piece(nom, reconnue[1], reconnue[0], octets))
    return tri


def verser(session, tri: Tri, auteur) -> tuple[list[str], list[Ecart]]:
    """Écrit les pièces retenues. Rend leurs URLs, et TOUS les écarts.

    Une pièce que la famille refuse (trop lourde, contenu qui ne correspond pas à
    son type) rejoint les écarts avec la raison de la porte, et les autres
    passent : un fichier refusé ne fait pas perdre la réponse.
    """
    from fastapi import HTTPException

    from app.utils.fichiers import enregistrer_fichier_recu
    from app.utils.images import enregistrer_image_recue
    from app.utils.stockage import stockage

    urls: list[str] = []
    ecarts = list(tri.ecarts)
    for piece in tri.pieces:
        try:
            if piece.famille == "image":
                url = enregistrer_image_recue(
                    piece.octets, piece.nom, piece.type, "fichiers", user=auteur, session=session
                )
            else:
                nom = enregistrer_fichier_recu(
                    piece.octets,
                    piece.nom,
                    piece.type,
                    "document",
                    "fichiers",
                    user=auteur,
                    session=session,
                )
                url = stockage().url(f"fichiers/{nom}")
        except HTTPException as exc:
            ecarts.append(Ecart(piece.nom, str(exc.detail).rstrip(".")))
            continue
        urls.append(url)
    return urls, ecarts


#: Le texte d'une suite qui ne porte QUE des pièces (un transfert, un envoi sans mot).
PIECES_SEULES = "Pièces jointes transmises par courriel."


def joindre(session, ticket, auteur, suite, tri: Tri | None, *, expediteur: str, envoye_le):
    """Verse les pièces du message dans `suite` — ou dans une suite à elles.

    Rend la suite à écrire, ou None s'il n'y a rien à ajouter au fil. Une suite
    neuve n'est créée que si au moins une pièce a été reprise : un message sans
    mot dont toutes les pièces sont écartées n'apporte rien au fil.
    """
    if tri is None or not (tri.pieces or tri.ecarts):
        return suite
    urls, ecarts = verser(session, tri, auteur)
    if suite is None:
        if not urls:
            return None
        suite = _suite_des_pieces(ticket, auteur, expediteur, envoye_le)
    if urls:
        from app.utils.photos import parse_photos, photos_json

        suite.fichiers_urls = photos_json(parse_photos(suite.fichiers_urls) + urls)
    suite.contenu = (suite.contenu or "") + mention_des_ecarts(ecarts)
    if tri.au_dela:
        _prevenir_le_conseil(session, ticket, expediteur, len(tri.au_dela))
    return suite


def _suite_des_pieces(ticket, auteur, expediteur: str, envoye_le):
    from app.models.core import TicketEvolution
    from app.utils.noms import nom_affiche
    from app.utils.reponse_courriel import contenu_de_la_suite, moment_de_la_suite

    quand = moment_de_la_suite(envoye_le)
    nom = nom_affiche(auteur.prenom, auteur.nom)
    return TicketEvolution(
        ticket_id=ticket.id,
        type="commentaire",
        contenu=contenu_de_la_suite(expediteur, nom, quand, PIECES_SEULES),
        auteur_id=auteur.id,
        cree_le=quand,
    )


def _prevenir_le_conseil(session, ticket, expediteur: str, combien: int) -> None:
    """Au-delà de `MAX_PIECES`, le conseil sait que des pièces attendent dans la boîte."""
    from app.utils.cloche import sonner_systeme
    from app.utils.destinataires import membres_cs_ou_admin
    from app.utils.liens import lien_ticket

    for membre in membres_cs_ou_admin(session):
        sonner_systeme(
            session,
            "tache_du_conseil",
            destinataire_id=membre.id,
            type="ticket_update",
            titre=f"Pièces jointes non reprises sur le ticket #{ticket.numero}",
            corps=(
                f"Un message de « {expediteur} » portait plus de {MAX_PIECES} pièces "
                f"jointes : les {MAX_PIECES} premières sont dans le fil, {combien} autre(s) "
                "restent consultables dans la boîte de réception."
            ),
            lien=lien_ticket(ticket.id),
        )


def mention_des_ecarts(ecarts: list[Ecart]) -> str:
    """Le paragraphe HTML que la suite ajoute quand des pièces n'ont pas été reprises.

    🔴 ÉCHAPPÉ : le nom d'une pièce est écrit par l'expéditeur, et le contenu
    d'une suite est du HTML (`reponse_courriel.contenu_de_la_suite`).
    """
    from html import escape

    if not ecarts:
        return ""
    liste = " ; ".join(f"{e.nom} ({e.motif})" for e in ecarts)
    return f"<p><em>Pièce(s) jointe(s) non reprise(s) : {escape(liste, quote=False)}.</em></p>"
