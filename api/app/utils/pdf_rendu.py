"""Le rendu WeasyPrint, **hors du process de l'API**.

## Ce que ce module fait, et ce qu'il ne fait PAS

Il isole le rendu des documents imprimables dans un process jetable. Il achète
deux choses, mesurées sur le RPi le 16/09/2026 avec un vrai uvicorn mono-worker
servant le manuel complet (14 pages, ~20 s de rendu) pendant qu'un client
sondait `/health` :

| | `/health` au repos | `/health` pendant le rendu | durée du rendu |
|---|---|---|---|
| rendu **dans** le process | 0,6 ms | médiane 1,5 ms, **max 122 ms** | 20,4 s |
| rendu **hors** process | 0,6 ms | médiane 1,2 ms, **max 3,3 ms** | 22,5 s |

1. **une pointe de latence divisée par 37** sur les requêtes concurrentes ;
2. surtout, **l'isolation des pannes** : un WeasyPrint qui plante, boucle ou
   épuise la mémoire du RPi ne peut plus emporter l'API avec lui. C'est la
   raison principale de ce module.

🔴 **Ce qu'il ne corrige PAS, et il faut le dire ici parce que l'inverse a été
écrit et cru pendant une demi-journée** : il n'empêche aucun « figeage » du
site, parce qu'il n'y en avait pas. Le 16/09/2026 au matin, un
`GET /manuel/pdf` a mis 21 s et les logs de l'API ne montraient aucune autre
requête servie pendant ce temps — on en a conclu que le site était bloqué. La
mesure ci-dessus a infirmé cette lecture : hors démonstration ce site voit une
dizaine de requêtes par minute, et l'absence de requêtes ne dit rien de la
capacité à en servir. C'était un raisonnement sur un silence
(`standards/04-fiabilite-des-controles.md` §2, le cas zéro).

⚠️ **Le coût est réel : +1,5 à 2 s par document.** Il se paie sur chaque PDF, y
compris la fiche arrivant et l'annonce de hall qui se rendaient en moins d'une
seconde. C'est le prix de l'isolation, accepté en connaissance de cause.

## 🔴 SPAWN, JAMAIS FORK — et c'est la règle d'or anti-corruption

Le défaut de Python 3.12 sous Linux est `fork` (vérifié sur l'image :
`mp.get_start_method()` → `fork`). Un enfant **forké** hérite des descripteurs
de fichier ouverts du parent, **y compris ceux de `app.db`** tenus par le pool
SQLAlchemy. Quand il se termine, SQLite peut s'y croire dernière connexion et
supprimer `app.db-wal` sous l'API vivante : l'incident du 17/07/2026, ~12 h
d'écritures perdues, mais déclenché depuis l'intérieur.

`spawn` démarre un interpréteur neuf qui ne partage **aucun** descripteur. Le
prix est un import à payer (`import weasyprint` : 0,59 s mesuré sur le RPi).

C'est vérifié par le **comportement**, pas par la forme du code :
`test_pdf_hors_process.py` importe `app.database` dans le parent puis exige que
l'enfant ne l'ait pas — ce qu'un `fork` ne pourrait pas satisfaire.

⚠️ Corollaire de `spawn` : le module principal de l'appelant est réimporté dans
l'enfant. Il doit donc porter un garde `if __name__ == "__main__"`, sans quoi il
se rejoue en entier. Le point d'entrée de production l'a (`/usr/local/bin/uvicorn`,
vérifié), et pytest aussi ; un script maison, non — c'est ce qui est arrivé à la
première vérification de ce module, d'où la mention dans le message d'erreur.

## Pourquoi un process jetable et non un worker résident

Un worker persistant économiserait 0,59 s par document. Il coûterait en échange
une mémoire résidente permanente sur un RPi, un recyclage à écrire (WeasyPrint
fuit), une fermeture à câbler au `lifespan`, et un plantage qui empoisonne
l'appel suivant. Les PDF de ce site se comptent par jour, pas par seconde.

## Le journal de l'enfant remonte au parent — ce n'est pas un détail

Les lignes `weasyprint` et `fontTools` sont émises **dans l'enfant**, où rien
n'est configuré : elles seraient perdues. Or elles servent deux fois :

1. **en production** — ce sont elles qui ont permis de dater le rendu de 21 s à
   la seconde près ;
2. **en test** — `test_documents_pdf.py::test_la_fiche_avec_ses_icones…` lit
   `caplog` pour vérifier que WeasyPrint ne se plaint pas du document. Un
   `caplog` devenu vide l'aurait rendu **toujours vert** : le contrôle serait
   mort sans que rien ne le dise (`standards/04` §14).

L'enfant les collecte donc et les renvoie ; le parent les **rejoue** dans les
loggers de même nom, où ses propres niveaux et handlers s'appliquent comme
avant. Seule différence observable : elles arrivent groupées à la fin du rendu
plutôt qu'au fil de l'eau.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys

logger = logging.getLogger("hostachy.pdf")

#: Au-delà, le rendu est considéré perdu et le process abattu. Large à dessein :
#: le manuel complet demande ~21 s sur un RPi, et un document plus lourd doit
#: pouvoir sortir. Ce délai ne protège pas le site (l'isolation s'en charge) —
#: il protège seulement d'une requête HTTP qui ne se terminerait jamais.
DELAI_RENDU_S = 180.0

#: Borne du journal remonté. Un rendu normal en produit quelques centaines (une
#: ligne `fontTools` par table de police) ; la borne existe pour qu'un document
#: pathologique ne fasse pas transiter des mégaoctets de texte.
MAX_JOURNAL = 5_000


#: Les seuls protocoles que le moteur a le droit d'ouvrir pendant un rendu (#1908).
#:
#: 🔴 Le défaut de WeasyPrint est d'ouvrir TOUT ce que le document désigne —
#: `http(s)`, `ftp`, `file` — depuis le serveur. Une image `http://…` glissée
#: dans un contenu rendu (le texte d'une annonce de hall, une page du manuel)
#: aurait fait sortir une requête de l'API : SSRF vers le réseau local des RPi,
#: ou lecture d'un fichier du conteneur par `file://`. Les documents de ce site
#: sont AUTONOMES (images en data-URI, CSS dans `<style>`) : le data-URI est donc
#: le seul protocole utile, et tout le reste se refuse. WeasyPrint journalise
#: alors un avertissement et rend le document sans la ressource.
#: 🔒 `test_pdf_hors_reseau.py` le vérifie par le comportement : un serveur
#: local témoin ne doit recevoir aucune requête.
PROTOCOLES_ADMIS = frozenset({"data"})

#: Ce que le dernier enfant a rapporté de lui-même : `{"pid", "base_chargee"}`.
#: Renseigné à chaque rendu, y compris quand il échoue — c'est le point de
#: mesure de `test_pdf_hors_process.py`, et il ne dépend d'aucune configuration
#: de logging.
dernier_temoin: dict | None = None

#: Le journal brut rapporté par le dernier enfant, avant rejeu. Sert au
#: diagnostic : un journal plein avec un `caplog` vide désigne le parent, un
#: journal vide désigne l'enfant. La distinction a coûté deux passages de CI.
dernier_journal: list[tuple[str, int, str]] = []


class RenduPdfImpossible(RuntimeError):
    """Le PDF n'a pas pu être produit — on ne rend jamais un document partiel."""


