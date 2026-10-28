"""Garde-fou préventif : tout lien fabriqué par l'API doit exister côté front.

POURQUOI (26/07/2026) : le fil d'activité du tableau de bord renvoyait vers
`/documents` pour un nouveau document (« Voir → ») et pour un diagnostic. Cette route
n'a **jamais existé** dans `front/src/routes/` — il n'y a pas de page « tous les
documents », chaque document s'affiche là où il est rattaché. Résultat : un **404**
en pleine page, signalé par l'utilisateur depuis un PV d'AG.

Rien ne pouvait l'attraper : côté API c'est une chaîne de caractères, côté front une
route absente, et les deux moitiés ne se rencontrent qu'au clic. Les notifications
fabriquent des liens de la même façon (`lien=`, `lien_path=`) dans une dizaine de
routers — la même faute de frappe y produirait le même 404, dans un e-mail cette fois.

Ce test relie les deux moitiés : il extrait tous les liens émis par l'API et vérifie
qu'une page les sert réellement, en tenant compte des groupes SvelteKit — `(app)` est
transparent dans l'URL — et des segments dynamiques (`/tickets/{id}` → `[id]`).

MISE À JOUR (28/07/2026) : les liens vers un élément précis ne sont plus des f-strings
éparpillées, ils sortent tous de la table `EMPLACEMENTS` (`app/utils/liens.py`). Ce
fichier vérifie donc la table elle-même, ligne par ligne — page, onglet, ancre — en
plus des liens encore écrits à la main. Il gagne au passage le contrôle qui manquait :
**l'ancre doit être rendue par l'onglet que le lien sélectionne**. C'est précisément ce
qui a échappé aux trois tests précédents avec `/prestataires#presta-23` : la page
existait, l'ancre existait, aucun `?onglet=` n'était présent — donc rien à valider — et
la fiche restait invisible derrière l'onglet « Prestations ponctuelles ».
"""

import pathlib
import re
import types

import pytest

from tests.aides_liens_email import liens_des_modeles_email
from tests.aides_routes_front import (
    _onglet_de_la_route,
    _page_du_lien,
    _page_existe,
    _resoudre,
    _routes_onglets_du_front,
    _segments_par_onglet,
    contenu_deplie,
)
from tests.aides_sources import modules_app

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_FRONT_SRC = _RACINE / "front" / "src"
_ROUTES = _FRONT_SRC / "routes"

# `lien="/x"`, `lien=f"/x/{y}"`, `lien_path="/x"` — les liens vers le front.
_MOTIF_LIEN = re.compile(r"""lien(?:_path)?\s*=\s*f?["'](/[^"']*)["']""")


def _liens_de_la_table() -> dict[str, list[str]]:
    """{lien: [source]} pour chaque ligne de `EMPLACEMENTS`, avec un id d'exemple."""
    from app.utils.liens import EMPLACEMENTS, lien_element

    return {
        lien_element(prefixe, 1): ["api/app/utils/liens.py (EMPLACEMENTS)"]
        for prefixe in EMPLACEMENTS
    }


def _liens_de_l_api() -> dict[str, list[str]]:
    """{lien: [fichiers qui l'émettent]} — table centrale + littéraux restants."""
    trouves: dict[str, list[str]] = {k: list(v) for k, v in _liens_de_la_table().items()}
    for m in modules_app():
        for lien in _MOTIF_LIEN.findall(m.source):
            trouves.setdefault(lien, []).append(str(m.chemin.relative_to(_RACINE)))
    return trouves


def page_element(prefixe: str) -> str:
    """Raccourci de lecture vers la table centrale."""
    from app.utils.liens import EMPLACEMENTS

    return EMPLACEMENTS[prefixe]


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_tous_les_liens_emis_par_l_api_existent_cote_front():
    """Un lien vers une route inexistante = 404 pour l'utilisateur, sans autre signal."""
    casses = []
    for lien, fichiers in sorted(_liens_de_l_api().items()):
        if not _page_existe(lien):
            casses.append(f"  {lien}  ← {', '.join(sorted(set(fichiers)))}")

    assert not casses, (
        "Ces liens émis par l'API ne correspondent à aucune page du front — "
        "l'utilisateur qui clique reçoit un 404 :\n" + "\n".join(casses)
    )


