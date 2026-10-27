#!/usr/bin/env python3
"""Aucun script shell ne juge l'horloge RÉELLE contre une date posée (#2261).

Un autotest qui lit `date +%F` pour comparer à une échéance écrite en dur est une
bombe à retardement : son verdict change sans qu'aucun code change. Le 26/10/2026,
`lib-maintenance-trace.sh --selftest` comparait `date +%F` à
`MAINT_TRANSITION_FIN=2026-10-25` et échouait passé cette date — tout rejeu, de
toute session, tombait sur le job `test-scripts` sans lien avec son lot
(`standards/04` : une décision se teste sur une date INJECTÉE).

Trois formes sont refusées, dans les `*.sh` versionnés (commentaires exclus) :
  A. une CONSTANTE datée (`NOM=2026-10-25`) dans un fichier qui lit aussi l'horloge
     réelle — c'est la forme exacte du 26/10 ;
  B. un littéral daté et une lecture de l'horloge réelle sur la MÊME ligne ;
  C. l'âge d'un horodatage LOCAL calculé à la main, `$(date +%s) - $(date -d "$ts" +%s)` :
     il rend un âge négatif pendant l'heure double d'octobre (#2232). L'âge se demande à
     `age_min_epoch` (`lib-horodatage.sh`), qui la corrige.

Ne comptent PAS comme lecture de l'horloge réelle :
  - `${AUJOURDHUI:-$(date +%F)}` — la forme injectable : le test pose la variable ;
  - `date -d '<littéral>' …` — une conversion, pas l'heure qu'il est.

Une exception se déclare dans `EXCEPTIONS` avec sa raison, et le contrôle échoue si
elle cesse de servir (`standards/05` §2) : elle est vide aujourd'hui.

Usage : horloge_autotests.py
        horloge_autotests.py --selftest
"""
import os
import re
import subprocess
import sys

#  « chemin » → raison. Vide : aucun script ne mêle constante datée et horloge réelle.
EXCEPTIONS = {}

_DATE = r'20\d\d-\d\d-\d\d'
CONSTANTE = re.compile(rf'^\s*(?:export\s+|readonly\s+|local\s+)?[A-Za-z_]\w*=["\']?{_DATE}')
LITTERAL = re.compile(_DATE)
#  `${VAR:-$(date +%F)}` : l'horloge n'est lue que si le test n'a rien injecté.
INJECTABLE = re.compile(r'\$\{\w+:-\$\((?:[^()]|\([^()]*\))*\)\}')
#  `date -d '2026-07-30 01:30:00' +%s` : convertir une date posée, pas lire l'heure.
CONVERSION = re.compile(r'''date\s+-d\s+('[^']*'|"[^"]*"|\S+)''')
HORLOGE = re.compile(r'date\s+(?:-u\s+)?\+%|\$EPOCHSECONDS|\$\(\s*date\s*\)')
AGE_A_LA_MAIN = re.compile(r'date\s+\+%s\s*\)\s*-\s*\\?\$\(\s*date\s+-d\b')
MINIMUM = 100  # moins de scripts lus : le motif git est cassé, pas « tout va bien »


def lit_l_horloge(ligne):
    """La ligne lit-elle l'heure RÉELLE (hors forme injectable et hors conversion) ?"""
    return bool(HORLOGE.search(CONVERSION.sub('', INJECTABLE.sub('', ligne))))


def juger(chemin, texte):
    """Les fautes d'un fichier : liste de (numéro de ligne, forme, ligne)."""
    lignes = [(i, l) for i, l in enumerate(texte.splitlines(), 1) if not l.lstrip().startswith('#')]
    horloge = [i for i, l in lignes if lit_l_horloge(l)]
    fautes = []
    for i, ligne in lignes:
        if horloge and CONSTANTE.match(ligne):
            fautes.append((i, 'A', ligne.strip()))
        if LITTERAL.search(ligne) and lit_l_horloge(ligne):
            fautes.append((i, 'B', ligne.strip()))
        if AGE_A_LA_MAIN.search(ligne):
            fautes.append((i, 'C', ligne.strip()))
    return fautes


def fichiers(racine='.'):
    sortie = subprocess.run(['git', '-C', racine, 'ls-files', '-z', '--', '*.sh'],
                            capture_output=True, check=True).stdout
    return [os.fsdecode(p) for p in sortie.split(b'\0') if p]


