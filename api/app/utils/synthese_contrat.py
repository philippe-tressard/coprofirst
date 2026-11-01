"""Proposer la synthèse d'un contrat d'entretien — le format, et ce qu'on envoie.

## Ce que ce module fait

Il assemble une demande et la pose au modèle configuré (`utils/llm.py`) :

1. **le gabarit** — les sept sections arrêtées par le conseil syndical ;
2. **des exemples** — les synthèses que le CS a déjà écrites, qui apprennent le
   ton et la longueur mieux qu'aucune consigne ne saurait les décrire ;
3. **ce que la base sait** du contrat — libellé, prestataire, dates, périmètre ;
4. **le texte des documents joints**, sans lesquels quatre sections sur sept
   resteraient vides.

Il ne rend qu'un TEXTE. Rien n'est enregistré : c'est le conseil syndical qui
relit, corrige et valide — une synthèse fausse au carnet d'entretien serait pire
que pas de synthèse, ce carnet étant un document réglementaire (décret
n° 2001-477).

## 🔴 Pourquoi le document part, et ce qui ne part pas

Arbitré le 11/09/2026. Les sept sections réclament l'adresse et le RCS du
fournisseur, les clauses de reconduction et de résiliation, les prestations
incluses et exclues, le détail des montants : **rien de tout cela n'existe dans
les champs d'un contrat**. Sans le PDF, la fonctionnalité n'a pas d'objet.

Ce qui part est donc le contrat lui-même, et lui seul :

| | |
|---|---|
| **tous les documents du contrat** | envoyés, en texte extrait — jamais les fichiers |
| une pièce jointe d'un ticket, d'une actualité, d'un autre objet | **jamais** |

⚠️ **Tous**, et pas seulement celui que le contrat désigne : un contrat en a
plusieurs — l'initial, ses avenants, les conditions générales (signalé à l'écran
le 11/09/2026). N'en lire qu'un rendrait la section 6 fausse dès le premier
avenant, puisque c'est là que le prix change.

⚠️ Ce sont des données **d'entreprise** — montants, RCS, clauses. Un contrat
d'entretien de copropriété ne porte pas de donnée personnelle de résident. La
réserve honnête tient au nom et à la signature du président du conseil syndical,
qui figurent parfois au pied d'un contrat signé : ils partiraient avec le reste.

⚠️ L'envoi se coupe depuis l'administration (`llm_envoi_document`). La synthèse
reste alors possible, mais elle ne remplit que ce que la base sait — et elle le
DIT, plutôt que de rendre des sections vides sans explication.
"""

from __future__ import annotations

import base64
import html
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from app.utils import horloge

from sqlmodel import Session, select

from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.dates_fr import datetime_longue_paris
from app.utils.llm import ConfigLLM, ErreurLLM, PieceJointe, config_llm, demander
from app.utils.stockage import stockage
from app.utils.equipements import libelle_equipement
from app.utils.llm_usages import USAGE_SYNTHESE_CONTRAT
from app.utils.perimetres import parse_json_perimetres, perimetre_label_liste
from app.utils.synthese_format import CONSIGNE, CONSIGNE_CITATIONS, GABARIT

logger = logging.getLogger("hostachy.synthese")

#: Combien de caractères du contrat au plus. Un contrat d'ascenseur fait deux à
#: dix pages ; au-delà de ce plafond on coupe, et on le dit au modèle plutôt que
#: de le laisser conclure sur un texte tronqué sans le savoir.
MAX_CARACTERES_DOCUMENT = 60_000

#: Au-delà, on ne joint pas le fichier : une requête trop lourde est refusée par
#: le service, et l'encodage en base64 l'alourdit encore d'un tiers. Un contrat
#: numérisé de quelques pages pèse deux à cinq cents kilo-octets ; ce qui dépasse
#: ce plafond n'est pas un contrat, c'est un rapport ou un plan.
MAX_OCTETS_DOCUMENT_JOINT = 4 * 1024 * 1024

#: Et au total, pour la requête entière.
MAX_OCTETS_JOINTS = 8 * 1024 * 1024

#: Combien de synthèses déjà écrites servent d'exemples. Trois suffisent à faire
#: passer un format ; au-delà on paie des jetons pour répéter la même leçon.
MAX_EXEMPLES = 3