def _liens_des_modeles_email() -> dict[str, list[str]]:
    """{lien: [modèles qui l'écrivent]} pour les `href="{{ app.url }}/…"`.

    Le contrôle au-dessus ne lit que les `lien=` fabriqués en Python. Or un
    modèle d'e-mail écrit ses URL **en dur dans du HTML**, et personne ne les
    relisait : `document_publie` a gardé pendant toute sa vie un bouton vers
    `/documents`, la route inexistante à l'origine même de ce fichier. Le défaut
    est resté invisible parce qu'aucune ligne de code n'envoyait ce modèle —
    un lien mort dans un e-mail que personne n'expédie ne se voit nulle part.

    Un lien d'e-mail est plus coûteux qu'un lien d'application : le destinataire
    est hors de l'outil, souvent sur son téléphone, et un 404 ne lui laisse
    aucun moyen de retrouver ce qu'on lui annonçait.

    Un chemin fourni ENTIER par une variable (`{{ app.url }}{{ document.lien }}`)
    provient de `EMPLACEMENTS`, déjà couvert ligne par ligne : il est écarté ici
    plutôt que deviné. Un SEGMENT variable, lui, est gardé depuis #1496 :
    `/tickets/{{ ticket.id }}` se résout comme `/tickets/[id]`. L'ancien motif
    exigeait un chemin sans aucun `{` et ne vérifiait donc aucun lien de ticket.

    L'extraction vit dans `aides_liens_email` : elle était écrite trois fois.
    """
    trouves: dict[str, list[str]] = {}
    for lien in liens_des_modeles_email():
        if lien.chemin is not None:
            trouves.setdefault(lien.chemin, []).append(f"modèle « {lien.modele} »")
    return trouves


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_liens_ecrits_dans_les_modeles_email_existent():
    """Un bouton d'e-mail vers une route absente envoie le destinataire nulle part."""
    casses = [
        f"  {lien}  ← {', '.join(sorted(set(sources)))}"
        for lien, sources in sorted(_liens_des_modeles_email().items())
        if not _page_existe(lien)
    ]
    assert not casses, (
        "Ces liens écrits dans un modèle d'e-mail ne correspondent à aucune "
        "page du front :\n" + "\n".join(casses)
    )


def test_des_liens_de_modeles_sont_analyses():
    """Cas zéro : si le motif ne trouve plus rien, le test au-dessus est décoratif."""
    assert _liens_des_modeles_email(), (
        "Aucun lien extrait des modèles d'e-mail — le motif ne reconnaît plus la "
        "façon dont les boutons sont écrits, et ce contrôle ne vérifie plus rien."
    )


