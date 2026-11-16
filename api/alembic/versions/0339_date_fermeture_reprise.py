"""Une affaire close reprend la date à laquelle elle a été FERMÉE (16/11/2026, #2804).

Corriger une affaire close renvoyait son état, et la route de correction réécrivait
`ferme_le` à l'instant de la correction : ranger une affaire résolue sous un
équipement la datait, au carnet et au fil, du jour du rangement. Le code ne le fait
plus (`routers/tickets/mise_a_jour.py`) ; cette migration répare ce qui a été écrit.

La vraie date se relit dans le fil — les deux seules traces d'une fermeture :
- une transition (`type = 'etat'`) vers un état clos ;
- une correction qui a changé l'état vers un état clos : une ligne « Correction : »
  qui contient « → Résolu » ou « → Annulé » (`mise_a_jour.py`, libellés
  `etat_affaire.STATUT_LABELS`). Une correction qui ne change pas l'état n'écrit rien.

La plus RÉCENTE de ces traces est la fermeture en vigueur (une affaire rouverte puis
refermée l'est à la seconde fois). `ferme_le` ne fait que RECULER vers elle : une
affaire sans trace, ou dont la date est déjà juste, n'est pas touchée. Les affaires
absorbées portent la date de leur principale (`fusion_affaires`) : hors champ.

Données seulement, compatible avec l'image précédente (#1757) ; rejouable.

Revision ID: 0339
Revises: 0338
"""

from alembic import op
from sqlalchemy import text

revision = "0339"
down_revision = "0338"
branch_labels = None
depends_on = None


REPRENDRE = text(
    """
    UPDATE ticket AS t
       SET ferme_le = f.ferme_le
      FROM (
            SELECT e.ticket_id, MAX(e.cree_le) AS ferme_le
              FROM ticket_evolution AS e
             WHERE (e.type = 'etat' AND e.nouveau_statut IN (:resolu, :annule))
                OR (e.type = 'commentaire'
                    AND e.contenu LIKE :correction
                    AND (e.contenu LIKE :vers_resolu OR e.contenu LIKE :vers_annule))
             GROUP BY e.ticket_id
           ) AS f
     WHERE f.ticket_id = t.id
       AND CAST(t.statut AS TEXT) IN (:resolu, :annule)
       AND t.fusionnee_dans_id IS NULL
       AND t.ferme_le > f.ferme_le
    """
).bindparams(
    resolu="résolu",
    annule="annulé",
    correction="Correction%",
    vers_resolu="%→ Résolu%",
    vers_annule="%→ Annulé%",
)


def upgrade() -> None:
    op.execute(REPRENDRE)


def downgrade() -> None:
    pass  # données : la date fausse n'est pas à rétablir
