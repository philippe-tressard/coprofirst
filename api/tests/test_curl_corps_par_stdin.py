"""Un corps de requête `curl` passe par l'entrée standard, jamais par la ligne de commande (#1964).

Sous Windows, le curl de Git Bash réencode ses ARGUMENTS dans la page de code du
système : un « é » de la charge devient l'octet 0xE9, un UTF-8 invalide, et l'API
refuse le corps en HTTP 400. Le 14/10/2026, le rapport d'une copie hors site en
échec — « écarts : … » — a été perdu ainsi : celui qu'il ne fallait pas perdre.
Un rapport sans accent passait, donc rien ne le montrait. Les nœuds (Linux) ne
réencodent rien, mais une même bibliothèque sert au poste et aux nœuds.

La forme sûre : `printf '%s' "$charge" | curl … --data-binary @-`.
"""

from __future__ import annotations

import re

from tests.conftest import scripts_shell_versionnes

#: Une option de corps suivie d'une valeur VARIABLE (`"$…`, `$…`), hors `@-`.
_CORPS_EN_ARGUMENT = re.compile(r"""(?<![\w-])(?:-d|--data(?:-raw|-binary|-urlencode)?)\s+"?\$""")


def commandes_curl(texte: str) -> list[str]:
    """Les commandes logiques qui appellent curl, continuations `\\` rejointes."""
    logiques, courante = [], ""
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("#"):
            continue
        courante += ligne.rstrip("\\") + " "
        if not ligne.rstrip().endswith("\\"):
            logiques.append(courante)
            courante = ""
    return [c for c in logiques if re.search(r"\bcurl\b", c)]


def test_le_releve_voit_la_forme_fautive():
    """Cas zéro : la forme qui a perdu le rapport est reconnue, la forme sûre non."""
    fautive = 'http=$(curl -s -X POST "$u" \\\n    -H "x: y" \\\n    -d "$charge")'
    sure = 'printf \'%s\' "$charge" | curl -s -X POST "$u" --data-binary @-'
    assert any(_CORPS_EN_ARGUMENT.search(c) for c in commandes_curl(fautive))
    assert not any(_CORPS_EN_ARGUMENT.search(c) for c in commandes_curl(sure))
    assert not commandes_curl('[ -d "$x" ] && date -d "$y"'), "pas de curl : rien à juger"


def test_aucun_corps_curl_en_argument():
    fautes = []
    #  Le relevé partagé lit `deploiement/` depuis #1965 : l'envoi de la réplique y vit.
    for script in scripts_shell_versionnes():
        for commande in commandes_curl(script.read_text(encoding="utf-8")):
            if _CORPS_EN_ARGUMENT.search(commande):
                fautes.append(f"{script.name} : {commande.strip()[:90]}")
    assert not fautes, (
        "corps de requête curl passé en argument — sous Windows il est réencodé et "
        f"l'API le refuse ; `printf '%s' \"$x\" | curl … --data-binary @-` : {fautes}"
    )
