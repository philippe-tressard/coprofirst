"""Tout ce que la CI installe par `pip` est épinglé (#1584, 02/10/2026).

POURQUOI — rejouer à l'identique (`standards/09`) : `pip install pip-audit` sans
version rend un verdict qui dépend du JOUR (la base d'avis et le comportement de
l'outil bougent seuls), et `reuse` non épinglé lisait `reuse lint --json` dans un
format qui suit la version de l'outil. Ruff l'était depuis #1048, `reuse` depuis
#1543 : chaque épinglage s'est fait au cas par cas, après coup, parce que rien ne
refusait le suivant. Ce test est ce rien.

CE QU'IL LIT : les lignes de code (hors commentaires) de `.github/workflows/ci.yml`
qui contiennent `pip install` ou `pip3 install`. Chaque paquet nommé s'écrit
`nom==version` ; `-r fichier` est suivi dans le fichier, dont chaque ligne doit
l'être aussi ; `-c` (contraintes) est refusé tel quel, il ne dit pas ce qu'il
installe. Une exception se NOMME dans `EXCEPTIONS` avec sa raison, et une exception
qui ne sert plus fait échouer le test : une liste qu'on ne nettoie pas finit par
tout autoriser.

DEPUIS #2962 (24/11/2026) : TOUS les workflows, plus seulement `ci.yml` — la veille
nocturne épinglait `pip-audit` une seconde fois, à la main. Les outils de la CI
(`ruff`, `pip-audit`, `reuse`) s'épinglent UNE fois, dans
`scripts/ci/outils/requirements.txt`, que Dependabot (`pip`) lit ; un même paquet
épinglé deux fois est refusé. `jscpd` (un paquet npm) vit dans les
`devDependencies` du front, version exacte, et `clones_python.py` l'y lit.

CE QU'IL NE LIT PAS : les `uses:` — `test_ci_actions_epinglees.py` (#1584) — ni la
protection de branche, qui se règle chez GitHub et non dans le dépôt.
"""

import re
import shlex
from pathlib import Path

from tests.conftest import racine_depot

RACINE = racine_depot()
WORKFLOW = RACINE / ".github" / "workflows" / "ci.yml"
WORKFLOWS = sorted((RACINE / ".github" / "workflows").glob("*.yml"))
OUTILS = RACINE / "scripts" / "ci" / "outils" / "requirements.txt"
DEPENDABOT = RACINE / ".github" / "dependabot.yml"
FRONT = RACINE / "front" / "package.json"

#: Installations non épinglées tolérées : clé = nom du paquet, valeur = la raison.
#: Vide, et c'est voulu : elle ne fait que baisser.
EXCEPTIONS: dict[str, str] = {}

_INSTALL = re.compile(r"\bpip3?\s+install\b(?P<reste>.*)$")
#: Ce qui suit la commande n'est plus à elle : `&&`, `;`, `|`, une redirection, `}`.
_FIN_DE_COMMANDE = re.compile(r"\s*(?:&&|\|\||[;|}]|\d?>).*$")


def _arguments(reste: str) -> list[str]:
    """Les arguments de `pip install`, la ligne coupée à la fin de la commande."""
    return shlex.split(_FIN_DE_COMMANDE.sub("", reste), comments=True)


_EPINGLE = re.compile(r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,.\-]+\])?==[^=\s]+$")


def _lignes_de_code(texte: str):
    """(numéro, ligne) hors commentaires entiers — un motif cité en commentaire n'installe rien."""
    for numero, ligne in enumerate(texte.splitlines(), 1):
        if ligne.strip() and not ligne.strip().startswith("#"):
            yield numero, ligne


def _exigences_fichier(chemin: Path) -> list[tuple[str, str]]:
    """(ligne, motif de refus) des lignes d'un fichier d'exigences qui ne sont pas épinglées."""
    refus = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        nue = ligne.split(" #")[0].strip()
        if not nue or nue.startswith("#"):
            continue
        if nue.startswith("-r "):
            sous = (chemin.parent / nue[3:].strip()).resolve()
            refus += _exigences_fichier(sous)
        elif not _EPINGLE.match(nue):
            refus.append((nue, f"non épinglé dans {chemin.name}"))
    return refus


