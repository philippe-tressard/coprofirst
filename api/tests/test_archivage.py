"""La règle d'archivage unique — décision ET concordance avec les modèles (#515).

Ce fichier fait **deux** choses, et la seconde est la plus importante.

## 1. La décision — un test par type, comme le demande le point 4

« Sinon la règle sera vraie pour ceux qu'on a regardés. » Les sept types sont
éprouvés, chacun sur son déclencheur propre.

## 2. 🔴 La concordance — ce que la relecture ne peut pas faire

`REGLES` est une déclaration : des noms de champs et des valeurs de statut,
écrits en toutes lettres. Rien, dans le code, n'oblige ces chaînes à
correspondre à quoi que ce soit. Un champ mal orthographié rend `getattr`
silencieux, un statut mal orthographié rend la comparaison silencieusement
fausse. Dans les deux cas la règle **ne lève pas** : elle répond simplement
« non » pour toujours, et l'objet reste éternellement en tête de liste.

C'est précisément la panne que #515 annonçait :

> Une règle générale qui compare des chaînes doit le savoir, sinon elle sera
> vraie pour six objets et fausse pour un — silencieusement.

Les tests ci-dessous confrontent donc chaque déclaration au **modèle réel** :
tout champ déclaré doit exister sur le modèle, tout statut déclaré doit être une
valeur possible de son énumération. C'est ce test qui a révélé que `Idee` ne
possédait aucune date de changement de statut — un manque qu'aucune relecture
n'avait vu, et qui aurait archivé d'un coup toutes les idées anciennes.

⚠️ Ce n'est pas un test de plus, c'est **le** garde-fou du module : sans lui,
`REGLES` est un commentaire exécuté.
"""

from datetime import datetime, timedelta

import pytest

from app.models.communaute import StatutAnnonce
from app.models.tickets import StatutTicket
from app.utils.archivage import (
    ARCHIVAGE_DELAI_JOURS,
    REGLES,
    est_archivable,
)
from app.utils.suivi_actualite import ETATS_SUIVI_ACTUALITE
from tests.aides_archivage import MODELES

#  Une horloge FIXE : sans elle, un test qui passe à 23 h 59 échoue à 0 h 01, et
#  personne ne comprend pourquoi. L'horloge dépréciée de `datetime` n'apparaît nulle part ici.
MAINTENANT = datetime(2026, 8, 20, 12, 0, 0)
VIEUX = MAINTENANT - timedelta(days=ARCHIVAGE_DELAI_JOURS + 1)
RECENT = MAINTENANT - timedelta(days=1)


def archivable(type_objet, **champs):
    """Raccourci : construit un objet nu et interroge la règle.

    Un simple porteur d'attributs suffit — c'est ce que « fonction pure »
    signifie ici, et c'est ce qui rend ces tests exécutables sans base.
    """
    objet = type("Objet", (), champs)()
    return est_archivable(type_objet, objet, maintenant=MAINTENANT)


#  ── 1. LA DÉCISION, TYPE PAR TYPE ───────────────────────────────────────────


#  L'actualité est une affaire de catégorie « Actualité » depuis le 23/09/2026
#  (#1091) : la règle « publication » est partie avec l'entité. Elle n'a plus
#  d'état en cours ni de brouillon — la réserve au conseil en tient lieu.


def test_actualite_publiee_depuis_plus_du_delai():
    assert archivable("actualite", statut="publie", cree_le=VIEUX)


def test_actualite_recente_reste_active():
    assert not archivable("actualite", statut="publie", cree_le=RECENT)


def test_actualite_epinglee_echappe_au_delai():
    #  Décision du 01/08/2026, prise avec le bandeau « Épinglé ».
    assert not archivable("actualite", statut="publie", cree_le=VIEUX, epingle=True)


def test_archivage_manuel_prime_meme_sur_un_objet_du_jour():
    assert archivable("actualite", statut="publie", cree_le=MAINTENANT, archive_manuel=True)


def test_ticket_resolu_accentue_est_bien_reconnu():
    #  🔴 Le cas que #515 désignait comme le piège principal.
    assert archivable("ticket", statut=StatutTicket.résolu, ferme_le=VIEUX)


def test_ticket_annule_est_archive_immediatement():
    assert archivable("ticket", statut=StatutTicket.annulé, ferme_le=MAINTENANT)


def test_ticket_ouvert_ne_s_archive_pas():
    assert not archivable("ticket", statut=StatutTicket.ouvert, cree_le=VIEUX)