def documents_du_contrat(session: Session, contrat: ContratEntretien) -> list[Document]:
    """TOUS les documents du contrat, du plus ancien au plus récent.

    🔴 **Un contrat en a plusieurs**, et c'est le cas normal (signalé à l'écran
    le 11/09/2026). Le contrat initial, ses avenants, les conditions générales,
    une attestation. N'en lire qu'un — fût-ce celui que le contrat désigne —
    produirait une synthèse fausse dès le premier avenant : les conditions
    financières y changent, et la section 6 annoncerait l'ancien prix.

    L'ordre CHRONOLOGIQUE porte le sens : ce qui vient après modifie ce qui
    précède. C'est pourquoi on ne trie ni par titre ni par taille.

    🔴 **Le pointeur `document_id` n'intervient plus** (17/09/2026, #989).

    Il insérait en tête « le document désigné, s'il n'est pas déjà joint » — et
    cette condition dit tout : un document réellement rattaché au contrat figure
    déjà dans la requête ci-dessous, donc la seule branche que le code pouvait
    prendre était celle d'un document **qui n'est pas de ce contrat**. Un
    contrat d'ascenseur a ainsi lu, et annoncé dans son encart de provenance,
    « Entretien toitures Bat 2 » : le fichier d'un autre contrat, parti au
    service d'IA, ce que l'en-tête de ce module interdit.

    La règle du document désigné n'a pas disparu : elle vit dans
    `utils/document_contrat`, où la fiche copropriété la consomme pour son lien
    de téléchargement, avec la garde qui manquait.
    """
    return list(
        session.exec(
            select(Document).where(Document.contrat_id == contrat.id).order_by(Document.publie_le)
        ).all()
    )


def texte_du_document(doc: Document) -> str:
    """Le texte d'un PDF, extrait côté serveur — jamais le fichier lui-même.

    Rend une chaîne vide quand il n'y a rien à lire : un PDF scanné sans couche
    de texte, un format non géré, un fichier absent. L'appelant le traite comme
    « pas de document », ce qui est vrai de son point de vue.
    """
    chemin = stockage().fichier_de(doc)
    if chemin is None or not (doc.mime_type or "").lower().endswith("pdf"):
        return ""
    try:
        from pypdf import PdfReader

        lecteur = PdfReader(chemin)
        morceaux = []
        total = 0
        for page in lecteur.pages:
            t = (page.extract_text() or "").strip()
            if not t:
                continue
            morceaux.append(t)
            total += len(t)
            if total >= MAX_CARACTERES_DOCUMENT:
                break
        return "\n\n".join(morceaux)[:MAX_CARACTERES_DOCUMENT]
    except Exception as exc:  # noqa: BLE001 — un PDF illisible n'est pas une panne
        logger.warning("Lecture du document %s impossible : %s", doc.id, exc)
        return ""


def exemples(session: Session, contrat: ContratEntretien) -> list[str]:
    """Les synthèses déjà écrites, qui apprennent le format de la maison.

    Priorité aux contrats du MÊME type d'équipement : une synthèse d'ascenseur
    ressemble plus à une autre synthèse d'ascenseur qu'à celle d'un contrat
    d'espaces verts — c'est le voisinage qui rend l'exemple utile.
    """
    tous = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.id != contrat.id,
            ContratEntretien.actif == True,  # noqa: E712
            ContratEntretien.notes != None,  # noqa: E711
        )
    ).all()
    avec_notes = [c for c in tous if (c.notes or "").strip()]
    meme_type = [c for c in avec_notes if c.type_equipement == contrat.type_equipement]
    autres = [c for c in avec_notes if c.type_equipement != contrat.type_equipement]
    return [(c.notes or "").strip() for c in (meme_type + autres)[:MAX_EXEMPLES]]


def ce_que_la_base_sait(session: Session, contrat: ContratEntretien) -> str:
    """Les champs du contrat, en clair — ils fondent les sections 1 à 3."""
    prest = session.get(Prestataire, contrat.prestataire_id)
    duree = (
        f"{contrat.duree_initiale_valeur} {contrat.duree_initiale_unite}"
        if contrat.duree_initiale_valeur
        else None
    )
    frequence = (
        f"{contrat.frequence_valeur} ({contrat.frequence_type})"
        if contrat.frequence_valeur
        else None
    )
    lignes = [
        ("Libellé", contrat.libelle),
        ("Type d'équipement", libelle_equipement(session, contrat.type_equipement)),
        ("Prestataire", prest.nom if prest else None),
        ("Téléphone du prestataire", prest.telephone if prest else None),
        ("Courriel du prestataire", prest.email if prest else None),
        ("Numéro de contrat", contrat.numero_contrat),
        ("Date de début", contrat.date_debut.isoformat() if contrat.date_debut else None),
        ("Durée initiale", duree),
        ("Fréquence des visites", frequence),
        (
            "Périmètre couvert",
            perimetre_label_liste(parse_json_perimetres(contrat.perimetre_cible)),
        ),
    ]
    return "\n".join(f"- {k} : {v}" for k, v in lignes if v)


