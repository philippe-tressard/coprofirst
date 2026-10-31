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

## 🔴 SPAWN, JAMAIS FORK

La mécanique — enfant `spawn`, délai borné, mort détectée — vit dans
`utils/process_isole` depuis #2396, qui l'a reprise d'ici pour les images reçues :
la raison de `spawn` (les connexions du pool SQLAlchemy) y est écrite. Le prix
propre à ce module est l'import du moteur dans l'enfant (`import weasyprint` :
0,59 s mesuré sur le RPi).

C'est vérifié par le **comportement**, pas par la forme du code :
`test_pdf_hors_process.py` importe `app.database` dans le parent puis exige que
l'enfant ne l'ait pas — ce qu'un `fork` ne pourrait pas satisfaire.

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
import os

from app.utils.process_isole import EchecIsole, executer_isole

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


def _rendre_dans_l_enfant(html: str) -> tuple[str, object, list[tuple[str, int, str]]]:
    """Rend le PDF : `(état, PDF ou message, journal)`. **Exécuté dans le process enfant.**

    Elle attrape ses propres erreurs, parce que le journal doit remonter AUSSI
    quand le rendu échoue : c'est lui qui dit pourquoi.

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

    logger.info("Rendu PDF dans le process %d", os.getpid())

    try:
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher

        recuperateur = URLFetcher(allowed_protocols=PROTOCOLES_ADMIS)
        pdf = HTML(string=html, url_fetcher=recuperateur).write_pdf()
    except BaseException as exc:  # noqa: BLE001 — tout est remonté au parent
        return "erreur", f"{type(exc).__name__}: {exc}", journal
    return "ok", pdf, journal


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
    try:
        (etat, charge, journal), temoin = executer_isole(
            __name__, "_rendre_dans_l_enfant", html, delai_s=delai_s, nom="rendu-pdf"
        )
    except EchecIsole as exc:
        raise RenduPdfImpossible(f"rendu PDF : {exc}") from exc
    global dernier_temoin, dernier_journal
    dernier_temoin = temoin
    dernier_journal = journal
    _rejouer(journal)
    if etat == "erreur":
        raise RenduPdfImpossible(charge)
    return charge
