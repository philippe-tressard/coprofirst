"""Les commandes ponctuelles lancées dans un conteneur : qui les lance (#2546).

Lu par `test_conteneurs_non_root.py`. Une commande lancée À CÔTÉ du processus d'un
service — `docker compose run [--entrypoint …] api`, `docker compose exec api`,
`docker exec hostachy_api` — ne passe pas par son point d'entrée, donc pas par sa
descente de root vers son compte (`setpriv` de `start.sh`, `privileges.js`). Dans
un conteneur DURCI (#2368), ce root n'a ni DAC_OVERRIDE ni FOWNER.

Le découpage est volontairement à plat — des mots, pas un analyseur de shell : il
lit aussi les documents et les docstrings, où la commande est écrite pour un
opérateur. Ses témoins sont dans le test.
"""

from __future__ import annotations

import re

#: Options de `run`/`exec` qui prennent une valeur dans le mot suivant.
AVEC_VALEUR = frozenset(
    {
        "-u",
        "--user",
        "-v",
        "--volume",
        "-e",
        "--env",
        "-w",
        "--workdir",
        "--entrypoint",
        "--name",
        "-p",
        "--publish",
        "-l",
        "--label",
        "--env-file",
        "--cap-add",
        "--cap-drop",
        "--index",
        "--pull",
    }
)
#: Ce qui termine une commande : le verbe d'après n'appartient plus à `compose`.
SEPARATEURS = frozenset({";", "&&", "||", "|", "then", "do", "else", "&", "$"})
COMPTES_ROOT = frozenset({"root", "0", "0:0", "root:root"})


def lignes_logiques(texte: str, *, script: bool) -> list[tuple[int, str]]:
    """(numéro, ligne) : commentaires d'un script blanchis, lignes coupées par `\\`
    rejointes et numérotées à leur première ligne."""
    sortie, tampon, debut = [], "", 0
    for numero, ligne in enumerate(texte.splitlines(), 1):
        if script and ligne.lstrip().startswith("#"):
            ligne = ""
        if not tampon:
            debut = numero
        if ligne.rstrip().endswith("\\"):
            tampon += ligne.rstrip()[:-1] + " "
            continue
        sortie.append((debut, tampon + ligne))
        tampon = ""
    if tampon:
        sortie.append((debut, tampon))
    return sortie


def commandes(ligne: str, conteneurs: dict[str, str]) -> list[tuple[str, str | None]]:
    """Chaque `compose run|exec <service>` et `docker exec <conteneur>` de la ligne :
    (service, compte écrit par `-u`/`--user`, ou None). Un conteneur se traduit en
    service par `conteneurs` ; un conteneur inconnu (banc, autre projet) est ignoré."""
    mots = re.sub(r"[\"'()`]", " ", ligne).split()
    trouvees = []
    for i, verbe in enumerate(mots):
        if verbe not in ("run", "exec") or i == 0:
            continue
        k = i - 1
        while k >= 0 and mots[k] not in SEPARATEURS:
            k -= 1
        commande = mots[k + 1 : i]
        par_compose = any("compose" in m.lower() for m in commande)
        par_docker = verbe == "exec" and commande[-1:] == ["docker"]
        if not (par_compose or par_docker):
            continue
        compte, j = None, i + 1
        while j < len(mots) and mots[j].startswith("-"):
            option = mots[j]
            if option.startswith("--user="):
                compte = option.split("=", 1)[1]
            elif option.startswith("-u") and not option.startswith("--") and len(option) > 2:
                compte = option[2:]
            elif option in AVEC_VALEUR and j + 1 < len(mots):
                if option in ("-u", "--user"):
                    compte = mots[j + 1]
                j += 1
            j += 1
        if j >= len(mots):
            continue
        cible = mots[j]
        if not par_compose:
            cible = conteneurs.get(cible)
            if cible is None:
                continue
        trouvees.append((cible, compte))
    return trouvees


def demarrent_en_root(services: dict, user_de_l_image: dict[str, str | None]) -> dict[str, str]:
    """Les services DURCIS (`cap_drop: [ALL]`) dont le processus 1 démarre en root —
    ni `user:` dans le compose, ni `USER` dans l'image —, avec leur conteneur.
    `user_de_l_image` : service → dernier `USER` de son Dockerfile (None sans)."""
    racines = {}
    for nom, service in services.items():
        if "ALL" not in (service.get("cap_drop") or []):
            continue
        compte = service.get("user") or user_de_l_image.get(nom)
        if compte and str(compte) not in COMPTES_ROOT:
            continue
        racines[nom] = service.get("container_name") or nom
    return racines


def fautes(
    texte: str, racines: dict[str, str], *, script: bool
) -> list[tuple[int, str, str | None]]:
    """(ligne, service, compte) de chaque commande sur un service de `racines` lancée
    sans compte, ou en root."""
    conteneurs = {c: s for s, c in racines.items()}
    return [
        (numero, service, compte)
        for numero, ligne in lignes_logiques(texte, script=script)
        for service, compte in commandes(ligne, conteneurs)
        if service in racines and (compte is None or compte in COMPTES_ROOT)
    ]
