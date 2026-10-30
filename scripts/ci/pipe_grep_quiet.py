#!/usr/bin/env python3
"""Aucun script shell ne décide sur `commande | grep -q …` (#2298).

Sous `set -o pipefail`, `producteur | grep -q motif` rend 141 (SIGPIPE) dès que grep
sort à la première correspondance AVANT que le producteur ait fini d'écrire : le
test dit « non » alors que le motif était là, et cela dépend de la charge — rouge
sur un passage, vert sur le suivant, sur le même arbre. Le 29/10/2026, le cas « le
cas CRLF contient bien un CR » de `precheck-mep.sh --selftest` est tombé ainsi sur la
PR #2297 et pas sur #2294. Le mécanisme se prouve (`--selftest`) avec un producteur
long ; l'échec de la CI, lui, n'a pas été reproduit sous Windows.

Forme refusée, dans les `*.sh` versionnés (commentaires exclus), y compris le tube
coupé en fin de ligne (`|` ou `| \\`, puis `grep -q` à la ligne suivante) :
    <producteur> | grep -q …    (aussi -qE, -qF, -qx, -Eq, --quiet)
Forme attendue : le producteur se lit d'abord, la décision se prend sans tube —
    _s=$(producteur)             grep -q motif <<<"$_s"
Un test sur une variable : `grep -q motif <<<"$x"` (jamais `printf … | grep -q`).

Deuxième forme refusée — celle que la correction de la première a elle-même introduite
(PR #2322 : `bibliotheques-pdf.sh` est mort sans un mot, `dpkg-query` rend 1 pour un
paquet absent) : sous `set -e`, `x=$(producteur)` suivi de `grep -q motif <<<"$x"` tue
le script quand le producteur sort non nul, alors que le tube d'avant ne regardait que
le statut de `grep`. Il faut `x=$(producteur || true)` : le verdict est celui du grep.
Un fichier sans `set -e`, une affectation par `local` (qui masque le code) ou déjà
protégée par `||` passent.

Hors périmètre, exprès : `| head -1` et `grep -m1`, dont la VALEUR est lue et non
le statut ; `| grep -c`, `| grep -o`, qui lisent tout.

Une exception se déclare dans `EXCEPTIONS` avec sa raison, et le contrôle échoue si
elle cesse de servir (`standards/05` §2) : elle est vide aujourd'hui.

Usage : pipe_grep_quiet.py
        pipe_grep_quiet.py --selftest
"""
import os
import re
import subprocess
import sys

#  « chemin » → raison. Vide : plus aucun script ne décide sur un tube vers `grep -q`.
EXCEPTIONS = {}

#  Un `|` simple (ni `||` ni `|&`), éventuellement suivi d'un retour à la ligne, puis
#  `grep` et, parmi ses options, un drapeau « silencieux » : -q, -qE, -Eq, --quiet…
TUBE_GREP_Q = re.compile(
    r'(?<!\|)\|(?![|&])[ \t]*\\?[ \t]*\n?[ \t]*grep[ \t]+'
    r'(?:[^\n|;&\'"]*?[ \t])?(?:-[A-Za-z]*q[A-Za-z]*|--quiet)'
    r'(?=[ \t\n\\;)&|]|\Z)'
)
#  Forme B : `NOM=$(commande)` seul sur sa ligne, puis un `grep` qui lit "$NOM" en
#  here-string à la ligne suivante (éventuellement niée par `!`).
AFFECTE_PUIS_GREP = re.compile(
    r'(?m)(?:^|;)[ \t]*(?P<nom>[A-Za-z_]\w*)=\$\((?P<cmd>[^\n]*)\)[ \t]*\n'
    r'[ \t]*(?:!\s+)?grep\b[^\n]*?<<<[ \t]*"?\$\{?(?P=nom)\b'
)
SOUS_SET_E = re.compile(r'(?m)^[ \t]*set[ \t]+-[A-Za-z]*e')
MINIMUM = 100  # moins de scripts lus : le motif git est cassé, pas « tout va bien »


def sans_commentaires(texte):
    """Les lignes `# …` blanchies, pour garder les numéros de ligne."""
    return '\n'.join('' if l.lstrip().startswith('#') else l for l in texte.split('\n'))


