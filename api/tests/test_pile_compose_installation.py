"""La pile compose d'une installation s'écrit une fois : `definir_compose` (claude-config#604).

La commande `docker compose -f docker-compose.yml -f …/compose.images.yml` était
recopiée dans quatre scripts. Celui de la mise à jour nocturne n'ajoutait pas la
surcouche d'une installation COMMUNE, que `creer-copropriete.sh` posait : chaque
mise à jour recréait la pile d'une installation propre. La commande vit désormais
dans `deploiement/standard/lib-installation.sh`, qui ajoute la surcouche dès que
`COPROPRIETES_FICHIER` est posé dans `.env`.

- les deux variantes, jouées par bash sur un `.env` jetable ;
- aucun script ne réécrit la pile à la main.
"""

import re
import subprocess

import pytest

from tests.conftest import racine_depot, scripts_shell_versionnes

RACINE = racine_depot()
LIB = RACINE / "deploiement" / "standard" / "lib-installation.sh"
SURCOUCHE_COMMUNE = "deploiement/standard/commune/compose.commune.yml"
#: La pile écrite à la main : `-f docker-compose.yml` dans un tableau ou une commande.
PILE_RECOPIEE = re.compile(r"docker compose\s+-f\s+docker-compose\.yml")


def _pile(env: str, dossier) -> list[str]:
    (dossier / ".env").write_text(env, encoding="utf-8")
    sortie = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; definir_compose; printf "%s\\n" "${{COMPOSE[@]}}"'],
        cwd=dossier,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sortie.split()


def test_installation_propre_sans_surcouche_commune(tmp_path):
    pile = _pile("COPROFIRST_VERSION=3.0.0\n", tmp_path)
    assert pile[:3] == ["docker", "compose", "-f"], pile
    assert "deploiement/standard/compose.images.yml" in pile
    assert SURCOUCHE_COMMUNE not in pile


@pytest.mark.parametrize("valeur", ["/coproprietes.json", '"/coproprietes.json"\r'])
def test_installation_commune_avec_sa_surcouche(tmp_path, valeur):
    pile = _pile(f"COPROPRIETES_FICHIER={valeur}\n", tmp_path)
    assert pile[-2:] == ["-f", SURCOUCHE_COMMUNE], pile
    #  La surcouche des images vient AVANT : la commune se pose par-dessus elle.
    assert pile.index("deploiement/standard/compose.images.yml") < pile.index(SURCOUCHE_COMMUNE)


def test_cle_vide_reste_une_installation_propre(tmp_path):
    assert SURCOUCHE_COMMUNE not in _pile("COPROPRIETES_FICHIER=\n", tmp_path)


def test_aucun_script_ne_recopie_la_pile():
    lus, fautes = 0, []
    for script in scripts_shell_versionnes():
        if script == LIB:
            continue
        lus += 1
        for n, ligne in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            if PILE_RECOPIEE.search(ligne) and not ligne.lstrip().startswith("#"):
                fautes.append(f"{script.relative_to(RACINE)}:{n}: {ligne.strip()}")
    assert lus > 20, "relevé des scripts vide : contrôle impossible"
    assert not fautes, "pile compose recopiée — appeler definir_compose :\n" + "\n".join(fautes)
    assert PILE_RECOPIEE.search(
        "COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml)"
    ), "le motif ne reconnaît plus la forme d'avant le correctif"
