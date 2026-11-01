"""Une commande hors requête NOMME sa copropriété sur une installation commune (#2053).

`python -m app.seed`, `python -m app.demo.charger`… s'exécutent sans requête, donc
sans hôte à résoudre. Ils travaillaient pour « la » copropriété de la configuration
(`contexte.courante()` s'y repliait) : sur une installation commune, c'est celle
que l'installation ne sert jamais, ou pire, celle qu'on n'a pas voulu toucher.

- **installation propre à une copropriété** : rien à nommer, comme avant ;
  `--copropriete principale` est accepté, toute autre est refusée ;
- **installation commune** : `--copropriete <identifiant>` est exigé, et désigne
  une copropriété de la déclaration — sinon la commande refuse (code 2), sans rien
  avoir ouvert.

```bash
docker compose exec -u app api python -m app.seed --copropriete tilleuls
```

🔒 `tests/test_commandes_nomment_leur_copropriete.py` : un module de `app/` qui se
lance (`__main__`) passe par ici, ou se déclare sans copropriété avec sa raison.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from app import contexte

OPTION = "--copropriete"


def copropriete_nommee(argv: list[str]) -> tuple[contexte.Copropriete, list[str]]:
    """La copropriété que nomme la ligne de commande, et les arguments qui restent.

    Lève `contexte.HorsCopropriete` si elle n'est pas nommée sur une installation
    commune, ou si le nom ne désigne aucune copropriété de l'installation.
    """
    reste = list(argv)
    nommee: str | None = None
    if OPTION in reste:
        rang = reste.index(OPTION)
        nommee = reste[rang + 1] if rang + 1 < len(reste) else ""
        del reste[rang : rang + 2]
    if not contexte.est_commune():
        if nommee not in (None, contexte.IDENTIFIANT_UNIQUE):
            raise contexte.HorsCopropriete(
                f"Cette installation ne sert qu'une copropriété : {OPTION} {nommee!r} n'en "
                "désigne aucune."
            )
        return contexte.de_la_configuration(), reste
    if not nommee:
        raise contexte.HorsCopropriete(
            f"Installation commune : nommez la copropriété ({OPTION} <identifiant>)."
        )
    return contexte.par_identifiant(nommee), reste


def lancer(principal: Callable[[list[str]], int | None], argv: list[str] | None = None) -> int:
    """Exécute `principal(arguments restants)` dans le contexte de la copropriété nommée.

    Rend son code de sortie, ou 2 si la copropriété n'est pas nommée — le message dit
    pourquoi, et rien n'a été ouvert.
    """
    try:
        copro, reste = copropriete_nommee(sys.argv[1:] if argv is None else argv)
    except contexte.HorsCopropriete as refus:
        print(f"REFUS : {refus}", file=sys.stderr)
        return 2
    with contexte.dans(copro):
        return principal(reste) or 0
