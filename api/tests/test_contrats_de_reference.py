"""Les deux sections de la fiche adossées à un contrat — assurance et syndic.

## Ce que ce lot a changé (#553, 20/08/2026)

L'assurance était **déduite** : *« le contrat d'assurance actif le plus récent
gagne »* (#490). La règle était juste — une copropriété change d'assureur et
l'ancien contrat reste en base, c'est tout l'intérêt d'en avoir fait un contrat
— mais **rien à l'écran ne disait laquelle des lignes faisait foi**.

Elle devient un **choix** (`assurance_contrat_id`), et le syndic entre dans le
même moule (`syndic_contrat_id`).

## Ce que ces tests protègent

1. **Le repli** sur l'ancienne règle, sans lequel une fiche perdrait son
   assurance devant un contrat qui existe ;
2. **La distinction valeur / désignation** — on ne saisit pas un assureur, on dit
   lequel des contrats existants fait foi ;
3. 🔴 **L'invariant qui compte : les deux sections sont LE MÊME GESTE.** Une
   fonction unique les sert. Le jour où quelqu'un ajoute un enrichissement à
   l'assurance sans le donner au syndic, ce fichier le dit — c'est
   `standards/02` §2 rendu exécutoire.
"""

from __future__ import annotations

import ast
import pathlib

from app.routers.copropriete import (
    SECTIONS_CONTRAT,
    assurance_du_contrat,
    contrat_de_reference,
    syndic_du_contrat,
)

SOURCE = pathlib.Path(__file__).parent.parent / "app" / "routers" / "copropriete.py"


class _SessionFactice:
    """Rend l'objet demandé par `session.get`, et rien par `session.exec`."""

    def __init__(self, par_id=None, exec_resultat=None, exec_suite=None):
        self._par_id = par_id or {}
        #  ⚠️ `exec_suite` rend un résultat DIFFÉRENT par appel successif.
        #  La première version rendait le même objet à chaque `exec` : la requête
        #  de repli sur le contrat recevait alors un membre du syndic, et le test
        #  échouait sur un `AttributeError` qui ne disait rien du code. Un double
        #  qui répond n'importe quoi à n'importe quelle question ne prouve rien.
        self._suite = list(exec_suite) if exec_suite is not None else None
        self._exec = exec_resultat

    def get(self, _modele, identifiant):
        return self._par_id.get(identifiant)

    def exec(self, _requete):
        if self._suite is not None:
            resultat = self._suite.pop(0) if self._suite else None
        else:
            resultat = self._exec

        class _R:
            def first(self_inner):
                return resultat

        return _R()


class _Copro:
    def __init__(self, assurance_contrat_id=None, syndic_contrat_id=None):
        self.id = 1
        self.assurance_contrat_id = assurance_contrat_id
        self.syndic_contrat_id = syndic_contrat_id


class _Contrat:
    def __init__(self, id=7):
        self.id = id
        self.prestataire_id = 3
        self.numero_contrat = "P-42"
        self.date_debut = None
        self.prochaine_visite = None
        self.document_id = None
        #  Ni résilié ni remplacé : `successeur_en_vigueur` lit ces deux champs.
        self.resilie_le = None
        self.remplace_par_id = None


#  ── La désignation, et son repli ────────────────────────────────────────────


def test_le_contrat_DESIGNE_gagne_sur_la_deduction():
    """C'est tout le lot : le choix remplace la règle implicite.

    Le contrat 7 est désigné ; la requête de repli rendrait le contrat 99. C'est
    7 qui doit sortir — sinon la sélection à l'écran ne servirait à rien.
    """
    designe, replie = _Contrat(7), _Contrat(99)
    session = _SessionFactice(par_id={7: designe}, exec_resultat=replie)
    assert contrat_de_reference(session, _Copro(assurance_contrat_id=7), "assurance") is designe


def test_sans_designation_le_repli_s_applique():
    """⚠️ Le repli n'est pas de la prudence, il évite un écran qui ment.

    La migration 0157 renseigne les bases existantes, mais une copropriété créée
    après coup — ou un contrat saisi avant qu'on ait pensé à le désigner —
    laisserait la fiche vide **alors que le contrat existe**. Un écran qui dit
    « aucun contrat » devant un contrat est pire qu'une règle implicite.
    """
    replie = _Contrat(99)
    session = _SessionFactice(exec_resultat=replie)
    assert contrat_de_reference(session, _Copro(), "assurance") is replie


def test_un_contrat_designe_puis_SUPPRIME_ne_se_replie_pas():
    """🔴 Le repli ne doit pas ressusciter une déduction qu'on a écartée.

    Si la fiche désigne un contrat qui n'existe plus, la bonne réponse est
    « aucun » — pas « le plus récent ». Se replier ici afficherait un contrat que
    personne n'a choisi, et masquerait la suppression : l'administration croirait
    sa désignation intacte.
    """
    session = _SessionFactice(par_id={}, exec_resultat=_Contrat(99))
    assert contrat_de_reference(session, _Copro(assurance_contrat_id=7), "assurance") is None


#  ── L'invariant de factorisation ────────────────────────────────────────────


def test_les_deux_sections_sont_declarees_au_MEME_endroit():
    """Cas zéro : sans la table, il n'y a plus d'invariant à vérifier."""
    assert set(SECTIONS_CONTRAT) == {"assurance", "syndic"}, sorted(SECTIONS_CONTRAT)
    for section, (champ, _type) in SECTIONS_CONTRAT.items():
        assert champ == f"{section}_contrat_id", (
            f"la colonne de « {section} » ne suit pas la convention : {champ}"
        )