@dataclass(frozen=True)
class Matiere:
    """Ce qu'on envoie au modèle, et l'inventaire de ce qui a servi.

    🔴 L'inventaire n'est pas décoratif : l'encart de provenance doit nommer ce
    qui a été LU, et surtout ce qui ne l'a pas été. Le 11/09/2026, les deux PDF
    d'un contrat de porte de parking étaient des numérisations sans couche de
    texte : la synthèse rendait « non précisé » sur quatre sections et rien ne
    disait pourquoi — cela ressemblait à un mauvais modèle.
    """

    message: str
    #: Les fichiers joints tels quels, faute de texte extractible.
    fichiers: tuple[PieceJointe, ...]
    #: Titres des documents dont le texte a été extrait.
    lus_en_texte: tuple[str, ...]
    #: Titres des documents joints en fichier.
    joints: tuple[str, ...]
    #: Titres des documents qu'on n'a su ni lire ni joindre, avec le motif.
    ecartes: tuple[tuple[str, str], ...]


def piece_jointe(doc: Document) -> PieceJointe | None:
    """Le document tel quel, prêt à être lu par le modèle — ou `None`.

    ⚠️ On ne joint QUE ce qu'on n'a pas su lire : un PDF dont le texte s'extrait
    coûte bien moins cher en texte qu'en fichier, pour le même contenu.
    """
    chemin = stockage().fichier_de(doc)
    if chemin is None:
        return None
    if os.path.getsize(chemin) > MAX_OCTETS_DOCUMENT_JOINT:
        return None
    try:
        with open(chemin, "rb") as fichier:
            octets = fichier.read()
    except OSError as exc:  # noqa: BLE001 - un fichier illisible n'est pas une panne
        logger.warning("Lecture du fichier %s impossible : %s", doc.id, exc)
        return None
    return PieceJointe(
        nom=doc.fichier_nom or f"document-{doc.id}.pdf",
        mime=doc.mime_type or "application/pdf",
        donnees_b64=base64.b64encode(octets).decode("ascii"),
    )


