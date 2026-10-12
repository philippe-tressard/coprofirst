#!/usr/bin/env python3
"""Les PR ouvertes vers `main` hors de `dev`, et la reprise des PR Dependabot (#1870).

## Pourquoi (12/10/2026)

Chaque MEP fusionne `dev → main` en squash, et le dépôt supprime alors `dev`
(`delete_branch_on_merge`). GitHub RÉORIENTE vers `main` toute PR ouverte qui
visait `dev` — dont celles de Dependabot (`target-branch: dev`). Le 12/10 : sept
en une journée. Une PR verte vers `main` se fusionne d'un clic, et
`auto-deploy.sh` la déploie dans les cinq minutes : sans `dev`, sans pré-check,
sans bump, avec une branche partie d'un ancien `dev` qui embarque des dizaines de
fichiers sans rapport.

Arbitré le 12/10/2026 : on garde le flux, et la reprise devient un geste outillé.

## Ce que fait ce script

    reprendre-dependabot.py              liste les PR Dependabot réorientées et
                                         leurs montées (à reprendre dans un lot)
    reprendre-dependabot.py --fermer     les ferme, chacune avec son motif
    reprendre-dependabot.py --verifier   une ligne pour le pré-check (point 0h) :
                                         OK | ECART <détail> | INCONNU <motif>
    reprendre-dependabot.py --selftest

Les montées ne sont PAS appliquées ici : une majeure se juge (`dependabot.yml`),
un lock se laisse écrire par npm, une action s'épingle par SHA vérifié contre son
tag. Le script dit QUOI reprendre ; le lot le fait, rejoué en CI.
"""
import json
import pathlib
import re
import subprocess
import sys

#  La console de ce poste est en cp1252 : le POURQUOI vit dans `lib_console`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib_console import console_utf8  # noqa: E402

#: La branche de travail : la seule qui ait le droit d'ouvrir une PR vers `main`.
BRANCHE_DE_TRAVAIL = 'dev'
#: L'auteur des PR Dependabot, tel que `gh` le rend.
DEPENDABOT = 'app/dependabot'

MOTIF_FERMETURE = (
    "Fermée sans fusion : réorientée vers `main` par GitHub quand `dev` a été supprimée "
    "à la MEP précédente (squash). La fusionner contournerait `dev`, le pré-check et le "
    "bump ; et sa branche, partie d'un ancien `dev`, embarque des fichiers sans rapport.\n\n"
    "La montée est à reprendre dans un lot `deps` sur `dev`, rejoué en CI "
    "(`scripts/poste/reprendre-dependabot.py`, #1870)."
)

_TITRE = re.compile(r'bump (\S+) from (\S+) to (\S+)(?: in (\S+))?', re.I)
_CORPS = re.compile(r'^Updates `([^`]+)` from (\S+) to (\S+?)\.?\s*$', re.M)
#: Le tableau en tête d'une PR groupée : il est COMPLET. Les lignes « Updates … »
#: sont plus bas, et Dependabot tronque la description à 65 535 caractères — la
#: montée de `vite` de #1858 s'y était perdue.
_TABLEAU = re.compile(r'^\| \[([^\]]+)\]\([^)]*\) \| `([^`]+)` \| `([^`]+)` \|', re.M)


def montees_de(titre, corps):
    """[(paquet, de, vers)] : le tableau d'une PR groupée, ses lignes « Updates »,
    sinon le titre (PURE)."""
    trouvees = _TABLEAU.findall(corps or '') or _CORPS.findall(corps or '')
    if trouvees:
        vues, uniques = set(), []
        for m in trouvees:
            if m not in vues:
                vues.add(m)
                uniques.append(m)
        return uniques
    m = _TITRE.search(titre or '')
    return [(m.group(1), m.group(2), m.group(3))] if m else []


def hors_de_dev(prs):
    """Les PR ouvertes vers `main` dont la branche n'est pas `dev` (PURE)."""
    return [p for p in prs if p.get('headRefName') != BRANCHE_DE_TRAVAIL]


def verdict(prs):
    """La ligne du pré-check (PURE). `None` = la liste n'a pas pu être lue."""
    if prs is None:
        return 'INCONNU liste des PR illisible (gh absent, hors ligne ou non authentifié)'
    fautives = hors_de_dev(prs)
    if not fautives:
        return 'OK aucune PR vers main hors de dev'
    noms = ', '.join(f"#{p['number']} ({p.get('headRefName', '?')})" for p in fautives)
    return (f'ECART {len(fautives)} PR vers main hors de dev : {noms} — '
            'reprendre : python scripts/poste/reprendre-dependabot.py')


