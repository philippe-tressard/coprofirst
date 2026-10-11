"""Ce que le front SERT — la moitié « front » de `test_liens_front.py`.

Sortie du fichier de test le 05/09/2026, sur refus du contrôle de modularité :
512 lignes pour un fichier déjà au-dessus du plafond. La découpe n'est pas
arbitraire — elle sépare deux métiers qui n'ont en commun que le sujet :

  - **ici** : lire l'arborescence des routes SvelteKit, la table des pages et le
    balisage des écrans. Aucune assertion, aucun import de l'API.
  - **là-bas** : confronter les liens que l'API fabrique à ce que ces fonctions
    répondent.

⚠️ Trois subtilités du routage vivent ici, et elles se périment si le front
change de mécanique — c'est le seul endroit à rouvrir :
  1. les groupes `(app)` sont transparents dans l'URL ;
  2. `reroute` (`front/src/hooks.ts`) fait rendre `/annonces` par la route
     `/sondages` : une adresse d'onglet n'a **pas** de dossier à elle ;
  3. un écran délégué à un composant ajoute un niveau de dépliage ;
  4. un dossier `[...reste]` sert TOUT chemin sous lui, le vide compris —
     `/calendrier` en est un depuis le 23/09/2026 (#1092), une adresse qui
     redirige. L'ignorer déclarait morts des liens déjà envoyés qui aboutissent.
"""

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FRONT_SRC = _RACINE / "front" / "src"
_ROUTES = _FRONT_SRC / "routes"


def _resoudre(base: pathlib.Path, segments: list[str]) -> bool:
    """Une page SvelteKit sert-elle ce chemin depuis `base` ?"""
    if not base.is_dir():
        return False
    sous_dossiers = [d for d in base.iterdir() if d.is_dir()]
    #  Subtilité 4 : `[...reste]` sert tout ce qui suit, y compris rien.
    if any(d.name.startswith("[...") and (d / "+page.svelte").exists() for d in sous_dossiers):
        return True
    if not segments:
        return (base / "+page.svelte").exists()

    seg, reste = segments[0], segments[1:]

    # Les groupes `(app)`, `(marketing)`… n'apparaissent pas dans l'URL : on traverse.
    for groupe in (d for d in sous_dossiers if d.name.startswith("(")):
        if _resoudre(groupe, segments):
            return True

    if seg.startswith("{"):  # segment dynamique d'une f-string → `[id]`, `[slug]`…
        candidats = [d for d in sous_dossiers if d.name.startswith("[")]
    else:
        candidats = [d for d in sous_dossiers if d.name == seg]

    return any(_resoudre(c, reste) for c in candidats)


#  Les URL dédiées des onglets, lues dans la table du front (`$lib/pages.ts`).
#  Aucune n'a de dossier de route à elle : `reroute` (`front/src/hooks.ts`) les
#  envoie toutes au fichier de leur page — `/annonces` est rendue par
#  `routes/(app)/sondages/+page.svelte`. Les chercher dans l'arborescence
#  déclarerait donc mortes des adresses qui fonctionnent. C'est la table qui fait
#  foi, ici comme dans le navigateur.
_MOTIF_ROUTE_ONGLET = re.compile(r"id: '([\w-]+)',\s*route: '([^']+)'")
_MOTIF_HREF_PAGE = re.compile(r"href: '([^']+)'")


def _pages_ts() -> str:
    """La table des pages, en UN texte — elle vit en DEUX fichiers.

    🔴 `pages-roles.ts` est né le 12/09/2026 (#928) : `pages.ts` avait franchi
    son plafond de modularité, et les pages réservées à un rôle en sont parties.

    ⚠️ Ce test a été le QUATRIÈME contrôle rendu aveugle par cette extraction —
    après `lint:pages`, `lint:manuel-menus` et le parcours de `check-pages`. Il a
    aussitôt déclaré qu'un lien émis par l'API menait à une 404, alors que la
    page existait : il ne la voyait plus. **Découper un fichier, c'est rendre
    aveugle tout ce qui le lisait**, et rien ne le signale avant l'échec.
    """
    textes = [
        (_FRONT_SRC / "lib" / nom).read_text(encoding="utf-8-sig")
        for nom in ("pages.ts", "pages-roles.ts")
        if (_FRONT_SRC / "lib" / nom).is_file()
    ]
    return chr(10).join(textes)


