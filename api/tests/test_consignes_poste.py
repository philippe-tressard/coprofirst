"""Une consigne ne donne pas une commande que le poste ne sait pas jouer (#2935).

Le poste est un Mac depuis le 30/10/2026 : ni `pwsh` ni `powershell` n'y existent,
et la consigne globale demande l'outil Bash. Le 23/11/2026, deux skills donnaient
encore des blocs ```powershell (`Get-ChildItem … | Select-String`, `Copy-Item`) :
une session qui les suit échoue, ou réécrit la commande de mémoire.

Le poste Windows reste déclaré : un chemin ou un lanceur `.cmd` peut être NOMMÉ à
côté de celui du Mac. Ce qui est refusé, c'est la commande PowerShell donnée comme
la façon de faire.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]

#: Les cmdlets PowerShell, et le bloc qui les annonce.
POWERSHELL = re.compile(r"```powershell|\b(?:Get-ChildItem|Select-String|Copy-Item|Set-Content)\b")

#: Les consignes qui en portent encore, et pourquoi. Une entrée qui ne sert plus
#: fait échouer le contrôle.
EXCEPTIONS = {
    ".claude/skills/security-audit/SKILL.md": (
        "neuf blocs, réécrits par le lot de l'audit de sécurité du 23/11/2026, qui "
        "tient cette skill"
    ),
}


def _consignes() -> list[pathlib.Path]:
    trouves = [_RACINE / "CLAUDE.md", *sorted((_RACINE / ".claude").rglob("*.md"))]
    assert len(trouves) >= 8, "la portée des consignes a changé : le contrôle ne mesure plus rien"
    return trouves


def test_aucune_consigne_ne_donne_une_commande_powershell():
    fautes, inutiles = [], []
    for chemin in _consignes():
        relatif = chemin.relative_to(_RACINE).as_posix()
        lignes = [
            f"  {relatif}:{n}"
            for n, ligne in enumerate(chemin.read_text(encoding="utf-8").split("\n"), 1)
            if POWERSHELL.search(ligne)
        ]
        if relatif in EXCEPTIONS:
            if not lignes:
                inutiles.append(relatif)
            continue
        fautes += lignes
    assert not inutiles, f"exceptions qui ne servent plus (à retirer) : {inutiles}"
    assert not fautes, (
        "Une consigne donne une commande PowerShell, que le poste (Mac) ne sait pas "
        "jouer — l'écrire en `grep`/`rg`, `cp` :\n" + "\n".join(fautes)
    )


def test_le_motif_reconnait_un_bloc_et_une_cmdlet():
    assert POWERSHELL.search("```powershell")
    assert POWERSHELL.search("Copy-Item docs/manuel-utilisateur.html front/static/")
    assert not POWERSHELL.search("cp docs/manuel-utilisateur.html front/static/")
    assert set(EXCEPTIONS) <= {p.relative_to(_RACINE).as_posix() for p in _consignes()}
