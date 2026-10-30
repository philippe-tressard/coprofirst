"""Transcrire un procès-verbal d'AG en décisions lisibles par les questions (29/10/2026).

## Le parcours, une fois par an

1. Le PV de l'assemblée est déposé dans la Fiche (catégorie `pv_ag`), comme avant.
2. La tâche quotidienne `transcription_pv` le voit — déposé depuis moins de
   `AGE_MAX_AUTO`, jamais transcrit — et demande à l'assistant ses RÉSOLUTIONS en
   Markdown. Un PV plus ancien se transcrit par le bouton de l'onglet Règlement.
3. La transcription attend la relecture (`a_relire`) ; le gestionnaire du site en
   est avisé par la cloche.
4. L'administration la relit, la corrige au besoin, et la VALIDE : elle devient un
   fichier de la catégorie `texte_decisions_ag`, que les questions lisent.

## 🔴 Rien n'entre sans relecture humaine

Le code vérifie qu'une citation de l'avis figure dans le texte lu
(`extraits.verifier`) — pas que ce texte dit ce que dit le PV. Une résolution mal
transcrite deviendrait une citation « vérifiée » et fausse : la validation est le
seul contrôle de la transcription, et elle appartient à l'administration.

## Ce qui part chez le fournisseur

La consigne de l'usage et le procès-verbal ENTIER — son texte s'il en a un, le
fichier sinon (un PV signé est numérisé) : les mêmes voies que la synthèse d'un
contrat (`synthese_contrat.texte_du_document`, `piece_jointe`). Un PV nomme les
copropriétaires présents et qui a voté contre : la consigne demande de n'en rien
recopier, et la politique de confidentialité le dit
(`seed/contenus_legaux_decisions_ag`).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.core import Document, Utilisateur
from app.models.reglement import TranscriptionPV
from app.utils import horloge
from app.utils.fichiers import nom_stocke
from app.utils.question_reglement.texte import CODE_CATEGORIE_AG, categorie, titre_ag
from app.utils.stockage import DOSSIER_PRIVE, stockage

logger = logging.getLogger("hostachy.assistant")

#: Le code de l'usage — lu par `llm_usages`.
USAGE_TRANSCRIPTION_PV = "transcription_pv_ag"
#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "transcription_pv"
#: La catégorie des PV dans la Fiche — posée par le seed.
CODE_PV = "pv_ag"
#: Au-delà, un PV n'est transcrit que sur demande : l'historique coûte, et se choisit.
AGE_MAX_AUTO = timedelta(days=60)

EN_COURS = "en_cours"
A_RELIRE = "a_relire"
VALIDEE = "validee"
ECHEC = "echec"
#: Les statuts, et leur libellé — la SEULE liste : l'écran le reçoit avec la ligne.
STATUTS: dict[str, str] = {
    EN_COURS: "Transcription en cours",
    A_RELIRE: "À relire",
    VALIDEE: "Validée",
    ECHEC: "Échec",
}
#: En deçà, l'assistant n'a rien transcrit d'utile.
MIN_CARACTERES = 200
#: Une transcription relue se borne comme un fichier du règlement.
MAX_CARACTERES = 200_000

#: Le prompt D'ORIGINE — l'administration peut le reprendre (Admin › Assistant IA).
CONSIGNE = (
    "Tu es clerc d'un syndic de copropriété. On te remet le procès-verbal d'une assemblée "
    "générale de copropriétaires. Transcris-en les RÉSOLUTIONS, et rien d'autre, en "
    "Markdown.\n"
    "\n"
    "Pour chaque résolution, dans l'ordre du procès-verbal :\n"
    "- un titre de niveau 2 : « ## Résolution n° <numéro> — <intitulé> » ;\n"
    "- la majorité requise (article 24, 25, 25-1 ou 26 de la loi du 10 juillet 1965, "
    "unanimité) quand elle figure ;\n"
    "- le résultat : adoptée, rejetée, ou sans objet, avec les voix (en tantièmes) pour, "
    "contre et abstentions quand elles figurent, SANS le nom des votants ;\n"
    "- le texte de la décision, MOT POUR MOT, tel que le procès-verbal l'écrit.\n"
    "\n"
    "Avant le texte de chaque page, pose un repère sur sa propre ligne : "
    "« ⟦ PV — p. <numéro de page> ⟧ ».\n"
    "\n"
    "Ne transcris ni la feuille de présence, ni les débats, ni les questions diverses sans "
    "vote. Ne recopie AUCUN nom de personne physique : désigne chacun par sa qualité (le "
    "président de séance, le syndic, un copropriétaire). Le nom d'une entreprise retenue "
    "pour des travaux peut rester. Si un passage est illisible, écris [illisible] plutôt "
    "que de deviner.\n"
    "\n"
    "Réponds par le Markdown seul, sans texte autour ni bloc de code."
)


def statut_libelle(statut: str) -> str:
    return STATUTS.get(statut, statut)


def disponible(session: Session) -> bool:
    """L'usage est-il activé aux deux étages, avec clé et modèle ?"""
    from app.utils.llm import config_llm

    return config_llm(session, USAGE_TRANSCRIPTION_PV).pret