def _routes_onglets_du_front() -> dict[str, str]:
    """{route d'onglet: route de la PAGE qui la rend} — la table de `reroute`."""
    table: dict[str, str] = {}
    #  Une entrée de page commence par son `id:` en début de bloc et porte son
    #  `href:` juste après ; ses onglets suivent, avec leurs routes. On découpe
    #  donc sur les `href:`, ce qui donne exactement un segment par page.
    segments = _pages_ts().split("href: ")
    for segment in segments[1:]:
        href = _MOTIF_HREF_PAGE.search("href: " + segment)
        if not href:
            continue
        for _id, route in _MOTIF_ROUTE_ONGLET.findall(segment):
            table[route] = href.group(1)
    return table


def _page_existe(lien: str) -> bool:
    chemin = lien.split("#")[0].split("?")[0]
    chemin = _routes_onglets_du_front().get(chemin.rstrip("/"), chemin)
    segments = [s for s in chemin.strip("/").split("/") if s]
    return _resoudre(_ROUTES, segments)


def _page_du_lien(lien: str) -> pathlib.Path | None:
    """Fichier `+page.svelte` qui sert ce lien (pour inspecter ancres et onglets).

    Passe d'abord par la table de `reroute` : `/annonces` n'a pas de dossier, elle
    est rendue par la route de sa page. Chercher le fichier au chemin littéral
    rendrait ce contrôle muet sur toutes les adresses d'onglet — c'est-à-dire sur
    la moitié d'`EMPLACEMENTS`.
    """
    chemin = lien.split("#")[0].split("?")[0]
    chemin = _routes_onglets_du_front().get(chemin.rstrip("/"), chemin)
    segments = [s for s in chemin.strip("/").split("/") if s]

    def descendre(base: pathlib.Path, restants: list[str]) -> pathlib.Path | None:
        if not restants:
            page = base / "+page.svelte"
            return page if page.exists() else None
        seg, suite = restants[0], restants[1:]
        if not base.is_dir():
            return None
        sous = [d for d in base.iterdir() if d.is_dir()]
        for groupe in (d for d in sous if d.name.startswith("(")):
            trouve = descendre(groupe, restants)
            if trouve:
                return trouve
        cibles = (
            [d for d in sous if d.name.startswith("[")]
            if seg.startswith("{")
            else [d for d in sous if d.name == seg]
        )
        for c in cibles:
            trouve = descendre(c, suite)
            if trouve:
                return trouve
        return None

    return descendre(_ROUTES, segments)


#  `$lib/components/X.svelte` ou `./X.svelte` : un composant voisin s'importe aussi
#  en relatif (`ListeAnnonces` → `./AnnonceCard.svelte`), et ne suivre que la
#  première forme laissait l'ancre qu'il pose hors de la vue du contrôle.
_MOTIF_IMPORT_COMPOSANT = re.compile(
    r"import\s+(\w+)\s+from\s+['\"](\$lib/components/|\./)([\w./-]+\.svelte)['\"]"
)