def verifier(racine='.', ecrire=print):
    chemins = fichiers(racine)
    if len(chemins) < MINIMUM:
        ecrire(f"::error::{len(chemins)} script(s) lu(s) (minimum {MINIMUM}) — le motif git est cassé,"
               " un contrôle qui ne lit presque rien ne prouve rien")
        return 2
    etat = 0
    utilisees = set()
    for chemin in chemins:
        with open(os.path.join(racine, chemin), encoding='utf-8', errors='replace') as f:
            fautes = juger(chemin, f.read())
        if not fautes:
            continue
        if chemin in EXCEPTIONS:
            utilisees.add(chemin)
            continue
        for numero, forme, ligne in fautes:
            ecrire(f"::error file={chemin},line={numero}::horloge réelle contre une date posée (forme {forme}) : "
                   f"{ligne} — injecter la date (`${{AUJOURDHUI:-$(date +%F)}}`) et jouer un cas avant et un après")
        etat = 1
    for chemin in sorted(set(EXCEPTIONS) - utilisees):
        ecrire(f"::error file={chemin}::exception inutile ({EXCEPTIONS[chemin]}) — la retirer de EXCEPTIONS")
        etat = 1
    return etat


def _selftest():
    echecs = []

    def attendre(libelle, obtenu, voulu):
        if obtenu != voulu:
            echecs.append(f"{libelle} : obtenu {obtenu!r}, voulu {voulu!r}")

    #  Le témoin : la forme exacte du 26/10/2026.
    bombe = 'MAINT_TRANSITION_FIN=2026-10-25\n[ "$(date +%F)" \\< "$MAINT_TRANSITION_FIN" ] && echo ok\n'
    attendre('forme A : constante échue + horloge', [f[1] for f in juger('x.sh', bombe)], ['A'])
    attendre('forme A : constante entre guillemets', [f[1] for f in juger(
        'x.sh', 'export FIN="2026-10-25"\nnow=$EPOCHSECONDS\n')], ['A'])
    attendre('forme B : même ligne', [f[1] for f in juger(
        'x.sh', '[ "$(date +%s)" -gt "$(date -d 2026-10-25 +%s)" ] && [ "$(date +%F)" = 2026-10-25 ]\n')], ['B'])
    attendre('forme C : âge à la main (point 8)', [f[1] for f in juger(
        'x.sh', 'echo $(( ( $(date +%s) - $(date -d "$d" +%s) ) / 60 ))\n')], ['C'])
    attendre('forme C : âge à la main, échappé pour ssh (point 13)', [f[1] for f in juger(
        'x.sh', r'echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))' + '\n')], ['C'])
    attendre('forme C : le relevé à deux epoch est sain', juger(
        'x.sh', 'echo "$(date -d "$d" +%s) $(date +%s)"\n'), [])
    #  Ce qui est sain doit passer.
    attendre('injectable : sain', juger('x.sh', 'FIN=2026-10-25\nJOUR=${AUJOURDHUI:-$(date +%F)}\n'), [])
    attendre('conversion d\'une date posée : saine', juger(
        'x.sh', 'AGE=$(beat_age_min "2026-07-30 01:00:00" "$(date -d \'2026-07-30 01:30:00\' +%s)")\n'), [])
    attendre('constante sans horloge : saine', juger('x.sh', 'FIN=2026-10-25\necho "$FIN"\n'), [])
    attendre('horloge sans constante : saine', juger('x.sh', 'maintenant=$(date +%s)\n'), [])
    attendre('commentaire ignoré', juger('x.sh', '# FIN=2026-10-25 ; date +%F\nFIN=2026-10-25\n'), [])
    attendre('données datées dans un test : saines', juger(
        'x.sh', 't "ligne" "2026-10-02 09:05:01" "healthwatch_dernier=2026-10-02 09:05:01"\n'), [])

    #  De bout en bout : un dépôt jeté, le cas zéro, la bombe refusée, l'exception inutile.
    import tempfile
    with tempfile.TemporaryDirectory() as dossier:
        def git(*args):
            subprocess.run(['git', '-C', dossier, '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
                           check=True, capture_output=True)
        git('init', '-q')
        lignes = []
        attendre('cas zéro : presque rien lu → 2', verifier(dossier, lignes.append), 2)
        attendre('cas zéro : le dit', 'ne prouve rien' in '\n'.join(lignes), True)
        for n in range(MINIMUM):
            with open(os.path.join(dossier, f's{n}.sh'), 'w') as f:
                f.write('echo ok\n')
        git('add', '-A')
        lignes = []
        attendre('dépôt sain → 0', verifier(dossier, lignes.append), 0)
        with open(os.path.join(dossier, 'bombe.sh'), 'w') as f:
            f.write(bombe)
        git('add', '-A')
        lignes = []
        attendre('bombe → 1', verifier(dossier, lignes.append), 1)
        attendre('la bombe est nommée', 'bombe.sh,line=1' in '\n'.join(lignes), True)
        EXCEPTIONS['s0.sh'] = 'raison de test'
        lignes = []
        verifier(dossier, lignes.append)
        attendre('exception inutile refusée', 'exception inutile' in '\n'.join(lignes), True)
        del EXCEPTIONS['s0.sh']

    if echecs:
        print('FAIL horloge_autotests :', *echecs, sep='\n  ')
        return 1
    print('OK horloge_autotests — formes A, B et C, injection, conversion, cas zéro, exception inutile')
    return 0


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[1:] == ['--selftest']:
        return _selftest()
    return verifier()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
