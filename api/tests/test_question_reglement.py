"""Questions au règlement de copropriété — Ma résidence › Règlement (03/10/2026).

Ce qui est tenu ici :

- le texte se charge en versions, et le même contenu n'en crée pas une seconde ;
- le conseil et l'administration passent toujours ; les copropriétaires, seulement
  si l'usage leur est ouvert ; locataires et profils externes jamais (11/10/2026) ;
- un copropriétaire ne lit que SES questions, sans modèle ni coût, et ne publie
  pas dans la FAQ ;
- les fichiers du règlement sont à l'administration SEULE — le conseil ne les lit
  ni ne les dépose — et l'assistant lit tous les Markdown joints, bout à bout ;
- les autres lisent un lien vers le règlement le plus récent qu'ils peuvent lire ;
- le règlement part EN TÊTE du message, la question à la fin (lecture en cache) ;
- chaque extrait cité est RECHERCHÉ dans le texte : un extrait reformulé est
  signalé, un extrait retrouvé reçoit la page et l'acte du texte, pas du modèle ;
- une réponse publiée dans la FAQ l'est une fois, avec le texte relu ;
- la politique de confidentialité nomme la transmission (migration 0256).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.core import (
    CategorieDocument,
    ConfigSite,
    Document,
    FaqItem,
    ProfilAccesDocument,
    RoleUtilisateur,
)
from app.seed.contenus_legaux import ASSISTANT_DEUX_AUTOMATIQUES, QUESTION_REGLEMENT
from app.utils import llm
from app.utils.description_format import ReponseIllisible
from app.utils.question_reglement.extraits import verifier
from app.utils.question_reglement.format import lire_reponse
from app.config import get_settings
from app.utils.question_reglement.documents import CODE_REGLEMENT_PUBLIE
from app.utils.question_reglement.texte import CODE_CATEGORIE, preparer
from tests.aides_base import moteur_memoire
from tests.aides_http import base_http, client_http
from tests.aides_migrations import charger_migration

#: Un règlement FICTIF — le dépôt est public, aucun acte réel n'y entre.
TEXTE = (
    '---\ntitle: "Règlement fictif de la résidence"\n---\n\n'
    "# LIVRE I — Règlement de copropriété (1 janvier 1990)\n\n"
    "**⟦ RCP 1990 — PDF p. 12 — folio 11 ⟧**\n\n"
    "## DESTINATION DE L'IMMEUBLE\n\n"
    "L'immeuble est destiné à l'usage d'habitation bourgeoise. L'exercice de professions "
    "libérales est toutefois toléré dans les appartements à condition de ne pas nuire à "
    "la tranquillité de l'immeuble.\n\n"
    "**⟦ RCP 1990 — PDF p. 13 — folio 12 ⟧**\n\n"
    "Aucun animal bruyant ne pourra être détenu dans les parties privatives. "
    + "Clause de remplissage sans portée particulière. "
    * 25
    + "\n\n# LIVRE II — Modificatif (2 février 1995)\n\n"
    "**⟦ MOD 1995 — PDF p. 3 ⟧**\n\n"
    "Les balcons pourront être fermés par des vérandas après autorisation de l'assemblée.\n"
)

CITATION_VRAIE = (
    "L’exercice de professions libérales est toutefois toléré dans les appartements "
    "à condition de ne pas nuire à la tranquillité de l’immeuble"
)


@pytest.fixture(name="moteur")
def moteur_fixture(monkeypatch, tmp_path):
    """La base, la catégorie des fichiers du règlement, et un disque jetable."""
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    with base_http() as moteur:
        _categorie(moteur, CODE_CATEGORIE, ["syndic"])
        yield moteur


def _categorie(moteur, code: str, roles: list[str]) -> int:
    """La catégorie `code` (créée si absente), d'un profil lisible des `roles`."""
    with Session(moteur) as s:
        cat = s.exec(select(CategorieDocument).where(CategorieDocument.code == code)).first()
        if cat is None:
            profil = ProfilAccesDocument(
                code=f"p-{code}", libelle=code, roles_autorises=json.dumps(roles)
            )
            s.add(profil)
            s.commit()
            cat = CategorieDocument(code=code, libelle=code, profil_acces_id=profil.id)
            s.add(cat)
            s.commit()
        return cat.id


