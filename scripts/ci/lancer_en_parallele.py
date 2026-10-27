#!/usr/bin/env python3
"""Lance en parallèle une liste de commandes indépendantes, lue sur l'entrée (#2231).

Les ~80 self-tests du job `test-scripts` sont des fonctions de décision PURES
(aucun SSH, docker ni écriture hors de leur dossier jetable) : rien ne les lie
entre eux, et les jouer l'un après l'autre coûtait 135 à 250 s sur le poste — plus
de 900 s côte à côte avec pytest. Ce lanceur garde la LISTE telle qu'elle est écrite
dans `ci.yml` (une commande par ligne, les commentaires `#` ignorés : c'est elle que
lit `verifier-selftests-branches.sh`) et la joue sur plusieurs processus.

Ce qu'il garantit, parce qu'un lanceur parallèle peut mentir en silence :
  - TOUTES les commandes sont jouées, un échec n'arrête pas les autres : le bilan
    nomme chaque commande fautive, avec sa sortie complète ;
  - une liste vide échoue (code 2) — « rien à lancer » n'est pas « tout va bien » ;
  - le code de sortie est 1 dès qu'une commande a échoué, 0 sinon.

Usage : lancer_en_parallele.py [--travailleurs N] < liste
        lancer_en_parallele.py --selftest
Le nombre de travailleurs vient de `--travailleurs`, sinon de `LANCER_TRAVAILLEURS`,
sinon des cœurs (au plus 6 : le poste y partage ses cœurs avec d'autres jobs).
"""
import concurrent.futures
import os
import subprocess
import sys
import time

PLAFOND_PAR_DEFAUT = 6


def lire_commandes(lignes):
    """Les commandes d'une liste : une par ligne, sans les lignes vides ni les commentaires."""
    commandes = []
    for ligne in lignes:
        ligne = ligne.strip()
        if ligne and not ligne.startswith('#'):
            commandes.append(ligne)
    return commandes


def nombre_de_travailleurs(demande=None, environnement=None):
    environnement = os.environ if environnement is None else environnement
    for source in (demande, environnement.get('LANCER_TRAVAILLEURS')):
        if source:
            return max(1, int(source))
    return max(1, min(os.cpu_count() or 1, PLAFOND_PAR_DEFAUT))


def jouer(commande):
    """(commande, code, sortie, durée) — la sortie est gardée, jamais affichée en vrac."""
    debut = time.monotonic()
    fini = subprocess.run(['bash', '-c', commande], stdin=subprocess.DEVNULL, capture_output=True)
    sortie = (fini.stdout + fini.stderr).decode('utf-8', errors='replace')
    return commande, fini.returncode, sortie, time.monotonic() - debut


def lancer(commandes, travailleurs, ecrire=print):
    if not commandes:
        ecrire("::error::aucune commande à lancer — une liste vide ne prouve rien")
        return 2
    debut = time.monotonic()
    echecs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=travailleurs) as pool:
        for commande, code, sortie, duree in pool.map(jouer, commandes):
            if code:
                echecs.append(commande)
                ecrire(f"::error::échec (code {code}) : {commande}")
                ecrire(sortie.rstrip())
            else:
                ecrire(f"OK {duree:5.1f} s  {commande}")
    total = time.monotonic() - debut
    ecrire(f"{len(commandes) - len(echecs)}/{len(commandes)} commande(s) réussie(s) "
           f"en {total:.0f} s sur {travailleurs} travailleur(s)")
    return 1 if echecs else 0


def _selftest():
    echecs = []

    def attendre(libelle, obtenu, voulu):
        if obtenu != voulu:
            echecs.append(f"{libelle} : obtenu {obtenu!r}, voulu {voulu!r}")

    attendre('lecture : commentaires et vides ignorés',
             lire_commandes(['# un', '', '  true  ', '   # deux', 'false']), ['true', 'false'])
    attendre('travailleurs : demande prioritaire', nombre_de_travailleurs('3', {'LANCER_TRAVAILLEURS': '5'}), 3)
    attendre('travailleurs : environnement', nombre_de_travailleurs(None, {'LANCER_TRAVAILLEURS': '5'}), 5)
    attendre('travailleurs : jamais moins de 1', nombre_de_travailleurs('0', {}), 1)
    attendre('travailleurs : par défaut, borné', 1 <= nombre_de_travailleurs(None, {}) <= PLAFOND_PAR_DEFAUT, True)

    lignes = []
    attendre('tout réussit → 0', lancer(['true', 'echo bonjour'], 2, lignes.append), 0)
    #  Le témoin : un échec au MILIEU n'arrête pas les suivantes, et il est nommé.
    lignes = []
    code = lancer(['true', 'echo cause-visible; exit 3', 'echo apres'], 2, lignes.append)
    texte = '\n'.join(lignes)
    attendre('un échec → 1', code, 1)
    attendre('l\'échec est nommé', 'exit 3' in texte, True)
    attendre('sa sortie est donnée', 'cause-visible' in texte, True)
    attendre('la suivante est jouée', 'OK' in texte and 'echo apres' in texte, True)
    #  Le cas zéro.
    lignes = []
    attendre('liste vide → 2', lancer([], 2, lignes.append), 2)
    attendre('liste vide : dit pourquoi', 'ne prouve rien' in '\n'.join(lignes), True)

    if echecs:
        print('FAIL lancer_en_parallele :', *echecs, sep='\n  ')
        return 1
    print('OK lancer_en_parallele — succès, échec nommé, suite jouée, liste vide')
    return 0


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[1:] == ['--selftest']:
        return _selftest()
    travailleurs = None
    if argv[1:2] == ['--travailleurs'] and len(argv) > 2:
        travailleurs = argv[2]
    elif len(argv) > 1:
        print(__doc__)
        return 64
    return lancer(lire_commandes(sys.stdin), nombre_de_travailleurs(travailleurs))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
