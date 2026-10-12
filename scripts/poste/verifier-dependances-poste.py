#!/usr/bin/env python3
"""Le poste a-t-il installé ce que le lot ÉPINGLE ? (#1417, 28/09/2026)

`rejouer-ci.sh` n'exécute jamais une étape d'installation — elle écraserait
l'environnement du poste. Les contrôles qui la suivent tournent donc sur ce qui
est DÉJÀ installé. Pour un lot qui monte ses dépendances, le rejeu de #1415 a
rendu « pytest OK » avec sqlmodel 0.0.39 quand le lot posait 0.0.44 : le vert
ne disait rien du lot. C'est le faux vert de `standards/04` — un contrôle qui
s'exécute sur autre chose que ce qu'on croit mesurer.

Ce script lit le corps d'une étape d'installation sur l'entrée standard et
compare ce qu'elle installerait à ce qui est installé :

  - `pip install -r fichier` et `pip install nom==version` : contre
    `importlib.metadata` de l'interpréteur qui fera tourner les contrôles ;
  - `npm ci` / `npm install` : `package-lock.json` contre le lock caché que npm
    tient dans `node_modules/.package-lock.json`.

Il écrit UNE ligne :
  ALIGNE                         — le poste a exactement ce que le lot épingle ;
                                   jamais quand rien n'a été comparé (#1863) ;
  ECART <paquet épinglé→poste>…  — les contrôles du job ne mesurent pas le lot ;
  INCONNU <motif>                — rien pour comparer : jamais lu comme un vert.

Usage : verifier-dependances-poste.py --rep <répertoire de l'étape> < corps
        verifier-dependances-poste.py --selftest
"""
import json
import pathlib
import re
import sys

#  La console de ce poste est en cp1252 : le POURQUOI vit dans `lib_console`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib_console import console_utf8  # noqa: E402


def nom_normalise(nom):
    """PEP 503 : `Pydantic_Core` et `pydantic-core` sont le même paquet."""
    return re.sub(r'[-_.]+', '-', nom).lower()


def lire_requirements(chemin, vus=None):
    """{nom normalisé: version} des lignes `nom==version` ; suit les `-r`."""
    vus = vus if vus is not None else set()
    chemin = pathlib.Path(chemin).resolve()
    if chemin in vus:
        return {}
    vus.add(chemin)
    epingles = {}
    for brut in chemin.read_text(encoding='utf-8').splitlines():
        ligne = brut.split('#', 1)[0].strip()
        if not ligne:
            continue
        m = re.match(r'^-r\s+(\S+)$', ligne) or re.match(r'^--requirement[= ](\S+)$', ligne)
        if m:
            epingles.update(lire_requirements(chemin.parent / m.group(1), vus))
            continue
        epingles.update(specs_pip([ligne.split(';', 1)[0].strip()]))
    return epingles


def specs_pip(mots):
    """{nom normalisé: version} des arguments `nom==version` ; les autres (non
    épinglés, options) ne s'éprouvent pas : il n'y a rien à comparer."""
    epingles = {}
    for mot in mots:
        m = re.match(r'^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?==([^\s,;]+)$', mot)
        if m:
            epingles[nom_normalise(m.group(1))] = m.group(3)
    return epingles


def ecart_pip(epingles, installes):
    """Liste des écarts « nom épinglé→poste » (PURE)."""
    return [
        f'{nom} {version}→{installes.get(nom, "absent")}'
        for nom, version in sorted(epingles.items())
        if installes.get(nom) != version
    ]


def ecart_npm(lock, installe):
    """Liste des écarts entre le lock du dépôt et celui de `node_modules` (PURE).

    Un paquet OPTIONNEL absent n'est pas un écart : npm n'installe que celui de
    la plateforme (`@esbuild/win32-x64` ici, `linux-x64` en CI)."""
    ecarts = []
    poste = installe.get('packages', {})
    for cle, entree in sorted(lock.get('packages', {}).items()):
        if not cle or entree.get('link') or 'version' not in entree:
            continue
        a = poste.get(cle)
        if a is None:
            if not entree.get('optional'):
                ecarts.append(f'{cle.rsplit("node_modules/", 1)[-1]} {entree["version"]}→absent')
        elif a.get('version') != entree['version']:
            ecarts.append(f'{cle.rsplit("node_modules/", 1)[-1]} {entree["version"]}→{a.get("version")}')
    return ecarts


def installes_pip():
    from importlib import metadata
    return {nom_normalise(d.metadata['Name']): d.version for d in metadata.distributions() if d.metadata['Name']}