@pytest.fixture()
def assistant(monkeypatch):
    """Un assistant prêt ; `assistant.messages` garde ce qu'il a reçu, et
    `assistant.ouvert` ouvre l'usage aux copropriétaires (fermé par défaut)."""
    messages: list[str] = []
    etat = SimpleNamespace(messages=messages, ouvert=False)

    def config(session, usage=None):
        return SimpleNamespace(
            pret=True, prompt="PROMPT", modele="modele-test", ouvert_coproprietaires=etat.ouvert
        )

    async def demander(session, *, usage, message, consigne=None, **_):
        messages.append(message)
        texte = json.dumps(
            {
                "verdict": "sous_conditions",
                "reponse": "<p>Oui, sans nuire à la tranquillité.</p>",
                "extraits": [
                    {
                        "citation": CITATION_VRAIE,
                        "reference": "Livre I, p. 12",
                        "apport": "Tolérance",
                    },
                    {"citation": "Les professions libérales sont autorisées sans aucune condition"},
                ],
                "reserves": "",
            }
        )
        return SimpleNamespace(texte=texte, jetons_entree=60_000, jetons_sortie=900, jetons_cache=0)

    monkeypatch.setattr(llm, "config_llm", config)
    monkeypatch.setattr(llm, "demander", demander)
    return etat


def _cs(moteur):
    return client_http(moteur, RoleUtilisateur.conseil_syndical)[0]


def _admin(moteur):
    """Seule l'administration charge le texte : les tests qui en ont besoin passent par elle."""
    return client_http(moteur, RoleUtilisateur.admin)[0]


def _joindre(http, moteur, contenu: str = TEXTE, nom: str = "rcp.md"):
    """Joint un fichier du règlement par la route STANDARD des documents."""
    return http.post(
        "/documents",
        data={"titre": nom, "categorie_id": str(_categorie(moteur, CODE_CATEGORIE, []))},
        files={"file": (nom, contenu.encode("utf-8"), "text/markdown")},
    )


# ── Le texte ───────────────────────────────────────────────────────────────


def test_le_meme_texte_sous_windows_et_ailleurs_a_la_meme_empreinte():
    a = preparer(TEXTE, "rcp.md")
    b = preparer("﻿" + TEXTE.replace("\n", "\r\n"), "rcp.md")
    assert a == b
    assert a[1] == "Règlement fictif de la résidence"


@pytest.mark.parametrize(
    "contenu, nom, code",
    [("Trop court.", "rcp.md", 400), ("x" * 1_000_001, "rcp.md", 413)],
    ids=["trop-court", "trop-long"],
)
def test_un_texte_qui_n_est_pas_un_reglement_est_refuse(contenu, nom, code):
    with pytest.raises(HTTPException) as refus:
        preparer(contenu, nom)
    assert refus.value.status_code == code


def test_les_markdown_joints_se_lisent_bout_a_bout_et_font_une_version(moteur, assistant):
    """Tous les .md, dans l'ordre d'ajout ; un PDF joint n'est pas lu ; le même
    contenu ne crée pas une seconde version, un fichier de plus en crée une."""
    admin = _admin(moteur)
    _joindre(admin, moteur)
    suite = "## Modificatif fictif de 2024\n\nLes vélos se rangent au sous-sol.\n"
    _joindre(admin, moteur, suite, "modificatif.md")
    _joindre(admin, moteur, "%PDF-1.4 acte", "acte.pdf")
    premiere = admin.post("/reglement/questions", json={"question": "Puis-je ?"}).json()
    message = assistant.messages[0]
    assert message.index("DESTINATION DE L'IMMEUBLE") < message.index("Les vélos se rangent")
    assert "%PDF" not in message
    seconde = admin.post("/reglement/questions", json={"question": "Et ici ?"}).json()
    assert seconde["texte_id"] == premiere["texte_id"]
    _joindre(admin, moteur, suite + "Ajout.\n", "ajout.md")
    assert all(not q["texte_en_vigueur"] for q in admin.get("/reglement/questions").json())


# ── Les droits ─────────────────────────────────────────────────────────────


def _refuse_partout(http, moteur, attendu: int) -> None:
    assert http.get("/reglement").status_code == attendu
    assert http.get("/reglement/questions").status_code == attendu
    assert _joindre(http, moteur).status_code == attendu
    assert http.post("/reglement/questions", json={"question": "Puis-je ?"}).status_code == attendu


@pytest.mark.parametrize("ouvert", [False, True], ids=["usage-ferme", "usage-ouvert"])
@pytest.mark.parametrize("role", [None, RoleUtilisateur.résident, RoleUtilisateur.externe])
def test_locataires_et_profils_externes_ne_passent_jamais(moteur, assistant, role, ouvert):
    """Le locataire (résident) et le mandataire ou le syndic (externe) restent dehors,
    même usage ouvert : c'est la règle du carnet d'entretien."""
    assistant.ouvert = ouvert
    http, _ = client_http(moteur, role)
    attendu = 401 if role is None else 403
    _refuse_partout(http, moteur, attendu)
    assert http.get("/reglement/acces").status_code == attendu
    assert assistant.messages == []


