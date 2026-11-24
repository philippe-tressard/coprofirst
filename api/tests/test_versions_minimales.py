"""La version minimale servie, et ce qu'elle prouve pour la sortie d'une version (#2994).

Une version de production ne sort d'`EN_CIRCULATION` que sous la version minimale que
le serveur SERT à son app, depuis assez longtemps, et si elle la lisait ; une version
de test, quand sa piste ne la distribue plus. Rien d'autre (`contrat/circulation.py`).
"""

from __future__ import annotations

from app.contrat import circulation as circ
from app.contrat import versions_minimales as vm
from app.utils.config_publique import cles_calculees


def _sortie(etiquette="v1.0.0", le="01/06/2027", motif=vm.MOTIF_MINIMALE, lisait=True):
    return circ.VersionSortie("coprofirst-ios", etiquette, le, "essai", motif, lisait)


MINIMALE = {"coprofirst-ios": ("v1.2.0", "01/01/2027")}


def test_une_sortie_prouvee_par_la_version_minimale_passe():
    assert vm.sorties_non_prouvees((_sortie(),), MINIMALE) == []


def test_une_version_qui_ne_lisait_pas_la_minimale_ne_sort_pas():
    assert "ne lisait pas" in vm.sorties_non_prouvees((_sortie(lisait=False),), MINIMALE)[0]


def test_une_version_au_niveau_de_la_minimale_ne_sort_pas():
    assert "n'est pas sous" in vm.sorties_non_prouvees((_sortie("v1.2.0"),), MINIMALE)[0]
    assert "n'est pas sous" in vm.sorties_non_prouvees((_sortie(),), {})[0]


def test_la_minimale_doit_avoir_ete_servie_assez_longtemps():
    trop_tot = _sortie(le="15/01/2027")
    assert "jours exigés" in vm.sorties_non_prouvees((trop_tot,), MINIMALE)[0]


def test_une_sortie_de_piste_de_test_et_un_motif_inconnu():
    assert vm.sorties_non_prouvees((_sortie(motif=vm.MOTIF_TEST, lisait=False),), {}) == []
    assert "inconnu" in vm.sorties_non_prouvees((_sortie(motif="usage faible"),), {})[0]


def test_les_sorties_declarees_sont_prouvees():
    """LE garde-fou sur les vraies déclarations."""
    assert vm.sorties_non_prouvees(circ.SORTIES) == []


def test_une_version_minimale_est_une_version_declaree_d_une_app_connue():
    declarees = {(v.app, v.etiquette) for v in circ.EN_CIRCULATION} | {
        (s.app, s.etiquette) for s in circ.SORTIES
    }
    for app, (etiquette, le) in vm.VERSIONS_MINIMALES.items():
        assert app in circ.APPS, app
        assert (app, etiquette) in declarees, (app, etiquette)
        vm._jour(le)


def test_get_config_sert_une_cle_par_app():
    servies = cles_calculees({})
    for app in circ.APPS:
        attendu = vm.VERSIONS_MINIMALES.get(app, ("", ""))[0]
        assert servies[vm.cle_publique(app)] == attendu
