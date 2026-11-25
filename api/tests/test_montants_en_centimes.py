"""Un montant se stocke en centimes entiers, jamais en flottant (socle 06 §7, #3011).

`petite_annonce.prix` était la seule colonne monétaire en flottant du dépôt, et
rien ne refusait la suivante. Ce fichier tient :

- la liste FIGÉE des colonnes flottantes de la base, chacune avec ce qu'elle
  mesure — aucune n'est un montant (`petite_annonce.prix` en est sortie avec la
  contraction de #3011 : le modèle ne la déclare plus) ;
- la conversion euros ↔ centimes (`utils/montants`) et l'écriture du prix
  (`utils/prix_annonce`).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import SQLModel

import app.models.core  # noqa: F401 — enregistre toutes les tables
from app.models.communaute import PetiteAnnonce
from app.utils.montants import en_centimes, en_euros
from app.utils.prix_annonce import poser_prix, prix_euros

#: (table, colonne) → ce qu'elle mesure. 🔴 Un montant n'y entre pas : il s'écrit
#: en centimes entiers. Une entrée dont la colonne n'existe plus doit sortir.
FLOTTANTES = {
    ("lot", "superficie"): "une surface en m², pas un montant",
    ("user_lot", "quote_part"): "des millièmes de copropriété, pas un montant",
    ("historique_telemetrie", "duree_secondes"): "une durée, pas un montant",
}


def colonnes_flottantes() -> set[tuple[str, str]]:
    return {
        (t.name, c.name)
        for t in SQLModel.metadata.tables.values()
        for c in t.columns
        if isinstance(c.type, (sa.Float, sa.Numeric))
    }


def test_chaque_colonne_flottante_est_declaree():
    trouvees = colonnes_flottantes()
    assert len(SQLModel.metadata.tables) > 40, "cas zéro : aucune table lue"
    neuves = sorted(trouvees - set(FLOTTANTES))
    assert not neuves, (
        f"colonne(s) en flottant : {neuves} — un montant s'écrit en centimes entiers "
        "(socle 06 §7) ; une autre mesure se déclare dans FLOTTANTES avec ce qu'elle mesure"
    )
    mortes = sorted(set(FLOTTANTES) - trouvees)
    assert not mortes, f"entrée(s) qui ne servent plus, à retirer de FLOTTANTES : {mortes}"


def test_en_centimes_ne_perd_pas_un_centime():
    assert en_centimes(19.99) == 1999, "int(19.99 * 100) rendrait 1998"
    assert en_centimes(0.1 + 0.2) == 30
    assert en_centimes(180) == 18000
    assert en_centimes(10.005) == 1001, "la moitié s'éloigne de zéro, comme ROUND(numeric)"
    assert en_centimes(0) == 0
    assert en_centimes(None) is None
    assert en_euros(1999) == 19.99 and en_euros(None) is None


def test_le_prix_s_ecrit_et_se_lit_en_centimes():
    """Le prix saisi en euros s'écrit en centimes ; le champ servi `prix` s'en calcule."""
    annonce = PetiteAnnonce(titre="t", description="d", auteur_id=1)
    poser_prix(annonce, 19.99)
    assert annonce.prix_centimes == 1999 and prix_euros(annonce) == 19.99
    poser_prix(annonce, None)
    assert annonce.prix_centimes is None and prix_euros(annonce) is None
    assert "prix" not in PetiteAnnonce.model_fields, "l'ancienne colonne ne se déclare plus"
