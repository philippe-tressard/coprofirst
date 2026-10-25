"""Un espace se lit avec son parent, et les espaces d'un même parent se suivent.

## L'élargissement du 27/08/2026 — signalé à l'écran

La règle ci-dessous ne qualifiait un espace que si son parent portait un
`batiment_id`, au motif — écrit dans son commentaire — que les enfants du parking
ou des locaux techniques « portent déjà des libellés distincts ». C'était vrai du
**seed**, et de lui seul : une « Voie d'accès » créée depuis `/admin/patrimoine`
sous AFUL s'affichait nue, alors que le sélecteur, lui, écrivait « AFUL › Voie
d'accès ». Le même objet avait deux écritures selon l'écran.

Et l'ordre affiché était celui des CLICS, jamais trié : les deux espaces d'un même
bâtiment se retrouvaient séparés par un périmètre étranger —

    Bât. 4 › Logement · Voie d'accès · Bât. 4 › Jardin Bâtiment

au lieu de ce que l'utilisateur a validé, et que le sélecteur affichait déjà :

    Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès

## Pourquoi ce garde-fou (18/08/2026)

Le gabarit du patrimoine pose les **mêmes neuf espaces** sous chaque bâtiment —
Hall, Paliers, Escaliers, Ascenseur, Caves, Toit, Local électrique… Un ticket
visant les toits de deux bâtiments s'affichait donc :

    Toit · Toit

Deux mentions identiques, et rien pour dire de quel bâtiment il s'agit. Signalé à
l'écran, sur une carte de ticket puis, **une seconde fois**, sur le fil d'activité.

## 🔴 Ce que la seconde fois enseigne, et qui est l'objet de ce test

La règle a d'abord été corrigée **côté front** (`front/src/lib/perimetres.ts`).
Le fil d'activité a continué d'afficher « Toit · Toit » — parce que ses libellés
sont calculés **côté serveur** (`app/utils/perimetres.py`) et transportés déjà mis
en forme.

Une même règle, deux implémentations, une seule corrigée : c'est très exactement
ce que la mémoire `project_partage_front_api_impossible` décrit — les contextes de
build sont `./api` et `./front`, rien de la racine n'entre dans les images, et
**le seul pattern viable est la copie plus un test**. Sans ce test, la troisième
occurrence est une question de temps.

⚠️ Ce fichier ne peut pas vérifier le front (il ne s'exécute pas en Python). Il
verrouille la forme **serveur** et **nomme** son jumeau, pour qu'une correction
d'un côté rappelle l'autre.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.perimetre import Perimetre

#  Importé pour ses tables : `create_all` ne peut pas résoudre la clé étrangère
#  `perimetre.modifie_par_id` sans le modèle `Utilisateur` en mémoire.
from app.models.core import Utilisateur  # noqa: F401
from app.utils import perimetres as P
from tests.aides_purge import monter_batiments, vider_patrimoine, vider_perimetres


@pytest.fixture()
def arbre_deux_batiments():
    """Deux bâtiments, chacun avec un « Toit » — le cas qui a produit le défaut."""
    SQLModel.metadata.create_all(engine)
    suffixe = uuid.uuid4().hex[:6]
    codes = []
    with Session(engine) as session:
        #  Par VAGUES : `perimetre` s'auto-référence, un DELETE global viole la
        #  clé sur les enfants dès que les clés sont vérifiées (#546).
        vider_perimetres(session)
        #  🔴 Les bâtiments sont MONTÉS, pas supposés. `Perimetre.batiment_id`
        #  est une clé étrangère : la fixture posait `batiment_id=3` sur un
        #  bâtiment qui n'existait pas, et la base ne disait rien tant qu'elle ne
        #  vérifiait pas ses clés (#546).
        #  ⚠️ Le NUMÉRO du bâtiment et son IDENTIFIANT sont deux choses. Le
        #  premier est ce que le résident lit (« Bât. 3 ») ; le second est la
        #  clé étrangère. La fixture les confondait — elle écrivait
        #  `batiment_id=3` — et ça tenait tant que la base ne vérifiait rien et
        #  que l'auto-incrément partait de 1 sur une table vide. Deux paris, et
        #  le second faussait le libellé dès qu'on montait les bâtiments.
        for numero, batiment_id in zip(("3", "4"), monter_batiments(session, ("3", "4"))):
            bat = f"bat{suffixe}:{numero}"
            noeud_bat = Perimetre(
                code=bat,
                libelle=f"Bâtiment {numero}",
                libelle_court=f"Bât. {numero}",
                description="",
                batiment_id=batiment_id,
                profondeur=0,
                ordre=int(numero),
                actif=True,
                selectionnable=True,
            )
            session.add(noeud_bat)
            #  ⚠️ Le lien de parenté est `parent_id`, un ENTIER — pas un code. Mon
            #  premier jet posait `parent="bat:3"` : SQLModel ignore en silence un
            #  champ qui n'existe pas, l'arbre voyait donc un toit SANS parent, et
            #  le test accusait le code de production d'un défaut qui était le sien.
            #  Il faut donc committer le bâtiment AVANT, pour disposer de son id.
            session.commit()
            session.refresh(noeud_bat)
            toit = f"{bat}/toit"
            session.add(
                Perimetre(
                    code=toit,
                    parent_id=noeud_bat.id,
                    libelle="Toit",
                    libelle_court="Toit",
                    description="",
                    batiment_id=batiment_id,
                    profondeur=1,
                    ordre=1,
                    actif=True,
                    selectionnable=True,
                )
            )
            codes.append((bat, toit))
        session.commit()
    P.invalider_cache()
    yield codes
    with Session(engine) as session:
        #  Le patrimoine ENTIER, bâtiments montés compris : laissés dans la base
        #  du processus, ils attendaient le test suivant (#2223).
        vider_patrimoine(session)
    P.invalider_cache()


def test_deux_toits_ne_se_lisent_plus_pareil(arbre_deux_batiments):
    """« Toit · Toit » devient « Bât. 3 › Toit · Bât. 4 › Toit »."""
    (_, toit3), (_, toit4) = arbre_deux_batiments

    rendu = P.perimetre_label([toit3, toit4])

    assert rendu == "Bât. 3 › Toit · Bât. 4 › Toit", rendu
    #  Le fait, pas le symptôme : les deux mentions doivent être DISTINCTES.
    #  Un test qui n'affirmerait que « ça contient Toit » serait passé au vert sur
    #  le défaut qu'il est censé attraper.
    gauche, droite = rendu.split(" · ")
    assert gauche != droite


def test_un_batiment_entier_garde_son_libelle(arbre_deux_batiments):
    """Seuls les ESPACES sont qualifiés — un bâtiment ne se préfixe pas lui-même."""
    (bat3, _), _ = arbre_deux_batiments

    assert P.perimetre_label_un(bat3) == "Bâtiment 3"


@pytest.fixture()
def arbre_du_ticket():
    """L'arbre EXACT du ticket signalé le 27/08/2026.

    Un regroupement « Bâtiments » qui ne se cible pas, un bâtiment qui porte deux
    espaces, et un nœud transverse (AFUL) qui en porte un — c'est la combinaison
    qui produisait les deux défauts à la fois.
    """
    SQLModel.metadata.create_all(engine)
    suffixe = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        #  Par VAGUES : `perimetre` s'auto-référence, un DELETE global viole la
        #  clé sur les enfants dès que les clés sont vérifiées (#546).
        vider_perimetres(session)

        #  Un REGROUPEMENT : racine, non sélectionnable. Il ne doit jamais préfixer
        #  ses enfants — « Bâtiments › Bât. 4 » n'apprendrait rien.
        groupe = Perimetre(
            code=f"batiments{suffixe}",
            libelle="Bâtiments",
            libelle_court="Bâtiments",
            description="",
            profondeur=0,
            ordre=10,
            actif=True,
            selectionnable=False,
        )
        aful = Perimetre(
            code=f"aful{suffixe}",
            libelle="AFUL",
            libelle_court="AFUL",
            description="",
            profondeur=0,
            ordre=40,
            actif=True,
            selectionnable=True,
            portee_globale=True,
        )
        #  La racine par défaut : c'est elle qu'un contenu SANS périmètre désigne,
        #  et c'est son libellé — pas la chaîne « Copropriété entière » écrite dans
        #  le code — que l'affiche de hall doit imprimer.
        racine = Perimetre(
            code=f"residence{suffixe}",
            libelle="Copropriété entière",
            libelle_court="Copropriété",
            description="",
            profondeur=0,
            ordre=0,
            actif=True,
            selectionnable=True,
            portee_globale=True,
        )
        session.add_all([groupe, aful, racine])
        session.commit()
        session.refresh(groupe)
        session.refresh(aful)

        bat = Perimetre(
            code=f"bat{suffixe}:4",
            parent_id=groupe.id,
            libelle="Bâtiment 4",
            libelle_court="Bât. 4",
            description="",
            #  Monté ici : `batiment_id=4` ne tenait que grâce aux bâtiments que
            #  la fixture voisine laissait dans la base du processus (#2223).
            batiment_id=monter_batiments(session, ("4",))[0],
            profondeur=1,
            ordre=3,
            actif=True,
            selectionnable=True,
        )
        session.add(bat)
        session.commit()
        session.refresh(bat)

        #  `ordre` volontairement NON contigu : c'est la position dans le gabarit
        #  (Logement en 2ᵉ, Jardin Bâtiment en 9ᵉ), et le tri doit s'y conformer.
        espaces = {
            "logement": Perimetre(
                code=f"{bat.code}/logement",
                parent_id=bat.id,
                libelle="Logement",
                libelle_court="Logement",
                description="",
                profondeur=2,
                ordre=1,
                actif=True,
                selectionnable=True,
            ),
            "jardin": Perimetre(
                code=f"{bat.code}/jardin",
                parent_id=bat.id,
                libelle="Jardin Bâtiment",
                libelle_court="Jardin Bât.",
                description="",
                profondeur=2,
                ordre=7,
                actif=True,
                selectionnable=True,
            ),
            "voie": Perimetre(
                code=f"{aful.code}/voie",
                parent_id=aful.id,
                libelle="Voie d'accès",
                libelle_court="Voie d'accès",
                description="",
                profondeur=1,
                ordre=0,
                actif=True,
                selectionnable=True,
            ),
        }
        session.add_all(espaces.values())
        session.commit()
        codes = {nom: n.code for nom, n in espaces.items()}
        codes["bat"] = bat.code
        codes["aful"] = aful.code
    P.invalider_cache()
    yield codes
    with Session(engine) as session:
        #  Le patrimoine ENTIER, bâtiments montés compris : laissés dans la base
        #  du processus, ils attendaient le test suivant (#2223).
        vider_patrimoine(session)
    P.invalider_cache()


def test_un_espace_transverse_est_qualifie_par_son_parent(arbre_du_ticket):
    """« Voie d'accès » ne se lit plus nue : rien ne disait qu'elle est à l'AFUL."""
    assert P.perimetre_label_un(arbre_du_ticket["voie"]) == "AFUL › Voie d'accès"


