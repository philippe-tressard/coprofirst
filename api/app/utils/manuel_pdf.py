"""Le manuel utilisateur en PDF — page de garde, sommaire, mentions.

## 🔴 UNE SEULE SOURCE, ET C'EST LE POINT QUI COMPTE

Le PDF n'est **pas une seconde rédaction** du manuel : il en est une mise en
page. Le contenu est lu tel qu'il est servi aux résidents —
`http://front:3000/manuel-utilisateur.html`, le conteneur voisin — puis
transformé.

Écrire un second document aurait été plus simple à court terme et faux à moyen
terme : ce dépôt a déjà payé quatre fois la divergence de deux textes qui
décrivent la même chose (périmètres, canaux de notification, table des pages,
chiffres du manuel). Un PDF re-rédigé aurait divergé au premier écran modifié,
sans que rien ne le signale — et c'est le PDF, imprimé et distribué, qu'on aurait
lu le plus longtemps après sa péremption.

⚠️ **Cette lecture est une requête réseau, et c'est assumé.** La règle du dépôt —
« aucune requête au rendu » — vise les RESSOURCES (images, polices, CSS), qui
doivent être embarquées en data-URI parce qu'elles sont chargées hors requête
HTTP. Ici on récupère la SOURCE, une fois, avant de composer. Si le front est
indisponible, la génération échoue franchement : mieux vaut pas de PDF qu'un PDF
d'un manuel qu'on n'a pas pu lire.

## Ce que la mise en page ajoute

| | |
|---|---|
| **page de garde** | logo, titre, le QR code du site, la date d'édition |
| **sommaire** | construit depuis les `<h2>` réellement présents — jamais une liste tenue à la main |
| **mentions** | éditeur, version du manuel, avertissement de péremption |

Le sommaire mérite un mot : le construire **depuis le document** est ce qui
l'empêche de mentir. Une table des matières recopiée est une table de plus, et ce
manuel vient précisément de perdre toutes ses tables recopiées (#651).
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("hostachy.manuel")

import re
import threading
import urllib.request
from datetime import date
from app.utils import horloge
from html import escape, unescape
from pathlib import Path

from sqlmodel import Session

from app import contexte
from app.utils import manuel_pdf_cache
from app.utils.config_site import config_site
from app.utils.liens import adresse_du_site, nom_site
from app.utils.logo import logo_televerse_png
from app.utils.manuel_pdf_css import css_du_pdf
from app.utils.manuel_pdf_pages import garde, mentions
from app.utils.pdf_theme import html_to_pdf

#: Le manuel, tel qu'il est SERVI. Nom de service Docker : les deux conteneurs
#: partagent le réseau `hostachy`.
URL_MANUEL_INTERNE = "http://front:3000/manuel-utilisateur.html"

#: Ce qu'on garde du manuel : son corps, sans la barre latérale ni le script de
#: navigation, qui n'ont aucun sens sur un feuillet imprimé.
_MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
_TITRES = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.S | re.I)
_BALISES = re.compile(r"<[^>]+>")
_ID = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.I)
_VERSION = re.compile(r"Manuel utilisateur (v[\d.]+)")


class ManuelIndisponible(RuntimeError):
    """Le manuel n'a pas pu être lu — on ne compose pas un PDF sur du vide."""