def lire_prs():
    """Les PR ouvertes vers `main`, ou `None` si `gh` n'a pas répondu."""
    try:
        sortie = subprocess.run(
            ['gh', 'pr', 'list', '--base', 'main', '--state', 'open', '--limit', '100',
             '--json', 'number,headRefName,author,title,body'],
            capture_output=True, text=True, encoding='utf-8', timeout=60, check=True,
        ).stdout
        return json.loads(sortie)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def selftest():
    ko = 0

    def cas(libelle, obtenu, attendu):
        nonlocal ko
        ok = obtenu == attendu
        ko |= not ok
        print(f'{"PASS" if ok else "FAIL"}  {libelle} → {obtenu!r}')

    cas('titre simple',
        montees_de('chore(deps): bump actions/setup-node from 7.0.0 to 7.1.0', ''),
        [('actions/setup-node', '7.0.0', '7.1.0')])
    cas('groupe : le corps prime, sans doublon',
        montees_de('chore(deps): bump the npm-mineur group with 2 updates',
                   'Updates `vite` from 6.4.3 to 6.4.4\nUpdates `svelte` from 5.57.0 to 5.57.2\n'
                   'Updates `vite` from 6.4.3 to 6.4.4'),
        [('vite', '6.4.3', '6.4.4'), ('svelte', '5.57.0', '5.57.2')])
    cas('description tronquée : le tableau de tête est complet',
        montees_de('chore(deps): bump the npm-mineur group with 2 updates',
                   '| Package | From | To |\n| --- | --- | --- |\n'
                   '| [svelte](https://x) | `5.57.0` | `5.57.2` |\n'
                   '| [vite](https://y) | `6.4.3` | `6.4.4` |\n\n'
                   'Updates `svelte` from 5.57.0 to 5.57.2\n…\n_Description has been truncated_'),
        [('svelte', '5.57.0', '5.57.2'), ('vite', '6.4.3', '6.4.4')])
    cas('titre illisible : rien, jamais une invention', montees_de('Mise à jour', ''), [])
    dev = {'number': 1, 'headRefName': 'dev'}
    dep = {'number': 2, 'headRefName': 'dependabot/pip/api/dev/x'}
    cas('la PR de MEP depuis dev : OK', verdict([dev]), 'OK aucune PR vers main hors de dev')
    cas('aucune PR : OK', verdict([]), 'OK aucune PR vers main hors de dev')
    cas('une PR réorientée : ÉCART qui la nomme',
        verdict([dev, dep]).split(' — ')[0],
        'ECART 1 PR vers main hors de dev : #2 (dependabot/pip/api/dev/x)')
    cas('liste illisible : INCONNU, jamais OK', verdict(None).split()[0], 'INCONNU')
    print('== ÉCHECS ==' if ko else '== TOUS OK ==')
    return ko


def main():
    console_utf8()
    if '--selftest' in sys.argv:
        return selftest()
    prs = lire_prs()
    if '--verifier' in sys.argv:
        print(verdict(prs))
        return 0
    if prs is None:
        print(verdict(prs))
        return 2
    cibles = [p for p in hors_de_dev(prs) if (p.get('author') or {}).get('login') == DEPENDABOT]
    autres = [p for p in hors_de_dev(prs) if p not in cibles]
    if not cibles:
        print('Aucune PR Dependabot réorientée vers main.')
    for p in cibles:
        print(f"#{p['number']}  {p['title']}")
        for paquet, de, vers in montees_de(p['title'], p.get('body')):
            print(f'    {paquet} {de} → {vers}')
    for p in autres:
        print(f"⚠ #{p['number']} ({p['headRefName']}) vise main sans être Dependabot : à regarder.")
    if '--fermer' in sys.argv:
        for p in cibles:
            r = subprocess.run(['gh', 'pr', 'close', str(p['number']), '--comment', MOTIF_FERMETURE],
                               capture_output=True, text=True, encoding='utf-8')
            print(f"#{p['number']} : {'fermée' if r.returncode == 0 else 'ÉCHEC — ' + r.stderr.strip()}")
    elif cibles:
        print('\n(rien n’est fermé : relancer avec --fermer, puis reprendre ces montées dans un lot sur dev)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