def test_les_deux_lectures_rendent_les_MEMES_champs_communs():
    """🔴 L'invariant du lot : assurance et syndic sont le même geste.

    Les deux sections affichent la même chose sous des noms préfixés :
    l'organisation, son téléphone, son courriel, le numéro du contrat, ses dates,
    son document. Le jour où quelqu'un enrichit l'une sans l'autre, l'écran se met
    à montrer deux sections qui ne se ressemblent plus — et personne ne le dit,
    puisque rien ne casse.

    ⚠️ `syndic_interlocuteur*` est EXCLU à dessein : il vient de `MembreSyndic`,
    l'annuaire, et l'assurance n'a pas d'équivalent. C'est la seule divergence
    légitime, et elle est nommée ici plutôt que subie.
    """
    contrat = _Contrat(7)
    session = _SessionFactice(par_id={7: contrat}, exec_resultat=None)

    assurance = assurance_du_contrat(session, _Copro(assurance_contrat_id=7))
    syndic = syndic_du_contrat(session, _Copro(syndic_contrat_id=7))

    def suffixes(lu, prefixe, exclus=()):
        return {c[len(prefixe) :] for c in lu if c.startswith(prefixe) and c not in exclus}

    #  `compagnie` et `cabinet` désignent la même chose sous deux mots : c'est le
    #  vocabulaire du métier, pas une divergence de structure.
    communs_assurance = suffixes(assurance, "assurance_") - {"compagnie", "numero_police"}
    communs_syndic = suffixes(
        syndic, "syndic_", exclus={"syndic_interlocuteur", "syndic_interlocuteur_email"}
    ) - {"cabinet", "numero_mandat"}

    assert communs_assurance == communs_syndic, (
        f"les deux sections ont divergé — assurance : {sorted(communs_assurance)}, "
        f"syndic : {sorted(communs_syndic)}"
    )


def _appels(fonction: ast.FunctionDef, nom: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(fonction)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == nom
    ]


def test_chaque_section_lit_son_contrat_par_la_MEME_fonction():
    """⚠️ La factorisation se vérifie, elle ne se raconte pas.

    Deux copies de « lire le contrat, lire son prestataire, composer un
    préfixe » divergeraient au premier enrichissement. Ce test lit l'ARBRE du
    module, pour chaque section de `SECTIONS_CONTRAT` :

    * sa lecture `<section>_du_contrat` appelle `contrat_de_reference` ;
    * elle reçoit l'échéance par `_echeance_lue("<section>")`, et par elle seule
      (29/08/2026) — le jour où quelqu'un donne un enrichissement à l'une sans
      le donner à l'autre, ce test le dit ;
    * elle ne refait pas la requête sur `ContratEntretien`.

    ⚠️ Interdire TOUT `select` était trop large : `syndic_du_contrat` lit
    légitimement `MembreSyndic`, une autre table. Ce qu'aucune des deux ne doit
    refaire, c'est la requête sur le CONTRAT — c'est elle qui porte la règle de
    sélection, et deux copies en feraient deux vérités.
    """
    fonctions = {
        n.name: n
        for n in ast.walk(ast.parse(SOURCE.read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef)
    }
    fautes = []
    for section in SECTIONS_CONTRAT:
        nom = f"{section}_du_contrat"
        fonction = fonctions.get(nom)
        if fonction is None:
            fautes.append(f"  {nom} est introuvable dans copropriete.py")
            continue
        if not _appels(fonction, "contrat_de_reference"):
            fautes.append(
                f"  {nom} ne passe pas par `contrat_de_reference` : la lecture du "
                "contrat est de nouveau recopiée"
            )
        echeances = [
            a.args[0].value
            for a in _appels(fonction, "_echeance_lue")
            if a.args and isinstance(a.args[0], ast.Constant)
        ]
        if echeances != [section]:
            fautes.append(
                f"  {nom} appelle `_echeance_lue` avec {echeances} au lieu de "
                f"[{section!r}] : les deux sections ne reçoivent plus le même enrichissement"
            )
        if any(
            isinstance(a, ast.Name) and a.id == "ContratEntretien"
            for appel in _appels(fonction, "select")
            for a in appel.args
        ):
            fautes.append(
                f"  {nom} refait sa propre requête sur ContratEntretien au lieu de "
                "passer par `contrat_de_reference` — deux règles de sélection"
            )
    assert not fautes, "Assurance et syndic ne sont plus le même geste :\n" + "\n".join(fautes)


def test_le_syndic_rend_son_interlocuteur_meme_SANS_contrat():
    """Le cabinet peut n'avoir pas de contrat saisi ; ses membres, eux, existent.

    Rendre un dictionnaire vide effacerait de la fiche une information qu'on
    POSSÈDE — et l'annuaire la porte depuis des mois.
    """

    class _Membre:
        prenom, nom, fonction, email = "Claire", "Fontaine", "gestionnaire", "c@iff.test"

    #  Deux requêtes dans l'ordre : le repli sur le contrat (rien), puis le
    #  membre principal de l'annuaire.
    session = _SessionFactice(exec_suite=[None, _Membre()])
    lu = syndic_du_contrat(session, _Copro())
    assert lu["syndic_interlocuteur"].startswith("Claire Fontaine")
    assert lu["syndic_interlocuteur_email"] == "c@iff.test"
    assert "syndic_cabinet" not in lu, "un cabinet sans contrat ne doit pas être inventé"
