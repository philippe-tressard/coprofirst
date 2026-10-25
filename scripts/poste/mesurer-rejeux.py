#!/usr/bin/env python3
"""Où passe le temps des rejeux de la CI ? (#2224, 24/10/2026)

`rejouer-ci.sh` écrit, à la fin de CHAQUE rejeu — complet ou partiel, vert,
rouge, INCONNU, interrompu ou refusé au pré-vol —, une ligne par étape jouée et
une ligne de bilan (job `@rejeu`) dans `rejeu-durees.log`, au répertoire git
COMMUN. Jusque-là, la mesure dépendait des journaux épars des sessions : 72
rejeux relus à la main pour découvrir que 35 % du temps partait dans des rejeux
non verts, et que quatre étapes faisaient 35 min sur 44.

Ce script en sort trois choses, que la coordination lit chaque heure :
  - la part du temps passée dans des rejeux NON VERTS ;
  - les dix étapes les plus longues (médiane et maximum) ;
  - la minute du premier rouge, rejeu par rejeu.

Colonnes du journal (TSV) : date · rejeu · sha · worktree · job · étape ·
durée (s) · verdict · fin (s depuis le début du rejeu).

Usage : mesurer-rejeux.py [--journal CHEMIN] [--jours N] [--derniers N]
        mesurer-rejeux.py --selftest
"""
import datetime
import pathlib
import statistics
import subprocess
import sys

#  La console de ce poste est en cp1252 : le POURQUOI vit dans `lib_console`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib_console import console_utf8  # noqa: E402

BILAN = '@rejeu'
VERT = 'VERT'


def lire(lignes):
    """Lignes du journal → {rejeu: {'bilan': dict|None, 'etapes': [dict]}}, dans l'ordre."""
    rejeux = {}
    for brut in lignes:
        champs = brut.rstrip('\r\n').split('\t')
        if len(champs) != 9:
            continue  # une ligne tronquée (rejeu tué pendant l'écriture) ne compte pas
        date, rejeu, sha, wt, job, etape, duree, verdict, fin = champs
        try:
            duree, fin = int(duree), int(fin)
        except ValueError:
            continue
        r = rejeux.setdefault(rejeu, {'bilan': None, 'etapes': [], 'date': date,
                                      'sha': sha, 'worktree': wt})
        if job == BILAN:
            r['bilan'] = {'portee': etape, 'duree': duree, 'verdict': verdict}
        else:
            r['etapes'].append({'job': job, 'etape': etape, 'duree': duree,
                                'verdict': verdict, 'fin': fin})
    return rejeux


def verdict_et_duree(r):
    """Le verdict et la durée d’un rejeu — sans bilan (rejeu tué) : « SANS BILAN », jamais VERT."""
    if r['bilan']:
        return r['bilan']['verdict'], r['bilan']['duree']
    return 'SANS BILAN', max((e['fin'] for e in r['etapes']), default=0)


def part_non_verte(rejeux):
    """(secondes non vertes, secondes en tout)."""
    non_vert = total = 0
    for r in rejeux.values():
        verdict, duree = verdict_et_duree(r)
        total += duree
        if verdict != VERT:
            non_vert += duree
    return non_vert, total


def etapes_les_plus_longues(rejeux, n=10):
    """[(job, étape, médiane, max, nombre)] — par médiane décroissante.

    Seules les étapes réellement JOUÉES comptent (OK ou FAIL) : un INCONNU
    mesure un outil absent, pas l'étape."""
    durees = {}
    for r in rejeux.values():
        for e in r['etapes']:
            if e['verdict'] in ('OK', 'FAIL'):
                durees.setdefault((e['job'], e['etape']), []).append(e['duree'])
    lignes = [(job, etape, statistics.median(d), max(d), len(d))
              for (job, etape), d in durees.items()]
    return sorted(lignes, key=lambda x: (-x[2], -x[3], x[0], x[1]))[:n]


def premier_rouge(r):
    """La minute (décimale) du premier rouge d'un rejeu, ou None."""
    fins = [e['fin'] for e in r['etapes'] if e['verdict'] == 'FAIL']
    return round(min(fins) / 60, 1) if fins else None


def filtrer(rejeux, jours, maintenant=None):
    """Les rejeux des `jours` derniers jours (None : tous)."""
    if jours is None:
        return rejeux
    limite = (maintenant or datetime.datetime.now()) - datetime.timedelta(days=jours)
    garde = {}
    for k, r in rejeux.items():
        try:
            quand = datetime.datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if quand >= limite:
            garde[k] = r
    return garde


def mmss(s):
    return f'{int(s) // 60}:{int(s) % 60:02d}'


