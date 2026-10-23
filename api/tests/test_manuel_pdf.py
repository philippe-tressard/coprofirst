"""Le manuel PDF est une MISE EN PAGE du manuel, jamais une seconde rédaction.

## 🔴 Ce que ce fichier protège

Demandé le 03/09/2026 : un manuel en PDF, avec page de garde, QR code, sommaire
et mentions. La tentation évidente était de le rédiger — et ce dépôt a déjà payé
**quatre fois** la divergence de deux textes décrivant la même chose (périmètres,
canaux de notification, table des pages, chiffres du manuel).

Un PDF re-rédigé aurait divergé au premier écran modifié, sans que rien ne le
signale. Et c'est le PDF, imprimé et distribué, qu'on aurait lu le plus longtemps
après sa péremption.

Le contenu est donc **lu tel qu'il est servi**, puis transformé. Ce fichier
vérifie que la transformation ne perd rien et n'invente rien.

## Ce qu'il ne peut pas vérifier

Le rendu PDF lui-même : WeasyPrint exige des bibliothèques système que le poste
de développement n'a pas (elles sont dans `api/Dockerfile`). La composition est
donc séparée du rendu — `composer_html` d'un côté, `html_to_pdf` de l'autre — et
c'est la composition qui porte toutes les décisions.

Même coupure que `courriel_ingestion` / `courriel_boite` : la décision se teste,
le tuyau se branche.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from app.utils import manuel_pdf as m
from app.utils.manuel_pdf import (
    ManuelIndisponible,
    composer_html,
    corps_du_manuel,
    lire_manuel,
    sommaire,
    titres_ancres,
)
from app.utils.manuel_pdf_css import css_du_pdf
from app.utils.plateforme import LICENCE_SPDX
from tests.aides_caddy import bloc_handle, caddyfile

_RACINE = Path(__file__).resolve().parents[2]
_MANUEL = _RACINE / "docs" / "manuel-utilisateur.html"


@pytest.fixture(scope="module")
def manuel() -> str:
    return _MANUEL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def document(manuel) -> str:
    return composer_html(
        "5Hostachy",
        "https://5hostachy.fr",
        logo_png=None,
        html_manuel=manuel,
        edite_le=date(2026, 9, 3),
    )


# ── La source est bien le manuel, et rien d'autre ────────────────────────────


def test_le_contenu_du_manuel_se_retrouve_dans_le_PDF(document, manuel):
    """🔴 Le cœur : une phrase du manuel doit être dans le document composé.

    Si quelqu'un remplaçait un jour la lecture par une rédaction, ce test
    tomberait à la première divergence — c'est le seul moyen de tenir la
    promesse faite au lecteur dans le lien de téléchargement : l'essentiel du
    manuel, pas un autre texte.
    """
    for extrait in (
        "Le menu, écran par écran",
        "Réglez votre profil",
        "Mini sommaire par profil",
    ):
        assert extrait in manuel, f"le manuel a changé : « {extrait} » a disparu"
        assert extrait in document, (
            f"« {extrait} » est dans le manuel mais pas dans le PDF : la mise en "
            "page perd du contenu"
        )


def test_les_TREIZE_ecrans_sont_dans_le_PDF(document):
    """La grille est l'essentiel du manuel : en perdre une carte le mutilerait.

    🔴 Quinze jusqu'au 12/09/2026, puis quatorze (« Accès & badges » absorbé par
    « Mes lots & accès », #928), puis douze le 23/09 : Actualités et Calendrier
    sont absorbées par Affaires, dont elles sont devenues des filtres (#1091,
    #1092). Aucune carte n'a été PERDUE : trois ont été absorbées, par décision.

    ⚠️ Le nombre est FIGÉ, et c'est délibéré : ce test protège contre la perte
    accidentelle d'une carte, pas contre une réorganisation voulue. Un test qui
    compterait les écrans de `pages.ts` passerait au vert le jour où l'on
    supprime une page ET sa carte — c'est-à-dire précisément le jour où il
    devrait crier. La comparaison avec `pages.ts`, elle, est faite par
    `npm run lint:manuel-menus`."""
    assert document.count('class="ecran-card"') == 12


# ── 🔴 Les blocs « En savoir plus » : retirés, et le retrait se dit ─────────


def test_les_blocs_en_savoir_plus_sont_RETIRES_et_SIGNALES(document, manuel):
    """Le PDF donne l'essentiel ; le détail reste en ligne (23/10/2026).

    Ces blocs portaient 62 % du texte : ouverts dans le PDF (choix du
    03/09/2026), ils en faisaient 33 pages, avec des fiches plus hautes qu'une
    page, que le moteur ne coupe pas — leur texte sortait de la feuille. Demandé :
    un document divisé par deux, sans paragraphe qu'on ne lira jamais.

    🔴 Le compte vient de la SOURCE : l'invariant est que CHAQUE bloc du manuel
    laisse un renvoi à sa place — un retrait muet laisserait croire au lecteur
    qu'il a tout lu.
    """
    assert "<details" not in document and "<summary" not in document
    attendus = manuel.count("<details")
    #  🔴 Cas zéro : sans bloc dans la source, la comparaison ne mesurerait rien.
    assert attendus >= 5, f"le manuel ne porte plus que {attendus} bloc(s) dépliable(s)"
    assert document.count(m.RENVOI_EN_LIGNE) == attendus, (
        f"{attendus} bloc(s) dans le manuel, {document.count(m.RENVOI_EN_LIGNE)} renvoi(s) dans le PDF"
    )
    #  Témoins : du DÉTAIL (absent) et de l'ESSENTIEL de la même carte (présent).
    assert "C'est cet inventaire qui fait foi" in manuel
    assert "C'est cet inventaire qui fait foi" not in document
    assert "Vos lots, vos badges Vigik" in document
    #  Le sommaire dit où lire le reste, à l'adresse du site.
    assert "https://5hostachy.fr" + m.CHEMIN_MANUEL_EN_LIGNE in document


# ── Le sommaire est CONSTRUIT, pas recopié ───────────────────────────────────


def test_le_sommaire_suit_les_titres_du_document(manuel, document):
    """Une table des matières recopiée est une table de plus.

    Ce manuel vient précisément de perdre toutes ses tables recopiées (#651) :
    en réintroduire une, tenue à la main, serait le comble.
    """
    corps, releve = titres_ancres(manuel)
    assert len(releve) >= 18, (
        f"seulement {len(releve)} entrées : le sommaire s'arrête au niveau 2 et "
        "ne permet plus de trouver un écran"
    )
    #  Les quatorze écrans sont des `<h3>` : sans eux, on ne peut pas chercher
    #  « Accès & badges », c'est-à-dire ce pour quoi on ouvre un sommaire.
    assert sum(1 for niveau, _, _ in releve if niveau == 3) >= 16

    for _niveau, titre, ancre in releve:
        assert f'href="#{ancre}"' in document, f"« {titre} » manque au sommaire"
        assert f'id="{ancre}"' in corps, (
            f"l'ancre de « {titre} » n'est posée nulle part : le lien du "
            "sommaire pointerait dans le vide"
        )
    #  🔴 Posée, et la SEULE de sa balise : sur un titre à deux `id`, seul le
    #  premier compte — le contrôle ci-dessus passait pendant que le PDF
    #  journalisait « No anchor #som-27 » (v3.12.0).
    for balise in re.findall(r"<h[23]\b[^>]*>", corps):
        assert len(re.findall(r"\bid\s*=", balise)) <= 1, f"titre à deux id : {balise}"

    #  L'ordre du document, pas un ordre inventé.
    positions = [document.index(f'href="#{a}"') for _, _, a in releve]
    assert positions == sorted(positions)


def test_les_numeros_de_page_sont_RESOLUS_a_la_mise_en_page(document):
    """🔴 Jamais écrits — on ne sait pas encore combien de pages fera le document.

    `target-counter()` les résout au moment de la pagination. Un numéro saisi
    serait faux dès la première phrase ajoutée au manuel, et faux en silence :
    rien ne signale un sommaire qui renvoie à la mauvaise page.
    """
    assert "target-counter(attr(href), page)" in document


def test_le_sommaire_decode_les_entites(manuel):
    """« Une question&nbsp;? » ne doit pas s'afficher avec son entité brute.

    Défaut réel, vu au premier essai : un sommaire qui montre `&nbsp;` trahit sa
    fabrication, et la typographie française du manuel en emploie partout.
    """
    titres = sommaire(manuel)
    assert not any("&nbsp;" in t or "&amp;" in t for t in titres), titres
    assert any(t.startswith("Une question") for t in titres)


# ── La page de garde et les mentions ─────────────────────────────────────────


def test_la_page_de_garde_porte_le_QR_code_et_la_date(document):
    assert 'class="garde"' in document
    assert "data:image/png;base64," in document, "le QR code n'a pas été généré"
    assert "3 septembre 2026" in document
    assert "https://5hostachy.fr" in document


def test_le_sous_titre_de_la_garde_est_celui_d_Admin_Site(manuel):
    """Il se règle dans Admin › Site, comme celui de la connexion (08/10/2026).

    La garde disait « L'extranet de votre résidence », écrit en dur : la résidence
    qui changeait son sous-titre le voyait partout, sauf sur son manuel imprimé.
    """
    avec = composer_html(
        "5Hostachy",
        "https://5hostachy.fr",
        logo_png=None,
        sous_titre="Le site <de> la résidence",
        html_manuel=manuel,
        edite_le=date(2026, 9, 3),
    )
    assert "Le site &lt;de&gt; la résidence<br>" in avec, "le sous-titre réglé n'est pas repris"
    assert "L'extranet de votre résidence" not in avec, "le sous-titre écrit en dur est revenu"
    sans = composer_html("5Hostachy", "https://5hostachy.fr", logo_png=None, html_manuel=manuel)
    assert re.search(r'class="garde-sous">\s*Trouver vite', sans), (
        "un sous-titre vide laisse une ligne vide"
    )


def test_l_identite_du_manuel_lit_le_reglage_d_Admin_Site(session):
    from app.models.core import ConfigSite

    session.add(ConfigSite(cle="login_sous_titre", valeur="  Notre résidence  "))
    session.add(ConfigSite(cle="site_nom", valeur="Les Tilleuls"))
    session.commit()
    identite = m.identite_du_manuel(session)
    assert identite["sous_titre"] == "Notre résidence"
    assert identite["site_nom"] == "Les Tilleuls"
    assert set(identite) == {"site_nom", "site_url", "logo_png", "sous_titre"}


def test_les_mentions_identifient_l_editeur(document):
    """Ce qu'un document distribuable doit porter.

    ⚠️ L'avertissement de péremption a été RETIRÉ le 03/09/2026, à la demande —
    et ce test l'exigeait. Il ne le réclame donc plus : un contrôle qui survit à
    la décision qu'il gardait devient un obstacle, pas un garde-fou.

    Ce qui reste exigé n'a pas bougé : le document dit qui l'édite, et ne nomme
    aucune personne physique.

    🔴 LA LICENCE VIT DANS LES MENTIONS, ET NULLE PART AILLEURS (05/09/2026).

    Elle vivait dans le corps du manuel, et ce test s'en contentait — « dans le
    PDF par construction ». Le jour où la section « Un logiciel libre » est
    passée en fin de page, elle s'est retrouvée juste avant ces mentions-ci, qui
    la disent déjà : deux paragraphes de suite pour la même chose. Demandé à
    l'écran : *« à voir la cohérence pour qu'il n'y ait pas de redondance »*.

    Le corps imprimé la perd donc (`corps_du_manuel`), et ce test vérifie les
    DEUX moitiés : elle est bien là, et elle n'y est qu'UNE fois. Sans la
    seconde, retirer la section du corps sans la reporter ici aurait produit un
    feuillet sans licence — le défaut inverse, et silencieux.
    """
    assert 'class="mentions"' in document
    assert "conseil syndical de la copropriété" in document, "les mentions ne nomment aucun éditeur"
    assert "Philippe Tressard" not in document, (
        "un nom de personne réapparaît dans un document distribuable"
    )
    #  ⚠️ Les blancs sont aplatis AVANT la recherche : WeasyPrint replie les
    #  lignes, et le nom de la licence peut s'y trouver coupé en deux. Chercher
    #  la chaîne brute échouerait sur une coupure, pas sur une absence.
    plat = " ".join(document.split())
    assert LICENCE_SPDX in plat, "le feuillet ne dit plus sous quelle licence"
    assert "auto-hébergée" in document, "le feuillet ne dit plus où vivent les données"
    #  🔴 UNE SEULE FOIS — voir le pourquoi dans le docstring.
    assert plat.count(LICENCE_SPDX) == 1, (
        "la licence est écrite deux fois dans le feuillet : le corps la répète "
        "alors que les mentions la portent (`corps_du_manuel` doit retirer la "
        "section « Un logiciel libre »)."
    )


# ── La lecture de la source ──────────────────────────────────────────────────


def test_un_manuel_illisible_LEVE_au_lieu_de_composer_du_vide():
    """Un PDF d'un manuel qu'on n'a pas pu lire serait une couverture, rien de plus.

    Et personne ne s'en apercevrait avant de l'ouvrir : la page de garde, elle,
    se serait composée normalement.
    """
    with pytest.raises(ManuelIndisponible):
        lire_manuel("http://127.0.0.1:1/introuvable.html", timeout=0.2)


def test_le_manuel_annonce_le_lien_vers_son_PDF(manuel):
    """Le lien vit dans la section « Une question ? », comme demandé."""
    assert "/api/manuel/pdf" in manuel
    corps = corps_du_manuel(manuel)
    apres_aide = corps[corps.index('id="aide"') :]
    assert "/api/manuel/pdf" in apres_aide, (
        "le lien PDF n'est pas dans la section « Une question ? »"
    )


def test_le_PDF_est_atteignable_depuis_TROIS_endroits(manuel):
    """🔴 Un document qu'on ne trouve pas n'existe pas.

    Signalé à l'écran le 03/09/2026 : *« je ne vois pas où générer le pdf du
    manuel »*. Le lien existait — au BAS du manuel, une page qu'on ouvre déjà
    rarement. Il est désormais posé là où l'œil arrive.

    ⚠️ Ce test regarde les fichiers plutôt que le rendu : il ne prouve pas qu'un
    lecteur verra les liens, seulement qu'ils n'ont pas disparu d'un des trois
    endroits. C'est ce qu'un test peut tenir ; le reste se constate à l'écran.
    """
    front = _RACINE / "front" / "src"

    #  ⚠️ On découpe sur le BALISAGE, pas sur un nom de classe : la première
    #  occurrence de « quick-start » est dans la feuille de style, bien avant le
    #  bandeau. Le premier découpage s'y est fait prendre, et le test accusait un
    #  lien pourtant présent.
    debut_hero = manuel.index('<section class="hero"')
    hero = manuel[debut_hero : manuel.index("</section>", debut_hero)]

    endroits = {
        "en haut du manuel (bandeau d'accueil)": hero,
        "en bas du manuel (Une question ?)": manuel[manuel.index('id="aide"') :],
        #  Les deux entrées de guide ont été extraites de `Nav.svelte` le
        #  03/09/2026 : elles y étaient écrites DEUX fois, menu latéral et menu
        #  mobile. Le lien vit donc dans le composant, pas dans la page.
        "menu du site": (front / "lib" / "components" / "LiensGuide.svelte").read_text(
            encoding="utf-8"
        ),
        "FAQ": (front / "routes" / "(app)" / "faq" / "+page.svelte").read_text(encoding="utf-8"),
    }
    client = (front / "lib" / "api" / "index.ts").read_text(encoding="utf-8")  # #1578
    assert "pdfUrl: (): string => `${BASE}/manuel/pdf`" in client
    lien = ("/api/manuel/pdf", "manuel.pdfUrl()")  # le manuel en clair, les écrans par le client
    manquants = [ou for ou, t in endroits.items() if not any(x in t for x in lien)]
    assert not manquants, "le lien vers le PDF a disparu de : " + ", ".join(manquants)


#  Le CACHE (empreinte, bornes, logo) se teste dans `test_manuel_pdf_cache.py`.


# ── Le manuel doit être REVALIDÉ, jamais servi de mémoire ────────────────────


def test_le_manuel_impose_la_revalidation_au_navigateur():
    """🔴 Signalé le 04/09/2026 : *« je ne vois pas le menu générer un PDF »*.

    La production servait la bonne version ; le navigateur affichait la
    précédente. Le fichier ne portait **aucun** `Cache-Control` — le navigateur
    applique alors sa propre heuristique, calculée sur `Last-Modified`.

    ⚠️ Un document qui change à chaque lot et qu'on sert sans directive sera lu
    périmé, **et personne ne le saura** : la page s'affiche parfaitement. C'est la
    troisième forme de ce défaut ici — bandeau PWA (v2.24.0), `sw.js`
    (14/08/2026), le manuel aujourd'hui.

    `no-cache` n'interdit pas de stocker : il impose de revalider. Le fichier
    reste donc en cache local, et un `304` suffit quand il n'a pas changé.
    """
    bloc = bloc_handle(caddyfile(), "/manuel-utilisateur.html")
    assert bloc, (
        "aucun bloc `handle /manuel-utilisateur.html` : le manuel est servi sans "
        "directive de cache, donc mis en cache à l'heuristique du navigateur"
    )
    directive = re.search(r'header\s+>?Cache-Control\s+"([^"]+)"', bloc)
    assert directive, "le bloc du manuel n'impose plus de Cache-Control"
    valeur = directive.group(1).lower()
    assert "no-cache" in valeur or "no-store" in valeur, (
        f"Cache-Control « {directive.group(1)} » laisse servir le manuel de "
        "mémoire : une version périmée s'affichera sans que rien ne le signale"
    )
    #  ⚠️ Le `>` REMPLACE l'en-tête ; sans lui, `header` AJOUTE et la valeur
    #  d'amont subsiste — défaut constaté sur `sw.js` le 14/08/2026, où
    #  « max-age=14400 » avait survécu à la fusion.
    assert ">Cache-Control" in bloc, (
        "sans `>`, la directive s'AJOUTE à celle d'amont au lieu de la remplacer"
    )


# ── Les deux maquettes du menu : côte à côte, et le bouton expliqué ──────────


def test_les_deux_maquettes_sont_COTE_A_COTE_dans_le_PDF():
    """🔴 Le flux en colonnes les empilait — et empilées, elles ne comparent plus rien.

    `.maq-duo` était décrit en `column-count: 2`. Sur une figure plus haute que
    la colonne disponible, `break-inside: avoid` interdit à WeasyPrint de la
    répartir : il empile. Les deux maquettes se sont donc retrouvées l'une SOUS
    l'autre en production, signalé à l'écran le 04/09/2026.

    Le flux en colonnes est fait pour du texte qui coule ; ces deux figures ne
    coulent pas, elles se **comparent** : c'est la comparaison qui montre que
    c'est le même menu à deux endroits, et non deux menus différents.

    ⚠️ Ce test lit du CSS, ce qui est un pis-aller assumé : WeasyPrint n'est pas
    installable sur le poste de développement (libs système absentes du
    Dockerfile côté Windows), donc le rendu réel ne peut pas être mesuré ici.
    Il vaut mieux vérifier la cause connue que rien du tout — mais il ne prouve
    pas la mise en page, et cette limite est nommée exprès.
    """
    CSS = css_du_pdf("")
    bloc = re.search(r"\.maq-duo \{(.*?)\}", CSS, re.S)
    assert bloc, "la règle `.maq-duo` a disparu : les maquettes ne sont plus cadrées"
    regle = bloc.group(1)
    assert "column-count" not in regle, (
        "`.maq-duo` repasse en flux de colonnes : les deux maquettes s'empileront "
        "l'une sous l'autre dès que l'une dépassera la hauteur disponible"
    )
    assert "display: flex" in regle, (
        "seul un conteneur flex garantit les deux maquettes côte à côte quelle "
        "que soit leur hauteur"
    )


def test_le_bouton_du_menu_telephone_est_DESSINE_et_EXPLIQUE(manuel):
    """Un symbole que le lecteur doit déjà connaître n'explique rien.

    Le bouton portait le caractère ☰. Il ne dit rien à qui n'a jamais fait le
    rapprochement — c'est-à-dire au lecteur de ce guide, qui n'est pas
    informaticien : c'est la remarque du 04/09/2026. Il est désormais dessiné,
    encadré comme un bouton, et une ligne dit en toutes lettres ce qu'il fait.

    Le pendant côté manuel HTML est `npm run lint:manuel-menus`. Ce test-ci
    couvre la **mise en forme PDF**, que le contrôle front ne voit pas.
    """
    CSS = css_du_pdf("")
    assert 'class="maq-burger"' in manuel and "<svg" in manuel
    assert 'class="maq-explication"' in manuel, (
        "le bouton du menu téléphone est montré sans être expliqué"
    )
    #  Sans style, l'explication se fondrait dans le corps du texte : elle ne se
    #  rattacherait plus visuellement au bouton qu'elle décrit.
    assert ".maq-explication {" in CSS, (
        "l'explication du bouton n'a pas de style dans le PDF — elle s'y "
        "afficherait comme un paragraphe ordinaire, détachée de son bouton"
    )
