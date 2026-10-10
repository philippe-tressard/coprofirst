"""Ce qu'un compte supprimé laisse, et combien de temps un compte fermé se garde (#1688, #1821, #1822)

Arbitrages du 10/10/2026. Trois volets, une notion : le cycle de fin d'un compte.

## 1. Le contenu collectif reste, sans nom (#1688, #1821)

Celui du 28/08 (« le contenu part avec le compte ») est inversé pour le contenu
COLLECTIF. La purge référentielle supprime une ligne dont la référence au compte
est obligatoire, et délie une référence facultative : cette migration rend
facultative la référence de chaque contenu gardé. La liste et la raison de
chacun se lisent dans `utils/suppression_compte.CONTENUS_GARDES` ; elle est
RECOPIÉE ici, non importée — une migration appliquée ne change pas quand le code
évolue. `batch_alter_table` : un `ALTER … DROP NOT NULL` sous PostgreSQL (la
production), une recopie de la table sous SQLite — sans danger, le contexte
d'Alembic ne pose pas `foreign_keys=ON` (même geste que la 0213).

## 2. La fermeture d'un compte, et depuis quand (#1822)

`utilisateur.fermeture_compte` (`refus` | `desactivation`) et `compte_ferme_le`,
colonnes simples et facultatives : la purge compte la durée d'un compte fermé à
partir d'elles. `decision_compte_le` ne le pouvait pas — c'est la PREMIÈRE
décision, et un compte validé puis désactivé gardait la date de sa validation.

Les comptes déjà fermés ne disent pas s'ils ont été refusés ou désactivés : ils
sont classés « désactivation », la durée la plus longue, et datés de CETTE
migration — jamais plus tôt que l'annonce.

## 3. La politique servie le dit

Deux passages exacts, lus dans le seed : la phrase des comptes fermés
(`COMPTES_FERMES_ANCIEN` → `COMPTES_FERMES`), puis ce qui reste d'un compte
supprimé (`ANONYMISATION_CONTENUS`), posé après `CONSERVATION_COMPTES`. Un texte
reformulé depuis Admin › Légal n'est pas touché.

## Compatible avec la version précédente (#1757)

Que des expansions : des colonnes rendues facultatives, deux colonnes ajoutées
sans contrainte. Idempotente. Le retour arrière refuse d'inventer un auteur.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0276
Revises: 0275
"""

import sqlalchemy as sa

from alembic import op

revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None

#: (table, colonne) — identifiants : constantes du fichier.
COLONNES = (
    ("ticket", "auteur_id"),
    ("message_ticket", "auteur_id"),
    ("ticket_evolution", "auteur_id"),
    ("evenement", "auteur_id"),
    ("evenement_evolution", "auteur_id"),
    ("document", "publie_par_id"),
    ("diagnostic_rapport", "publie_par_id"),
    ("regle_residence", "cree_par_id"),
    ("annonce_hall", "auteur_id"),
    ("sondage", "auteur_id"),
    ("vote_sondage", "user_id"),
    ("commentaire_sondage", "auteur_id"),
    ("idee", "auteur_id"),
    ("vote_idee", "user_id"),
    ("reponse_communaute", "auteur_id"),
    ("notation_prestataire", "auteur_id"),
    ("delegation", "cree_par_id"),
)
COMPTE = "utilisateur"
FERMETURE = "fermeture_compte"
FERME_LE = "compte_ferme_le"
POLITIQUE = "politique_confidentialite"


def _tables(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _colonnes(conn, table: str) -> dict[str, bool]:
    """{colonne: facultative} — vide si la table manque."""
    if table not in _tables(conn):
        return {}
    return {c["name"]: bool(c["nullable"]) for c in sa.inspect(conn).get_columns(table)}


def _politique_actuelle(conn) -> str:
    return (
        conn.execute(
            sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=POLITIQUE)
        ).scalar()
        or ""
    )


def _politique(sens: int) -> None:
    from app.seed.contenus_legaux import (
        ANONYMISATION_CONTENUS,
        COMPTES_FERMES,
        COMPTES_FERMES_ANCIEN,
        CONSERVATION_COMPTES,
    )
    from app.utils.textes_livres import remplacer_passage

    conn = op.get_bind()
    if "config_site" not in _tables(conn):
        return

    def remplacer(avant: str, apres: str) -> None:
        remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)

    avec = CONSERVATION_COMPTES + ANONYMISATION_CONTENUS
    if sens > 0:
        remplacer(COMPTES_FERMES_ANCIEN, COMPTES_FERMES)
        if avec not in _politique_actuelle(conn):  # rejouée, elle la doublerait
            remplacer(CONSERVATION_COMPTES, avec)
    else:
        remplacer(avec, CONSERVATION_COMPTES)
        remplacer(COMPTES_FERMES, COMPTES_FERMES_ANCIEN)


def upgrade() -> None:
    conn = op.get_bind()
    for table, colonne in COLONNES:
        if _colonnes(conn, table).get(colonne) is False:
            with op.batch_alter_table(table) as lot:
                lot.alter_column(colonne, existing_type=sa.Integer(), nullable=True)

    presentes = _colonnes(conn, COMPTE)
    if presentes:
        if FERMETURE not in presentes:
            op.add_column(COMPTE, sa.Column(FERMETURE, sa.String(), nullable=True))
        if FERME_LE not in presentes:
            op.add_column(COMPTE, sa.Column(FERME_LE, sa.DateTime(), nullable=True))
        from app.utils import horloge

        t = sa.table(
            COMPTE,
            sa.column("actif"),
            sa.column("decision_compte_le"),
            sa.column(FERMETURE),
            sa.column(FERME_LE),
        )
        conn.execute(
            sa.update(t)
            .where(
                t.c.actif.is_(False),
                t.c.decision_compte_le.isnot(None),
                t.c[FERMETURE].is_(None),
            )
            .values({FERMETURE: "desactivation", FERME_LE: horloge.maintenant()})
        )
    _politique(+1)


def downgrade() -> None:
    _politique(-1)
    conn = op.get_bind()
    presentes = _colonnes(conn, COMPTE)
    a_retirer = [c for c in (FERMETURE, FERME_LE) if c in presentes]
    if a_retirer:
        with op.batch_alter_table(COMPTE) as lot:
            for colonne in a_retirer:
                lot.drop_column(colonne)
    for table, colonne in COLONNES:
        if _colonnes(conn, table).get(colonne) is not True:
            continue
        t = sa.table(table, sa.column(colonne))
        orphelines = conn.execute(
            sa.select(sa.func.count()).select_from(t).where(t.c[colonne].is_(None))
        ).scalar()
        if orphelines:
            raise RuntimeError(
                f"{table} : {orphelines} ligne(s) sans auteur (comptes supprimés) — "
                "le retour arrière n'invente pas d'auteur."
            )
        with op.batch_alter_table(table) as lot:
            lot.alter_column(colonne, existing_type=sa.Integer(), nullable=False)
