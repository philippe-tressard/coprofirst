"""L'assistant lit l'état descriptif du règlement et remplit l'atelier (#2218) — l'usage
`lecture_etat_descriptif`.

Une copropriété sans tableau tout prêt n'a qu'un règlement — celui qu'elle a versé
dans Ma résidence › Règlement pour les questions au règlement. Le transcrire à la
main pour cent ou deux cents lots est le frein qui laisserait les lots vides
(spec `specs/architecture/lots-et-perimetres.md` §8, chemin 3).

## Ce que l'assistant fait, et ce qu'il ne fait jamais

Il lit le texte du règlement (`question_reglement.texte.assembler`, la même source
que les questions) et rend, en JSON imposé, une ligne par lot — nature, bâtiment,
porte ou place, niveau, circulation qui le dessert, tantièmes par clé, la page ou le
passage d'où il les tient, et sa confiance — plus les clés et leur dénominateur tel
que l'acte le déclare.

🔴 **Il n'écrit jamais dans le patrimoine.** Sa réponse devient le MÊME tableau qu'un
fichier téléversé (`etat_descriptif.lire`), rangé dans la table de passage
(`etat_descriptif_application.ecrire`) : les mêmes contrôles s'appliquent — somme d'une
clé ≠ dénominateur, lot absent d'un côté… — et rien ne touche aux lots avant le geste
« Appliquer » de l'administrateur. Une ligne lue sans certitude porte la marque
`MARQUE_DOUTEUX` dans sa source, et un constat « À savoir » la relève.

## Pourquoi en tâche de fond

Un règlement entier, et une réponse de cent à deux cents lignes : l'appel dure
plusieurs minutes — au-delà de ce qu'un mandataire HTTP laisse attendre une
requête (Cloudflare coupe à 100 s). La route ouvre donc un import « lecture en
cours » et rend la main ; la tâche le remplit, ou y note son échec ; l'écran suit.

## Ce qui part chez le fournisseur

La consigne de l'usage et le texte du règlement — rien d'autre : ni nom de compte,
ni liste du syndic. C'est le texte que les questions au règlement envoient déjà, et
que la politique de confidentialité nomme.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator
from sqlmodel import Session

from app import contexte
from app.utils.description_format import ReponseIllisible, lire_objet
from app.utils.etat_descriptif import EN_TETES_FIXES, MARQUE_DOUTEUX

logger = logging.getLogger("hostachy.assistant")

#: Le code de l'usage — lu par `llm_usages`.
USAGE_LECTURE_ETAT_DESCRIPTIF = "lecture_etat_descriptif"

#: Le prompt D'ORIGINE — l'administration peut le reprendre (Admin › Assistant IA) ;
#: le FORMAT ci-dessous, lui, s'ajoute toujours : sans lui, la réponse ne se lit pas.
CONSIGNE = """Tu es un clerc de notaire qui transcrit l'état descriptif de division d'un \
règlement de copropriété français.

On te donne le texte du règlement, actes modificatifs compris. Rends, pour CHAQUE lot qui \
existe à la date du dernier acte, une ligne :
- lot : son numéro dans l'acte ;
- batiment : la lettre (ou le numéro) du bâtiment où il est situé, telle que l'acte l'écrit ; \
vide pour une place ou une cave d'un volume qui n'est pas un bâtiment lettré (parking commun) ;
- nature : logement, commerce, cave, parking ou divers ;
- numero_usage : la porte ou la place que le texte donne (« n° 12 »), « 5 & 6 » pour un \
double emplacement — qui reste UN lot ;
- niveau : le niveau en entier (rez-de-chaussée 0, premier étage 1, deuxième sous-sol -2) ;
- circulation : la lettre du bâtiment dont l'ascenseur et l'escalier DESSERVENT le lot — la \
colonne de desserte des tableaux de répartition (souvent « ASCEN ») ; vide s'il n'y en a pas \
(accès direct). Pour un logement, son propre bâtiment ;
- quotes : ses tantièmes, une entrée par clé de charges où il contribue — « Charges \
générales », puis, pour chaque bâtiment X dont il figure au tableau, « Bâtiment X », \
« Ascenseur X », « Escalier X », « Escalier X' »… selon les colonnes de l'acte ;
- lot_origine : seulement pour un lot né d'une division, le numéro du lot divisé ;
- page_source : où tu l'as lu (livre, page ou ligne, tableau) — OBLIGATOIRE ;
- confiance : « sûr », ou « douteux » si le passage est illisible, ambigu, ou marqué [?].

Et les clés : leur libellé, exactement comme dans les quotes, et leur dénominateur tel que \
l'acte le déclare (10 000, 1 000…) — le dernier acte modificatif l'emporte.

Règles :
- N'invente rien. Un lot supprimé par un acte modificatif ne figure plus ; un lot créé y figure.
- Ne corrige JAMAIS un chiffre pour qu'une somme tombe juste : recopie-le, et marque la \
ligne « douteux ». La somme se contrôle ailleurs.
- Aucun nom de personne : ni propriétaire, ni notaire, ni vendeur."""

#: Le format de réponse — imposé par le code, jamais par le prompt réglable.
FORMAT_REPONSE = """Réponds par un SEUL objet JSON, sans texte autour :
{"cles": [{"libelle": "Charges générales", "denominateur": 10000}],
 "lots": [{"lot": "12", "batiment": "A", "nature": "logement", "numero_usage": "12",
           "niveau": 1, "circulation": "A", "quotes": {"Charges générales": 120},
           "lot_origine": null, "page_source": "p. 14, état descriptif", "confiance": "sûr"}]}