def contenu_deplie(fichier: pathlib.Path, _profondeur: int = 4) -> str:
    """Le balisage d'une page, **composants locaux inclus**, à leur place d'appel.

    Une page qui rend `id="annonce-…"` directement, ou qui délègue à
    `<AnnonceCard>` qui le rend, produit le même écran : les contrôles d'ancre
    doivent voir les deux. Sans cela, découper une page en composants ferait
    échouer ces tests **sans qu'aucun lien ne soit cassé**, et la tentation serait
    de les affaiblir — alors qu'ils viennent d'attraper trois liens morts.

    Le découpage est une obligation permanente ici (rang 1 §4, « au fil de l'eau ») :
    ce dépliage n'est donc pas une commodité ponctuelle, c'est ce qui permet aux
    deux règles de coexister. Constaté le 14/08/2026, quand l'extraction de
    `AnnonceCard.svelte` a fait tomber deux de ces tests.

    ⚠️ La profondeur est passée de 2 à 3 le 05/09/2026 : `/annonces` monte
    `PageCommunaute`, qui monte `OngletAnnonces`, qui monte `AnnonceCard` — c'est
    cette dernière qui pose `id="annonce-…"`. Une route qui délègue son écran à un
    composant ajoute un niveau, et le contrôle doit le suivre, sinon il déclare
    l'ancre absente alors qu'elle est rendue.
    ⚠️ Et de 3 à 4 le 11/10/2026 : `OngletAnnonces` délègue désormais sa liste à
    `ListeAnnonces`, qui monte `AnnonceCard` — un niveau de plus, que personne
    n'avait vu, parce que le contrôle restait vert sur `id="annonce-titre-…"` du
    FORMULAIRE de création, importé alors d'emblée. Quand le formulaire a été
    chargé à la demande (`ChargementDiffere`), le vert de rencontre a disparu.
    Un préfixe d'ancre trouvé ne dit pas QUEL élément le porte.

    Le contenu du composant est **inséré** à l'endroit de sa balise plutôt que
    substitué : `_segments_par_onglet` découpe la page par onglet, et l'ancre doit
    donc tomber dans le segment où le composant est réellement invoqué. Une
    substitution demanderait de reconnaître la fin d'une balise dont les attributs
    contiennent des `>` (`onToggle={() => …}`), ce qu'aucune expression régulière
    ne fait correctement.
    """
    contenu = fichier.read_text(encoding="utf-8-sig")
    if _profondeur <= 0:
        return contenu

    for nom, base, cible in _MOTIF_IMPORT_COMPOSANT.findall(contenu):
        dossier = fichier.parent if base == "./" else _FRONT_SRC / "lib" / "components"
        chemin = dossier / cible
        if not chemin.is_file():
            continue
        position = contenu.find(f"<{nom}", contenu.find("</script>"))
        if position == -1:
            continue  # importé mais pas utilisé dans le balisage
        interne = contenu_deplie(chemin, _profondeur - 1)
        contenu = contenu[:position] + interne + contenu[position:]

    return contenu


def _onglet_de_la_route(route: str) -> str | None:
    """L'identifiant d'onglet que cette route ouvre, ou `None` si la page n'en a pas."""
    fichier = _FRONT_SRC / "lib" / "pages.ts"
    if not fichier.is_file():
        return None
    for ident, r in _MOTIF_ROUTE_ONGLET.findall(fichier.read_text(encoding="utf-8-sig")):
        if r == route:
            return ident
    return None


# Les pages à onglets branchent leur contenu sur `onglet === '…'` ou `activeTab === '…'`.
_MOTIF_BRANCHE_ONGLET = re.compile(r"(?:onglet|activeTab)\s*===\s*'([\w]+)'")


def _segments_par_onglet(contenu: str) -> dict[str, str]:
    """{onglet: portion(s) du fichier rendue(s) sous cet onglet}.

    Découpage volontairement grossier : chaque marqueur `onglet === 'x'` ouvre une
    portion qui court jusqu'au marqueur suivant. Une page déclare plusieurs fois le
    même onglet (bouton d'en-tête, onglet de la barre, bloc de contenu) → on
    concatène toutes ses portions. Suffisant pour répondre à la seule question
    posée : « cet onglet rend-il, quelque part, un `id="prefixe-…"` ? »
    """
    marqueurs = list(_MOTIF_BRANCHE_ONGLET.finditer(contenu))
    segments: dict[str, str] = {}
    for i, m in enumerate(marqueurs):
        fin = marqueurs[i + 1].start() if i + 1 < len(marqueurs) else len(contenu)
        segments[m.group(1)] = segments.get(m.group(1), "") + contenu[m.start() : fin]
    return segments