def construire_matiere(
    session: Session, contrat: ContratEntretien, *, avec_document: bool
) -> Matiere:
    """Le message posé au modèle, et l'inventaire de ce qui a servi.

    🔴 Trois sorts possibles pour un document, dans cet ordre de préférence
    (11/09/2026) :

    | Sort | Quand | Pourquoi |
    |---|---|---|
    | **texte extrait** | `pypdf` en tire quelque chose | bien moins cher, et exact |
    | **fichier joint** | aucun texte — une numérisation | le modèle le lit lui-même |
    | **écarté** | absent, trop lourd | on le DIT plutôt que de le taire |

    La deuxième ligne est née d'un vrai contrat : les deux PDF de la porte de
    parking étaient des numérisations signées, `pypdf` en tirait zéro caractère,
    et quatre sections sur sept sortaient vides. La majorité des contrats de
    copropriété sont signés, donc numérisés : sans cette voie, la fonctionnalité
    ne servait que les documents nés numériques.
    """
    blocs = []

    modeles = exemples(session, contrat)
    if modeles:
        blocs.append(
            "Voici des synthèses déjà rédigées par ce conseil syndical, pour d'AUTRES "
            "contrats. Reprends leur ton, leur longueur et leur façon de formuler — "
            "n'en reprends AUCUN fait : ni montant, ni durée, ni clause, ni "
            "fournisseur :\n\n" + "\n\n---\n\n".join(modeles)
        )

    blocs.append("Ce que la fiche du contrat indique :\n" + ce_que_la_base_sait(session, contrat))

    if not avec_document:
        blocs.append(
            "L'envoi du document est désactivé. Les sections 4 à 7 doivent porter "
            "« non précisé dans les éléments fournis »."
        )
        return Matiere("\n\n".join(blocs), (), (), (), ())

    #  Chaque document est ANNONCÉ par son titre et sa date : sans eux, le
    #  modèle lit une seule masse de texte et ne peut pas savoir qu'un avenant
    #  remplace une clause du contrat initial.
    lus, fichiers = [], []
    en_texte, en_fichier, ecartes = [], [], []
    budget = MAX_CARACTERES_DOCUMENT
    budget_octets = MAX_OCTETS_JOINTS
    for doc in documents_du_contrat(session, contrat):
        #  `publie_le` est un instant de la base (UTC) : son jour se lit à Paris.
        quand = horloge.jour_civil(doc.publie_le).isoformat() if doc.publie_le else "date inconnue"
        texte_doc = texte_du_document(doc)
        if texte_doc and budget > 0:
            extrait = texte_doc[:budget]
            budget -= len(extrait)
            tronque = " — TRONQUÉ" if len(extrait) < len(texte_doc) else ""
            lus.append(f"--- Document « {doc.titre} » (déposé le {quand}){tronque} ---\n{extrait}")
            en_texte.append(doc.titre)
            continue
        #  Pas de texte : le fichier part tel quel. C'est le cas NORMAL d'un
        #  contrat signé, donc numérisé.
        piece = piece_jointe(doc)
        if piece is None:
            ecartes.append((doc.titre, "illisible ou trop volumineux"))
            continue
        if len(piece.donnees_b64) > budget_octets:
            ecartes.append((doc.titre, "au-delà du volume que le service accepte"))
            continue
        budget_octets -= len(piece.donnees_b64)
        fichiers.append(piece)
        en_fichier.append(doc.titre)

    texte = "\n\n".join(lus)
    if texte:
        blocs.append(
            "Documents du contrat, du plus ancien au plus récent. Un document "
            "postérieur peut MODIFIER une clause d'un précédent — un avenant "
            "l'emporte sur le contrat initial :\n\n" + texte
        )
    if fichiers:
        blocs.append(
            "Les documents joints à ce message sont ceux de ce contrat, du plus ancien "
            "au plus récent : lis-les toi-même, leur texte n'a pas pu être extrait (ce "
            "sont des documents signés, donc numérisés). Un document postérieur MODIFIE "
            "une clause d'un précédent."
        )
    if not texte and not fichiers:
        #  ⚠️ On le DIT au modèle plutôt que de le laisser deviner : sans cette
        #  phrase, il comble les sections manquantes par des formules plausibles,
        #  ce qui est le pire résultat possible ici.
        blocs.append(
            "Aucun texte de contrat n'a pu être lu. Les sections 4 à 7 doivent porter "
            "« non précisé dans les éléments fournis »."
        )

    return Matiere(
        message="\n\n".join(blocs),
        fichiers=tuple(fichiers),
        lus_en_texte=tuple(en_texte),
        joints=tuple(en_fichier),
        ecartes=tuple(ecartes),
    )


def construire_message(session: Session, contrat: ContratEntretien, *, avec_document: bool) -> str:
    """Le message seul — l'inventaire et les pièces jointes vivent dans
    `construire_matiere`, dont ceci n'est que la face texte."""
    return construire_matiere(session, contrat, avec_document=avec_document).message


