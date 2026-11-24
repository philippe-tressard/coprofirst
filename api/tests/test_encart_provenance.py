"""Ce que l'encart de provenance DIT de la synthèse (#899, #989).

Sorti de `test_synthese_contrat.py` le 17/09/2026, sur refus du contrôle de
modularité : le fichier repassait au-dessus de 500 lignes en recevant la garde
du document désigné. La ligne de coupe n'est pas arbitraire — ici on éprouve ce
que l'encart **annonce** au lecteur, là-bas la matière qu'on envoie au modèle.

🔴 C'est cet encart qui a rendu visible le défaut du 17/09/2026 : il nommait un
document d'un autre contrat, et il disait vrai. Un encart qui tait ce qu'il a lu
ne peut pas être contredit par l'écran.
"""

from __future__ import annotations

from datetime import datetime

from app.utils.llm import config_llm
from app.utils.synthese_contrat import entete_provenance
from tests.aides_synthese_contrat import _config, session  # noqa: F401


#  ── L'encart de provenance ────────────────────────────────────────────────
#  Demandé le 11/09/2026 : la synthèse atterrit dans les notes du contrat, où
#  rien ne la distingue de celles que le conseil syndical a écrites. Les trois
#  informations verrouillées ici répondent chacune à une question qui se pose
#  plus tard — qui l'a écrite, quand, et sur quoi.


def _matiere(lus=(), joints=(), ecartes=()):
    from app.utils.synthese_contrat import Matiere

    return Matiere("msg", (), tuple(lus), tuple(joints), tuple(ecartes))


def test_l_encart_nomme_le_modele_la_date_et_les_fichiers(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Conditions Particulières AXA.pdf", "Conditions Générales AXA.pdf")),
        quand=datetime(2026, 9, 11, 12, 32),
        documents_joints=0,
    )
    assert "OpenAI" in encart
    assert "11 septembre 2026 à 14:32" in encart  # UTC → Paris
    assert "Conditions Particulières AXA.pdf ; Conditions Générales AXA.pdf" in encart


def test_l_encart_dit_quand_aucun_document_n_a_ete_lu(session):
    """Sans document, la synthèse ne vaut que ce que la fiche sait — et le dire
    est ce qui empêche de la lire comme une lecture du contrat."""
    _config(session)
    encart = entete_provenance(
        config_llm(session), _matiere(), quand=datetime(2026, 9, 11, 12, 0), documents_joints=0
    )
    assert "seules données de la fiche" in encart


def test_un_titre_de_fichier_est_echappe(session):
    """Un nom de fichier voyage jusqu'à un `{@html}` : il est échappé ICI, sans
    faire reposer la correction du rendu sur l'assainisseur du front."""
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Avenant <n°2> & suite.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "<n°2>" not in encart
    assert "&lt;n°2&gt; &amp; suite.pdf" in encart


#  ── Ce qui n'a PAS été lu se dit ───────────────────────────────────────────
#
#  🔴 11/09/2026, premier vrai contrat : les deux PDF de la porte de parking
#  étaient des numérisations sans couche de texte. Quatre sections sur sept
#  sortaient « non précisé » et rien n'expliquait pourquoi — cela ressemblait à
#  un mauvais modèle, alors que le modèle n'avait tout simplement rien reçu.


def test_un_document_ecarte_est_ANNONCE_avec_son_motif(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Contrat.pdf",), ecartes=(("Plan.pdf", "illisible ou trop volumineux"),)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "synthèse est donc partielle" in encart
    assert "Plan.pdf (illisible ou trop volumineux)" in encart


def test_un_fichier_joint_REFUSE_par_le_service_compte_comme_non_lu(session):
    """🔴 C'est le nombre REÇU qui fait foi, pas celui qu'on espérait joindre.
    Sans cela, l'encart nommerait comme lu un document que le service a refusé —
    et la synthèse, appauvrie, se présenterait comme complète."""
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(joints=("Contrat scanné.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "seules données de la fiche" in encart
    assert "Contrat scanné.pdf (non transmis au service)" in encart


def test_un_fichier_joint_ACCEPTE_figure_parmi_les_sources(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(joints=("Contrat scanné.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=1,
    )
    assert "à partir de Contrat scanné.pdf" in encart
    assert "partielle" not in encart