def installations_non_epinglees(texte: str, base: Path) -> list[tuple[int, str, str]]:
    """(numéro, paquet, raison) de chaque `pip install` de `texte` qui n'est pas épinglé.

    `base` résout les `-r fichier` (le `working-directory` de l'étape n'est pas
    reconstitué : les fichiers d'exigences sont cherchés sous `base` puis sous
    `base/api`, là où le dépôt les range).
    """
    fautes = []
    for numero, ligne in _lignes_de_code(texte):
        trouve = _INSTALL.search(ligne)
        if not trouve:
            continue
        try:
            jetons = _arguments(trouve.group("reste"))
        except ValueError:
            fautes.append((numero, ligne.strip(), "ligne illisible"))
            continue
        i = 0
        while i < len(jetons):
            jeton = jetons[i]
            if jeton in ("-r", "--requirement"):
                i += 1
                cible = jetons[i] if i < len(jetons) else ""
                fichier = next(
                    (c for c in (base / cible, base / "api" / cible) if c.is_file()), None
                )
                if fichier is None:
                    fautes.append((numero, cible, "fichier d'exigences introuvable"))
                else:
                    fautes += [(numero, p, r) for p, r in _exigences_fichier(fichier)]
            elif jeton in ("-c", "--constraint"):
                fautes.append((numero, jeton, "contraintes : ne dit pas ce qui s'installe"))
                i += 1
            elif jeton.startswith("-"):
                pass  # -q, --no-deps, --upgrade… : une option n'installe rien
            elif not _EPINGLE.match(jeton):
                fautes.append((numero, jeton, "non épinglé (`nom==version` attendu)"))
            i += 1
    return fautes


def test_le_detecteur_voit_et_ne_voit_que_le_non_epingle(tmp_path):
    """Cas zéro : le motif refuse ce qu'il doit refuser et laisse passer le reste."""
    (tmp_path / "exigences.txt").write_text("a==1\n# commentaire\nb==2 # note\n", encoding="utf-8")
    (tmp_path / "mal.txt").write_text("a==1\n-r exigences.txt\nc>=3\n", encoding="utf-8")

    refuses = (
        "run: pip install pip-audit",
        "python -m pip install reuse",
        "pip3 install ruff>=0.15",
        "pip install -q pytest==9.1.1 requests",
        "pip install -r mal.txt",
        "pip install -r absent.txt",
        "pip install -c contraintes.txt pytest==9.1.1",
    )
    permis = (
        "run: pip install ruff==0.15.8",
        "python -m pip install reuse==6.2.0",
        "pip install -q --no-deps pip-audit==2.10.1",
        "pip install 'uvicorn[standard]==0.53.0'",
        "pip install -r exigences.txt",
        "{ pip install -r exigences.txt >/dev/null && cd api && python x.py; } > f 2>&1",
        "# pip install pip-audit",
        "echo rien d'installé ici",
    )
    for ligne in refuses:
        assert installations_non_epinglees(ligne, tmp_path), f"devrait être refusée : {ligne}"
    for ligne in permis:
        assert not installations_non_epinglees(ligne, tmp_path), f"refusée à tort : {ligne}"


def test_la_ci_n_installe_rien_sans_version():
    """Chaque `pip install` de ci.yml est épinglé, sauf exception nommée et justifiée."""
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert len(re.findall(r"\bpip3?\s+install\b", texte)) >= 3, (
        "moins de trois `pip install` trouvés dans ci.yml : chemin ou motif cassé ?"
    )
    fautes = installations_non_epinglees(texte, RACINE)
    refus = [f for f in fautes if f[1] not in EXCEPTIONS]
    assert not refus, (
        "Installation(s) non épinglée(s) dans .github/workflows/ci.yml — le résultat "
        "de la CI dépendrait du jour :\n"
        + "\n".join(f"  l.{n} : {p} — {r}" for n, p, r in refus)
        + "\n  Épingler `nom==version` (ou nommer l'exception, avec sa raison, "
        "dans EXCEPTIONS)."
    )
    obsoletes = set(EXCEPTIONS) - {p for _n, p, _r in fautes}
    assert not obsoletes, (
        "exception(s) devenue(s) sans objet, à retirer d'EXCEPTIONS : "
        + ", ".join(sorted(obsoletes))
    )


def test_la_ci_declare_ses_droits_en_lecture_seule():
    """Le jeton du workflow se déclare (`contents: read`), il ne se déduit pas du réglage du dépôt.

    Aucun job de ci.yml n'écrit : une permission d'écriture ajoutée à un job se
    déclare DANS ce job, jamais en élargissant le bloc du workflow.
    """
    texte = WORKFLOW.read_text(encoding="utf-8")
    bloc = re.search(r"^permissions:\n((?:  .+\n)+)", texte, re.MULTILINE)
    assert bloc, "ci.yml n'a plus de bloc `permissions:` au niveau du workflow"
    droits = [ligne.strip() for ligne in bloc.group(1).splitlines()]
    assert droits == ["contents: read"], (
        f"droits du workflow élargis : {droits} — une écriture se déclare dans le job qui en a besoin"
    )


# ── Tous les workflows, un épinglage par outil (#2962) ─────────────────────────