def test_une_affaire_archivee_par_le_conseil_quitte_la_liste():
    """📦 remplace la corbeille dans la liste (24/09/2026) : même ouverte, elle part aux Archives."""
    assert archivable("ticket", statut=StatutTicket.ouvert, cree_le=MAINTENANT, archive_manuel=True)
    assert not archivable(
        "ticket", statut=StatutTicket.ouvert, cree_le=MAINTENANT, archive_manuel=False
    )


def test_une_affaire_absorbee_quitte_la_liste_et_pas_sa_principale():
    """🔀 L'absorbée hérite de l'état de la principale — « Chez le syndic » —, et
    deux cartes se lisaient comme deux affaires (#2186). Arbitré le 23/10/2026 :
    elle part aux Archives dès la fusion, la principale reste en vue."""
    absorbee = archivable(
        "ticket", statut=StatutTicket.en_cours, cree_le=MAINTENANT, fusionnee_dans_id=79
    )
    principale = archivable(
        "ticket", statut=StatutTicket.en_cours, cree_le=MAINTENANT, fusionnee_dans_id=None
    )
    assert absorbee and not principale


def test_annonce_vendue_depuis_plus_du_delai():
    assert archivable("annonce", statut=StatutAnnonce.vendu, statut_change_le=VIEUX)


def test_annonce_reservee_reste_visible():
    #  Une réservation peut tomber : l'annonce doit rester sous les yeux de son
    #  auteur, quelle que soit son ancienneté.
    assert not archivable("annonce", statut=StatutAnnonce.reserve, statut_change_le=VIEUX)


def test_annonce_annulee_est_archivee_immediatement():
    assert archivable("annonce", statut=StatutAnnonce.annule, statut_change_le=MAINTENANT)


def test_idee_retenue_apres_le_delai():
    assert archivable("idee", statut="retenue", statut_change_le=VIEUX)


def test_idee_rejetee_laisse_le_temps_de_voir():
    #  « pour laisser le temps de voir aux gens » : rejetée ≠ effacée aussitôt.
    assert not archivable("idee", statut="rejetee", statut_change_le=RECENT)


def test_idee_ouverte_ne_s_archive_pas():
    assert not archivable("idee", statut="ouverte", cree_le=VIEUX)


def test_sondage_archive_apres_la_date_de_cloture():
    assert archivable("sondage", cloture_le=VIEUX)


def test_sondage_dont_la_cloture_est_a_venir_reste_actif():
    #  Écart négatif — géré par le calcul, sans cas particulier.
    assert not archivable("sondage", cloture_le=MAINTENANT + timedelta(days=5))


def test_sondage_sans_date_de_cloture_reste_actif():
    assert not archivable("sondage", cloture_le=None, cree_le=VIEUX)


def test_affiche_de_hall_apres_l_envoi():
    assert archivable("annonce_hall", envoye_le=VIEUX)


def test_affiche_de_hall_jamais_envoyee_reste_en_preparation():
    #  Une affiche préparée et jamais affichée n'a pas commencé sa vie.
    assert not archivable("annonce_hall", envoye_le=None, cree_le=VIEUX)


#  ── 2. LES CAS LIMITES QUI FONT LES FAUX VERTS ──────────────────────────────


def test_etat_terminal_sans_aucune_date_ne_s_archive_pas():
    """On ne sait pas dater la décision : on ne décide donc pas.

    L'inverse — faire disparaître l'objet faute d'information — affirmerait une
    absence sans l'avoir constatée (`standards/04` §1). Un objet resté visible
    se voit et se corrige ; un objet effacé à tort ne se voit pas.
    """
    assert not archivable(
        "ticket", statut=StatutTicket.résolu, ferme_le=None, mis_a_jour_le=None, cree_le=None
    )


def test_type_inconnu_ne_s_archive_pas():
    assert not archivable("licorne", cree_le=VIEUX)


def test_le_delai_est_bien_celui_qu_on_passe():
    """Le seuil est un paramètre, pas une constante lue en douce."""
    objet = type("Objet", (), {"statut": "publie", "cree_le": MAINTENANT - timedelta(days=10)})()
    assert not est_archivable("actualite", objet, seuil_jours=30, maintenant=MAINTENANT)
    assert est_archivable("actualite", objet, seuil_jours=5, maintenant=MAINTENANT)


def test_le_jour_pile_du_seuil_archive():
    """Frontière incluse — sinon un objet resterait un jour de plus que promis."""
    pile = MAINTENANT - timedelta(days=ARCHIVAGE_DELAI_JOURS)
    assert archivable("actualite", statut="publie", cree_le=pile)


#  ── 3. 🔴 LA CONCORDANCE AVEC LES MODÈLES RÉELS ─────────────────────────────