def pvs(session: Session) -> list[Document]:
    """Les PV de la Fiche, du plus récent au plus ancien."""
    cat = categorie(session, CODE_PV)
    if cat is None:
        return []
    return list(
        session.exec(
            select(Document)
            .where(Document.categorie_id == cat.id)
            .order_by(
                col(Document.date_ag).desc().nulls_last(),
                col(Document.publie_le).desc(),
                col(Document.id).desc(),
            )
        ).all()
    )


def derniere_transcription(session: Session, pv_id: int) -> Optional[TranscriptionPV]:
    return session.exec(
        select(TranscriptionPV)
        .where(TranscriptionPV.pv_id == pv_id)
        .order_by(col(TranscriptionPV.cree_le).desc(), col(TranscriptionPV.id).desc())
    ).first()


def a_transcrire_d_office(session: Session) -> list[Document]:
    """Les PV récents qu'aucune transcription n'a encore touchés — ceux de la tâche."""
    limite = horloge.maintenant() - AGE_MAX_AUTO
    return [
        pv
        for pv in pvs(session)
        if pv.publie_le >= limite and derniere_transcription(session, pv.id) is None
    ]


def nettoyer(texte: str) -> str:
    """PURE. Le Markdown rendu, sans la clôture d'un bloc de code que le modèle ajoute
    parfois malgré la consigne — ou `ValueError` s'il n'y a rien d'utile."""
    t = (texte or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    t = t.strip()
    if len(t) < MIN_CARACTERES or "##" not in t:
        raise ValueError("L'assistant n'a rendu aucune résolution.")
    return t[:MAX_CARACTERES]


def _matiere(pv: Document) -> tuple[str, tuple]:
    """Le message et les fichiers : le texte du PV s'il en a, le fichier sinon."""
    from app.utils.synthese_contrat import piece_jointe, texte_du_document

    entete = f"Procès-verbal : {titre_ag(pv)}."
    texte = texte_du_document(pv)
    if texte:
        return f"{entete}\n\n<<<PV\n{texte}\nPV>>>", ()
    piece = piece_jointe(pv)
    if piece is None:
        raise ValueError("Le procès-verbal est introuvable, ou trop volumineux pour être lu.")
    return f"{entete}\n\nLe procès-verbal est joint : lis-le toi-même (document numérisé).", (
        piece,
    )


def ouvrir(session: Session, pv: Document, demandeur: Optional[int]) -> TranscriptionPV:
    """La ligne « en cours » — écrite et validée AVANT l'appel, que l'écran suit."""
    ligne = TranscriptionPV(pv_id=pv.id, statut=EN_COURS, demande_par_id=demandeur)
    session.add(ligne)
    session.commit()
    session.refresh(ligne)
    return ligne


async def remplir(session: Session, ligne: TranscriptionPV) -> TranscriptionPV:
    """Appelle l'assistant et range sa transcription, ou l'échec — jamais ne lève."""
    from app.utils.llm import ErreurLLM, config_llm, demander

    pv = session.get(Document, ligne.pv_id)
    try:
        if pv is None:
            raise ValueError("Le procès-verbal a été retiré de la Fiche.")
        message, fichiers = _matiere(pv)
        cfg = config_llm(session, USAGE_TRANSCRIPTION_PV)
        rep = await demander(
            session,
            usage=USAGE_TRANSCRIPTION_PV,
            message=message,
            fichiers=fichiers,
            demandeur=ligne.demande_par_id,
        )
        ligne.contenu, ligne.statut, ligne.modele = nettoyer(rep.texte), A_RELIRE, cfg.modele
    except (ErreurLLM, ValueError) as exc:
        ligne.statut, ligne.erreur = ECHEC, str(exc)
    except Exception:  # noqa: BLE001 — une ligne ne reste jamais « en cours »
        logger.exception("Transcription du PV %s : échec inattendu", ligne.pv_id)
        session.rollback()
        ligne.statut, ligne.erreur = ECHEC, "La transcription a échoué — réessayez."
    session.add(ligne)
    if ligne.statut == A_RELIRE:
        _aviser(session, pv)
    session.commit()
    session.refresh(ligne)
    return ligne


def _aviser(session: Session, pv: Document) -> None:
    """La cloche du gestionnaire du site : une transcription attend sa relecture."""
    from app.utils.cloche import sonner_systeme
    from app.utils.destinataires import site_manager_user_id

    gestionnaire = site_manager_user_id(session)
    if gestionnaire is None:
        return
    sonner_systeme(
        session,
        "relecture_transcription",
        destinataire_id=gestionnaire,
        type="system",
        titre="Décisions d'AG à relire",
        corps=f"La transcription du procès-verbal « {pv.titre} » attend votre relecture.",
        lien="/residence/reglement",
    )


async def en_tache_de_fond(copro, ligne_id: int) -> None:
    """Le bouton « Transcrire » : remplit la ligne ouverte par la route."""
    from app import contexte

    with contexte.dans(copro), contexte.nouvelle_session() as session:
        ligne = session.get(TranscriptionPV, ligne_id)
        if ligne is not None and ligne.statut == EN_COURS:
            await remplir(session, ligne)


def traiter_file(session: Optional[Session] = None) -> dict[str, int]:
    """La tâche quotidienne : transcrit les PV récents jamais transcrits.

    ⚠️ Ne lève jamais : sous le planificateur, une exception tuerait le job.
    Muette sur l'assistant éteint — la trace le dit, rien n'est ouvert."""
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    compte = {"a_relire": 0, "echecs": 0}
    try:
        if not disponible(session):
            logger.info("Transcription des PV d'AG : usage désactivé, rien à faire")
            return compte
        for pv in a_transcrire_d_office(session):
            ligne = asyncio.run(remplir(session, ouvrir(session, pv, None)))
            compte["a_relire" if ligne.statut == A_RELIRE else "echecs"] += 1
        #  Une trace à CHAQUE passage : un battement qu'on n'entend pas ne se
        #  distingue pas d'une tâche morte (`standards/07`).
        logger.info(
            "Transcription des PV d'AG : %d à relire, %d en échec",
            compte["a_relire"],
            compte["echecs"],
        )
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        logger.warning("Transcription des PV d'AG non traitée : %s", exc)
    finally:
        if propre:
            session.close()
    return compte


def enregistrer(planificateur) -> None:
    """La tâche permanente, chaque jour à 05:15, jouée pour chaque copropriété. Un
    passage manqué décale d'un jour : le PV attend, rien ne se perd."""
    from app import contexte

    planificateur.add_job(
        contexte.pour_chaque_copropriete(traiter_file, "transcription_pv"),
        "cron",
        hour=5,
        minute=15,
        id="transcription_pv",  # littéral : `test_taches_planifiees_declarees` lit les add_job
    )


def valider(
    session: Session, ligne: TranscriptionPV, contenu: str, user: Utilisateur
) -> TranscriptionPV:
    """Le texte RELU devient un fichier des décisions d'AG — l'assistant le lira.

    Un fichier PRODUIT par l'application (déclaré dans
    `test_televersement_source_unique.ECRIVAINS_DU_STOCKAGE`) : le Markdown relu
    est un texte saisi, pas un fichier reçu ; son extension et son type sont fixés ici.
    """
    if ligne.statut != A_RELIRE:
        raise HTTPException(409, "Cette transcription n'attend pas de relecture.")
    pv = session.get(Document, ligne.pv_id)
    if pv is None:
        raise HTTPException(409, "Le procès-verbal a été retiré de la Fiche.")
    cat_ag = categorie(session, CODE_CATEGORIE_AG)
    if cat_ag is None:  # pragma: no cover - posée par le seed
        raise HTTPException(500, "La catégorie des décisions d'AG manque.")
    texte = contenu.strip()
    if len(texte) < MIN_CARACTERES:
        raise HTTPException(400, "La transcription relue est trop courte.")
    octets = texte.encode("utf-8")
    nom = f"decisions-{pv.date_ag.isoformat() if pv.date_ag else pv.id}.md"
    cle = f"{DOSSIER_PRIVE}/{nom_stocke(nom, '.md')}"
    st = stockage()
    st.ecrire(cle, octets)
    doc = Document(
        titre=f"Décisions — {titre_ag(pv)}",
        fichier_nom=nom,
        **st.colonnes(cle),
        taille_octets=len(octets),
        mime_type="text/markdown",
        categorie_id=cat_ag.id,
        date_ag=pv.date_ag,
        publie_par_id=user.id,
    )
    session.add(doc)
    session.flush()
    ligne.contenu, ligne.statut, ligne.document_id = texte, VALIDEE, doc.id
    ligne.valide_par_id, ligne.valide_le = user.id, horloge.maintenant()
    session.add(ligne)
    session.commit()
    session.refresh(ligne)
    return ligne


__all__ = [
    "A_RELIRE",
    "AGE_MAX_AUTO",
    "CONSIGNE",
    "ECHEC",
    "EN_COURS",
    "ID_TACHE",
    "STATUTS",
    "USAGE_TRANSCRIPTION_PV",
    "VALIDEE",
    "a_transcrire_d_office",
    "derniere_transcription",
    "disponible",
    "en_tache_de_fond",
    "enregistrer",
    "nettoyer",
    "ouvrir",
    "pvs",
    "remplir",
    "statut_libelle",
    "traiter_file",
    "valider",
]