def _pose_ancre(contenu: str, prefixe: str) -> bool:
    """La page pose-t-elle cette ancre — directement, ou par une propriété ?

    🔴 Deux formes, et la seconde manquait (10/09/2026). Une ligne de liste qui
    reçoit son ancre en PROPRIÉTÉ (`ancreId="ev_archive-{id}"` sur
    `RangeeCalendrier`) la pose bel et bien dans le DOM — le composant rend
    `id={ancreId}`. Ne chercher que le littéral `id="…"` faisait déclarer
    orpheline une ancre parfaitement rendue, et poussait à envelopper la ligne
    dans un `<div>` inutile pour satisfaire le contrôle.

    ⚠️ C'est le contrôle qui s'adapte au balisage, jamais l'inverse : un contrôle
    qu'on contourne par une enveloppe décorative mesure la forme du contournement,
    plus la chose.
    """
    return f'id="{prefixe}-' in contenu or f'ancreId="{prefixe}-' in contenu


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_ancres_des_liens_sont_produites_par_la_page_visee():
    """`#doc-42` n'a de sens que si la page pose `id="doc-{…}"` sur ses éléments.

    Une ancre qui ne correspond à rien ne casse pas visiblement : le navigateur
    charge la page et ne bouge pas. L'utilisateur arrive en haut d'une longue liste
    et cherche lui-même — c'est ce que faisait « Voir l'annonce → », qui ouvrait la
    Communauté sur l'onglet Sondages (26/07/2026).
    """
    orphelines = []
    for lien, fichiers in sorted(_liens_de_l_api().items()):
        if "#" not in lien:
            continue
        ancre = lien.split("#", 1)[1]
        #  Le préfixe est tout ce qui précède l'identifiant : `question-reglement-3`
        #  porte un tiret dans son préfixe (11/10/2026).
        prefixe = ancre.rsplit("-", 1)[0]
        page = _page_du_lien(lien)
        if page is None:
            continue  # déjà couvert par le test précédent
        if not _pose_ancre(contenu_deplie(page), prefixe):
            orphelines.append(
                f"  {lien}  ← {', '.join(sorted(set(fichiers)))}\n"
                f'      {page.relative_to(_RACINE)} ne pose aucun id="{prefixe}-…"'
            )

    assert not orphelines, (
        "Ces ancres ne correspondent à aucun élément de la page visée — le lien "
        "ouvre la bonne page mais ne montre pas l'élément :\n" + "\n".join(orphelines)
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_routes_de_la_table_sont_des_onglets_declares():
    """Chaque route d'`EMPLACEMENTS` doit être une adresse que le front DÉCLARE.

    Le contrôle a changé de forme le 05/09/2026, pas d'objet. Il vérifiait qu'un
    `?onglet=xxx` correspondait à une valeur connue de la page ; il vérifie
    maintenant que la ROUTE écrite côté API est l'une de celles que `#lib/pages.ts`
    déclare — ou la page d'un écran sans onglets (`/actualites`, `/faq`).

    Sans lui, `/annonce` au lieu d'`/annonces` passerait : le segment de reste
    accepte tout, et c'est le front qui rendrait la 404 — chez l'utilisateur.
    """
    from app.utils.liens import EMPLACEMENTS

    declarees = set(_routes_onglets_du_front())
    assert declarees, (
        "aucune route d'onglet lue dans front/src/lib/pages.ts — le motif ne "
        "reconnaît plus la table, et ce contrôle ne vérifie plus rien"
    )

    inconnues = []
    for prefixe, route in sorted(EMPLACEMENTS.items()):
        if route in declarees:
            continue
        #  Une page sans onglets n'a pas de route déclarée : elle doit alors exister
        #  telle quelle dans l'arborescence.
        segments = [x for x in route.strip("/").split("/") if x]
        if _resoudre(_ROUTES, segments):
            continue
        inconnues.append(
            f"  {prefixe} → {route} : ni onglet déclaré dans pages.ts, ni page du front"
        )

    assert not inconnues, (
        "Ces routes ne correspondent à aucune adresse déclarée par le front :\n"
        + "\n".join(inconnues)
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_l_ancre_est_rendue_par_l_onglet_que_le_lien_selectionne():
    """Le contrôle manquant : viser la bonne page ET le bon onglet.

    `/prestataires#presta-23` (28/07/2026) passait les trois tests précédents — page
    existante, ancre existante, aucun `?onglet=` à valider — et déposait pourtant
    l'utilisateur sur « Prestations ponctuelles », où aucun élément ne porte cet id.
    L'ancre ne désignait rien de rendu : le navigateur restait immobile, la fiche
    introuvable.

    Ici on relie les deux : pour chaque ligne de `EMPLACEMENTS`, l'onglet déclaré doit
    être celui dont le balisage produit réellement l'ancre.
    """
    from app.utils.liens import EMPLACEMENTS, lien_element

    ecarts = []
    for prefixe, route in sorted(EMPLACEMENTS.items()):
        onglet = _onglet_de_la_route(route)
        fichier = _page_du_lien(route)
        if fichier is None:
            continue  # déjà couvert par le test des pages
        contenu = contenu_deplie(fichier)
        segments = _segments_par_onglet(contenu)
        ancre = f'id="{prefixe}-'
        ancre_prop = f'ancreId="{prefixe}-'

        if onglet is None:
            # Page sans onglets : l'ancre doit exister, et la page ne doit pas être
            # devenue une page à onglets sans que la table le sache.
            if segments and (ancre in contenu or ancre_prop in contenu):
                ecarts.append(
                    f"  {prefixe} → {route} : la page a désormais des onglets "
                    f"({', '.join(sorted(segments))}) mais aucun n'est déclaré pour "
                    f"cette route — le lien s'ouvrira sur l'onglet par défaut"
                )
            continue

        if onglet not in segments:
            ecarts.append(
                f"  {prefixe} → {lien_element(prefixe, 1)} : "
                f"{fichier.relative_to(_RACINE)} ne connaît pas l'onglet '{onglet}' "
                f"(onglets trouvés : {', '.join(sorted(segments)) or 'aucun'})"
            )
        elif ancre not in segments[onglet] and ancre_prop not in segments[onglet]:
            #  Les DEUX formes, ici aussi : `_pose_ancre` documente pourquoi.
            rendu_par = [o for o, seg in segments.items() if ancre in seg or ancre_prop in seg]
            ecarts.append(
                f"  {prefixe} → {lien_element(prefixe, 1)} : l'onglet '{onglet}' ne "
                f'rend aucun {ancre}…" — '
                + (
                    f"c'est l'onglet '{rendu_par[0]}' qui le rend"
                    if rendu_par
                    else "aucun onglet ne le rend"
                )
            )

    assert not ecarts, (
        "Ces liens ouvrent la bonne page mais un onglet où l'élément visé n'existe "
        "pas — l'utilisateur arrive et ne voit rien :\n" + "\n".join(ecarts)
    )


class _FauxUser:
    def __init__(self, cs: bool):
        self._cs = cs

    def has_role(self, *_roles):
        return self._cs


class _FauxSession:
    """`session.get(ContratEntretien, id)` — seul appel fait par `lien_document`."""

    def __init__(self, prestataire_id: int | None = 7):
        self._prestataire_id = prestataire_id

    def get(self, _modele, _id):
        return (
            types.SimpleNamespace(prestataire_id=self._prestataire_id)
            if self._prestataire_id is not None
            else None
        )


def _faux_document(**champs):
    base = dict(id=42, ticket_id=None, contrat_id=None, categorie=None)
    base.update(champs)
    return types.SimpleNamespace(**base)


def test_chaque_document_pointe_vers_l_endroit_ou_il_est_affiche():
    """La table de correspondance, testée sans base : c'est elle qui a produit le 404.

    Chaque cas correspond à un endroit réel de l'interface — pièce jointe d'actualité,
    fiche prestataire, section de /residence — ou à l'absence assumée de lien quand la
    catégorie n'est affichée nulle part.
    """
    from app.utils.documents import lien_document as _lien_document

    cs, resident = _FauxUser(cs=True), _FauxUser(cs=False)
    categorie = lambda code: types.SimpleNamespace(code=code)  # noqa: E731

    cas = [
        #  Une pièce jointe d'affaire — actualité comprise (#1091) : sa fiche.
        (_faux_document(ticket_id=3), resident, "/tickets/3"),
        # `/prestataires` EST l'adresse de l'onglet Prestataires depuis le
        # 05/09/2026 : l'onglet n'a plus à être porté par un paramètre.
        (_faux_document(contrat_id=9), cs, "/prestataires#presta-7"),
        # Page réservée au CS/admin : un résident n'a rien à y faire, même s'il a le
        # droit de lire le document.
        (_faux_document(contrat_id=9), resident, None),
        (_faux_document(categorie=categorie("pv_ag")), resident, "/residence#doc-42"),
        (_faux_document(categorie=categorie("plan_residence")), resident, "/residence#doc-42"),
        # Catégorie affichée nulle part → aucun lien, délibérément.
        (_faux_document(categorie=categorie("fiche_synthetique")), resident, None),
        (_faux_document(), resident, None),
    ]
    for doc, user, attendu in cas:
        assert _lien_document(doc, user, _FauxSession()) == attendu, (
            f"document {doc} pour un {'CS' if user.has_role() else 'résident'}"
        )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_categories_de_documents_du_fil_mènent_quelque_part():
    """Les catégories que le fil accepte de lier doivent aboutir sur une page réelle.

    C'est le remplacement de `/documents` : les documents liables (plans, règlement,
    PV d'AG) s'affichent tous dans /residence, page et onglet décidés une seule fois
    par `EMPLACEMENTS["doc"]`. Les catégories absentes de cet ensemble ne sont
    affichées nulle part et ne reçoivent AUCUN lien — c'est délibéré, pas un oubli.
    """
    from app.utils.documents import CATEGORIES_AVEC_LIEN as _CATEGORIES_DOCUMENT_AVEC_LIEN

    assert _CATEGORIES_DOCUMENT_AVEC_LIEN, "aucune catégorie de document n'est liable"
    assert _page_existe(page_element("doc")), (
        f"le fil renverrait les documents vers {page_element('doc')}, page inexistante"
    )