def verdict(corps, rep):
    rep = pathlib.Path(rep)
    ecarts, mesure, reconnue = [], False, False
    for ligne in corps.splitlines():
        mots = ligne.strip().split()
        if not mots or mots[0].startswith('#'):
            continue
        if mots[:2] in (['pip', 'install'], ['pip3', 'install']) or mots[:4] == ['python', '-m', 'pip', 'install']:
            reconnue = True
            args = mots[mots.index('install') + 1:]
            epingles = specs_pip(args)
            for i, mot in enumerate(args):
                if mot in ('-r', '--requirement') and i + 1 < len(args):
                    fichier = rep / args[i + 1]
                    if not fichier.is_file():
                        return f'INCONNU {args[i + 1]} introuvable'
                    epingles.update(lire_requirements(fichier))
            if epingles:
                mesure = True
                ecarts += ecart_pip(epingles, installes_pip())
        elif mots[:2] in (['npm', 'ci'], ['npm', 'install']):
            reconnue = True
            lock, cache = rep / 'package-lock.json', rep / 'node_modules' / '.package-lock.json'
            if not lock.is_file():
                return f'INCONNU {lock.name} introuvable'
            if not cache.is_file():
                return 'INCONNU node_modules non installé sur le poste'
            mesure = True
            ecarts += ecart_npm(json.loads(lock.read_text(encoding='utf-8')),
                                json.loads(cache.read_text(encoding='utf-8')))
    if ecarts:
        return 'ECART ' + ', '.join(ecarts[:8]) + (f' (+{len(ecarts) - 8})' if len(ecarts) > 8 else '')
    #  Cas zéro (#1863) : rien comparé n'est pas « aligné ».
    if not reconnue:
        return 'INCONNU aucune installation reconnue dans l’étape'
    if not mesure:
        return 'INCONNU aucune version épinglée à comparer'
    return 'ALIGNE'


def selftest():
    ko = 0

    def cas(libelle, obtenu, attendu):
        nonlocal ko
        ok = obtenu == attendu
        ko |= not ok
        print(f'{"PASS" if ok else "FAIL"}  {libelle} → {obtenu!r}')

    cas('specs épinglées, extras, options ignorées',
        specs_pip(['-q', 'Uvicorn[standard]==0.53.0', 'pip-audit', 'ruff==0.15.8']),
        {'uvicorn': '0.53.0', 'ruff': '0.15.8'})
    cas('écart pip : version différente et absent',
        ecart_pip({'sqlmodel': '0.0.44', 'pypdf': '6.19.0', 'ruff': '0.15.8'},
                  {'sqlmodel': '0.0.39', 'ruff': '0.15.8'}),
        ['pypdf 6.19.0→absent', 'sqlmodel 0.0.44→0.0.39'])
    cas('noms normalisés (PEP 503)', nom_normalise('Pydantic_Core'), 'pydantic-core')
    lock = {'packages': {'': {'name': 'front'},
                         'node_modules/vite': {'version': '6.4.0'},
                         'node_modules/@esbuild/linux-x64': {'version': '0.25.0', 'optional': True},
                         'node_modules/a/node_modules/b': {'version': '1.0.0'}}}
    cas('écart npm : l’optionnel d’une autre plateforme ne compte pas',
        ecart_npm(lock, {'packages': {'node_modules/vite': {'version': '6.3.5'},
                                      'node_modules/a/node_modules/b': {'version': '1.0.0'}}}),
        ['vite 6.4.0→6.3.5'])
    cas('écart npm : aligné', ecart_npm(lock, {'packages': {'node_modules/vite': {'version': '6.4.0'},
                                                           'node_modules/a/node_modules/b': {'version': '1.0.0'}}}), [])
    cas('npm sans node_modules → INCONNU, jamais ALIGNE',
        verdict('npm ci', pathlib.Path(__file__).parent / 'inexistant'), 'INCONNU package-lock.json introuvable')
    #  Cas zéro (#1863) : une étape d'où rien ne se compare n'a rien MESURÉ — jamais
    #  ALIGNE. Une installation qui changerait de forme (`uv pip sync`, `pip
    #  install .`) passait sinon pour alignée, le faux vert de #1415.
    cas('installation non épinglée → INCONNU, jamais ALIGNE',
        verdict('pip install pip-audit', '.'), 'INCONNU aucune version épinglée à comparer')
    cas('aucune installation reconnue → INCONNU',
        verdict('uv pip sync requirements.txt', '.'), 'INCONNU aucune installation reconnue dans l’étape')
    cas('corps vide → INCONNU', verdict('', '.'), 'INCONNU aucune installation reconnue dans l’étape')
    cas('commentaires seuls → INCONNU', verdict('# rien', '.'), 'INCONNU aucune installation reconnue dans l’étape')
    print('== ÉCHECS ==' if ko else '== TOUS OK ==')
    return ko


if __name__ == '__main__':
    console_utf8()
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    rep = sys.argv[sys.argv.index('--rep') + 1] if '--rep' in sys.argv else '.'
    print(verdict(sys.stdin.read(), rep))