def test_usage_ferme_le_coproprietaire_est_refuse_et_l_onglet_le_sait(moteur, assistant):
    _joindre(_admin(moteur), moteur)
    proprio, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert proprio.get("/reglement/acces").json() == {"acces": False}
    _refuse_partout(proprio, moteur, 403)
    assert assistant.messages == []
    #  Le conseil, lui, entre toujours.
    assert _cs(moteur).get("/reglement/acces").json() == {"acces": True}
    assert _cs(moteur).get("/reglement").status_code == 200


def test_usage_ouvert_le_coproprietaire_ne_lit_que_ses_questions(moteur, assistant):
    assistant.ouvert = True
    admin = _admin(moteur)
    _joindre(admin, moteur)
    admin.post("/reglement/questions", json={"question": "Question du conseil ?"})
    proprio, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert proprio.get("/reglement/acces").json() == {"acces": True}

    posee = proprio.post("/reglement/questions", json={"question": "Puis-je exercer ?"})
    assert posee.status_code == 201
    #  Ni le modèle ni le coût : il lit l'avis, pas son exploitation.
    assert posee.json()["modele"] is None and posee.json()["cout_usd"] is None
    (mienne,) = proprio.get("/reglement/questions").json()
    assert mienne["question"] == "Puis-je exercer ?"
    assert voisin.get("/reglement/questions").json() == []
    #  Le conseil les lit toutes, avec l'auteur et le modèle.
    toutes = _cs(moteur).get("/reglement/questions").json()
    assert len(toutes) == 2 and all(q["modele"] == "modele-test" for q in toutes)
    assert len({q["auteur_nom"] for q in toutes}) == 2


def test_le_coproprietaire_ne_publie_ni_ne_charge_ni_ne_lie(moteur, assistant):
    assistant.ouvert = True
    _joindre(_admin(moteur), moteur)
    proprio, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    q = proprio.post("/reglement/questions", json={"question": "Puis-je ?"}).json()
    corps = {"categorie": "Règlement", "question": "Puis-je ?", "reponse": "<p>Relue.</p>"}
    assert proprio.post(f"/reglement/questions/{q['id']}/faq", json=corps).status_code == 403
    assert _joindre(proprio, moteur, TEXTE + "\nAutre.").status_code == 403
    assert proprio.delete(f"/reglement/questions/{q['id']}").status_code == 403
    #  Il ne sait pas où les fichiers se déposent.
    etat = proprio.get("/reglement").json()
    assert etat["texte_disponible"] is True and etat["categorie_id"] is None
    #  Le conseil publie la question du copropriétaire.
    assert _cs(moteur).post(f"/reglement/questions/{q['id']}/faq", json=corps).status_code == 200


def test_les_fichiers_du_reglement_sont_a_l_administration_seule(moteur, assistant):
    """Le conseil interroge et publie ; il ne lit, ne joint ni ne retire les fichiers
    que l'assistant lit — la règle vit dans `visibility.CATEGORIES_ADMIN_SEUL`."""
    cs, admin = _cs(moteur), _admin(moteur)
    assert _joindre(cs, moteur).status_code == 403
    doc = _joindre(admin, moteur).json()
    cat = _categorie(moteur, CODE_CATEGORIE, [])
    assert cs.get(f"/documents?categorie_id={cat}").json() == []
    assert cs.get(f"/documents/{doc['id']}/télécharger").status_code in (403, 404)
    assert cs.patch(f"/documents/{doc['id']}", json={"titre": "x"}).status_code == 403
    assert cs.delete(f"/documents/{doc['id']}").status_code == 403
    assert CODE_CATEGORIE not in {c["code"] for c in cs.get("/documents/categories").json()}
    assert cs.get("/reglement").json()["categorie_id"] is None
    assert admin.get("/reglement").json()["categorie_id"] == cat
    assert [d["id"] for d in admin.get(f"/documents?categorie_id={cat}").json()] == [doc["id"]]
    assert admin.delete(f"/documents/{doc['id']}").status_code == 204
    assert admin.get("/reglement").json()["texte_disponible"] is False


