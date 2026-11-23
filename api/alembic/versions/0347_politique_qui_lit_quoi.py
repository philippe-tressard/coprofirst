"""La politique dit qui lit quoi, nomme les personnes sans compte, et ce qui part vers un téléphone.

Audit de cohérence du 23/11/2026 — #2917, #2957, #2981. Trois corrections du texte SERVI,
chacune par un remplacement exact : un texte qui ne porte plus la phrase d'avant (réécrit
par l'administrateur) ne change pas.

1. « 4. Destinataires » : « accessibles uniquement aux membres du conseil syndical et à
   l'administrateur » était faux (`seed/contenus_legaux_destinataires.QUI_LIT_QUOI`).
2. « 2. Données collectées » gagne la puce des personnes sans compte, et « 5. Durée de
   conservation » celle des baux, chacune juste avant la fin de sa liste.
3. La puce des notifications sur téléphone et leur conservation suivent la décision du
   18/11/2026 : seule l'alerte d'une actualité urgente part.

Deux formes de texte servi : celle du gabarit, et celle de l'éditeur d'Admin › Pages
légales (puces en `<li><p>…</p></li>`, espaces insécables en `&nbsp;`). La forme se lit
dans le texte (`&nbsp;`). Ancres vérifiées sur le texte servi en production le
23/11/2026 (forme de l'éditeur, une occurrence chacune). Données seules : l'image
précédente lit les mêmes clés (#1757).

Revision ID: 0347
Revises: 0346
"""

from alembic import op

from app.seed.contenus_legaux_destinataires import (
    ACCES_ANCIEN,
    CONSERVATION_BAUX,
    PERSONNES_SANS_COMPTE,
    QUI_LIT_QUOI,
)
from app.seed.contenus_legaux_notifications import (
    CONSERVATION_NOTIFICATIONS,
    CONSERVATION_NOTIFICATIONS_ANCIEN,
    NOTIFICATIONS_PUSH,
    NOTIFICATIONS_PUSH_ANCIEN,
)
from app.utils.textes_livres import forme_editeur, lire_texte, remplacer_passage

revision = "0347"
down_revision = "0346"
branch_labels = None
depends_on = None

TABLE, COLONNE = "config_site", "valeur"  # identifiants : constantes du fichier
CLE = {"cle": "politique_confidentialite"}

#: Les fins de liste avant lesquelles une puce s'insère.
FIN_SECTION_2 = "</ul><h2>3. Finalités et bases légales</h2>"
FIN_SECTION_5 = "</ul><h2>6. Vos droits</h2>"


def _passage(texte: str, editeur: bool) -> str:
    return texte.replace("\xa0", "&nbsp;") if editeur else texte


def _puce(puce: str, editeur: bool) -> str:
    return forme_editeur(puce) if editeur else puce


def _remplacements(editeur: bool) -> list[tuple[str, str]]:
    """(avant, après) dans la forme du texte servi."""
    return [
        (_passage(ACCES_ANCIEN, editeur), _passage(QUI_LIT_QUOI, editeur)),
        (FIN_SECTION_2, _puce(PERSONNES_SANS_COMPTE, editeur) + FIN_SECTION_2),
        (FIN_SECTION_5, _puce(CONSERVATION_BAUX, editeur) + FIN_SECTION_5),
        (_puce(NOTIFICATIONS_PUSH_ANCIEN, editeur), _puce(NOTIFICATIONS_PUSH, editeur)),
        (
            _puce(CONSERVATION_NOTIFICATIONS_ANCIEN, editeur),
            _puce(CONSERVATION_NOTIFICATIONS, editeur),
        ),
    ]


def _appliquer(sens: int) -> None:
    conn = op.get_bind()
    texte = lire_texte(conn, TABLE, CLE, COLONNE)
    if not texte:
        return  # rien en base : le gabarit est servi, et il porte déjà la rédaction
    editeur = "&nbsp;" in texte
    for avant, apres in _remplacements(editeur):
        if sens < 0:
            avant, apres = apres, avant
        #  Une puce déjà posée ne se pose pas deux fois (une seconde passe, une base
        #  qui l'aurait reçue autrement).
        if sens > 0 and apres in (lire_texte(conn, TABLE, CLE, COLONNE) or ""):
            continue
        remplacer_passage(conn, TABLE, CLE, COLONNE, avant, apres)


def upgrade() -> None:
    _appliquer(+1)


def downgrade() -> None:
    _appliquer(-1)
