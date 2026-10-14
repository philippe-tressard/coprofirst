"""Un script qui appelle une fonction SSH des modules pose `SSH_CMD` lui-même (#1781).

`lib-ssh-noeuds.sh` ne pose pas `SSH_CMD` : chaque script l'obtient par
`SSH_CMD=$(ssh_noeud_cmd N)`. `reconstruire-replique.sh` (v2.127.0) appelait
`role_base_pair` sans l'avoir posé — la commande se réduisait à l'adresse du pair, la
base du pair se lisait « illisible », et l'outil refusait toujours. Le contrôle
des variables sous `set -u` ne le voyait pas : la référence vit dans le module.

Ce test calcule, dans `scripts/lib/`, les fonctions qui se servent de `SSH_CMD`
— directement, ou en appelant l'une d'elles —, puis exige que tout script qui
en appelle une pose la variable.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]
_POSE = "SSH_CMD=$(ssh_noeud_cmd"
_UNE_LIGNE = re.compile(r"^([a-z_][a-z0-9_]*)\(\)\s*\{(.*)\}\s*$")
_OUVERTURE = re.compile(r"^([a-z_][a-z0-9_]*)\(\)\s*\{")


def _sans_commentaires(texte: str) -> str:
    return "\n".join(li for li in texte.splitlines() if not li.lstrip().startswith("#"))


def corps_des_fonctions(texte: str) -> dict[str, str]:
    """Les fonctions définies EN DÉBUT DE LIGNE d'un module : nom → corps.

    Une ligne (`f() { …; }`) ou un bloc fermé par `}` seul en colonne 0. Les
    fonctions indentées (celles d'un autotest) ne sont pas des fonctions du module.
    """
    corps: dict[str, str] = {}
    nom, lignes = None, []
    for ligne in texte.splitlines():
        if nom is None:
            if m := _UNE_LIGNE.match(ligne):
                corps[m.group(1)] = m.group(2)
            elif m := _OUVERTURE.match(ligne):
                nom, lignes = m.group(1), []
        elif ligne == "}":
            corps[nom] = "\n".join(lignes)
            nom = None
        else:
            lignes.append(ligne)
    return corps


def fonctions_ssh() -> set[str]:
    corps: dict[str, str] = {}
    modules = [p for p in scripts_shell_versionnes() if p.parent.name == "lib"]
    for module in sorted(m for m in modules if m.name.startswith("lib-")):
        corps |= corps_des_fonctions(_sans_commentaires(module.read_text(encoding="utf-8")))
    ssh = {nom for nom, c in corps.items() if "$SSH_CMD" in c}
    while True:  # fermeture : une fonction qui en appelle une autre en dépend aussi
        plus = {
            nom
            for nom, c in corps.items()
            if nom not in ssh and any(re.search(rf"\b{f}\b", c) for f in ssh)
        }
        if not plus:
            return ssh
        ssh |= plus


def test_le_releve_trouve_les_fonctions_ssh():
    ssh = fonctions_ssh()
    for attendue in (
        "role_base_pair",
        "verrou_poser",
        "phases_base_postgresql",
        "ecrire_database_url_pair",
    ):
        assert attendue in ssh, (
            f"{attendue} devrait dépendre de SSH_CMD — le relevé ne mesure plus rien"
        )
    assert "role_base_locale" not in ssh


#: Les scripts qui joignent les nœuds depuis le POSTE, par la clé de la personne qui
#: les lance — jamais par la clé inter-nœuds de root, illisible là. Ils posent
#: `SSH_CMD` eux-mêmes ; chaque entrée doit encore appeler une fonction SSH et poser
#: la variable, sinon elle ne sert plus et le test le dit.
DEPUIS_LE_POSTE = {
    "scripts/poste/export-hors-site.sh": "copie hors site, lancée à la main depuis le "
    "poste : `transferer_archive` et `copier_plateforme` (#1896) lisent le volume des "
    "sauvegardes par un conteneur jetable, sous le compte de la personne",
}


def _appels_ssh(code: str, ssh: set[str]) -> list[str]:
    return sorted(f for f in ssh if re.search(rf"(^|[\s;&|(]){f}\b", code, re.M))


def test_les_scripts_du_poste_declares_servent():
    ssh = fonctions_ssh()
    for chemin in DEPUIS_LE_POSTE:
        code = _sans_commentaires((RACINE / chemin).read_text(encoding="utf-8"))
        assert _appels_ssh(code, ssh), f"{chemin} n'appelle plus de fonction SSH : à retirer"
        assert re.search(r"(?m)^SSH_CMD=", code), f"{chemin} ne pose plus SSH_CMD lui-même"


def test_tout_appelant_pose_ssh_cmd():
    ssh = fonctions_ssh()
    fautes = []
    for script in scripts_shell_versionnes():
        relatif = script.relative_to(RACINE).as_posix()
        if "/lib/" in script.as_posix() or relatif in DEPUIS_LE_POSTE:
            continue
        code = _sans_commentaires(script.read_text(encoding="utf-8"))
        appels = _appels_ssh(code, ssh)
        if appels and _POSE not in code:
            fautes.append(f"{script.relative_to(RACINE).as_posix()} : {appels}")
    assert not fautes, (
        "ces scripts appellent une fonction SSH des modules sans poser "
        f"`SSH_CMD=$(ssh_noeud_cmd N)` : {fautes}"
    )


def _points_d_entree_root() -> set[str]:
    """Les scripts que root lance d'office : le crontab root et l'unité systemd."""
    dossier = RACINE / "infra" / "points-entree"
    textes = [(dossier / "cron-root.crontab").read_text(encoding="utf-8")]
    textes += [p.read_text(encoding="utf-8") for p in sorted(dossier.glob("*.service"))]
    return {nom for t in textes for nom in re.findall(r"([a-z][a-z0-9-]*\.sh)\b", t)}


def test_un_outil_lance_a_la_main_exige_root():
    """La clé inter-nœuds n'est lisible que par root (#1781, essai du 09/10/2026).

    Un script qui pose `SSH_CMD` sans être un point d'entrée root (crontab root,
    unité systemd) est un outil qu'une personne lance : il appelle
    `ssh_noeud_exiger_root`, qui refuse en le disant au lieu de lire le pair
    « illisible ». `reconstruire-replique.sh` refusait ainsi, lancé sans sudo.
    """
    entrees = _points_d_entree_root()
    assert {"bascule.sh", "check-reliability.sh", "boot-role-guard.sh"} <= entrees, (
        f"cas zéro : les points d'entrée root ne se lisent plus ({sorted(entrees)})"
    )
    fautes = []
    for script in scripts_shell_versionnes():
        if "/lib/" in script.as_posix() or script.name in entrees:
            continue
        code = _sans_commentaires(script.read_text(encoding="utf-8"))
        if _POSE in code and not re.search(r"(?m)^ssh_noeud_exiger_root\b", code):
            fautes.append(script.relative_to(RACINE).as_posix())
    assert not fautes, (
        "ces outils joignent le pair par la clé de root sans exiger root "
        f'(`ssh_noeud_exiger_root "$0"` après le chargement de lib-ssh-noeuds) : {fautes}'
    )
