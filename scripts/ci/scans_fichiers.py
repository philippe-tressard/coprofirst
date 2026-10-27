#!/usr/bin/env python3
"""Scans d'octets des fichiers versionnés — UN processus pour tous (#2231).

Trois contrôles du job `test-scripts` lisaient chaque fichier dans une boucle
shell (`head -c3 "$f" | grep …`, `tr … | tr … | wc`) : deux à quatre processus par
fichier, plusieurs milliers de fichiers. Sous Cygwin la création de processus se
sérialise, et côte à côte (#2224) les trois étapes sont devenues le chemin
critique du rejeu : 116 s, 200 s et 246 s en série, 470 à 920 s côte à côte.

Ce script les remplace par une lecture unique, avec les MÊMES règles et les mêmes
messages `::error file=…` :

  bom GLOB…        un fichier qui commence par EF BB BF
  crlf GLOB…       un fichier dont une ligne finit par un retour chariot
  controle GLOB…   un fichier qui contient un caractère de contrôle autre que la
                   tabulation, le saut de ligne et le retour chariot (U+0000 à
                   U+001F, et U+007F) — le NUL compris, que `grep` classe binaire
                   et ne voit pas

Les motifs sont ceux de `git ls-files -- GLOB…` (pathspec git, `*` traverse les
dossiers). Un scan qui ne couvre AUCUN fichier échoue : « rien trouvé » parce que
rien n'a été lu n'est pas un vert (`standards/04` §2).

Usage : scans_fichiers.py bom|crlf|controle GLOB…
        scans_fichiers.py --selftest
"""
import os
import subprocess
import sys
import tempfile

BOM = b'\xef\xbb\xbf'

#  Tout ce que `[:cntrl:]` reconnaît en locale C, moins les trois écrits exprès.
_CONTROLE = bytes(c for c in list(range(0, 32)) + [127] if c not in (9, 10, 13))

MESSAGES = {
    'bom': "BOM UTF-8 en tête — {consigne}",
    'crlf': "fins de ligne CRLF — attendu LF (.editorconfig)",
    'controle': ("{n} caractère(s) de contrôle invisible(s) (U+0008, U+0000 et voisins)"
                 " — ils changent un motif sans se voir"),
}
#  La consigne du BOM change avec la portée : un shebang n'est pas un fichier de configuration.
CONSIGNE_BOM = {
    'shell': "le shebang devient inexécutable",
    'autre': "écrire ce fichier sans BOM (Set-Content -Encoding utf8 en pose un)",
}


def verdict(mode, donnees, consigne_bom='autre'):
    """Le message d'erreur d'un fichier (octets) pour ce mode, ou None s'il est sain."""
    if mode == 'bom':
        if donnees.startswith(BOM):
            return MESSAGES['bom'].format(consigne=CONSIGNE_BOM[consigne_bom])
    elif mode == 'crlf':
        #  `grep -U $'\r$'` : un \r juste avant une fin de ligne, ou en fin de fichier.
        if b'\r\n' in donnees or donnees.endswith(b'\r'):
            return MESSAGES['crlf']
    elif mode == 'controle':
        gardes = donnees.translate(None, b'\n\r\t')
        n = len(gardes) - len(gardes.translate(None, _CONTROLE))
        if n:
            return MESSAGES['controle'].format(n=n)
    return None


def fichiers_versionnes(globs, racine='.'):
    sortie = subprocess.run(['git', '-C', racine, 'ls-files', '-z', '--', *globs],
                            capture_output=True, check=True).stdout
    return [os.fsdecode(p) for p in sortie.split(b'\0') if p]


def scanner(mode, globs, racine='.', ecrire=print):
    """Code de sortie : 0 sain, 1 fichier fautif, 2 scan qui n'a rien couvert."""
    chemins = fichiers_versionnes(globs, racine)
    if not chemins:
        ecrire(f"::error::scan {mode} : aucun fichier ne correspond à {' '.join(globs)}"
               " — un scan qui ne lit rien ne prouve rien")
        return 2
    #  Un script shell ou un hook : le BOM casse le shebang. Les autres : la configuration.
    consigne = 'shell' if all(g.endswith('.sh') or g.startswith('.githooks') for g in globs) else 'autre'
    etat = 0
    for chemin in chemins:
        try:
            with open(os.path.join(racine, chemin), 'rb') as f:
                donnees = f.read()
        except OSError:
            continue  # un lien cassé ou un sous-module : git le liste, il n'y a rien à lire
        message = verdict(mode, donnees, consigne)
        if message:
            ecrire(f"::error file={chemin}::{message}")
            etat = 1
    return etat


