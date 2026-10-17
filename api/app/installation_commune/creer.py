"""Créer une copropriété dans une installation commune — la part de l'API (#2053).

Le geste complet est `deploiement/standard/commune/creer-copropriete.sh`, sur la
machine : il crée le rôle et la base PostgreSQL, écrit les secrets dans le `.env`,
recrée l'API pour qu'elle les lise, puis appelle ce module. Les deux parties se
partagent le travail ainsi :

- `noms` — avant tout geste : la copropriété projetée est validée contre la
  déclaration EN SERVICE (alias, hôtes, identifiant uniques…), et les noms qui en
  dérivent sont rendus au script — rôle, base, variables, dossier. Écrits ICI, une
  fois : le script ne les recompose jamais ;
- `ajouter` — une fois la base créée et les secrets dans l'environnement : prépare
  la base (schéma, migrations : `utils/preparer_bases`), y pose les données de
  démarrage (seed, dans SON contexte), crée son dossier de fichiers, puis — en
  dernier — écrit la déclaration, d'un coup (fichier temporaire puis
  remplacement). L'API la relit : la copropriété est servie, sa base déjà prête.

Une déclaration qui ne se valide pas n'est JAMAIS écrite : elle ferait servir 503 à
toutes les copropriétés de l'installation. Aucun secret n'est affiché.

    python -m app.installation_commune.creer noms <identifiant> --code-postal 75015 \\
        --nom "Les Tilleuls" --expediteur contact@exemple.fr [--hote residence.fr]

🔒 `tests/test_installation_commune_creer.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.installation_commune.declaration import DeclarationInvalide, lire

#: Le dossier des fichiers de chaque copropriété, sous le volume `uploads`.
RACINE_DES_FICHIERS = "/app/uploads"


def noms_derives(identifiant: str) -> dict[str, str]:
    """Les noms que l'identifiant fixe — rôle et base PostgreSQL, variables, dossier.

    L'identifiant est déjà validé (`[a-z0-9-]`) : le tiret devient `_`, seul
    caractère admis par les noms de rôle et de base que le script interpole.
    """
    souligne = identifiant.replace("-", "_")
    return {
        "ROLE": f"copro_{souligne}",
        "BASE": f"copro_{souligne}",
        "VAR_BASE": f"{souligne.upper()}_DATABASE_URL",
        "VAR_SECRET": f"{souligne.upper()}_SECRET_KEY",
        "RACINE": f"{RACINE_DES_FICHIERS}/{identifiant}",
    }


def entree(args: argparse.Namespace) -> dict:
    """L'entrée de la déclaration que les arguments décrivent."""
    noms = noms_derives(args.identifiant)
    return {
        "identifiant": args.identifiant,
        "code_postal": args.code_postal,
        "nom": args.nom,
        "hotes": list(args.hote or []),
        "base": noms["VAR_BASE"],
        "secret": noms["VAR_SECRET"],
        "racine_fichiers": noms["RACINE"],
        "expediteur": args.expediteur,
        "nom_expediteur": args.nom,
    }


def _texte_actuel(chemin: Path) -> dict:
    if not chemin.exists():
        return {"coproprietes": []}
    return json.loads(chemin.read_text(encoding="utf-8"))


def projeter(chemin: Path, nouvelle: dict, environnement) -> tuple[str, object]:
    """La déclaration AVEC la copropriété nouvelle, validée en entier : (texte, déclaration).

    Lève `DeclarationInvalide` — doublon, nom d'hôte, secret absent — sans rien écrire.
    """
    actuelle = _texte_actuel(chemin)
    if any(c.get("identifiant") == nouvelle["identifiant"] for c in actuelle["coproprietes"]):
        raise DeclarationInvalide(f"La copropriété {nouvelle['identifiant']} est déjà déclarée.")
    actuelle["coproprietes"].append(nouvelle)
    texte = json.dumps(actuelle, ensure_ascii=False, indent=2) + "\n"
    return texte, lire(texte, get_settings().origin, environnement)


def _ecrire_d_un_coup(chemin: Path, texte: str) -> None:
    partiel = chemin.with_name(f".{chemin.name}.partiel")
    partiel.write_text(texte, encoding="utf-8")
    os.replace(partiel, chemin)  # l'API ne lit jamais une déclaration à moitié écrite


def ajouter(chemin: Path, nouvelle: dict, environnement, preparer, semer) -> str:
    """Prépare la base, sème, crée le dossier, PUIS déclare. Rend l'adresse de la copropriété.

    `preparer(url)` et `semer(copro)` sont injectés : les tests les éprouvent sans
    dépendre l'un de l'autre, la commande passe les vrais.
    """
    from app.utils.preparer_bases import PRETES

    texte, projetee = projeter(chemin, nouvelle, environnement)
    e = next(x for x in projetee.entrees if x.copropriete.identifiant == nouvelle["identifiant"])
    verdict = preparer(e.copropriete.url_base)
    if verdict not in PRETES:
        raise DeclarationInvalide(f"Base de {nouvelle['identifiant']} non préparée : {verdict}.")
    semer(e.copropriete)
    e.copropriete.racine_fichiers.mkdir(parents=True, exist_ok=True)
    _ecrire_d_un_coup(chemin, texte)
    return projetee.adresse(e)


def _semer(copro) -> None:
    from app import contexte
    from app.seed import seed

    with contexte.dans(copro):
        seed()
        contexte.moteur().dispose()  # une commande ne garde pas de connexion ouverte


def _arguments(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.installation_commune.creer")
    p.add_argument("geste", choices=("noms", "ajouter"))
    p.add_argument("identifiant")
    p.add_argument("--code-postal", required=True)
    p.add_argument("--nom", required=True)
    p.add_argument("--expediteur", required=True)
    p.add_argument("--hote", action="append")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from app.utils.preparer_bases import preparer_base

    args = _arguments(sys.argv[1:] if argv is None else argv)
    chemin = Path(get_settings().coproprietes_fichier.strip() or "/nulle-part")
    if not get_settings().coproprietes_fichier.strip():
        print(
            "REFUS : COPROPRIETES_FICHIER n'est pas posé — ce n'est pas une installation commune."
        )
        return 2
    nouvelle = entree(args)
    try:
        if args.geste == "noms":
            #  Les secrets n'existent pas encore : des valeurs d'essai, le temps de
            #  valider tout le reste contre la déclaration en service.
            essai = dict(os.environ)
            essai.setdefault(nouvelle["base"], "postgresql+psycopg://essai@postgres/essai")
            essai.setdefault(nouvelle["secret"], "e" * 64)
            _texte, projetee = projeter(chemin, nouvelle, essai)
            e = projetee.entrees[-1]
            for cle, valeur in noms_derives(args.identifiant).items():
                print(f"{cle}={valeur}")
            print(f"ALIAS={e.alias}")
            print(f"ADRESSE={projetee.adresse(e)}")
            return 0
        adresse = ajouter(chemin, nouvelle, os.environ, preparer_base, _semer)
    except DeclarationInvalide as refus:
        print(f"REFUS : {refus}")
        return 1
    print(f"Copropriété {args.identifiant} déclarée : {adresse}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
