"""La PROPOSITION de l'assistant pour fusionner des affaires liées (#2083) —
l'usage `fusion_affaires`.

> « L'IA propose automatiquement un nouveau titre relatif aux titres, et un
> nouveau résumé comprenant les affaires fusionnées (descriptifs, suites et PJ). »

Ce qui part, pour chaque affaire : numéro, catégorie, titre, date d'ouverture,
état, description (en texte), fil daté (`rassemblement.fil_date` : chaque
personne par son rôle, jamais un nom, jamais un message interne au conseil) et
le NOM des pièces jointes — jamais leur contenu.

La proposition n'écrit rien : le conseil la relit, la corrige, puis confirme
(`fusion_en_cours.fusionner`). Sans assistant prêt — service coupé, usage non
activé —, `proposer_fusion` rend une proposition SANS IA (titres joints, descriptions
mises bout à bout) : la fusion ne dépend pas d'un service facturé.

🔴 La réponse est du TEXTE, jamais du HTML : elle est échappée, puis mise en
paragraphes (`en_paragraphes`).
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.tickets import Ticket, TicketEvolution
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.dates_fr import date_courte
from app.utils.description_format import ReponseIllisible, lire_objet
from app.utils.fichiers import nom_lisible
from app.utils.photos import parse_photos
from app.utils.valeurs import valeur

logger = logging.getLogger("hostachy.assistant")

#: Le code de l'usage — lu par `llm_usages`.
USAGE_FUSION_AFFAIRES = "fusion_affaires"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu aides le conseil syndical d'une copropriété à FUSIONNER des affaires liées "
    "qui traitent du même besoin : la plus ancienne absorbe les autres, et prend un "
    "nouveau titre et une nouvelle description.\n"
    "- Le TITRE : court (80 caractères au plus), il nomme le besoin commun à toutes "
    "les affaires, sans numéro ni date.\n"
    "- La DESCRIPTION : en français, factuelle et sobre, quelques paragraphes — le "
    "besoin, ce que chaque affaire y apporte, où en est le dossier, ce qui reste à "
    "faire, et les pièces jointes utiles par leur nom.\n"
    "- Appuie-toi sur toute leur matière : titres, descriptions, fils datés, noms des "
    "pièces jointes. Les dates te sont DONNÉES : reprends-les, n'en invente aucune.\n"
    "- Ne cite aucun nom de personne, aucune adresse, aucun numéro de téléphone ; "
    "désigne les personnes par leur rôle (le syndic, le conseil syndical, l'auteur de "
    "l'affaire, un résident, le prestataire)."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à deux clés :\n"
    '{"titre": "<le nouveau titre>", "description": "<la nouvelle description, texte '
    'sans balise, paragraphes séparés par une ligne vide>"}'
)

MAX_TITRE = 120
MAX_DESCRIPTION = 6_000
MAX_CARACTERES_DESCRIPTIF = 2_000
MAX_CARACTERES_FIL = 4_000


@dataclass(frozen=True)
class Proposition:
    titre: str
    #: HTML : des paragraphes de texte échappé.
    description: str
    #: Rédigée par l'assistant — sinon, composée sans lui.
    assiste_ia: bool


def en_paragraphes(texte: str) -> str:
    """PURE. Du texte en paragraphes HTML échappés — une ligne vide les sépare."""
    blocs = [b.strip() for b in texte.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocs)


def _pieces(session: Session, t: Ticket) -> list[str]:
    urls = parse_photos(t.photos_urls) + parse_photos(t.fichiers_urls)
    for e in session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == t.id)).all():
        urls += parse_photos(e.fichiers_urls)
    return [nom_lisible(u) for u in urls]


def construire_message(blocs: list[dict]) -> str:
    """PURE. Un bloc par affaire, la plus ancienne en tête (elle absorbe)."""
    lignes = [f"Affaires à fusionner : {len(blocs)}. La première absorbe les autres."]
    for b in blocs:
        lignes += [
            "",
            f"### {b['numero']} — « {b['titre']} »",
            f"Catégorie : {b['categorie']} · ouverte le {b['ouverte_le']} · état : {b['etat']}.",
        ]
        if b["description"]:
            lignes.append(f"Description : {b['description'][:MAX_CARACTERES_DESCRIPTIF]}")
        if b["fil"]:
            lignes += ["Fil daté :", b["fil"][-MAX_CARACTERES_FIL:]]
        if b["pieces"]:
            lignes.append("Pièces jointes : " + ", ".join(b["pieces"]))
    return "\n".join(lignes)


def lire_reponse(texte: str) -> tuple[str, str]:
    """Le titre et la description, relus et bornés — illisible sans les deux."""
    objet = lire_objet(texte)
    titre, description = objet.get("titre"), objet.get("description")
    if not isinstance(titre, str) or not isinstance(description, str) or not titre.strip():
        raise ReponseIllisible("Réponse du modèle sans titre ni description.")
    return titre.strip()[:MAX_TITRE], description.strip()[:MAX_DESCRIPTION]


def sans_assistant(tickets: list[Ticket]) -> Proposition:
    """PURE. La proposition composée sans l'assistant : les titres joints, et
    chaque description sous le numéro de son affaire."""
    titre = " / ".join(t.titre for t in tickets)[:MAX_TITRE]
    description = "".join(
        f"<p><strong>{html.escape(t.numero)} — {html.escape(t.titre)}</strong></p>"
        + (t.description or "")
        for t in tickets
    )
    return Proposition(titre, description, False)


async def proposer_fusion(
    session: Session, tickets: list[Ticket], *, demandeur: int
) -> Proposition:
    """La proposition de l'assistant — ou, s'il n'est pas prêt, celle sans lui."""
    from app.routers.tickets.commun import STATUT_LABELS
    from app.utils.llm import config_llm, demander
    from app.utils.synthese_affaire.rassemblement import fil_date, reconnaisseur_syndic

    cfg = config_llm(session, USAGE_FUSION_AFFAIRES)
    if not cfg.pret:
        return sans_assistant(tickets)
    est_syndic = reconnaisseur_syndic(session)
    message = construire_message(
        [
            {
                "numero": t.numero,
                "titre": t.titre,
                "categorie": libelle_categorie(t.categorie),
                "ouverte_le": date_courte(t.cree_le),
                "etat": STATUT_LABELS.get(valeur(t.statut), valeur(t.statut)),
                "description": texte_brut(t.description or ""),
                "fil": fil_date(session, t, STATUT_LABELS, est_syndic),
                "pieces": _pieces(session, t),
            }
            for t in tickets
        ]
    )
    reponse = await demander(
        session,
        usage=USAGE_FUSION_AFFAIRES,
        consigne=cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE,
        message=message,
        demandeur=demandeur,
    )
    try:
        titre, description = lire_reponse(reponse.texte)
    except ReponseIllisible as exc:
        from app.utils.llm import ErreurLLM

        logger.warning("Fusion d'affaires : %s", exc)
        raise ErreurLLM("Le modèle n'a pas répondu dans le format attendu — réessayez.") from exc
    return Proposition(titre, en_paragraphes(description), True)
