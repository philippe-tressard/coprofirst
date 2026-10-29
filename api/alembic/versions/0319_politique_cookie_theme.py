"""La politique de confidentialité nomme le cookie de thème (#2174, lot S5).

La rubrique « 7. Cookies » disait que l'application utilise « exclusivement des
cookies techniques d'authentification ». Le choix Automatique / Clair / Sombre du
Profil se retient désormais sur l'appareil par le cookie `theme` : la phrase servie
devient fausse. La phrase neuve est LUE dans `seed/contenus_legaux_cookies` — le
gabarit et cette migration n'en ont qu'une rédaction ; l'ancienne est écrite ici, seul
endroit où elle doit encore être reconnue.

Remplacé seulement s'il figure TEL QUEL (`remplacer_passage`) : un texte retouché
depuis Admin › Pages légales ne change pas, et son administrateur ajoutera la
mention lui-même. Le texte modifié redevient « à relire » : son empreinte a changé.
Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0319
Revises: 0318
"""

from alembic import op

from app.seed.contenus_legaux_cookies import COOKIES
from app.utils.textes_livres import remplacer_passage

revision = "0319"
down_revision = "0318"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}

#: La phrase d'ouverture telle que le gabarit l'écrivait jusqu'à la v3.36 — SEULE : le
#: texte servi en a reçu d'autres à sa suite (mesure d'audience), relevé le 30/10/2026
#: sur la page publique, et elles restent.
ANCIEN = (
    "L'application utilise exclusivement des cookies techniques d'authentification "
    "(<code>access_token</code>, <code>refresh_token</code>) définis en "
    "<code>HttpOnly; Secure; SameSite=Strict</code>."
)


def upgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", ANCIEN, COOKIES)


def downgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", COOKIES, ANCIEN)
