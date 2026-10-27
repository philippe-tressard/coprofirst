"""Le rapport « Suivi des affaires » du Reporting CS (16/10/2026, maquette D2).

Ce qui est tenu :
- **qui entre** : les affaires que la relance du syndic retient — ni résolues,
  ni annulées, ni archivées, ni absorbées, ni entretien périodique (#2035) —,
  plus seulement celles suivies au kanban, jamais une actualité ;
- **la relance** : jours sans avancée, relances déjà envoyées, `a_relancer` ;
- **le résumé de chaque affaire** : gardé sur l'affaire, sans toucher sa date
  d'avancée, et montré à la place du descriptif ;
- **la porte** : le conseil et l'administration, pas un résident ;
- **l'ancienneté** et ses deux seuils ;
- **les résumés** : tirés de toute la matière de l'affaire (fil compris), aucun
  nom de personne ne part au modèle, la réponse est du texte borné, et le PDF
  comme le courriel échappent tout ce qu'ils reçoivent ;
- **le périmètre** de chaque affaire, tu quand c'est celui par défaut ;
- **la synthèse d'ensemble** (#2034) n'existe plus : ni route, ni PDF.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.description_format import ReponseIllisible
from app.utils.suivi_affaires import resumes as module_resumes
from app.utils.suivi_affaires.format import construire_message, lire_reponse
from app.utils.suivi_affaires.pdf import html_rapport
from app.utils.suivi_affaires.releve import Releve, lire_affaire, tranche
from tests.aides_horloge import il_y_a_jours
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte
from tests.aides_pdf import besoin_weasyprint


#  L'ancienneté se compte en jours civils de Paris : chaque test se rejoue aux deux heures où
#  24 h × N et N jours ne sont pas la même chose (#2257).
pytestmark = pytest.mark.usefixtures("heure_hostile")


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


# ── La porte ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("methode,route", [("get", ""), ("post", "/resumes"), ("post", "/pdf")])
def test_un_resident_est_refuse(moteur, methode, route):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    reponse = getattr(http, methode)(
        f"/suivi-affaires{route}", **({"json": {}} if methode == "post" else {})
    )
    assert reponse.status_code == 403


def test_un_anonyme_est_refuse(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/suivi-affaires").status_code == 401


# ── Qui entre au rapport ────────────────────────────────────────────────────


def test_toutes_les_affaires_non_closes_et_elles_seules(moteur):
    ouverte = affaire_ouverte(moteur, "Ouverte", jours=5)
    suivie = affaire_ouverte(
        moteur, "Chez le prestataire", statut="chez_prestataire", suivi_kanban=True
    )
    non_suivie = affaire_ouverte(
        moteur, "À l'AG", statut="en_ag", categorie="etude_travaux", jours=200
    )
    affaire_ouverte(moteur, "Résolue", statut="résolu")
    affaire_ouverte(moteur, "Annulée", statut="annulé")
    affaire_ouverte(moteur, "Actualité", statut="publie", categorie="actualite")
    #  Ce que la relance écarte, le suivi l'écarte aussi : une seule liste (#2035).
    affaire_ouverte(moteur, "Archivée", archive_manuel=True)
    affaire_ouverte(moteur, "Absorbée", fusionnee_dans_id=ouverte)
    affaire_ouverte(moteur, "Visite sous contrat", categorie="entretien", contrat_id=1)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    corps = http.get("/suivi-affaires").json()

    assert corps["total"] == 3
    assert [a["id"] for a in corps["affaires"]] == [non_suivie, ouverte, suivie]
    assert corps["anciennes"] == 1
    #  Les barres et leur nombre ; les tranches par bâtiment sont tenues par
    #  `test_suivi_repartition.py` (#2043).
    assert [(c["cle"], c["libelle"], c["nombre"]) for c in corps["par_categorie"]] == [
        ("panne", "Panne", 2),
        ("etude_travaux", "Étude & travaux", 1),
    ]
    premiere = corps["affaires"][0]
    assert premiere["anciennete"] == "ancienne"
    assert premiere["age_jours"] == 200
    #  Le descriptif est du TEXTE : l'écran ne fait aucun `{@html}`.
    assert premiere["descriptif"] == "La platine ne sonne plus ."
    #  Sans résumé de l'assistant, l'aperçu est le descriptif.
    assert premiere["apercu"] == premiere["descriptif"] and premiere["apercu_ia"] is False
    assert "resumes_disponibles" in corps and corps["delai_jours"] == 30
    #  Le périmètre par défaut ne se dit pas ; les codes vont au badge de l'écran.
    assert premiere["perimetre_cible"] == ["résidence"]


def test_aucune_affaire_ouverte(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    corps = http.get("/suivi-affaires").json()
    assert corps["total"] == 0 and corps["affaires"] == [] and corps["par_categorie"] == []


@pytest.mark.parametrize(
    "age,attendue",
    [(0, "recente"), (30, "recente"), (31, "moyenne"), (90, "moyenne"), (91, "ancienne")],
)
def test_les_seuils_d_anciennete(age, attendue):
    assert tranche(age) == attendue


# ── Les résumés ─────────────────────────────────────────────────────────


def _releve() -> Releve:
    jour = horloge.aujourd_hui()
    t = Ticket(
        id=7,
        numero="S-7",
        titre="Fuite colonne B",
        description="<p>Plombier mandaté.</p>",
        categorie="panne",
        statut="en_cours",
        perimetre_cible=json.dumps(["batiment_b"]),
        cree_le=il_y_a_jours(40),
        resume_ia="<b>Le syndic</b> attend le devis.",
    )
    return Releve(jour=jour, affaires=[lire_affaire(t, jour, {"en_cours": "Chez le syndic"})])


def test_le_resume_part_de_toute_la_matiere_jamais_d_un_nom(moteur, monkeypatch):
    from app.models.core import MessageTicket, TicketEvolution

    tid = affaire_ouverte(moteur, "Interphone muet", jours=12)
    with Session(moteur) as s:
        t = s.get(Ticket, tid)
        numero = t.numero
        s.add(
            TicketEvolution(
                ticket_id=tid,
                type="commentaire",
                contenu="Le technicien passe jeudi.",
                auteur_id=t.auteur_id,
            )
        )
        s.add(
            MessageTicket(
                ticket_id=tid, contenu="Note du conseil seul", interne=True, auteur_id=t.auteur_id
            )
        )
        s.commit()
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    envoye: dict = {}

    async def faux_demander(session, *, usage, consigne, message, demandeur):
        envoye.update(usage=usage, consigne=consigne, message=message)
        return SimpleNamespace(
            texte=json.dumps({"affaires": {numero: "Le technicien passe jeudi."}})
        )

    monkeypatch.setattr(module_resumes, "demander", faux_demander)
    reponse = http.post("/suivi-affaires/resumes")

    assert reponse.status_code == 200, reponse.text
    assert reponse.json() == {"rediges": 1}
    assert envoye["usage"] == "synthese_affaires_en_cours"
    message = envoye["message"]
    assert f"### {numero} — « Interphone muet »" in message and "(12 jours)" in message
    #  Le FIL part, par rôles ; jamais un nom, jamais un message interne.
    assert "Suite (l'auteur de l'affaire) : Le technicien passe jeudi." in message
    assert "Note du conseil seul" not in message
    assert "Durand" not in message and "Reine" not in message
    assert "JSON" in envoye["consigne"]


def test_sans_affaire_le_resume_le_dit(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    reponse = http.post("/suivi-affaires/resumes")
    assert reponse.status_code == 400
    assert "Aucune affaire" in reponse.json()["detail"]


def test_la_synthese_d_ensemble_n_existe_plus(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.post("/suivi-affaires/synthese").status_code in (404, 405)


def test_le_message_porte_perimetre_description_et_fil():
    message = construire_message(
        "16/10/2026",
        [
            {
                "numero": "S-7",
                "libelle_categorie": "Panne",
                "perimetre": "Bâtiment B",
                "titre": "Fuite colonne B",
                "ouverte_le": "06/09/2026",
                "age_jours": 40,
                "libelle_statut": "Chez le syndic",
                "descriptif": "Plombier mandaté.",
                "fil": "- 10/10/2026 — Suite (le syndic) : devis demandé",
            }
        ],
    )
    assert "### S-7 — « Fuite colonne B »" in message
    assert (
        "périmètre : Bâtiment B · ouverte le 06/09/2026 (40 jours) · état : Chez le syndic."
        in message
    )
    assert "Description : Plombier mandaté." in message
    assert "Fil daté :\n- 10/10/2026 — Suite (le syndic) : devis demandé" in message


def test_le_message_se_borne_aux_plus_anciennes():
    affaires = [
        {
            "numero": f"S-{i}",
            "libelle_categorie": "Panne",
            "titre": f"A{i}",
            "ouverte_le": "01/01/2026",
            "age_jours": 1,
            "libelle_statut": "Ouvert",
            "descriptif": "",
        }
        for i in range(160)
    ]
    message = construire_message("16/10/2026", affaires)
    assert "Affaires ouvertes : 160." in message
    assert "« A149 »" in message and "« A150 »" not in message


def test_une_reponse_sans_resume_d_affaire_est_illisible():
    with pytest.raises(ReponseIllisible):
        lire_reponse('{"resume": "x", "points": ["x"]}')


# ── Le PDF ──────────────────────────────────────────────────────────────────


def test_le_pdf_echappe_tout_ce_qu_il_recoit():
    html = html_rapport(_releve(), site_nom="Résidence <Test>", logo_png=None)
    #  Le résumé vient d'un modèle : il est échappé comme le reste.
    assert "<b>Le syndic</b>" not in html and "&lt;b&gt;Le syndic&lt;/b&gt;" in html
    assert "Résidence &lt;Test&gt;" in html
    assert "Fuite colonne B" in html and "Par catégorie" in html
    assert "line-clamp: 5" in html
    #  Le périmètre de l'affaire, quand ce n'est pas celui par défaut.
    assert "Périmètre : " in html


def test_le_pdf_ne_porte_plus_de_synthese_d_ensemble():
    assert "Synthèse de l'assistant" not in html_rapport(_releve(), site_nom="R", logo_png=None)


@besoin_weasyprint
def test_l_export_rend_un_pdf(moteur):
    affaire_ouverte(moteur, "Interphone muet", jours=3)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    reponse = http.post("/suivi-affaires/pdf")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"
    assert reponse.content.startswith(b"%PDF")
    assert "suivi-des-affaires-" in reponse.headers["content-disposition"]


# ── La relance (#2035) ──────────────────────────────────────────────────────


def test_jours_sans_avancee_et_relances_envoyees(moteur):
    from app.models.core import TicketEvolution

    vieille = affaire_ouverte(moteur, "Sans nouvelles", jours=100)
    recente = affaire_ouverte(moteur, "Avance bien", jours=100)
    with Session(moteur) as s:
        for tid, avancee in ((vieille, 45), (recente, 3)):
            t = s.get(Ticket, tid)
            t.mis_a_jour_le = il_y_a_jours(avancee)
            s.add(t)
        for jours in (60, 45):
            s.add(
                TicketEvolution(
                    ticket_id=vieille,
                    type="relance",
                    contenu="Relance",
                    cree_le=il_y_a_jours(jours),
                )
            )
        s.commit()
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    par_id = {a["id"]: a for a in http.get("/suivi-affaires").json()["affaires"]}

    assert par_id[vieille]["jours_sans_avancee"] == 45 and par_id[vieille]["a_relancer"]
    assert len(par_id[vieille]["relances"]) == 2
    assert par_id[vieille]["relances"] == sorted(par_id[vieille]["relances"])
    assert par_id[recente]["a_relancer"] is False and par_id[recente]["relances"] == []


# ── Le résumé de chaque affaire (#2035) ─────────────────────────────────────


def test_le_resume_de_chaque_affaire_est_garde_sans_dater_une_avancee(moteur, monkeypatch):
    tid = affaire_ouverte(moteur, "Interphone muet", jours=12)
    with Session(moteur) as s:
        numero = s.get(Ticket, tid).numero
        avant = s.get(Ticket, tid).mis_a_jour_le

    async def faux_demander(session, *, usage, consigne, message, demandeur):
        assert numero in message
        return SimpleNamespace(
            texte=json.dumps(
                {"affaires": {numero: "Le syndic attend un devis.", "S-9999": "Inventée."}}
            )
        )

    monkeypatch.setattr(module_resumes, "demander", faux_demander)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.post("/suivi-affaires/resumes").json() == {"rediges": 1}

    with Session(moteur) as s:
        t = s.get(Ticket, tid)
        assert t.resume_ia == "Le syndic attend un devis." and t.resume_ia_le is not None
        #  Un résumé n'est pas une avancée : la relance mesure `mis_a_jour_le`.
        assert t.mis_a_jour_le == avant
    affaire = http.get("/suivi-affaires").json()["affaires"][0]
    assert affaire["apercu"] == "Le syndic attend un devis." and affaire["apercu_ia"] is True


def test_les_resumes_d_affaire_sont_bornes_et_un_illisible_est_ecarte():
    lu = lire_reponse(json.dumps({"affaires": {"S-1": "x" * 900, "S-2": 3}}))
    assert lu == {"S-1": "x" * 400}
    with pytest.raises(ReponseIllisible):
        lire_reponse('{"affaires": "pas un objet"}')


def test_le_courriel_de_relance_lit_le_resume():
    from app.seed.emails import EMAIL_TEMPLATES
    from app.utils.email.rendu import _render as rendre

    corps = next(c for code, _, _, c, _ in EMAIL_TEMPLATES if code == "relance_syndic")
    item = {
        "numero": "S-1",
        "titre": "T",
        "categorie": "panne",
        "priorite": "normale",
        "perimetre": "",
        "relance_count": 0,
        "historique": [],
        "description": "La description",
    }
    ctx = {"residence": {"nom": "R"}, "interlocuteurs": "Madame", "anciennete": "un mois"}
    avec = rendre(
        corps, {**ctx, "tickets": [{**item, "resume": "Le point de situation"}]}, html=True
    )
    sans = rendre(corps, {**ctx, "tickets": [{**item, "resume": ""}]}, html=True)
    assert "Le point de situation" in avec and "La description" not in avec
    assert "La description" in sans


def test_le_resume_est_echappe_dans_le_courriel():
    from app.seed.emails import EMAIL_TEMPLATES
    from app.utils.email.rendu import _render

    corps = next(c for code, _, _, c, _ in EMAIL_TEMPLATES if code == "relance_syndic")
    item = {"numero": "S-1", "titre": "T", "relance_count": 0, "historique": []}
    ctx = {"residence": {"nom": "R"}, "interlocuteurs": "Madame", "anciennete": "un mois"}
    rendu = _render(
        corps, {**ctx, "tickets": [{**item, "resume": "<script>x</script>"}]}, html=True
    )
    assert "<script>x" not in rendu and "&lt;script&gt;" in rendu


def test_le_courriel_numerote_la_relance_qui_part():
    from app.seed.emails import EMAIL_TEMPLATES
    from app.utils.email.rendu import _render

    corps = next(c for code, _, _, c, _ in EMAIL_TEMPLATES if code == "relance_syndic")
    ctx = {"residence": {"nom": "R"}, "interlocuteurs": "Madame", "anciennete": "un mois"}
    item = {"numero": "S-1", "titre": "T", "historique": [], "resume": ""}
    #  Deux relances déjà parties : celle-ci est la troisième.
    assert "Relance n°3" in _render(
        corps, {**ctx, "tickets": [{**item, "relance_count": 2}]}, html=True
    )
    assert "1ère relance" in _render(
        corps, {**ctx, "tickets": [{**item, "relance_count": 0}]}, html=True
    )