#: Les valeurs de statut possibles, par type. `Idee` n'a **pas** d'énumération
#: côté serveur — son champ est un `str` libre, et `PATCH /idees/{id}/statut`
#: accepte n'importe quelle chaîne. C'est une faiblesse réelle, signalée à part ;
#: en attendant, la liste ci-dessous reprend le commentaire du modèle, qui fait
#: foi faute de mieux.
STATUTS_POSSIBLES = {
    "ticket": {s.value for s in StatutTicket},
    "actualite": {s.value for s in StatutTicket},
    "actualite_suivie": set(ETATS_SUIVI_ACTUALITE),
    "annonce": {s.value for s in StatutAnnonce},
    "idee": {"ouverte", "retenue", "rejetee", "realisee"},
    "sondage": set(),
    "annonce_hall": set(),
    "prestataire": set(),
    "contrat": set(),
}


def test_chaque_type_declare_a_un_modele():
    """Aucune règle orpheline : déclarer, c'est s'engager sur un modèle."""
    assert set(REGLES) == set(MODELES) == set(STATUTS_POSSIBLES)


@pytest.mark.parametrize("type_objet", sorted(REGLES))
def test_les_champs_declares_existent_sur_le_modele(type_objet):
    """Un champ mal orthographié rend `getattr` muet — donc la règle fausse.

    C'est ce test qui a montré que `Idee` n'avait pas de `statut_change_le`
    (migration 0155). Le module en avait besoin, le modèle ne l'avait pas, et
    rien n'aurait signalé l'écart à l'exécution : la règle serait simplement
    retombée sur `cree_le` et aurait archivé les idées à leur anniversaire.
    """
    regle = REGLES[type_objet]
    connus = set(MODELES[type_objet].model_fields)
    #  ⚠️ `champs_peremption` en fait partie depuis #1093 : `visible_jusqu_au`
    #  déclaré et absent du modèle rendrait la péremption muette — `getattr`
    #  retomberait sur `fin`, et l'actualité sortirait du fil à la date de
    #  l'événement au lieu de celle que l'auteur a choisie. Vrai pour les six
    #  autres objets, faux pour celui-là, et silencieux.
    declares = set(regle.champs_date) | set(regle.champs_peremption)
    for champ in (
        regle.champ_statut,
        regle.champ_archive_manuel,
        regle.champ_actif,
        regle.champ_absorbe,
        regle.champ_epingle,
        regle.champ_brouillon,
    ):
        if champ:
            declares.add(champ)
    inconnus = declares - connus
    assert not inconnus, (
        f"{type_objet} : champ(s) déclaré(s) absent(s) du modèle "
        f"{MODELES[type_objet].__name__} : {sorted(inconnus)}"
    )


@pytest.mark.parametrize("type_objet", sorted(REGLES))
def test_les_statuts_declares_sont_des_valeurs_possibles(type_objet):
    """Un statut mal orthographié ne lève pas : il ne correspond jamais.

    Le cas concret : les tickets sont les seuls du site à porter des statuts
    ACCENTUÉS (`résolu`, `annulé`). Écrire `resolu` ici serait invisible en
    relecture et rendrait la règle inopérante pour les tickets seuls.
    """
    regle = REGLES[type_objet]
    possibles = STATUTS_POSSIBLES[type_objet]
    declares = set(regle.statuts_immediats) | set(regle.statuts_terminaux)
    if regle.statut_defaut:
        declares.add(regle.statut_defaut)
    if not possibles:
        assert not declares, f"{type_objet} n'a pas de statut, mais en déclare"
        return
    inconnus = declares - possibles
    assert not inconnus, (
        f"{type_objet} : statut(s) déclaré(s) impossible(s) : {sorted(inconnus)} "
        f"— valeurs réelles : {sorted(possibles)}"
    )


@pytest.mark.parametrize("type_objet", sorted(REGLES))
def test_chaque_regle_explique_son_declencheur(type_objet):
    """Une règle sans phrase est une règle que personne ne pourra expliquer.

    Le texte part dans le manuel utilisateur : le laisser facultatif garantit
    qu'il manquera pour le type ajouté un soir de livraison.
    """
    assert REGLES[type_objet].declencheur.strip(), f"{type_objet} : déclencheur non documenté"


def test_un_statut_immediat_n_est_jamais_aussi_terminal():
    """Les deux listes se contrediraient : immédiat gagne, mais silencieusement.

    Mieux vaut refuser la déclaration ambiguë que laisser deviner l'ordre des
    tests dans le code.
    """
    for type_objet, regle in REGLES.items():
        chevauchement = set(regle.statuts_immediats) & set(regle.statuts_terminaux)
        assert not chevauchement, f"{type_objet} : {sorted(chevauchement)} déclaré deux fois"