Les tantièmes sont des ENTIERS. Une clé citée dans « quotes » figure dans « cles »."""


class CleLue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    libelle: str = Field(min_length=1)
    denominateur: StrictInt = Field(gt=0)


class LotLu(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lot: str = Field(min_length=1)
    batiment: Optional[str] = None
    nature: str = Field(min_length=1)
    numero_usage: Optional[str] = None
    niveau: Optional[int] = None
    circulation: Optional[str] = None
    quotes: dict[str, StrictInt] = {}
    lot_origine: Optional[str] = None
    page_source: str = Field(min_length=1)
    confiance: Literal["sûr", "douteux"] = "douteux"

    @field_validator("lot", "lot_origine", "numero_usage", mode="before")
    @classmethod
    def _en_texte(cls, v):
        """Un numéro rendu en nombre reste un numéro — « 12 », pas 12."""
        return str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


class LectureIA(BaseModel):
    cles: list[CleLue]
    lots: list[LotLu] = Field(min_length=1)


def lire_reponse(texte: str) -> LectureIA:
    """PURE. La réponse du modèle, validée — ou `ReponseIllisible`.

    Refusé : une ligne sans `page_source`, un tantième qui n'est pas un entier, une
    clé citée qui n'est pas déclarée. Mieux vaut refuser toute la lecture que de
    poser dans l'atelier un tableau qu'on ne pourrait pas faire remonter à l'acte.
    """
    try:
        lecture = LectureIA.model_validate(lire_objet(texte))
    except ValidationError as exc:
        raise ReponseIllisible(f"Réponse hors format : {exc.error_count()} écart(s).") from exc
    declarees = {c.libelle for c in lecture.cles}
    inconnues = sorted({k for lu in lecture.lots for k in lu.quotes} - declarees)
    if inconnues:
        raise ReponseIllisible("Clé citée sans dénominateur : " + ", ".join(inconnues))
    return lecture


def en_tableau(lecture: LectureIA) -> list:
    """PURE. La lecture, sous la forme d'un classeur téléversé — en-têtes compris.

    Les lignes douteuses passent EN TÊTE : ce sont elles que l'administrateur relit
    d'abord. Leur source porte `MARQUE_DOUTEUX`, que les contrôles relèvent.
    """
    cles = [c.libelle for c in lecture.cles]
    en_tetes = [*EN_TETES_FIXES, *(f"{c.libelle} /{c.denominateur}" for c in lecture.cles)]
    lignes = []
    for lu in sorted(lecture.lots, key=lambda x: x.confiance != "douteux"):
        source = lu.page_source
        if lu.confiance == "douteux":
            source = f"{source} — {MARQUE_DOUTEUX}"
        lignes.append(
            [
                lu.lot,
                lu.batiment,
                lu.nature,
                lu.numero_usage,
                None if lu.niveau is None else str(lu.niveau),
                lu.circulation or "/",
                lu.lot_origine,
                source,
                *(lu.quotes.get(c) for c in cles),
            ]
        )
    return [en_tetes, *lignes]


async def lire_le_reglement(session: Session, demandeur: Optional[int]) -> list:
    """Interroge l'assistant sur le règlement versé ; rend le tableau. Lève `ErreurLLM`."""
    from app.utils.llm import ErreurLLM, config_llm, demander
    from app.utils.question_reglement.texte import assembler

    texte = assembler(session)
    if texte is None:
        raise ErreurLLM("Aucun règlement n'est versé (Ma résidence › Règlement).")
    cfg = config_llm(session, USAGE_LECTURE_ETAT_DESCRIPTIF)
    reponse = await demander(
        session,
        usage=USAGE_LECTURE_ETAT_DESCRIPTIF,
        consigne=cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE,
        message=texte.contenu,
        demandeur=demandeur,
    )
    try:
        return en_tableau(lire_reponse(reponse.texte))
    except ReponseIllisible as exc:
        logger.warning("Lecture de l'état descriptif : %s", exc)
        raise ErreurLLM(
            "L'assistant n'a pas rendu le tableau attendu — réessayez, ou importez un fichier."
        ) from exc


async def remplir_en_tache_de_fond(copro, import_id: int, demandeur: Optional[int]) -> None:
    """Remplit l'import « lecture en cours », ou y note l'échec — jamais ne lève.

    `copro` est celle de la requête : la tâche tourne après la réponse, et ne doit
    pas dépendre de ce que le contexte devient d'ici là.
    """
    from app.models.etat_descriptif import ImportEtatDescriptif
    from app.utils.etat_descriptif_application import LECTURE_TERMINEE, ecrire, noter_echec
    from app.utils.llm import ErreurLLM

    with contexte.dans(copro), contexte.nouvelle_session() as session:
        try:
            rows = await lire_le_reglement(session, demandeur)
            erreur = None
        except ErreurLLM as exc:  # limites d'appels comprises (`RefusLimite`)
            rows, erreur = None, str(exc)
        except Exception:
            #  Rien ne doit laisser l'import « en cours » : l'écran le relirait sans fin.
            logger.exception("Lecture de l'état descriptif : échec inattendu")
            session.rollback()
            rows, erreur = None, "La lecture a échoué — réessayez, ou importez un fichier."
        imp = session.get(ImportEtatDescriptif, import_id)
        if imp is None or imp.applique_le is not None:
            return  # remplacé ou appliqué entre-temps : la lecture n'a plus d'objet
        if rows is None:
            noter_echec(session, imp, erreur or "Échec de la lecture.")
        else:
            ecrire(session, imp, rows, lecture_ia=LECTURE_TERMINEE)
        session.commit()