def test_un_regroupement_ne_prefixe_pas_ses_enfants(arbre_du_ticket):
    """« Bâtiments » est un nœud d'organisation, pas une cible : il ne se dit pas.

    C'est la borne de l'élargissement — sans elle, qualifier « par le parent quel
    qu'il soit » produirait « Bâtiments › Bâtiment 4 » sur tous les écrans.
    """
    assert P.perimetre_label_un(arbre_du_ticket["bat"]) == "Bâtiment 4"


def test_le_rendu_du_ticket_signale(arbre_du_ticket):
    """La chaîne validée par l'utilisateur, au caractère près."""
    codes = [arbre_du_ticket["logement"], arbre_du_ticket["voie"], arbre_du_ticket["jardin"]]

    assert P.perimetre_label(codes) == ("Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès")


def test_l_ordre_des_clics_n_a_plus_d_effet(arbre_du_ticket):
    """Le fait, pas le symptôme : TOUTES les permutations rendent la même chaîne.

    Le défaut venait de là — `PerimetrePicker` stocke l'ordre des clics, et rien
    ne triait ensuite. Un test sur un seul ordre serait passé au vert sur la
    moitié des saisies.
    """
    import itertools

    codes = [arbre_du_ticket["logement"], arbre_du_ticket["voie"], arbre_du_ticket["jardin"]]
    rendus = {P.perimetre_label(list(p)) for p in itertools.permutations(codes)}

    assert len(rendus) == 1, f"le rendu dépend encore de l'ordre de saisie : {rendus}"


