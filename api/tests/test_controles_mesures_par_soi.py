"""Ce qu'un nœud ne sait mesurer que chez LUI ne se juge pas chez le pair.

`check-reliability.sh` collecte les mêmes champs sur les deux nœuds : en local
(`S_<champ>`, root) et chez le pair par SSH (`P_<champ>`, compte d'exploitation sans root).
Deux mesures n'y valent rien de l'autre côté (#2199, 23/10/2026) :

- les **droits** du fichier du jeton du tunnel (C39) : `/etc/cloudflared` ne se
  lit qu'en root, le pair rendait « ? » à chaque passage, et le contrôle comptait
  un vert pour une moitié qu'il n'avait pas jugée ;
- le **cache de build** (C16) : du 15 au 24/10/2026, la mesure du pair est revenue
  vide 17 fois depuis rpi1 et 9 depuis rpi2 ; celle de chaque nœud par lui-même,
  jamais.

Chaque nœud mesure et rapporte les siens ; un pair muet, c'est « Peer injoignable »
et « check-reliability ne tourne plus » qui le disent. La liste se lit ici : un
champ déclaré qui disparaît de la collecte fait échouer le test.
"""

from __future__ import annotations

import re

from tests.aides_shell import lignes_hors_autotest
from tests.conftest import racine_depot, scripts_shell_versionnes

#: champ de la collecte → pourquoi il ne se lit que chez soi
MESURES_PAR_SOI = {
    "buildcache": "C16 — mesure du pair vide plusieurs fois par jour, jamais chez soi (#2199)",
    "tunnel_jeton_mode": "C39 — droits de /etc/cloudflared lisibles en root seulement (#2199)",
}


def _lignes() -> list[tuple[str, str]]:
    racine = racine_depot()
    return [
        (f"{chemin.relative_to(racine).as_posix()}:{no}", ligne)
        for chemin in scripts_shell_versionnes()
        for no, ligne in lignes_hors_autotest(chemin)
    ]


def test_chaque_champ_declare_est_collecte():
    tout = "\n".join(ligne for _, ligne in _lignes())
    absents = [c for c in MESURES_PAR_SOI if not re.search(rf"\b{c}=", tout)]
    assert not absents, f"champ déclaré qui n'est plus collecté — le retirer : {absents}"


def test_aucun_champ_par_soi_n_est_lu_chez_le_pair():
    fautifs = [
        f"{ou} ({champ})"
        for ou, ligne in _lignes()
        for champ in MESURES_PAR_SOI
        #  `P_champ` en clair, ou composé (`${p}_champ` dans une boucle sur S/P).
        if re.search(rf"\bP_{champ}\b|\$\{{?p\}}?_{champ}\b", ligne)
    ]
    assert not fautifs, f"mesure du pair lue pour un champ qui ne vaut que chez soi : {fautifs}"