def _rendre_dans_l_enfant(tube, html: str) -> None:
    """Rend le PDF et le renvoie par le tube. **Exécuté dans le process enfant.**

    Rien ici ne doit toucher la base : ce module n'importe volontairement que la
    bibliothèque standard et WeasyPrint, et `test_pdf_hors_process.py` vérifie
    qu'il en reste ainsi.
    """
    journal: list[tuple[str, int, str]] = []

    class _Collecteur(logging.Handler):
        def emit(self, enregistrement: logging.LogRecord) -> None:
            if len(journal) < MAX_JOURNAL:
                journal.append(
                    (
                        enregistrement.name,
                        enregistrement.levelno,
                        enregistrement.getMessage(),
                    )
                )

    #  L'enfant ne sait pas de quoi il hérite : avec `spawn` il réimporte le
    #  module principal de l'appelant (pytest, uvicorn…), qui a pu désactiver le
    #  logging globalement ou relever des niveaux. On repart donc d'un état
    #  connu, sans quoi la collecte rend un journal vide sans rien dire.
    logging.disable(logging.NOTSET)
    racine = logging.getLogger()
    racine.setLevel(logging.INFO)
    racine.addHandler(_Collecteur())
    for nom in ("weasyprint", "fontTools"):
        interesse = logging.getLogger(nom)
        interesse.setLevel(logging.NOTSET)  # hérite du racine
        interesse.propagate = True

    #  🔴 Le témoin voyage DANS le message, pas par le journal.
    #
    #  Il a d'abord été une ligne de log, et c'était fragile : sa remontée
    #  dépendait alors de la configuration du logging des DEUX process. Le
    #  contrôle est passé au vert sur le poste (WeasyPrint absent, l'enfant
    #  échouant à l'import) et au rouge en intégration continue, où le rendu
    #  aboutit — une propriété critique ne doit pas dépendre d'un canal qui
    #  varie selon ce qui a été importé.
    temoin = {"pid": os.getpid(), "base_chargee": "app.database" in sys.modules}
    logger.info(
        "Rendu PDF dans le process %d (base chargée : %s)",
        temoin["pid"],
        temoin["base_chargee"],
    )

    try:
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher

        recuperateur = URLFetcher(allowed_protocols=PROTOCOLES_ADMIS)
        pdf = HTML(string=html, url_fetcher=recuperateur).write_pdf()
    except BaseException as exc:  # noqa: BLE001 — tout est remonté au parent
        tube.send(("erreur", f"{type(exc).__name__}: {exc}", journal, temoin))
    else:
        tube.send(("ok", pdf, journal, temoin))
    finally:
        tube.close()