def entete_provenance(
    cfg: ConfigLLM, matiere: Matiere, *, quand: datetime, documents_joints: int
) -> str:
    """L'encart qui dit d'où vient le texte : quel modèle, quand, sur quoi.

    🔴 Demandé le 11/09/2026, et ce n'est pas une politesse. La synthèse atterrit
    dans les notes du contrat, où elle devient indiscernable de celles que le
    conseil syndical a écrites à la main — or elle n'a ni le même auteur, ni la
    même fiabilité, et elle VIEILLIT : un avenant déposé après coup la rend
    fausse sans rien changer à son texte.

    Les trois informations répondent chacune à une question qui se pose plus
    tard : *qui l'a écrite ?* (le modèle, nommé — deux modèles ne rendent pas la
    même chose), *de quand date-t-elle ?*, et *qu'a-t-elle lu ?* — c'est la
    dernière qui permet de voir qu'un document manquait.

    🔴 Et surtout : ce qu'elle n'a PAS lu. Le même jour, sur le premier vrai
    contrat, les deux PDF étaient des numérisations sans texte ; la synthèse
    rendait « non précisé » sur quatre sections et rien ne disait pourquoi. Un
    document écarté se DIT, sinon la synthèse se lit comme une lecture complète.

    ⚠️ Tout est ÉCHAPPÉ puis rendu en HTML : un nom de fichier peut porter un `&`
    ou un chevron, et il voyage jusqu'à un `{@html}` (assaini, mais on ne fait
    pas reposer la correction du rendu sur l'assainisseur).
    """
    e = html.escape
    phrases = []
    lus = list(matiere.lus_en_texte)
    #  Un fichier que le service a refusé n'a pas été lu, quoi qu'on ait envoyé :
    #  c'est le nombre REÇU qui fait foi, pas celui qu'on espérait joindre.
    if documents_joints:
        lus += list(matiere.joints)
        ecartes = list(matiere.ecartes)
    else:
        ecartes = list(matiere.ecartes) + [
            (titre, "non transmis au service") for titre in matiere.joints
        ]

    if lus:
        phrases.append(" à partir de " + " ; ".join(e(t) for t in lus))
    else:
        phrases.append(" à partir des seules données de la fiche du contrat")

    entete = (
        "<blockquote><p><em>Synthèse proposée par "
        f"{e(cfg.fournisseur.libelle)} · {e(cfg.modele)} le "
        f"{e(datetime_longue_paris(quand))}{''.join(phrases)}. "
        "À relire et à corriger avant de l'enregistrer.</em></p>"
    )
    if ecartes:
        details = " ; ".join(f"{e(titre)} ({e(motif)})" for titre, motif in ecartes)
        entete += f"<p><em>⚠️ Document non lu, la synthèse est donc partielle : {details}.</em></p>"
    return entete + "</blockquote>"


async def synthetiser(session: Session, contrat: ContratEntretien, *, demandeur: int) -> str:
    """Propose la synthèse d'un contrat, précédée de sa provenance. N'enregistre RIEN.

    🔴 La consigne n'est PLUS `synthese_format.CONSIGNE` (17/09/2026, #984) :
    c'est le prompt de l'usage, tel que l'administration l'a réglé — `CONSIGNE`
    n'en est que la valeur d'origine, posée en base une fois par la migration
    0194. `demander` la lit lui-même quand on ne lui en passe pas.
    """
    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    matiere = construire_matiere(session, contrat, avec_document=cfg.envoi_document)
    reponse = await demander(
        session,
        usage=USAGE_SYNTHESE_CONTRAT,
        message=matiere.message,
        fichiers=matiere.fichiers,
        demandeur=demandeur,
    )
    #  L'horodatage est pris APRÈS la réponse : c'est la date de la synthèse
    #  rendue, pas celle de la demande — une requête peut durer une minute.
    entete = entete_provenance(
        cfg, matiere, quand=horloge.maintenant(), documents_joints=reponse.documents_joints
    )
    return entete + "\n" + reponse.texte.strip()


def synthese_disponible(session: Session, contrat: ContratEntretien) -> bool:
    """Le geste a-t-il un sens sur ce contrat ?

    🔴 C'est le SERVEUR qui le dit, pas l'écran. Une règle de disponibilité
    écrite dans une page serait une règle de plus à tenir à jour, et la
    configuration de l'assistant n'a rien à faire dans la session d'un membre du
    conseil syndical (`standards/03` §1 — l'autorisation est centralisée).

    ⚠️ Un contrat sans document reste éligible **si** l'envoi du document est
    désactivé : la synthèse est alors partielle, et c'est un choix assumé de
    l'administration. Ce qui n'a pas de sens, c'est de proposer une synthèse
    complète sans la matière qui la remplit.
    """
    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    #  `pret` vérifie les DEUX étages d'activation, la clé et le modèle de
    #  l'usage — la même règle que `verifier()`, pas une seconde écriture.
    if not cfg.pret:
        return False
    if not cfg.envoi_document:
        return True
    return bool(documents_du_contrat(session, contrat))


__all__ = [
    "CONSIGNE",
    "CONSIGNE_CITATIONS",
    "GABARIT",
    "ErreurLLM",
    "Matiere",
    "construire_matiere",
    "construire_message",
    "entete_provenance",
    "documents_du_contrat",
    "exemples",
    "synthese_disponible",
    "synthetiser",
    "texte_du_document",
]