def test_un_code_inconnu_est_conserve_et_rejete_a_la_fin(arbre_du_ticket):
    """Un nœud supprimé depuis ne fait pas perdre son badge au contenu."""
    rendu = P.perimetre_label([arbre_du_ticket["voie"], "bat:99"])

    assert rendu == "AFUL › Voie d'accès · Bât. 99", rendu


def test_l_affiche_de_hall_ne_peut_plus_imprimer_un_code_brut(arbre_du_ticket):
    """`perimetre_libelle` — QUATRIÈME table écrite en dur — imprimait le code.

    Elle vivait dans `utils/annonce_hall.py`, connaissait cinq codes (`résidence`,
    `parking`, `cave`, `aful`, le préfixe `bat:`) et rendait `else: le code tel
    quel` : une « Voie d'accès » créée depuis l'administration s'imprimait
    `aful/voie` sur l'affiche du hall, **sur papier**. Elle avait échappé à la
    fusion des trois autres (#316) parce qu'elle portait un autre nom.

    Ce test verrouille le remplacement, y compris son cas vide : « aucun périmètre
    précisé » se lit avec le libellé de la racine par défaut, pris dans l'arbre —
    une copropriété qui la renomme voit son affiche suivre.
    """
    assert P.perimetre_label_liste([arbre_du_ticket["voie"]]) == "AFUL › Voie d'accès"
    assert P.perimetre_label_liste([]) == "Copropriété entière"