def test_seule_l_administration_supprime_une_question(moteur, assistant):
    admin = _admin(moteur)
    _joindre(admin, moteur)
    cs = _cs(moteur)
    identifiant = admin.post("/reglement/questions", json={"question": "Puis-je ?"}).json()["id"]
    assert cs.delete(f"/reglement/questions/{identifiant}").status_code == 403
    assert len(cs.get("/reglement/questions").json()) == 1
    assert admin.delete(f"/reglement/questions/{identifiant}").status_code == 204
    assert cs.get("/reglement/questions").json() == []
    assert admin.delete(f"/reglement/questions/{identifiant}").status_code == 404


def test_sans_texte_la_question_ne_part_pas(moteur, assistant):
    reponse = _cs(moteur).post("/reglement/questions", json={"question": "Puis-je ?"})
    assert reponse.status_code == 400
    assert assistant.messages == []


# ── La réponse ─────────────────────────────────────────────────────────────


def test_le_reglement_part_en_tete_et_la_question_a_la_fin(moteur, assistant):
    http = _admin(moteur)
    _joindre(http, moteur)
    assert (
        http.post("/reglement/questions", json={"question": "Puis-je exercer ?"}).status_code == 201
    )
    message = assistant.messages[0]
    assert message.index("DESTINATION DE L'IMMEUBLE") < message.index(
        "Question : Puis-je exercer ?"
    )
    assert message.rstrip().endswith("Puis-je exercer ?")


def test_chaque_extrait_est_verifie_et_situe_par_le_code(moteur, assistant):
    http = _admin(moteur)
    _joindre(http, moteur)
    q = http.post("/reglement/questions", json={"question": "Puis-je exercer ?"}).json()
    assert q["verdict"] == "sous_conditions"
    assert q["verdict_libelle"] == "Oui, sous conditions"
    vrai, faux = q["extraits"]
    assert vrai["verifie"] is True
    assert vrai["page"] == "RCP 1990 — PDF p. 12 — folio 11"
    assert vrai["acte"] == "LIVRE I"
    assert vrai["reference"] == "Livre I, p. 12"  # celle du modèle reste visible
    assert faux["verifie"] is False and faux["page"] is None
    assert q["texte_en_vigueur"] is True and q["modele"] == "modele-test"


def test_une_reponse_garde_la_version_qu_elle_a_lue(moteur, assistant):
    http = _admin(moteur)
    _joindre(http, moteur)
    http.post("/reglement/questions", json={"question": "Puis-je exercer ?"})
    _joindre(http, moteur, "Version corrigée.\n", "correction.md")
    (ancienne,) = http.get("/reglement/questions").json()
    assert ancienne["texte_en_vigueur"] is False


def test_un_extrait_coupe_ou_a_cheval_sur_deux_pages_est_retrouve():
    coupe = "L'immeuble est destiné à l'usage d'habitation bourgeoise […] professions libérales"
    a_cheval = "la tranquillité de l'immeuble. Aucun animal bruyant ne pourra être détenu"
    court = "de la […] à la"
    e_coupe, e_cheval, e_court = verifier(
        TEXTE, [{"citation": coupe}, {"citation": a_cheval}, {"citation": court}]
    )
    assert e_coupe.verifie and e_coupe.page == "RCP 1990 — PDF p. 12 — folio 11"
    assert e_cheval.verifie
    assert not e_court.verifie  # un fragment trop court ne prouve rien
    (modif,) = verifier(TEXTE, [{"citation": "Les balcons pourront être fermés par des vérandas"}])
    assert modif.acte == "LIVRE II" and modif.page == "MOD 1995 — PDF p. 3"


def test_un_verdict_inconnu_devient_incertain_et_une_reponse_vide_est_refusee():
    lu = lire_reponse(json.dumps({"verdict": "peut-être", "reponse": "<p>Voir.</p>"}))
    assert lu["verdict"] == "incertain" and lu["extraits"] == []
    with pytest.raises(ReponseIllisible):
        lire_reponse(json.dumps({"verdict": "oui", "reponse": ""}))


# ── La FAQ ─────────────────────────────────────────────────────────────────


def test_une_reponse_relue_se_publie_une_fois_dans_la_faq(moteur, assistant):
    http = _admin(moteur)
    _joindre(http, moteur)
    q = http.post("/reglement/questions", json={"question": "Puis-je exercer ?"}).json()
    corps = {
        "categorie": "Règlement",
        "question": "Profession libérale ?",
        "reponse": "<p>Relue.</p>",
    }
    publiee = http.post(f"/reglement/questions/{q['id']}/faq", json=corps).json()
    with Session(moteur) as s:
        item = s.exec(select(FaqItem)).one()
    assert publiee["faq_item_id"] == item.id and item.reponse == "<p>Relue.</p>"
    assert http.post(f"/reglement/questions/{q['id']}/faq", json=corps).status_code == 409