def juger(texte):
    """Les fautes d'un fichier : liste de (numéro de ligne, ligne, forme `A` ou `B`)."""
    texte = sans_commentaires(texte)
    lignes = texte.split('\n')
    fautes = []
    for m in TUBE_GREP_Q.finditer(texte):
        n = texte.count('\n', 0, m.start())
        fautes.append((n + 1, lignes[n].strip(), 'A'))
    if SOUS_SET_E.search(texte):
        for m in AFFECTE_PUIS_GREP.finditer(texte):
            if '||' in m.group('cmd'):
                continue
            n = texte.count('\n', 0, m.start('nom'))
            fautes.append((n + 1, lignes[n].strip(), 'B'))
    return sorted(fautes)


def fichiers(racine='.'):
    sortie = subprocess.run(['git', '-C', racine, 'ls-files', '-z', '--', '*.sh', '.githooks/*'],
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
        if not os.path.exists(os.path.join(racine, chemin)):
            continue  # supprimé dans l'arbre de travail, pas encore dans l'index
        with open(os.path.join(racine, chemin), encoding='utf-8', errors='replace') as f:
            fautes = juger(f.read())
        if not fautes:
            continue
        if chemin in EXCEPTIONS:
            utilisees.add(chemin)
            continue
        for numero, ligne, forme in fautes:
            if forme == 'A':
                ecrire(f"::error file={chemin},line={numero}::`| grep -q` : sous pipefail, grep qui sort tôt "
                       f"donne 141 au producteur et le test ment (#2298) : {ligne} — lire le producteur "
                       "(`_s=$(… || true)`), puis `grep -q motif <<<\"$_s\"`")
            else:
                ecrire(f"::error file={chemin},line={numero}::`x=$(producteur)` sans `|| true`, sous set -e : "
                       f"un producteur non nul (dpkg-query, grep, git…) tue le script avant le grep (#2298) : "
                       f"{ligne} — `x=$(producteur || true)`")
        etat = 1
    for chemin in sorted(set(EXCEPTIONS) - utilisees):
        ecrire(f"::error file={chemin}::exception inutile ({EXCEPTIONS[chemin]}) — la retirer de EXCEPTIONS")
        etat = 1
    return etat


def _bash(corps):
    """Le verdict (`oui`/`non`) d'un bout de shell joué sous pipefail."""
    sortie = subprocess.run(['bash', '-c', 'set -uo pipefail\n' + corps], capture_output=True, text=True)
    return sortie.stdout.strip()


def _selftest():
    echecs = []

    def attendre(libelle, obtenu, voulu):
        if obtenu != voulu:
            echecs.append(f"{libelle} : obtenu {obtenu!r}, voulu {voulu!r}")

    def lignes_fautives(texte):
        return [n for n, _, _ in juger(texte)]

    #  Le MÉCANISME, avec un producteur qui n'en finit pas : grep -q sort au premier
    #  « y », `yes` prend SIGPIPE, pipefail rend 141 — le test dit « non » à tort.
    avant = 'if yes | grep -q y; then echo oui; else echo non; fi'
    apres = '_s=$(yes | head -c 100000)\nif grep -q y <<<"$_s"; then echo oui; else echo non; fi'
    attendre('mécanisme : le tube ment sous pipefail', _bash(avant), 'non')
    attendre('mécanisme : sans tube, le test dit vrai', _bash(apres), 'oui')
    attendre('mécanisme : le contrôle refuse la forme fautive', lignes_fautives(avant + '\n'), [1])
    attendre('mécanisme : le contrôle laisse passer la forme saine', lignes_fautives(apres + '\n'), [])

    #  Les formes refusées.
    for libelle, texte in [
        ('printf | grep -q', "if printf '%s' \"$x\" | grep -q motif; then :; fi\n"),
        ('grep -qE', "od -c f | grep -qE '\\\\r' && echo oui\n"),
        ('grep -Eq (drapeaux inversés)', "cat f | grep -Eq 'a|b' && echo oui\n"),
        ('grep -qxF', "echo \"$l\" | grep -qxF -- \"$c\" || return\n"),
        ('--quiet', "cmd | grep --quiet motif\n"),
        ('autre drapeau avant -q', "cmd | grep -v -q motif\n"),
        ('tube en fin de ligne', "cmd |\n  grep -q motif\n"),
        ('tube + barre oblique inverse', "cmd | \\\n  grep -q motif\n"),
        ('deuxième étage d\'une chaîne', "a | grep -v x | grep -q y\n"),
    ]:
        attendre(f'refusé : {libelle}', len(lignes_fautives(texte)), 1)
    #  Les numéros de ligne désignent le tube.
    attendre('numéro de ligne', lignes_fautives('echo ok\ncmd | grep -q x\n'), [2])

    #  La forme B : l'affectation nue sous set -e (PR #2322, bibliotheques-pdf.sh).
    entete = 'set -euo pipefail\n'
    nue = entete + '_st=$(dpkg-query -W -f=x "$p" 2>/dev/null)\ngrep -q "ok" <<<"$_st" || manquants=1\n'
    attendre('forme B : affectation nue puis grep', [(n, f) for n, _, f in juger(nue)], [(2, 'B')])
    attendre('forme B : grep nié par !', [f for _, _, f in juger(
        entete + 'v=$(git log -1)\n! grep -q x <<<"$v"\n')], ['B'])
    attendre('forme B : numéro de ligne', [n for n, _, _ in juger(nue)], [2])
    for libelle, texte in [
        ('|| true derrière le producteur', entete + '_st=$(dpkg-query -W x || true)\ngrep -q ok <<<"$_st"\n'),
        ('un fichier sans set -e', '_st=$(dpkg-query -W x)\ngrep -q ok <<<"$_st"\n'),
        ('set -u seul', 'set -u\n_st=$(dpkg-query -W x)\ngrep -q ok <<<"$_st"\n'),
        ('local masque le code', entete + 'local _st=$(dpkg-query -W x)\ngrep -q ok <<<"$_st"\n'),
        ('le grep lit une autre variable', entete + '_st=$(dpkg-query -W x)\ngrep -q ok <<<"$autre"\n'),
        ('pas de grep derrière', entete + '_st=$(dpkg-query -W x)\necho "$_st"\n'),
        ('commentaire ignoré', entete + '# _st=$(dpkg-query -W x)\n# grep -q ok <<<"$_st"\n'),
    ]:
        attendre(f'sain (forme B) : {libelle}', juger(texte), [])

    #  Les formes saines.
    for libelle, texte in [
        ('here-string', 'grep -q motif <<<"$x"\n'),
        ('|| puis grep -q', '[ -z "$m" ] || grep -qF -- "$m" <<<"$out"\n'),
        ('&& puis grep -q', 'cmd && grep -q motif f\n'),
        ('grep -q sur un fichier', 'grep -q motif fichier.txt\n'),
        ('grep -c lit tout', 'cmd | grep -c motif\n'),
        ('grep -o lit tout', 'cmd | grep -o motif | head -1\n'),
        ('grep -v sans -q', 'cmd | grep -v motif\n'),
        ('|& n\'est pas un tube simple', 'cmd |& tee f\n'),
        ('commentaire ignoré', '# cmd | grep -q motif\n'),
        ('motif contenant « q »', 'cmd | grep -E "quoi"\n'),
        ('un nom de fichier -quiet.log', 'cmd | grep motif --exclude=-quiet.log\n'),
    ]:
        attendre(f'sain : {libelle}', lignes_fautives(texte), [])

    #  De bout en bout : un dépôt jeté, le cas zéro, la faute refusée, l'exception inutile.
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
        with open(os.path.join(dossier, 'fautif.sh'), 'w') as f:
            f.write('echo ok\ncmd | grep -q motif\n')
        git('add', '-A')
        lignes = []
        attendre('faute → 1', verifier(dossier, lignes.append), 1)
        attendre('la faute est nommée', 'fautif.sh,line=2' in '\n'.join(lignes), True)
        EXCEPTIONS['fautif.sh'] = 'raison de test'
        lignes = []
        attendre('exception déclarée → 0', verifier(dossier, lignes.append), 0)
        EXCEPTIONS['s0.sh'] = 'raison de test'
        lignes = []
        attendre('exception inutile → 1', verifier(dossier, lignes.append), 1)
        attendre('exception inutile nommée', 'exception inutile' in '\n'.join(lignes), True)
        del EXCEPTIONS['s0.sh'], EXCEPTIONS['fautif.sh']

    if echecs:
        print('FAIL pipe_grep_quiet :', *echecs, sep='\n  ')
        return 1
    print('OK pipe_grep_quiet — mécanisme SIGPIPE, formes refusées et saines, cas zéro, exception inutile')
    return 0


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[1:] == ['--selftest']:
        return _selftest()
    return verifier()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
