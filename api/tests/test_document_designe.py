"""Le document désigné par un contrat doit être LE SIEN (#989, 17/09/2026).

## Ce que ce test protège

Un contrat désigne « son » document par `ContratEntretien.document_id`. Deux
consommateurs suivent ce pointeur : la **synthèse IA**, qui envoie le document
au service, et la **fiche copropriété**, qui en fait un lien de téléchargement.
Aucun des deux ne vérifiait que le document appartient au contrat.

Signalé à l'écran le 17/09/2026 : la synthèse d'un contrat d'ascenseur
annonçait avoir lu « Entretien toitures Bat 2 », un document d'un autre
contrat. L'encart disait vrai — le fichier avait bien été lu, et il était bien
parti au service. C'est ce que ces tests refusent désormais.

⚠️ Ils éprouvent la règle **sur les deux consommateurs**, pas seulement sur
celui qui a montré le défaut : la portée du contrôle fait partie du contrôle
(`standards/05` §9).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.core import ConfigSite
from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.document_contrat import document_designe, id_document_designe
from app.utils.synthese_contrat import construire_matiere, documents_du_contrat


@pytest.fixture()
def session(session):
    session.add(Prestataire(id=1, nom="5M Services", specialite="ascenseur"))
    for cle, valeur in {
        "llm_actif": "1",
        "llm_api_key": "sk-x",
        "llm_envoi_document": "1",
        "llm_synthese_contrat_actif": "1",
        "llm_synthese_contrat_modele": "gpt-4o-mini",
    }.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return session


def _contrat(session, libelle="Ascenseur Bât. 4"):
    c = ContratEntretien(
        copropriete_id=1, prestataire_id=1, libelle=libelle, date_debut=date(2024, 1, 1)
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _document(session, titre, contrat_id):
    d = Document(
        titre=titre,
        fichier_nom="c.pdf",
        mime_type="application/pdf",
        contrat_id=contrat_id,
        publie_par_id=1,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


# ── 1. La règle, à un seul endroit ─────────────────────────────────────────


def test_le_document_du_contrat_est_bien_designe(session):
    c = _contrat(session)
    d = _document(session, "Contrat de maintenance ascenseur", c.id)
    c.document_id = d.id
    session.add(c)
    session.commit()
    assert document_designe(session, c).id == d.id
    assert id_document_designe(session, c) == d.id


def test_le_document_d_un_AUTRE_contrat_n_est_PAS_designe(session):
    """🔴 Le défaut du 17/09/2026, dans les deux sens : ni lu, ni annoncé."""
    ascenseur = _contrat(session)
    toitures = _contrat(session, "Entretien toitures Bat 2")
    etranger = _document(session, "Entretien toitures Bat 2", toitures.id)
    ascenseur.document_id = etranger.id
    session.add(ascenseur)
    session.commit()
    assert document_designe(session, ascenseur) is None
    assert id_document_designe(session, ascenseur) is None


def test_un_document_de_la_BIBLIOTHEQUE_n_est_pas_un_document_de_contrat(session):
    """`contrat_id` vide : un plan ou un règlement n'est le document d'aucun
    contrat, même si un pointeur hérité le désigne."""
    c = _contrat(session)
    libre = _document(session, "Règlement de copropriété", None)
    c.document_id = libre.id
    session.add(c)
    session.commit()
    assert document_designe(session, c) is None


def test_un_pointeur_qui_ne_mene_a_rien_ne_lève_pas(session):
    """Le document a pu être supprimé : le contrat reste lisible."""
    c = _contrat(session)
    c.document_id = 4242
    session.add(c)
    session.commit()
    assert document_designe(session, c) is None


# ── 2. Le consommateur qui a montré le défaut : la synthèse ────────────────


def test_la_synthese_ne_LIT_pas_le_document_d_un_autre_contrat(session):
    ascenseur = _contrat(session)
    sien = _document(session, "Contrat de maintenance ascenseur", ascenseur.id)
    toitures = _contrat(session, "Entretien toitures Bat 2")
    etranger = _document(session, "Entretien toitures Bat 2", toitures.id)
    ascenseur.document_id = etranger.id
    session.add(ascenseur)
    session.commit()

    lus = documents_du_contrat(session, ascenseur)
    assert [d.id for d in lus] == [sien.id]
    #  Et l'inventaire de la matière ne le nomme pas non plus : c'est lui que
    #  l'encart de provenance recopie.
    m = construire_matiere(session, ascenseur, avec_document=True)
    nomme = set(m.lus_en_texte) | set(m.joints) | {t for t, _ in m.ecartes}
    assert "Entretien toitures Bat 2" not in nomme


def test_le_document_designe_du_contrat_reste_EN_TETE(session):
    """La garde ne retire pas la règle qu'elle protège : le document de
    référence passe devant ses avenants."""
    c = _contrat(session)
    avenant = _document(session, "Avenant 1", c.id)
    reference = _document(session, "Contrat initial", c.id)
    c.document_id = reference.id
    session.add(c)
    session.commit()
    #  Le désigné est déjà rattaché : il n'est pas inséré deux fois, et l'ordre
    #  chronologique de la requête est conservé.
    lus = documents_du_contrat(session, c)
    assert [d.id for d in lus] == [avenant.id, reference.id]
    assert len(lus) == 2
