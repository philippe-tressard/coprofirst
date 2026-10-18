"""Les textes légaux de la référence : trois écarts corrigés à leur place (#2069, suite de #2065).

Les mentions légales et la politique de confidentialité de la référence vivent en
base, écrites à la main avant le chantier multi-copropriétés. Le relevé de #2065
y a trouvé trois écarts que le gabarit ne porte plus :

1. **L'éditeur et le responsable du traitement étaient « le conseil syndical »** —
   qui n'a pas la personnalité juridique. Le syndicat n'a pas décidé de ce site : il
   est l'initiative d'une personne, copropriétaire, qui l'administre à titre non
   professionnel (réponse de l'auteur, 17/10/2026). L'éditeur, le directeur de la
   publication et le responsable deviennent donc « l'administrateur du site » —
   SANS NOM : le dépôt est public (`test_identites_fictives`). Si le nom doit être
   publié, il entre en base par Admin › Pages légales, jamais par le dépôt.
2. **« Ce site est servi par CoproConnect »**, avec un lien vers l'ancien dépôt :
   la 0270 a posé le paragraphe de licence le 08/10/2026, la veille du renommage
   en CoproFirst (#1772). Il prend le nom et l'adresse d'aujourd'hui
   (`utils/plateforme`).
3. **Trois passages de télémétrie contredisaient les suivants** : « données de
   navigation anonymisées après 30 jours », trois durées « anonymes » et « des
   statistiques de navigation anonymisées » — alors que la mesure d'audience est
   rattachée au compte (`TELEMETRIE_COLLECTE`, `TELEMETRIE_CONSERVATION`, déjà
   dans le texte). Ils partent ou renvoient au point 2.

Chaque passage n'est remplacé que s'il figure TEL QUEL (`remplacer_passage`) : une
installation qui ne les a jamais eus, ou un texte retouché depuis Admin › Pages
légales, ne change pas. Données seules ; l'image précédente lit les mêmes clés
(#1757). Le texte modifié redevient « à relire » : son empreinte a changé.

⚠️ Projet soumis à la coordination, comme tout texte juridique de #2065 ; la
relecture par un juriste reste à faire.

Revision ID: 0298
Revises: 0297
"""

from alembic import op

from app.utils.plateforme import LICENCE_URL, NOM_PLATEFORME
from app.utils.textes_livres import remplacer_passage

revision = "0298"
down_revision = "0297"
branch_labels = None
depends_on = None

_NBSP = "\xa0"

#: (clé de `config_site`, avant, après) — tels qu'en base, caractère pour caractère.
REMPLACEMENTS: list[tuple[str, str, str]] = [
    (
        "mentions_legales",
        "<p><strong>Le conseil syndical de la copropriété</strong>, éditeur à titre non "
        "professionnel.",
        "<p><strong>L'administrateur du site</strong>, copropriétaire de la résidence, éditeur "
        "à titre non professionnel, joignable à l'adresse de contact ci-dessous. Le conseil "
        "syndical utilise l'outil pour ses échanges avec les résidents ; il n'en est pas "
        "l'éditeur.",
    ),
    (
        "mentions_legales",
        "<p>Le président du conseil syndical, joignable à l'adresse de contact ci-dessous.</p>",
        "<p>L'administrateur du site, éditeur, joignable à l'adresse de contact ci-dessous.</p>",
    ),
    (
        "politique_confidentialite",
        "Le responsable du traitement est <strong>le conseil syndical de la copropriété</strong>, "
        "éditeur du site.",
        "Le responsable du traitement est <strong>l'administrateur du site</strong>, "
        "copropriétaire de la résidence, qui l'édite à titre non professionnel ; le conseil "
        "syndical utilise l'outil sans en être le responsable.",
    ),
    ("mentions_legales", "Ce site est servi par CoproConnect,", f"Ce site est servi par {NOM_PLATEFORME},"),
    (
        "mentions_legales",
        "https://github.com/philippe-tressard/5hostachy/blob/main/LICENSE",
        LICENCE_URL,
    ),
    (
        "politique_confidentialite",
        f"<li><strong>Données de navigation{_NBSP}:</strong> pages visitées, actions effectuées "
        f"(anonymisées après 30{_NBSP}jours). Ces données sont collectées sur la base de "
        f"l'intérêt légitime (art.{_NBSP}6-1-f) afin d'améliorer le service. Vous pouvez "
        "désactiver cette collecte à tout moment depuis votre profil.</li>",
        "",
    ),
    (
        "politique_confidentialite",
        f"<li>Télémétrie détaillée (avec identifiant){_NBSP}: 30{_NBSP}jours.</li>"
        f"<li>Télémétrie agrégée quotidienne (anonyme){_NBSP}: 12{_NBSP}mois.</li>"
        f"<li>Télémétrie agrégée mensuelle (anonyme){_NBSP}: 10{_NBSP}ans.</li>",
        "",
    ),
    (
        "politique_confidentialite",
        " L'application collecte également des statistiques de navigation anonymisées (pages "
        "visitées) pour améliorer le service. Cette collecte peut être désactivée dans votre "
        "profil.",
        " La mesure d'audience interne, rattachée à votre compte, est décrite au point 2 ; elle "
        "se refuse depuis votre profil.",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for cle, ancien, nouveau in REMPLACEMENTS:
        remplacer_passage(conn, "config_site", {"cle": cle}, "valeur", ancien, nouveau)


def downgrade() -> None:
    #  Les passages RETIRÉS (après vide) ne se remettent pas : sans ancre, on ne sait
    #  plus où ils étaient. Le retour arrière reste un changement d'image (#1757) —
    #  l'image précédente lit ces textes tels qu'ils sont.
    conn = op.get_bind()
    for cle, ancien, nouveau in REMPLACEMENTS:
        if nouveau:
            remplacer_passage(conn, "config_site", {"cle": cle}, "valeur", nouveau, ancien)
