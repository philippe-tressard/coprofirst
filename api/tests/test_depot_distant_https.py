"""Le code des nœuds se tire en HTTPS, et la liste de sortie n'ouvre aucun SSH (#2367, 02/11/2026).

La sortie des nœuds se ferme par liste blanche, et ufw ne nomme pas un hôte.
`git fetch` passait par SSH vers `github.com`, qui se résout parfois vers l'une
des ~55 adresses isolées d'`api.github.com/meta` : rpi2 a émis 62 connexions en
24 h vers `20.250.119.67:22`, hors de toute plage déclarée — le mode refus aurait
coupé le déploiement. Le dépôt est public : l'HTTPS se passe de clé, et le 443
est déjà ouvert. Ce test tient ce que le self-test shell ne voit pas :

- l'adresse du dépôt n'est écrite qu'une fois (`lib-depot-distant.sh`) et reste
  celle de `SOURCE_IMAGES` ;
- les trois chemins qui tirent le code (auto-deploy, reprise en main, bascule
  chez le pair) passent par elle ;
- aucun script ne nomme un remote SSH, et la liste de sortie ne déclare aucun
  port 22 : une plage de GitHub figée re-casserait le déploiement au prochain
  changement d'adresse.
"""

from __future__ import annotations

import re

from tests.aides_compose import RACINE

LIB = RACINE / "scripts" / "lib" / "lib-depot-distant.sh"
LISTE = RACINE / "scripts" / "lib" / "lib-durcissement.sh"
IMAGES = RACINE / "scripts" / "lib" / "lib-images-ci.sh"
CHEMINS = {
    "auto-deploy": RACINE / "scripts" / "exploitation" / "auto-deploy.sh",
    "reprise en main": RACINE / "scripts" / "exploitation" / "MaJ-Hostachy.sh",
    "bascule": RACINE / "scripts" / "exploitation" / "bascule.sh",
}
#  Un remote SSH : `git@github.com:proprietaire/depot` ou `ssh://git@…`.
REMOTE_SSH = re.compile(r"git@github\.com:[\w.-]+/|ssh://git@")


def _constante(chemin, nom: str) -> str:
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(f"{nom}="):
            return ligne.split("=", 1)[1].strip().strip('"')
    raise AssertionError(f"{nom} introuvable dans {chemin.name}")


def test_l_adresse_du_depot_est_celle_des_images_et_en_https():
    """Deux adresses du même dépôt divergeraient au premier renommage."""
    url = _constante(LIB, "DEPOT_DISTANT_URL")
    assert url == _constante(IMAGES, "SOURCE_IMAGES") + ".git"
    assert url.startswith("https://") and "@" not in url


def test_les_trois_chemins_qui_tirent_le_code_passent_par_la_lib():
    """Un chemin oublié garderait le SSH, et le refus le couperait seul."""
    for nom, chemin in CHEMINS.items():
        texte = chemin.read_text(encoding="utf-8")
        assert "lib-depot-distant.sh" in texte, nom
    assert "depot_distant_preparer" in CHEMINS["auto-deploy"].read_text(encoding="utf-8")
    assert "depot_distant_preparer" in CHEMINS["reprise en main"].read_text(encoding="utf-8")
    #  Chez le pair, le code est encore l'ancien : la commande se joue AVANT son fetch.
    bascule = CHEMINS["bascule"].read_text(encoding="utf-8")
    assert re.search(r"depot_distant_commande\)\s*&&\s*git fetch", bascule)


def test_aucun_script_ne_nomme_un_remote_ssh():
    trouves = [
        str(f.relative_to(RACINE))
        for dossier in ("scripts", "deploiement", "infra")
        for f in (RACINE / dossier).rglob("*")
        if f.is_file() and f.suffix in {".sh", ".py", ".service", ".crontab", ".yml"}
        if REMOTE_SSH.search(f.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not trouves, f"remote SSH dans {trouves} : le code se tire en HTTPS (lib-depot-distant.sh)"


def test_la_liste_de_sortie_n_ouvre_aucun_port_22():
    """GitHub change d'adresse : toute plage figée re-casserait le déploiement un jour."""
    bloc = LISTE.read_text(encoding="utf-8").split('DURCISSEMENT_UFW_SORTANT="', 1)[1].split('"\n', 1)[0]
    ssh = [ligne for ligne in bloc.splitlines() if re.search(r"port 22\b|\b22/tcp", ligne)]
    assert not ssh, f"SSH sortant déclaré : {ssh}"