def test_le_front_porte_la_meme_regle():
    """Le jumeau TypeScript existe et porte, lui aussi, les deux règles.

    ⚠️ Contrôle de PRÉSENCE, pas d'exécution : ce test ne peut pas lancer le
    module front. Il vérifie que la règle y est écrite et signale son absence —
    ce qui est déjà plus que rien, puisque c'est justement l'oubli d'un des deux
    côtés qui a produit le défaut deux fois.

    ⚠️ Ce qui est cherché doit être ce qui a CHANGÉ. La version précédente
    cherchait `batiment_id` — un mot que `perimetres.ts` porte encore ailleurs
    (l'interface, `perimetreDuBatiment`, `batimentsCibles`) : le jour où la
    qualification a cessé de s'appuyer dessus, ce contrôle serait resté vert en
    affirmant une règle qui n'existait plus. On cherche donc les deux noms qui
    portent réellement la décision.

    Un contrôle qui ne peut pas mesurer doit le DIRE : si le fichier est
    introuvable, ce test échoue au lieu de conclure au vert (`standards/04` §2).
    """
    from pathlib import Path

    jumeau = (
        Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "perimetres" / "libelles.ts"
    )
    assert jumeau.exists(), (
        f"{jumeau} est introuvable : ce contrôle ne peut plus rien établir. "
        "Ne pas lire son silence comme un succès."
    )
    source = jumeau.read_text(encoding="utf-8")
    manquants = [
        nom
        for nom in ("parentQualifiant", "estGroupeRacine", "cheminOrdre", "SEPARATEUR_GROUPE", "›")
        if nom not in source
    ]
    assert not manquants, (
        f"Le front ne porte plus : {', '.join(manquants)}. Les deux implémentations "
        "doivent rester d'accord — la copie est le seul pattern viable entre "
        "`./api` et `./front`, et elle se vérifie ici."
    )
    assert P.SEPARATEUR_GROUPE.strip() in source, (
        "Le séparateur de groupe diffère entre les deux implémentations : le même "
        "contenu se lirait autrement selon l'écran qui l'affiche."
    )
