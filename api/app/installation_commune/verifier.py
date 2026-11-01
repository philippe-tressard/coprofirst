"""Vérifier la déclaration d'une installation commune AVANT de la servir (#1894).

    docker compose exec -u app api python -m app.installation_commune.verifier [--bases]

Rend 0 et liste chaque copropriété — alias, adresse, état — si la déclaration peut
servir ; 1 et les règles violées sinon ; 2 sur une installation propre à une
copropriété, où il n'y a rien à vérifier. N'écrit aucun secret.

`--bases` : une ligne `identifiant VARIABLE` par copropriété — le nom de la variable
qui porte l'URL de sa base, jamais sa valeur. La mise à jour nocturne en tire les
bases à sauvegarder (`deploiement/standard/mise-a-jour.sh`, #2053).
"""

from __future__ import annotations

import sys

from app.installation_commune.declaration import DeclarationInvalide, declaration


def main(argv: list[str] | None = None) -> int:
    bases = "--bases" in (sys.argv[1:] if argv is None else argv)
    try:
        commune = declaration()
    except DeclarationInvalide as e:
        print(f"ECHEC : {e}")
        return 1
    if commune is None:
        print("Installation propre à une copropriété : COPROPRIETES_FICHIER n'est pas posé.")
        return 2
    if bases:
        for e in commune.entrees:
            print(f"{e.copropriete.identifiant} {e.variable_base}")
        return 0
    print(f"Hôte commun : {commune.hote_commun}")
    for e in commune.entrees:
        etat = "SUSPENDUE" if e.suspendue else "active"
        anciens = ", ".join(sorted(e.anciens_alias)) or "—"
        print(
            f"- {e.copropriete.identifiant} ({etat}) : alias {e.alias}, "
            f"adresse {commune.adresse(e)}, anciens alias {anciens}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