def lire_manuel(url: str = URL_MANUEL_INTERNE, timeout: float = 5.0) -> str:
    """Le manuel tel qu'il est servi aux résidents.

    Lève `ManuelIndisponible` plutôt que de rendre une chaîne vide : un PDF d'un
    manuel qu'on n'a pas pu lire serait une couverture et rien d'autre, et
    personne ne s'en apercevrait avant de l'ouvrir.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as reponse:  # noqa: S310
            if reponse.status != 200:
                raise ManuelIndisponible(f"HTTP {reponse.status} sur {url}")
            brut = reponse.read()
    except ManuelIndisponible:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ManuelIndisponible(f"manuel illisible ({url}) : {exc}") from exc

    texte = brut.decode("utf-8", "replace")
    if "ecran-card" not in texte:
        raise ManuelIndisponible(
            "le document lu n'est pas le manuel : sa grille des écrans est absente"
        )
    return texte


def corps_du_manuel(html: str) -> str:
    """Le contenu imprimable : le `<main>`, sans la navigation ni les scripts.

    🔴 LES BLOCS DÉPLIABLES SONT OUVERTS À LA COMPOSITION, pas par du CSS.

    Un `<details>` fermé est du contenu **invisible** — donc, sur du papier, du
    contenu perdu. Et c'est justement celui qu'on a demandé à voir : Tickets,
    Communauté et Mon profil, les trois écrans dont l'usage ne se devine pas.

    La première version s'en remettait à `display: block !important` sur l'enfant.
    Ça ne suffit pas : le repli d'un `<details>` est un comportement natif, pas
    une règle de style — le navigateur l'a confirmé à l'aperçu, et un moteur PDF
    n'a aucune raison de faire mieux. On transforme donc la balise, ce qui ne
    dépend d'aucun moteur.

    Le `<summary>` devient un intertitre : « En savoir plus » n'a plus de sens
    quand tout est déjà là, mais le supprimer collerait deux paragraphes.
    """
    trouve = _MAIN.search(html)
    corps = trouve.group(1) if trouve else html
    corps = re.sub(r"<script.*?</script>", "", corps, flags=re.S | re.I)
    corps = re.sub(
        r"<summary[^>]*>.*?</summary>",
        '<p class="ecran-detail-titre">En détail</p>',
        corps,
        flags=re.S | re.I,
    )
    #  Le `name` d'un `<details>` le range dans un accordéon (un seul déplié à la
    #  fois, à l'écran) : il n'a pas de sens sur un `<div>`, et tout est déplié ici.
    corps = re.sub(
        r"<details([^>]*)>",
        lambda m: "<div" + re.sub(r'\s+name="[^"]*"', "", m.group(1)) + ">",
        corps,
        flags=re.I,
    )
    corps = re.sub(r"</details>", "</div>", corps, flags=re.I)
    #  🔴 « UN LOGICIEL LIBRE » NE FIGURE PAS DEUX FOIS (05/09/2026).
    #
    #  Demandé à l'écran : *« le § Un logiciel libre est à déplacer à la fin, et
    #  dans le PDF après le § À propos de ce document — à voir la cohérence pour
    #  qu'il n'y ait pas de redondance »*.
    #
    #  Sur la page, cette section est désormais la dernière. Dans le feuillet
    #  imprimé, elle tomberait donc juste AVANT `mentions`, qui porte déjà la
    #  la licence — deux paragraphes de suite pour dire la même chose. Le corps
    #  la perd ici, et les mentions restent le seul endroit qui l'énonce : c'est
    #  là qu'on regarde quand on cherche « qui a fait ça, et sous quelles
    #  conditions ».
    #
    #  ⚠️ C'est le SEUL retrait du corps imprimé, et il ne se généralise pas :
    #  tout le reste de la page est repris tel quel. Une section retirée est une
    #  section qu'un lecteur du PDF n'a jamais vue — cf. les blocs dépliables
    #  juste au-dessus, ouverts pour la même raison, en sens inverse.
    corps = re.sub(r'<section[^>]*id="logiciel-libre".*?</section>', "", corps, flags=re.S | re.I)
    #  Les liens de navigation interne (#ancre) n'ont pas de sens imprimés, mais
    #  on garde le texte : les retirer amputerait des phrases.
    return corps


def styles_du_manuel(html: str) -> str:
    """La feuille de style du manuel, reprise telle quelle.

    🔴 Reprise, jamais réécrite. Le PDF doit ressembler au manuel : redessiner
    ses cartes et ses couleurs ici créerait une seconde charte, qui dériverait à
    la première retouche de l'écran.
    """
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))


def _ancre(indice: int) -> str:
    """L'identifiant posé sur un titre pour que le sommaire puisse le viser.

    Un compteur, pas un slug du titre : deux écrans peuvent porter le même mot,
    et un identifiant en double ferait pointer deux entrées au même endroit.
    """
    return f"som-{indice}"


def titres_ancres(html: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Le corps AVEC des ancres, et la liste `(niveau, titre, ancre)`.

    🔴 Les deux sont rendus ENSEMBLE, et c'est délibéré : un sommaire dont les
    ancres seraient calculées séparément du corps pointerait à côté au premier
    titre ajouté. Ici, l'identifiant est posé et relevé dans la même passe — ils
    ne peuvent pas diverger.

    ⚠️ Niveaux 2 ET 3 : les quinze écrans sont des `<h3>`. Un sommaire qui
    s'arrêterait au niveau 2 n'offrirait que trois entrées, et ne permettrait pas
    de trouver « Accès & badges » — c'est-à-dire ce pour quoi on ouvre un
    sommaire.
    """
    corps = corps_du_manuel(html)
    releve: list[tuple[int, str, str]] = []

    def poser(m: re.Match) -> str:
        niveau, attrs, contenu = int(m.group(1)), m.group(2), m.group(3)
        #  `unescape` avant de normaliser : le manuel écrit « Une question&nbsp;? »
        #  en typographie française, et un sommaire qui afficherait l'entité
        #  brute trahirait sa fabrication.
        titre = re.sub(r"\s+", " ", unescape(_BALISES.sub("", contenu))).strip()
        if not titre:
            return m.group(0)
        #  🔴 Un titre qui porte DÉJÀ un `id` (un lien du manuel le vise) garde le
        #  sien, et le sommaire le vise : un second `id` sur la balise est ignoré
        #  — le premier gagne —, et le lien du sommaire pointait dans le vide
        #  (« No anchor #som-27 », v3.12.0, `<h3 id="fusion-correction">`).
        existant = _ID.search(attrs)
        ancre = existant.group(1) if existant else _ancre(len(releve))
        releve.append((niveau, titre, ancre))
        if existant:
            return m.group(0)
        return f'<h{niveau}{attrs} id="{ancre}">{contenu}</h{niveau}>'

    return _TITRES.sub(poser, corps), releve