# ── La politique de confidentialité (migration 0256) ───────────────────────


def _politique_apres(
    sens: list[str], depart: str, migration: str = "0256_questions_reglement"
) -> str:
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(
            text("INSERT INTO config_site VALUES ('politique_confidentialite', :v)"), {"v": depart}
        )
    for s in sens:
        with m.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(charger_migration(migration), s)()
    with m.connect() as conn:
        return conn.execute(text("SELECT valeur FROM config_site")).scalar()


def test_la_politique_servie_nomme_la_transmission_une_seule_fois():
    depart = "<li>Assistant. " + ASSISTANT_DEUX_AUTOMATIQUES + "</li>"
    deux_fois = _politique_apres(["upgrade", "upgrade"], depart)
    assert deux_fois.count(QUESTION_REGLEMENT) == 1
    assert _politique_apres(["upgrade", "downgrade"], depart) == depart


# ── Le lien vers le règlement publié (11/10/2026) ──────────────────────────


def _document(moteur, roles: list[str], auteur_id: int, titre: str) -> int:
    """Un document de la catégorie du règlement publié, lisible des `roles`."""
    with Session(moteur) as s:
        categorie_id = _categorie(moteur, CODE_REGLEMENT_PUBLIE, ["propriétaire"])
        profil = ProfilAccesDocument(
            code=f"p-{titre}", libelle=titre, roles_autorises=json.dumps(roles)
        )
        s.add(profil)
        s.commit()
        doc = Document(
            titre=titre,
            fichier_nom="acte.pdf",
            fichier_chemin="/inexistant/acte.pdf",
            categorie_id=categorie_id,
            profil_acces_override_id=profil.id,
            publie_par_id=auteur_id,
        )
        s.add(doc)
        s.commit()
        return doc.id


def test_les_autres_lisent_un_lien_vers_le_reglement_le_plus_recent(moteur, assistant):
    """Aucun numéro dans le code : le plus récent de la catégorie, s'il est lisible."""
    assistant.ouvert = True
    admin, admin_id = client_http(moteur, RoleUtilisateur.admin)
    proprio, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert proprio.get("/reglement").json()["lien_reglement"] is None
    ancien = _document(moteur, ["propriétaire"], admin_id, "original")
    lisible = _document(moteur, ["propriétaire"], admin_id, "consolide")
    _document(moteur, ["conseil_syndical"], admin_id, "reserve")
    assert ancien != lisible
    assert proprio.get("/reglement").json()["lien_reglement"] == f"/residence#doc-{lisible}"
    assert admin.get("/reglement").json()["lien_reglement"] is None


def test_l_ouverture_aux_coproprietaires_se_lit_dans_la_configuration_de_l_usage(moteur):
    """Sans substitut de l'assistant : la case de l'administration, et elle seule."""
    from app.utils.llm import config_llm
    from app.utils.llm_usages import CHAMP_COPROPRIETAIRES, USAGES, champs
    from app.utils.question_reglement.format import USAGE_QUESTION_REGLEMENT

    usage = USAGES[USAGE_QUESTION_REGLEMENT]
    with Session(moteur) as s:
        assert config_llm(s, USAGE_QUESTION_REGLEMENT).ouvert_coproprietaires is False
        s.add(ConfigSite(cle=usage.cle(CHAMP_COPROPRIETAIRES), valeur="1"))
        s.commit()
        assert config_llm(s, USAGE_QUESTION_REGLEMENT).ouvert_coproprietaires is True
    #  Seul cet usage porte la case : l'écran ne la montre nulle part ailleurs.
    ouvrables = [u.code for u in USAGES.values() if CHAMP_COPROPRIETAIRES in champs(u)]
    assert ouvrables == [USAGE_QUESTION_REGLEMENT]


def test_la_politique_servie_dit_que_les_coproprietaires_interrogent_le_reglement():
    """La 0279 remplace le paragraphe de la 0256 — une fois, et se défait."""
    migration = "0279_politique_reglement_coproprietaires"
    avant = charger_migration(migration).AVANT
    depart = "<li>Assistant. " + avant + ASSISTANT_DEUX_AUTOMATIQUES + "</li>"
    deux_fois = _politique_apres(["upgrade", "upgrade"], depart, migration)
    assert deux_fois.count(QUESTION_REGLEMENT) == 1 and avant not in deux_fois
    assert "copropriétaire" in QUESTION_REGLEMENT
    assert _politique_apres(["upgrade", "downgrade"], depart, migration) == depart