def _rejouer(journal: list[tuple[str, int, str]]) -> None:
    """Réémet dans ce process les lignes produites par l'enfant.

    🔴 **Un logger `disabled` avale tout, en silence — et ce process en a.**
    `fileConfig()` vaut `disable_existing_loggers=True` par défaut : à la
    seconde où Alembic joue une migration, **tous** les loggers déjà créés
    passent à `disabled = True` pour le reste de la vie du process. Les lignes
    que l'enfant a bel et bien collectées disparaîtraient alors ici sans un mot,
    et `test_documents_pdf.py` conclurait « WeasyPrint ne s'est pas plaint » sur
    un `caplog` vide — le faux vert exact que ce transfert existe pour empêcher.

    Le dépôt avait déjà payé ce prix : la fixture `journal` de
    `tests/aides_courriel.py` le décrit, et deux garde-fous y rendaient un verdict dépendant de l'ordre des
    tests. Ne pas relire ce qu'un voisin a appris, c'est refaire son défaut.

    On lève donc l'extinction le temps d'émettre, puis on la restaure : l'état du
    process n'est pas le nôtre à changer, mais une ligne produite ailleurs n'a
    pas à mourir d'une configuration posée ici.
    """
    for nom, niveau, message in journal:
        journaliseur = logging.getLogger(nom)
        eteint = journaliseur.disabled
        journaliseur.disabled = False
        try:
            journaliseur.log(niveau, message)
        finally:
            journaliseur.disabled = eteint


def rendre_pdf(html: str, *, delai_s: float = DELAI_RENDU_S) -> bytes:
    """Rend un document HTML autonome en PDF, dans un process séparé.

    Le HTML doit être **autonome** : CSS dans un `<style>`, images en data-URI.
    Aucune requête réseau n'est effectuée au rendu : toute ressource qui n'est
    pas un data-URI est refusée (`PROTOCOLES_ADMIS`).

    Lève `RenduPdfImpossible` si le rendu échoue, dépasse `delai_s`, ou si le
    process meurt en route (OOM — le risque est réel sur un RPi).

    `dernier_temoin` retient ce que l'enfant a rapporté de lui-même (son pid, et
    s'il avait la base en mémoire) : c'est ce que lisent les contrôles.
    """
    contexte = multiprocessing.get_context("spawn")
    lecture, ecriture = contexte.Pipe(duplex=False)
    enfant = contexte.Process(
        target=_rendre_dans_l_enfant,
        args=(ecriture, html),
        name="rendu-pdf",
        daemon=True,
    )
    enfant.start()
    #  ⚠️ Fermer NOTRE copie de l'extrémité d'écriture, sinon le tube n'atteint
    #  jamais EOF quand l'enfant meurt : `poll()` attendrait le délai complet au
    #  lieu de signaler la mort immédiatement.
    ecriture.close()

    try:
        if not lecture.poll(delai_s):
            raise RenduPdfImpossible(
                f"rendu abandonné après {delai_s:.0f} s — document trop lourd ou moteur bloqué"
            )
        try:
            message = lecture.recv()
        except EOFError as exc:
            #  ⚠️ Deux causes très différentes, et les nommer toutes les deux
            #  évite l'heure perdue au mauvais endroit : la première est
            #  plausible en production sur un RPi, la seconde apparaît dès qu'on
            #  appelle ce module depuis un script sans garde `if __name__ ==
            #  "__main__"` — `spawn` réimporte le module principal, qui se
            #  rejoue alors en entier dans l'enfant. Vu dès la première
            #  vérification du correctif (16/09/2026).
            raise RenduPdfImpossible(
                f"le process de rendu est mort sans rien produire (code de "
                f"sortie {enfant.exitcode}) — mémoire insuffisante, ou module "
                f'principal sans garde `if __name__ == "__main__"` '
                f"(voir la trace du process enfant ci-dessus)"
            ) from exc
    finally:
        lecture.close()
        enfant.join(5)
        if enfant.is_alive():
            enfant.terminate()
            enfant.join(5)
        if enfant.is_alive():
            enfant.kill()
            enfant.join()

    etat, charge, journal, temoin = message
    global dernier_temoin, dernier_journal
    dernier_temoin = temoin
    dernier_journal = journal
    _rejouer(journal)
    if etat == "erreur":
        raise RenduPdfImpossible(charge)
    return charge
