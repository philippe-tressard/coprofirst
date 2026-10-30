"""Les questions au règlement lisent aussi les décisions d'AG (29/10/2026).

Deux ajouts, tous deux additifs — l'image précédente les ignore (#1757) :

- trois colonnes nullables de `question_reglement` : l'avis se rend en SECTIONS
  (d'après le règlement, d'après les AG, synthèse) ; un avis plus ancien les laisse
  vides et l'écran le montre comme avant ;
- la table `transcription_pv` : la transcription d'un PV d'AG par l'assistant,
  à relire par l'administration avant d'entrer dans les décisions lues.

La catégorie `texte_decisions_ag` est posée par le seed (`profils_documents`).

Revision ID: 0317
Revises: 0316
"""

import sqlalchemy as sa
from alembic import op

revision = "0317"
down_revision = "0316"
branch_labels = None
depends_on = None


QUESTIONS = "question_reglement"  # identifiant : constante du fichier
SECTIONS = ("selon_reglement", "selon_ag", "synthese")  # identifiants : constantes du fichier
TRANSCRIPTIONS = "transcription_pv"  # identifiant : constante du fichier


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    inspecteur = sa.inspect(op.get_bind())
    presentes = {c["name"] for c in inspecteur.get_columns(QUESTIONS)}
    for nom in SECTIONS:
        if nom not in presentes:
            op.add_column(QUESTIONS, sa.Column(nom, sa.String(), nullable=True))
    if TRANSCRIPTIONS in inspecteur.get_table_names():
        return
    op.create_table(
        TRANSCRIPTIONS,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pv_id", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("contenu", sa.String(), nullable=True),
        sa.Column("erreur", sa.String(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("demande_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("valide_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("modele", sa.String(), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("valide_le", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transcription_pv_pv_id", TRANSCRIPTIONS, ["pv_id"])
    op.create_index("ix_transcription_pv_statut", TRANSCRIPTIONS, ["statut"])
    op.create_index("ix_transcription_pv_cree_le", TRANSCRIPTIONS, ["cree_le"])


def downgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if TRANSCRIPTIONS in inspecteur.get_table_names():
        op.drop_table(TRANSCRIPTIONS)
    presentes = {c["name"] for c in inspecteur.get_columns(QUESTIONS)}
    for nom in SECTIONS:
        if nom in presentes:
            op.drop_column(QUESTIONS, nom)