def sommaire(html: str) -> list[str]:
    """Les titres du document, dans l'ordre. Conservé pour la lisibilité des tests."""
    return [titre for _, titre, _ in titres_ancres(html)[1]]


def version_du_manuel(html: str) -> str:
    """La version imprimée dans le pied du manuel, ou une chaîne vide."""
    trouve = _VERSION.search(_BALISES.sub(" ", html))
    return trouve.group(1) if trouve else ""


def _sommaire(releve: list[tuple[int, str, str]]) -> str:
    """Le sommaire, à DEUX niveaux et avec les numéros de page.

    🔴 Les numéros ne sont pas calculés ici — ils ne peuvent pas l'être : on ne
    sait pas encore combien de pages fera le document. C'est `target-counter()`
    qui les résout au moment de la mise en page, une fonctionnalité CSS Paged
    Media que WeasyPrint implémente. Un numéro écrit à la main serait faux dès
    la première phrase ajoutée au manuel.
    """
    if not releve:
        return ""
    lignes = "".join(
        f'<li class="som-n{niveau}"><a href="#{ancre}">{escape(titre)}</a></li>'
        for niveau, titre, ancre in releve
    )
    return f'<section class="sommaire"><h2>Sommaire</h2><ol>{lignes}</ol></section>'


def identite_du_manuel(session: Session) -> dict:
    """Ce que la garde porte de l'instance — une lecture pour la route ET le préchauffage.

    Le sous-titre est celui d'Admin › Présentation › Connexion et pied de page ; il était écrit en dur (08/10/2026).
    """
    cfg = config_site(session, "login_sous_titre")
    return {
        "site_nom": nom_site(cfg.get("site_nom")),
        "site_url": adresse_du_site(),
        "logo_png": logo_televerse_png(session),
        "sous_titre": (cfg.get("login_sous_titre") or "").strip(),
    }