def rapport(rejeux, derniers=20):
    """Le texte du rapport. Cas zéro : aucun rejeu → on le DIT, sans pourcentage."""
    if not rejeux:
        return '? Aucun rejeu dans le journal — rien n’est mesuré, ce n’est pas un « 0 % ».'
    out = []
    non_vert, total = part_non_verte(rejeux)
    verdicts = {}
    for r in rejeux.values():
        v, _ = verdict_et_duree(r)
        verdicts[v] = verdicts.get(v, 0) + 1
    out.append(f'{len(rejeux)} rejeu(x) — ' + ', '.join(f'{v} {n}' for v, n in sorted(verdicts.items())))
    part = f'{100 * non_vert / total:.0f} %' if total else '—'
    out.append(f'Temps dans des rejeux non verts : {mmss(non_vert)} sur {mmss(total)} ({part})')
    out.append('')
    out.append('Les dix étapes les plus longues (médiane · max · nombre) :')
    for job, etape, med, mx, nb in etapes_les_plus_longues(rejeux):
        out.append(f'  {mmss(med):>6} · {mmss(mx):>6} · {nb:>3}  {job} — {etape}')
    out.append('')
    out.append(f'Les {derniers} derniers rejeux (premier rouge à la minute) :')
    for k in list(rejeux)[-derniers:]:
        r = rejeux[k]
        v, d = verdict_et_duree(r)
        rouge = premier_rouge(r)
        portee = r['bilan']['portee'] if r['bilan'] else '—'
        out.append(f"  {r['date']}  {r['sha']:<10} {r['worktree'][:28]:<28} {v:<10} {mmss(d):>6}"
                   f"  {'rouge à ' + str(rouge) + ' min' if rouge is not None else '':<18} {portee}")
    return '\n'.join(out)


def journal_par_defaut():
    commun = subprocess.run(['git', 'rev-parse', '--git-common-dir'], capture_output=True,
                            text=True, check=False).stdout.strip() or '.git'
    return pathlib.Path(commun).resolve() / 'rejeu-durees.log'


def selftest():
    ko = 0

    def cas(libelle, obtenu, attendu):
        nonlocal ko
        ok = obtenu == attendu
        ko += not ok
        print(('PASS  ' if ok else 'FAIL  ') + libelle + ('' if ok else f'  attendu={attendu!r} obtenu={obtenu!r}'))

    def ligne(rejeu, job, etape, duree, verdict, fin, date='2026-10-24 10:00:00'):
        return '\t'.join([date, rejeu, 'abc1234', 'wt', job, etape, str(duree), verdict, str(fin)])

    journal = [
        ligne('r1', 'test-backend', 'Run pytest', 1500, 'OK', 1600),
        ligne('r1', 'test-scripts', 'Modularité', 30, 'FAIL', 40),
        ligne('r1', BILAN, 'complet', 1600, 'ROUGE', 1600),
        ligne('r2', 'test-backend', 'Run pytest', 900, 'OK', 950),
        ligne('r2', 'test-scripts', 'Modularité', 20, 'OK', 30),
        ligne('r2', 'build-frontend', 'npm absent', 0, 'INCONNU', 1),
        ligne('r2', BILAN, 'complet', 1000, 'VERT', 1000),
        ligne('r3', 'lint-backend', 'Ruff', 5, 'OK', 6),
        'ligne\ttronquée',
    ]
    rejeux = lire(journal)
    cas('trois rejeux, la ligne tronquée écartée', len(rejeux), 3)
    cas('part non verte : le rouge et le rejeu SANS BILAN', part_non_verte(rejeux), (1606, 2606))
    cas('sans bilan : verdict dit, durée = dernière fin', verdict_et_duree(rejeux['r3']), ('SANS BILAN', 6))
    top = etapes_les_plus_longues(rejeux)
    cas('le plus long en tête, médiane de deux mesures', top[0][:5], ('test-backend', 'Run pytest', 1200, 1500, 2))
    cas('un INCONNU ne compte pas parmi les durées', [t[1] for t in top].count('npm absent'), 0)
    cas('premier rouge en minutes', premier_rouge(rejeux['r1']), 0.7)
    cas('aucun rouge : None', premier_rouge(rejeux['r2']), None)
    #  🔴 Le cas zéro : un journal vide n'est pas « 0 % de temps perdu ».
    cas('journal vide : dit, jamais 0 %', rapport({}).startswith('?'), True)
    vieux = lire([ligne('v', BILAN, 'complet', 10, VERT, 10, date='2026-09-01 10:00:00')])
    cas('filtre par jours', len(filtrer(vieux, 7, datetime.datetime(2026, 10, 24))), 0)
    cas('le rapport nomme la part non verte', 'Temps dans des rejeux non verts : 26:46 sur 43:26 (62 %)' in rapport(rejeux), True)
    print('== ÉCHECS ==' if ko else '== TOUS OK ==')
    return ko


def main(args):
    if '--selftest' in args:
        return 1 if selftest() else 0

    def valeur(nom, defaut=None):
        return args[args.index(nom) + 1] if nom in args and args.index(nom) + 1 < len(args) else defaut

    chemin = pathlib.Path(valeur('--journal') or journal_par_defaut())
    if not chemin.exists():
        print(f'? Journal absent : {chemin} — aucun rejeu mesuré depuis #2224.')
        return 2
    lignes = []
    for c in (chemin.with_name(chemin.name + '.1'), chemin):   # l'ancien d'abord : l'ordre du temps
        if c.exists():
            lignes += c.read_text(encoding='utf-8', errors='replace').splitlines()
    jours = valeur('--jours')
    rejeux = filtrer(lire(lignes), int(jours) if jours else None)
    print(rapport(rejeux, int(valeur('--derniers', '20'))))
    return 0 if rejeux else 2


if __name__ == '__main__':
    console_utf8()
    sys.exit(main(sys.argv[1:]))
