"""La configuration de Caddy d'une installation commune est un fait du dépôt (claude-config#604).

La procédure faisait ajouter à la main, dans le `Caddyfile`, l'import de la garde
des pages et du relais des fichiers vers l'API ; la mise à jour nocturne remplace
le `Caddyfile` par celui de l'archive, et la retouche disparaissait. Désormais :

- le `Caddyfile` importe chaque fragment par un MOTIF (`commune/<nom>*.caddy`), qui
  n'importe rien sur une installation propre, où rien n'est monté ;
- la surcouche `compose.commune.yml` monte chaque fragment au chemin importé ;
- le relais des fichiers est importé AVANT le `handle /uploads/*` qui sert la
  racine unique (même précision de chemin : l'ordre d'écriture décide) ;
- la procédure ne demande plus de retoucher le `Caddyfile`.

Que Caddy charge les deux variantes, et dans cet ordre, se prouve sur un vrai
binaire : workflow `.github/workflows/caddyfile.yml` (`scripts/ci/caddy_variantes.py`).
"""

import re

import yaml

from tests.aides_caddy import caddyfile
from tests.conftest import racine_depot

RACINE = racine_depot()
COMMUNE = RACINE / "deploiement" / "standard" / "commune"
IMPORT = re.compile(r"^\s*import\s+commune/([\w-]+)\*\.caddy\s*$", re.M)


def _montages() -> dict[str, str]:
    """Chemin dans le conteneur Caddy → fichier du dépôt, lus dans la surcouche."""
    surcouche = yaml.safe_load((COMMUNE / "compose.commune.yml").read_text(encoding="utf-8"))
    montages = {}
    for volume in surcouche["services"]["caddy"]["volumes"]:
        source, cible, *_ = volume.split(":")
        montages[cible] = source
    return montages


def test_chaque_fragment_est_importe_et_monte():
    importes = set(IMPORT.findall(caddyfile()))
    fragments = {f.stem for f in COMMUNE.glob("*.caddy")}
    assert fragments == {"fichiers", "garde-des-pages"}, fragments  # cas zéro
    assert importes == fragments, f"importés {importes}, livrés {fragments}"
    montages = _montages()
    for nom in fragments:
        source = montages.get(f"/etc/caddy/commune/{nom}.caddy")
        assert source == f"./deploiement/standard/commune/{nom}.caddy", (nom, montages)
        assert (RACINE / source).is_file(), source


def test_le_relais_des_fichiers_precede_le_service_de_la_racine():
    texte = caddyfile()
    relais = texte.index("import commune/fichiers*.caddy")
    racine = texte.index("\thandle /uploads/* {")
    assert relais < racine


def test_la_garde_des_pages_est_dans_le_dernier_handle():
    texte = caddyfile()
    dernier = texte.rindex("\thandle {")
    corps = texte[dernier : texte.index("\n\t}", dernier)]
    assert "import commune/garde-des-pages*.caddy" in corps
    assert corps.index("import commune/") < corps.index("reverse_proxy front:3000")


def test_la_procedure_ne_retouche_pas_le_caddyfile():
    lisezmoi = (COMMUNE / "LISEZMOI.md").read_text(encoding="utf-8")
    assert not re.search(r"(?i)importer[^.\n]*dans le `Caddyfile`", lisezmoi), (
        "une retouche du Caddyfile est effacée par la mise à jour suivante"
    )