def _selftest():
    """Les trois règles sur des fichiers piégés (témoins), et le cas zéro."""
    echecs = []

    def attendre(libelle, obtenu, voulu):
        if obtenu != voulu:
            echecs.append(f"{libelle} : obtenu {obtenu!r}, voulu {voulu!r}")

    #  Règles pures : chaque mode refuse son témoin et laisse passer le fichier sain.
    attendre('bom présent', verdict('bom', BOM + b'x = 1\n') is not None, True)
    attendre('bom absent', verdict('bom', b'x = 1\n'), None)
    attendre('bom au milieu', verdict('bom', b'x' + BOM), None)
    attendre('bom shell : consigne', 'shebang' in verdict('bom', BOM, 'shell'), True)
    attendre('bom autre : consigne', 'Set-Content' in verdict('bom', BOM, 'autre'), True)
    attendre('crlf présent', verdict('crlf', b'a\r\nb\n') is not None, True)
    attendre('crlf en fin de fichier', verdict('crlf', b'a\n\r') is not None, True)
    attendre('crlf absent', verdict('crlf', b'a\nb\n'), None)
    attendre('contrôle : recul', verdict('controle', b'a\x08b') is not None, True)
    attendre('contrôle : NUL', verdict('controle', b'a\x00b\n') is not None, True)
    attendre('contrôle : DEL', verdict('controle', b'a\x7fb\n') is not None, True)
    attendre('contrôle : compte', '3 caractère' in (verdict('controle', b'\x01\x02\x08') or ''), True)
    attendre('contrôle : tab, LF, CR tolérés', verdict('controle', b'a\tb\r\nc\n'), None)
    attendre('contrôle : accents tolérés', verdict('controle', 'é — ✓\n'.encode()), None)

    #  De bout en bout, sur un vrai dépôt jetable : le cas zéro et chaque témoin.
    with tempfile.TemporaryDirectory() as dossier:
        def git(*args):
            subprocess.run(['git', '-C', dossier, '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
                           check=True, capture_output=True)

        git('init', '-q')
        for nom, contenu in {'sain.py': b'x = 1\n', 'bom.py': BOM + b'x = 1\n',
                             'crlf.sh': b'#!/bin/bash\r\necho\r\n', 'recul.py': b'a\x08b\n',
                             'zero.py': b'a\x00b\n', 'dossier/profond.py': BOM + b'y\n'}.items():
            chemin = os.path.join(dossier, nom)
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with open(chemin, 'wb') as f:
                f.write(contenu)
        git('add', '-A')

        def jouer(mode, *globs):
            lignes = []
            code = scanner(mode, list(globs), dossier, lignes.append)
            return code, '\n'.join(lignes)

        code, texte = jouer('bom', '*.py')
        attendre('bom : code', code, 1)
        attendre('bom : nomme le fichier', '::error file=bom.py::' in texte, True)
        attendre('bom : traverse les dossiers', 'dossier/profond.py' in texte, True)
        attendre('bom : épargne le sain', 'sain.py' in texte, False)
        code, texte = jouer('crlf', '*.sh')
        attendre('crlf : code', (code, 'crlf.sh' in texte), (1, True))
        code, texte = jouer('controle', '*.py')
        attendre('contrôle : recul et NUL nommés', ('recul.py' in texte, 'zero.py' in texte), (True, True))
        attendre('contrôle : épargne le sain', 'sain.py' in texte, False)
        #  Le cas zéro : un motif qui ne couvre rien n'est jamais un vert.
        code, texte = jouer('bom', '*.inexistant')
        attendre('cas zéro : code', code, 2)
        attendre('cas zéro : dit pourquoi', 'ne lit rien' in texte, True)
        #  Le témoin sain : sans fichier fautif, le code est 0.
        git('rm', '-q', '-f', 'bom.py', 'dossier/profond.py')
        code, _ = jouer('bom', '*.py')
        attendre('bom : tout sain → 0', code, 0)

    if echecs:
        print('FAIL scans_fichiers :', *echecs, sep='\n  ')
        return 1
    print('OK scans_fichiers — bom, crlf, contrôle, cas zéro')
    return 0


def main(argv):
    #  La console du poste est en cp1252 : les messages portent des accents et des tirets.
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[1:] == ['--selftest']:
        return _selftest()
    if len(argv) < 3 or argv[1] not in MESSAGES:
        print(__doc__)
        return 64
    return scanner(argv[1], argv[2:])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
