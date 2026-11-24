"""L'en-tête d'`auto-deploy.sh` dit ce que fait le déploiement d'aujourd'hui (#2965).

C'est le point d'entrée du déploiement, et sa première ligne disait encore
« Synchronisation automatique git + rebuild si changements » : depuis #1758, les
images viennent de la CI, et la construction sur le nœud n'est qu'un secours, qui
se signale (`signaler_secours`). Le standby, lui, « construisait ses images » sur
« une copie » de la base — c'est une réplique en continu depuis DI-7b.

Tant que le secours existe, l'en-tête ne présente pas la construction locale comme
le chemin normal ; s'il disparaît, ce test échoue et se retire avec lui.
"""

import re

from tests.conftest import racine_depot

SCRIPT = racine_depot() / "scripts" / "exploitation" / "auto-deploy.sh"
#: Les mots de l'état d'avant : la construction comme chemin normal, la base copiée.
PERIMES = re.compile(r"rebuild|construit ses images|sa base est une copie", re.I)


def _entete() -> str:
    lignes = SCRIPT.read_text(encoding="utf-8").splitlines()
    fin = next(i for i, ligne in enumerate(lignes) if ligne.startswith("set -"))
    return "\n".join(lignes[:fin])


def test_le_secours_existe_encore():
    #  La raison d'être du test suivant : sans secours, il n'a plus d'objet.
    assert "signaler_secours()" in SCRIPT.read_text(encoding="utf-8")


def test_l_entete_ne_decrit_pas_la_construction_comme_le_chemin_normal():
    entete = _entete()
    assert len(entete) > 500, "en-tête introuvable : contrôle impossible"
    assert "images" in entete.splitlines()[1] and "CI" in entete
    perimes = PERIMES.findall(entete)
    assert not perimes, f"en-tête d'auto-deploy.sh périmé : {perimes}"


def test_le_motif_reconnait_l_ancien_en_tete():
    assert PERIMES.search(
        "# auto-deploy.sh — Synchronisation automatique git + rebuild si changements"
    )