def composer_html(
    site_nom: str,
    site_url: str,
    *,
    logo_png: bytes | None,
    sous_titre: str = "",
    html_manuel: str | None = None,
    edite_le: date | None = None,
) -> str:
    """Le document imprimable, AVANT rendu — garde, sommaire, contenu, mentions.

    🔴 Séparée du rendu à dessein. WeasyPrint exige des bibliothèques système
    (cf. `api/Dockerfile`) qu'un poste de développement Windows n'a pas : sans
    cette coupure, la composition ne serait éprouvable que dans un conteneur,
    c'est-à-dire jamais pendant qu'on l'écrit.

    C'est la même leçon que `courriel_ingestion` — la décision se teste, le tuyau
    se branche.
    """
    html = html_manuel if html_manuel is not None else lire_manuel()
    edite_le = edite_le or horloge.aujourd_hui()
    version = version_du_manuel(html)
    #  Le corps et le relevé viennent de la MÊME passe : voir `titres_ancres`.
    corps, releve = titres_ancres(html)

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Manuel utilisateur — {escape(site_nom)}</title>
<style>{css_du_pdf(styles_du_manuel(html))}</style>
</head><body>
{garde(site_nom, site_url, version, edite_le, logo_png, sous_titre)}
{_sommaire(releve)}
{corps}
{mentions(site_nom, site_url, version, edite_le)}
</body></html>"""


#: 🔴 LE PDF EST MIS EN CACHE (04/09/2026), et voici pourquoi ça se justifie.
#:
#: Signalé à l'écran : *« plus de 10 secondes sans message, avec une page vide
#: d'attente »*. WeasyPrint recomposait TOUT le document à chaque clic — polices,
#: colonnes, pagination, résolution des numéros de page — sur un Raspberry Pi.
#:
#: Or le résultat ne dépend que de trois choses : le manuel servi, le nom et
#: l'URL du site, et la date d'édition. Aucune ne change entre deux clics.
#:
#: ⚠️ La clé est l'EMPREINTE DU MANUEL, pas sa version : une retouche livrée sans
#: bump de version doit produire un PDF neuf. Se fier au numéro de version aurait
#: servi un document périmé sans que rien ne le signale — le défaut qu'on
#: passe son temps à corriger ailleurs.
#:
#: ⚠️ Le cache en mémoire disparaît à chaque redémarrage, donc à chaque
#: déploiement. Il est doublé, depuis le 25/09/2026, d'une copie SUR DISQUE :
#: voir `manuel_pdf_cache` (#1071).
#:
#: Un cache par copropriété (#1744, spec §4.5) : le PDF porte son nom, son adresse
#: et son logo.
def _cache() -> dict[tuple[str, ...], bytes]:
    return contexte.etat("manuel_pdf")


#: Au-delà, on jette le plus ancien. Deux entrées suffisent (la date change à
#: minuit) ; la borne existe pour qu'une boucle anormale ne gonfle pas la mémoire
#: d'un conteneur qui n'en a pas beaucoup. Même borne sur le disque.
_CACHE_MAX = 4

#: 🔴 UN SEUL RENDU À LA FOIS (#1071, 25/09/2026). Deux lecteurs sur un cache
#: vide lançaient deux rendus complets de 21 s — sur un Raspberry Pi, chacun
#: dans son propre process. Le second attend désormais le premier, et repart
#: avec son résultat au lieu de tout recomposer.
_VERROU = threading.Lock()


def generer_manuel_pdf(
    site_nom: str,
    site_url: str,
    *,
    logo_png: bytes | None,
    sous_titre: str = "",
    html_manuel: str | None = None,
    edite_le: date | None = None,
    dossier: Path | None = None,
) -> bytes:
    """Le manuel complet en PDF : la mémoire, puis le disque, puis le rendu.

    `dossier` sert aux tests ; en service, c'est celui de `manuel_pdf_cache`.
    """
    import hashlib

    html = html_manuel if html_manuel is not None else lire_manuel()
    edite_le = edite_le or horloge.aujourd_hui()
    cle = (
        hashlib.sha256(html.encode("utf-8")).hexdigest(),
        site_nom,
        site_url,
        edite_le.isoformat(),
        #  Le logo est DANS le document (#1728) : un logo changé est un autre PDF.
        hashlib.sha256(logo_png).hexdigest() if logo_png else "neutre",
        #  Le sous-titre aussi : il se règle dans Admin › Présentation › Connexion et pied de page.
        sous_titre,
    )
    memoire = _cache()
    if cle in memoire:
        return memoire[cle]

    with _VERROU:
        #  Relu SOUS le verrou : un rendu a pu aboutir pendant l'attente.
        if cle in memoire:
            return memoire[cle]
        dossier = dossier if dossier is not None else manuel_pdf_cache.dossier_par_defaut()
        pdf = manuel_pdf_cache.lire(cle, dossier)
        if pdf is None:
            pdf = html_to_pdf(
                composer_html(
                    site_nom,
                    site_url,
                    logo_png=logo_png,
                    sous_titre=sous_titre,
                    html_manuel=html,
                    edite_le=edite_le,
                )
            )
            manuel_pdf_cache.ecrire(cle, pdf, dossier, garder=_CACHE_MAX)
        if len(memoire) >= _CACHE_MAX:
            memoire.pop(next(iter(memoire)))
        memoire[cle] = pdf
    return pdf


#: Combien de fois le préchauffage réessaie quand le MANUEL est illisible, et
#: à quel intervalle. Après un déploiement, `front` démarre APRÈS l'API
#: (`depends_on: api`) : la première lecture pouvait tomber sur un front pas
#: encore prêt, et le préchauffage abandonnait — le premier lecteur payait alors
#: le rendu entier (#1071). Six essais à 15 s couvrent une minute et demie.
TENTATIVES_PRECHAUFFAGE = 6
PAUSE_PRECHAUFFAGE_S = 15.0


def prechauffer(
    site_nom: str,
    site_url: str,
    *,
    logo_png: bytes | None,
    sous_titre: str = "",
    pause_s: float | None = None,
) -> bool:
    """Rend le manuel une fois, pour que personne n'attende le premier rendu.

    ## 🔴 Pourquoi (18/09/2026, demandé par Philippe)

    Un manuel modifié change la clé du cache, en mémoire comme sur disque. Le
    prix en était payé par le premier lecteur d'après, et il est lourd :
    **21,1 secondes** mesurées en production, contre 0,15 s ensuite.

    ⚠️ Il se relance chaque nuit, parce que la clé du cache porte la DATE
    d'édition : sans cela, le premier lecteur du jour repaierait les 21 s.

    ⚠️ Il RÉESSAIE quand le manuel est illisible — le front démarre après
    l'API —, jamais quand le MOTEUR échoue : un rendu cassé le serait encore
    quinze secondes plus tard.

    Ne lève jamais : un manuel indisponible ou un moteur en panne ne doit pas
    empêcher l'application de démarrer. Rend `True` si le cache est garni.
    """
    import time

    pause = PAUSE_PRECHAUFFAGE_S if pause_s is None else pause_s
    for essai in range(1, TENTATIVES_PRECHAUFFAGE + 1):
        try:
            generer_manuel_pdf(site_nom, site_url, logo_png=logo_png, sous_titre=sous_titre)
        except ManuelIndisponible as exc:
            if essai == TENTATIVES_PRECHAUFFAGE:
                _logger.warning("Préchauffage du manuel PDF impossible : %s", exc)
                return False
            time.sleep(pause)
            continue
        except Exception as exc:  # noqa: BLE001 — au démarrage, aucune panne ne doit remonter
            _logger.warning("Préchauffage du manuel PDF impossible : %s", exc)
            return False
        _logger.info("Manuel PDF préchauffé (cache garni, %d entrée(s)).", len(_cache()))
        return True
    return False
