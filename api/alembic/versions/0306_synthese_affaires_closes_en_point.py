"""Rattrapage : les affaires closes à la validation d'un point CS / Syndic reçoivent leur synthèse

Jusqu'au 21/10/2026, seule une affaire du carnet recevait une synthèse à sa
clôture. Le point du 19/10/2026, validé le 21/10, a clos une question et une
nuisance : aucune synthèse. Désormais toute affaire close en reçoit une
(`synthese_affaire.production.peut_etre_produite`) ; cette migration inscrit
la demande des affaires déjà closes par un point validé, sans synthèse vivante
pour cette clôture — la file les produit à son passage suivant (le délai de
grâce est passé : `cree_le` est l'instant de la clôture).

Une affaire close autrement, avant cette version, ne se rattrape pas ici : le
bouton « Produire la synthèse » le fait à la demande, comme pour toute affaire
close avant la mise en service (#1643).

Additive (#1757) : des lignes `a_produire`, que la version précédente sait lire.
Rejouée, elle n'inscrit rien de plus (`NOT EXISTS`).

Revision ID: 0306
Revises: 0305
"""

from sqlalchemy import text

from alembic import op

revision = "0306"
down_revision = "0305"
branch_labels = None
depends_on = None

INSCRIRE = text(
    """
    INSERT INTO synthese_affaire (ticket_id, statut, cloture_le, assiste_ia, cree_le, mis_a_jour_le)
    SELECT DISTINCT t.id, :a_produire, t.ferme_le, FALSE, t.ferme_le, t.ferme_le
    FROM point_conseil_cr c
    JOIN point_conseil p ON p.id = c.point_id
    JOIN ticket t ON t.id = c.ticket_id
    WHERE p.etat = :valide
      AND c.etat_cible IN (:resolu, :annule)
      AND CAST(t.statut AS TEXT) = c.etat_cible
      AND t.ferme_le IS NOT NULL
      AND t.fusionnee_dans_id IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM synthese_affaire s
        WHERE s.ticket_id = t.id
          AND s.cloture_le = t.ferme_le
          AND s.statut IN (:a_produire, :brouillon, :validee)
      )
    """
).bindparams(
    a_produire="a_produire",
    brouillon="brouillon",
    validee="validee",
    valide="valide",
    resolu="résolu",
    annule="annulé",
)


def upgrade():
    op.execute(INSCRIRE)


def downgrade():
    #  Rien à défaire : revenue à la version précédente, une demande hors du
    #  carnet est périmée par la file (`annulee`, sans appel) — rien ne casse.
    pass