def _epinglages(texte: str, base: Path) -> list[str]:
    """Les paquets épinglés par les `pip install` de `texte`, `-r` suivis compris."""
    noms = []
    for _n, ligne in _lignes_de_code(texte):
        trouve = _INSTALL.search(ligne)
        if not trouve:
            continue
        jetons = _arguments(trouve.group("reste"))
        for i, jeton in enumerate(jetons):
            if jeton in ("-r", "--requirement") and i + 1 < len(jetons):
                cible = jetons[i + 1].replace("$GITHUB_WORKSPACE/", "")
                fichier = next(
                    (c for c in (base / cible, base / "api" / cible) if c.is_file()), None
                )
                if fichier is not None:
                    noms += _noms_du_fichier(fichier)
            elif _EPINGLE.match(jeton) and (i == 0 or jetons[i - 1] not in ("-r", "--requirement")):
                noms.append(jeton.split("==")[0].split("[")[0].lower())
    return noms


def _noms_du_fichier(chemin: Path) -> list[str]:
    noms = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        nue = ligne.split(" #")[0].strip()
        if nue.startswith("-r "):
            noms += _noms_du_fichier((chemin.parent / nue[3:].strip()).resolve())
        elif nue and not nue.startswith("#"):
            noms.append(nue.split("==")[0].split("[")[0].lower())
    return noms


def test_aucun_workflow_n_installe_sans_version():
    assert len(WORKFLOWS) >= 5, "les workflows ne sont pas lus en entier"  # cas zéro
    refus = []
    for flux in WORKFLOWS:
        refus += [
            f"{flux.name} l.{n} : {p} — {r}"
            for n, p, r in installations_non_epinglees(flux.read_text(encoding="utf-8"), RACINE)
            if p not in EXCEPTIONS
        ]
    assert not refus, refus


def test_un_outil_de_ci_s_epingle_une_seule_fois():
    """Deux épinglages du même outil divergent à la première montée : la veille jugeait
    déjà avec la version de `ci.yml` parce qu'on l'y avait recopiée à la main."""
    par_flux = {
        flux.name: set(_epinglages(flux.read_text(encoding="utf-8"), RACINE)) for flux in WORKFLOWS
    }
    en_ligne = []
    for flux in WORKFLOWS:
        for _n, ligne in _lignes_de_code(flux.read_text(encoding="utf-8")):
            trouve = _INSTALL.search(ligne)
            if trouve:
                en_ligne += [j for j in _arguments(trouve.group("reste")) if _EPINGLE.match(j)]
    assert not en_ligne, (
        f"outil(s) épinglé(s) dans une ligne de commande : {en_ligne} — le ranger dans "
        f"{OUTILS.relative_to(RACINE)}, que Dependabot lit"
    )
    noms = _noms_du_fichier(OUTILS)
    assert len(noms) == len(set(noms)), f"un outil épinglé deux fois dans {OUTILS.name} : {noms}"
    assert {"ruff", "pip-audit", "reuse"} <= set(noms), noms
    assert any("pip-audit" in v for v in par_flux.values()), (
        "plus aucun workflow n'installe pip-audit"
    )


def test_dependabot_lit_les_outils_de_la_ci():
    import yaml

    blocs = [
        b
        for b in yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))["updates"]
        if b["package-ecosystem"] == "pip"
    ]
    dossiers = {d for b in blocs for d in (b.get("directories") or [b["directory"]])}
    assert "/" + OUTILS.parent.relative_to(RACINE).as_posix() in dossiers, dossiers


def test_jscpd_s_epingle_dans_le_front_et_nulle_part_ailleurs(tmp_path):
    import json
    import subprocess

    version = json.loads(FRONT.read_text(encoding="utf-8"))["devDependencies"].get("jscpd", "")
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"jscpd doit être épinglé en version EXACTE dans front/package.json (lu : {version!r}) : "
        "le compte des clones change d'une version à l'autre"
    )
    import sys

    sys.path.insert(0, str(RACINE / "scripts" / "ci"))
    import clones_python

    assert clones_python.jscpd_epingle() == f"jscpd@{version}"
    #  Témoin : une plage ou un manifeste sans jscpd rendent INCONNU, jamais une version supposée.
    for contenu in (
        '{"devDependencies": {"jscpd": "^5.4.0"}}',
        '{"devDependencies": {}}',
        "illisible",
    ):
        faux = tmp_path / "package.json"
        faux.write_text(contenu, encoding="utf-8")
        assert clones_python.jscpd_epingle(faux) is None, contenu
    recopies = subprocess.run(
        ["git", "grep", "-n", "-E", r"jscpd@[0-9]", "--", "scripts", ".github", ".claude/cloud"],
        cwd=RACINE, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    assert not recopies, f"version de jscpd recopiée : {recopies}"
