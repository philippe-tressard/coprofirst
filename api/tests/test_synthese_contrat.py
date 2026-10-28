"""La synthèse proposée d'un contrat — ce qu'on envoie, et ce qu'on n'envoie pas.

## Ce que ce test protège

1. **Le geste n'est proposé que s'il a un sens** : assistant configuré, et
   matière à lire. Une icône qui échoue toujours est pire qu'une icône absente.
2. **Le gabarit en sept sections est imposé**, pas suggéré : c'est le format du
   carnet d'entretien de cette copropriété, pas celui qu'un modèle trouverait
   joli.
3. **Les synthèses déjà écrites servent d'exemples** — c'est ce qui fait que la
   proposition ressemble à celles du conseil syndical, et pas à un texte générique.
4. **Rien n'est enregistré.** Le modèle propose ; le conseil syndical relit et
   valide. Une synthèse fausse au carnet d'entretien serait pire que pas de
   synthèse : ce carnet est un document réglementaire (décret n° 2001-477).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.core import ConfigSite
from app.utils.synthese_contrat import (
    GABARIT,
    CONSIGNE,
    CONSIGNE_CITATIONS,
    construire_matiere,
    construire_message,
    documents_du_contrat,
    exemples,
    synthese_disponible,
)


@pytest.fixture()
def session(session):
    session.add(Prestataire(id=1, nom="5M Services", specialite="ascenseur"))
    session.commit()
    return session


def _config(session, **kw):
    #  Les DEUX étages (#984) : le commun, et l'usage `synthese_contrat` avec
    #  son activation et son modèle — un usage sans modèle ne part pas.
    valeurs = {
        "llm_actif": "1",
        "llm_api_key": "sk-x",
        "llm_envoi_document": "1",
        "llm_synthese_contrat_actif": "1",
        "llm_synthese_contrat_modele": "gpt-4o-mini",
    }
    valeurs.update(kw)
    for cle, valeur in valeurs.items():
        existant = session.get(ConfigSite, cle)
        if existant:
            existant.valeur = valeur
            session.add(existant)
        else:
            session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()


def _contrat(session, libelle="Ascenseur Bât. 1", **kw):
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=1,
        libelle=libelle,
        date_debut=date(2024, 1, 1),
        **kw,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _document(session, contrat, **kw):
    kw.setdefault("titre", "Contrat")
    kw.setdefault("fichier_cle", "prive/introuvable.pdf")
    d = Document(
        fichier_nom="c.pdf",
        mime_type="application/pdf",
        contrat_id=contrat.id,
        publie_par_id=1,
        **kw,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


# ── 1. Quand le geste est-il proposé ? ──────────────────────────────────────


def test_sans_assistant_configuré_le_geste_n_est_PAS_proposé(session):
    c = _contrat(session)
    _document(session, c)
    _config(session, llm_actif="0")
    assert synthese_disponible(session, c) is False


def test_sans_clé_le_geste_n_est_PAS_proposé(session):
    """Une icône qui échoue toujours est pire qu'une icône absente."""
    c = _contrat(session)
    _document(session, c)
    _config(session, llm_api_key="")
    assert synthese_disponible(session, c) is False


def test_sans_document_le_geste_n_est_PAS_proposé(session):
    """Quatre sections sur sept resteraient vides : montants, prestations
    incluses et exclues ne vivent que dans le PDF."""
    c = _contrat(session)
    _config(session)
    assert synthese_disponible(session, c) is False


def test_sans_document_MAIS_envoi_désactivé_le_geste_reste_proposé(session):
    """La synthèse est alors partielle — et c'est un choix assumé de
    l'administration, pas un accident."""
    c = _contrat(session)
    _config(session, llm_envoi_document="0")
    assert synthese_disponible(session, c) is True


def test_TOUS_les_documents_du_contrat_sont_lus(session):
    """🔴 Un contrat en a PLUSIEURS, et c'est le cas normal (signalé à l'écran).

    Contrat initial, avenants, conditions générales, attestation. N'en lire
    qu'un produirait une synthèse fausse dès le premier avenant : les conditions
    financières y changent, et la section 6 annoncerait l'ancien prix.
    """
    c = _contrat(session)
    initial = _document(session, c)
    avenant = _document(session, c)
    lus = documents_du_contrat(session, c)
    assert [d.id for d in lus] == [initial.id, avenant.id]


def test_l_ordre_est_CHRONOLOGIQUE_car_un_avenant_modifie_ce_qui_précède(session):
    """Ce qui vient après amende ce qui précède : l'ordre porte le sens, on ne
    trie donc ni par titre ni par taille."""

    c = _contrat(session)
    recent = _document(session, c, publie_le=datetime(2026, 5, 1))
    ancien = _document(session, c, publie_le=datetime(2024, 1, 1))
    assert [d.id for d in documents_du_contrat(session, c)] == [ancien.id, recent.id]


def test_un_document_DÉSIGNÉ_qui_n_est_PAS_du_contrat_est_ignoré(session):
    """🔴 Le défaut du 17/09/2026, signalé à l'écran.

    Ce test remplace `…_vient_en_tête_s_il_n_est_pas_déjà_joint`, qui
    verrouillait le défaut : il posait un document SANS `contrat_id` et exigeait
    qu'il soit lu. Un document rattaché au contrat figure déjà dans la requête,
    donc cette branche ne pouvait s'ouvrir que sur un document étranger — celui
    d'un autre contrat, envoyé au service et nommé dans l'encart.

    La règle et ses autres cas vivent dans `test_document_designe.py`.
    """
    c = _contrat(session)
    sien = _document(session, c, titre="Contrat de maintenance ascenseur")
    etranger = Document(
        titre="Entretien toitures Bat 2",
        fichier_nom="toitures.pdf",
        mime_type="application/pdf",
        publie_par_id=1,
    )
    session.add(etranger)
    session.commit()
    session.refresh(etranger)
    c.document_id = etranger.id
    session.add(c)
    session.commit()
    assert [d.id for d in documents_du_contrat(session, c)] == [sien.id]


# ── 2. Ce qu'on envoie ──────────────────────────────────────────────────────


def test_les_synthèses_existantes_servent_d_EXEMPLES(session):
    """Le format s'apprend des synthèses de la maison, il ne se décrit pas."""
    _contrat(
        session,
        "Ancien",
        notes="1. Identification du fournisseur\n- Untel",
        type_equipement="ascenseur",
    )
    c = _contrat(session, type_equipement="ascenseur")
    assert exemples(session, c) == ["1. Identification du fournisseur\n- Untel"]

    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "Untel" in message
    assert "déjà rédigées" in message


def test_un_contrat_du_MÊME_équipement_passe_devant(session):
    """Une synthèse d'ascenseur ressemble plus à une autre synthèse d'ascenseur
    qu'à celle d'un contrat d'espaces verts."""
    _contrat(session, "Vert", notes="SYNTHÈSE ESPACES VERTS", type_equipement="espaces_verts")
    _contrat(session, "Asc", notes="SYNTHÈSE ASCENSEUR", type_equipement="ascenseur")
    c = _contrat(session, type_equipement="ascenseur")
    assert exemples(session, c)[0] == "SYNTHÈSE ASCENSEUR"


def test_sans_texte_lisible_on_le_DIT_au_modèle(session):
    """⚠️ Sans cette phrase, le modèle comble les sections manquantes par des
    formules plausibles — le défaut exact que la consigne interdit."""
    c = _contrat(session)
    _document(session, c)  # chemin introuvable : aucun texte extrait
    _config(session)
    message = construire_message(session, c, avec_document=True)
    assert "Aucun texte de contrat n'a pu être lu" in message
    assert "non précisé dans les éléments fournis" in message


def test_les_champs_connus_de_la_base_partent_toujours(session):
    c = _contrat(
        session, numero_contrat="AB123", duree_initiale_valeur=3, duree_initiale_unite="ans"
    )
    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "5M Services" in message
    assert "AB123" in message
    assert "3 ans" in message


#  ── La source des faits est CE contrat, et rien d'autre ───────────────────
#
#  🔴 Demandé le 11/09/2026 après le premier essai. Le risque n'est pas
#  théorique : trois synthèses d'AUTRES contrats voyagent dans le même message
#  comme exemples de format, et un modèle qui les lit peut en reprendre un
#  montant ou une durée. Rien, à la relecture, ne distinguerait alors un chiffre
#  emprunté d'un chiffre lu — et la synthèse alimente le carnet d'entretien,
#  qui est réglementaire (décret n° 2001-477). Ce que la consigne en dit est
#  tenu par `EXIGENCES_CONSIGNE` (section 3) ; ce que le message en dit, ici.


def test_les_exemples_s_annoncent_comme_UN_FORMAT_pas_comme_des_faits(session):
    """Le bloc d'exemples doit se désigner lui-même comme un modèle de rédaction
    portant sur d'AUTRES contrats — sinon il se lit comme de la matière."""
    autre = _contrat(session, libelle="Ascenseur Bât. 2", notes="1. Fournisseur : ACME")
    assert autre.notes
    c = _contrat(session)
    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "AUTRES" in message
    assert "n'en reprends AUCUN fait" in message


#  ── Un PDF sans couche de texte part TEL QUEL ─────────────────────────────
#
#  🔴 C'est le cas NORMAL, pas l'exception : un contrat signé est numérisé. Les
#  deux PDF du contrat de porte de parking rendaient zéro caractère à `pypdf`
#  (mesuré en production le 11/09/2026, 2 pages et 1 page, 212 et 417 Ko).


def _pdf_sans_texte(tmp_path, nom="scan.pdf"):
    """Un PDF valide dont aucune page ne porte de texte — comme une numérisation."""
    from pypdf import PdfWriter

    chemin = tmp_path / nom
    ecrivain = PdfWriter()
    ecrivain.add_blank_page(width=595, height=842)
    with open(chemin, "wb") as f:
        ecrivain.write(f)
    return nom  # la clé : `tmp_path` est la racine du stockage (`disque_jetable`)


def test_un_pdf_sans_texte_est_JOINT_au_lieu_d_etre_abandonne(session, disque_jetable):
    c = _contrat(session)
    _document(session, c, titre="Contrat signé", fichier_cle=_pdf_sans_texte(disque_jetable))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert len(m.fichiers) == 1
    assert m.joints == ("Contrat signé",)
    assert m.lus_en_texte == ()
    #  Et le message DIT au modèle de les lire lui-même, sinon il ne sait pas
    #  qu'il a reçu autre chose que du texte.
    assert "lis-les toi-même" in m.message
    #  ⚠️ Surtout, il ne porte PLUS la phrase qui ordonne de rendre les sections
    #  vides : elle ferait rendre « non précisé » alors que le contrat est joint.
    assert "Aucun texte de contrat n'a pu être lu" not in m.message


def test_un_pdf_LISIBLE_part_en_texte_et_pas_en_fichier(session, tmp_path):
    """Joindre un fichier dont le texte s'extrait coûterait bien plus cher pour
    exactement le même contenu."""
    c = _contrat(session)
    d = _document(session, c, titre="Contrat natif")
    _config(session)
    #  `texte_du_document` rend du texte : on simule un PDF avec couche texte.
    import app.utils.synthese_contrat as mod

    origine = mod.texte_du_document
    mod.texte_du_document = lambda doc: "ARTICLE 1 — Objet du contrat"
    try:
        m = construire_matiere(session, c, avec_document=True)
    finally:
        mod.texte_du_document = origine
    assert d.titre
    assert m.fichiers == ()
    assert m.lus_en_texte == ("Contrat natif",)


def test_un_fichier_ABSENT_est_ecarte_avec_son_motif(session):
    """Le chemin des fixtures est introuvable : ni texte, ni fichier joignable."""
    c = _contrat(session)
    _document(session, c, titre="Fantôme")
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Fantôme", "illisible ou trop volumineux"),)


def test_un_fichier_TROP_LOURD_n_est_pas_joint(session, disque_jetable, monkeypatch):
    """Une requête trop lourde est refusée par le service — et le base64
    l'alourdit encore d'un tiers. Mieux vaut l'écarter en le disant."""
    import app.utils.synthese_contrat as mod

    monkeypatch.setattr(mod, "MAX_OCTETS_DOCUMENT_JOINT", 10)
    c = _contrat(session)
    _document(session, c, titre="Plan", fichier_cle=_pdf_sans_texte(disque_jetable))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Plan", "illisible ou trop volumineux"),)


# ── 3. Ce que la consigne EXIGE ────────────────────────────────────────────
#
#  Une phrase par exigence, et sa raison en une ligne. Seize tests ne faisaient
#  que `assert "<phrase>" in CONSIGNE` : réunis ici, l'échec les nomme TOUTES,
#  au lieu de s'arrêter à la première.

EXIGENCES_CONSIGNE: dict[str, str] = {
    #  ── Ne rien inventer, et rendre au format du champ de notes (#901) ──
    "n'invente jamais": (
        "🔴 le point qui compte le plus : une synthèse plausible mais fausse, dans un "
        "document réglementaire, est le pire résultat possible (#901)"
    ),
    "non précisé dans les éléments fournis": (
        "une section vide se dit vide, elle ne se comble pas d'une formule plausible (#901)"
    ),
    "<h3>": "les notes sont un champ ENRICHI : balise que `sanitize.ts` et Tiptap relisent (#901)",
    "<ul><li>": "du texte brut à tirets arriverait en un seul paragraphe (#901)",
    "<p>": "balise de paragraphe que le champ de notes accepte (#901)",
    "Markdown": "le Markdown n'est pas rendu par le champ de notes : la consigne l'écarte (#901)",
    #  ── La source des faits est CE contrat, et rien d'autre (#903) ──
    "CE contrat": "les exemples d'AUTRES contrats ne sont pas une source de faits (#903)",
    "connaissance générale": "un chiffre « habituel » n'est pas un chiffre lu (#903)",
    "habituel": "un montant ou une durée d'usage ne se substitue pas au contrat (#903)",
    "COPROPRIÉTÉ": (
        "le domaine cadre la lecture : ce qui compte est ce que la copropriété devra "
        "surveiller, pas un résumé commercial (#903)"
    ),
    #  ── La citation, ce qui rend la synthèse VÉRIFIABLE (#905) ──
    #  🔴 11/09/2026, proposé par Philippe après le premier essai. Un montant sans
    #  la phrase qui le porte oblige à rouvrir le PDF pour le contrôler — c'est-à-
    #  dire à refaire le travail. Avec la citation, une erreur du modèle saute aux
    #  yeux : la citation ne dit pas ce que la puce affirme.
    "phrase EXACTE": "une citation sous chaque fait chiffré, mot pour mot (#905)",
    "guillemets": "la citation se distingue de la reformulation (#905)",
    "montant": "un montant est un fait chiffré qui exige sa citation (#905)",
    "préavis": "un préavis est un fait chiffré qui exige sa citation (#905)",
    "Si tu ne peux pas citer": (
        "la citation rend constatable l'interdiction d'inventer : un fait qu'on ne peut "
        "pas citer n'a pas été lu (#905)"
    ),
    "HT ou TTC": "« 390 € HT/an » n'est pas « environ 390 € » : l'unité EST l'information (#905)",
    "en supplément": "une option chiffrée n'est pas une prestation incluse (#905)",
    #  ── Les EXTRAITS des clauses citées (17/09/2026, #991) ──
    #  🔴 Demandé après les premières synthèses réelles : la citation prouve UNE
    #  ligne, l'extrait donne la clause ENTIÈRE (trente lignes au plus).
    "8. Extraits des clauses citées": "une HUITIÈME section, d'extraits (#991)",
    "Respecte EXACTEMENT ces sept sections": (
        "la huitième s'ajoute APRÈS les sept, qui restent imposées mot pour mot (#991)"
    ),
    "ne remplace aucune des sept autres": "l'extrait s'ajoute, il ne remplace rien (#991)",
    "TRENTE LIGNES AU PLUS": (
        "sans borne, une clause recopiée mangerait le plafond de jetons de la synthèse (#991)"
    ),
    "coupe à la fin d'une phrase": "un extrait borné se coupe à la fin d'une phrase (#991)",
    "milieu d'un montant": (
        "une coupure au milieu d'un montant dirait autre chose que le contrat (#991)"
    ),
    "non reproduit dans les éléments fournis": (
        "un RÉSUMÉ sous un titre d'article se lirait comme le texte du contrat (#991)"
    ),
    "ne le résume jamais": "un résumé ne tient pas lieu d'extrait (#991)",
    "la section 8 est ABSENTE": (
        "sans clause citée, pas de section : vide, elle se lirait comme une information "
        "manquante (#991)"
    ),
    "L'extrait ne remplace pas la citation": (
        "la citation prouve la ligne, l'extrait donne la clause : les confondre ferait "
        "disparaître la plus vérifiable (#991)"
    ),
    CONSIGNE_CITATIONS: "l'exigence de citation sous chaque fait reste dans la consigne (#991)",
    #  ── Extraits repliés, article nommé (17/09/2026, #992) ──
    "« Non reproduit » est un aveu, pas un raccourci": (
        "🔴 onze extraits, onze fois « non reproduit », alors que les mêmes articles "
        "étaient cités : qui a pu citer peut recopier (#992)"
    ),
    "peux pas déclarer cet article non reproduit": (
        "la porte de sortie se ferme par la cohérence avec les citations (#992)"
    ),
    "n'écris pas la section 8": (
        "si RIEN ne peut être recopié, onze titres vides feraient croire à une lecture "
        "qui n'a pas eu lieu (#992)"
    ),
    "SEULS": "🔴 la section 8 ne porte QUE les articles que la synthèse nomme (#992)",
    "que la synthèse ne cite": "un article non cité n'a pas sa place dans les extraits (#992)",
    "Ce n'est pas le sommaire du contrat": "le modèle avait déroulé le SOMMAIRE du contrat (#992)",
    "TU NOMMES L'ARTICLE D'OÙ LE FAIT VIENT": (
        "sans référence d'article, aucune puce n'en nommait et la section 8 ne se "
        "déclenchait jamais (#992)"
    ),
    "<details><summary>": (
        "onze extraits de trente lignes, dépliés, noieraient la synthèse — balises tenues "
        "d'accord avec le front par `test_consigne_balises.py` (#992)"
    ),
    "bloc DÉPLIABLE, replié à l'ouverture": "l'extrait est replié à l'ouverture (#992)",
    "n'écris JAMAIS l'attribut `open`": (
        "`open` est de toute façon retiré par `#lib/sanitize` : consigne et rendu disent "
        "la même chose, et c'est le rendu qui tranche (#992)"
    ),
}


def test_cas_zero_la_table_des_exigences_et_le_gabarit_sont_la():
    """Une table vide ferait passer le contrôle suivant sans rien vérifier."""
    assert EXIGENCES_CONSIGNE, "la table des exigences de la consigne est vide"
    assert GABARIT in CONSIGNE, "le gabarit des sept sections n'est plus dans la consigne"


def test_la_consigne_porte_chaque_exigence():
    absentes = [
        f"  « {phrase} » — {raison}"
        for phrase, raison in EXIGENCES_CONSIGNE.items()
        if phrase not in CONSIGNE
    ]
    assert not absentes, (
        f"{len(absentes)} exigence(s) absente(s) de la consigne de synthèse :\n"
        + "\n".join(absentes)
    )


#  Les sept sections, mot pour mot (#901), et ce que tout contrat renseigne (#905).
SECTIONS_GABARIT = tuple(f"{n}." for n in range(1, 8)) + (
    "Prestations non incluses",
    "Points d'attention",
)
UNIVERSELS_GABARIT = ("SIRET", "préavis", "indexation", "option")
SPECIFIQUES_INTERDITS = ("parking", "ascenseur", "contrôle d'accès", "porte")


def test_le_gabarit_reste_GENERIQUE_a_tout_contrat_de_copropriete():
    """Le gabarit en SEPT sections est imposé, et il reste générique.

    ⚠️ Un schéma détaillé par type de contrat (porte de parking, contrôle
    d'accès) aurait été exact une fois et faux au contrat suivant : une assurance
    n'a ni visites annuelles ni pièces détachées. Ce qui est imposé vaut pour
    TOUT contrat ; le détail vient du document."""
    gabarit = GABARIT.lower()
    ecarts = [f"  section absente : « {s} »" for s in SECTIONS_GABARIT if s not in GABARIT]
    ecarts += [f"  spécifique à un type : « {s} »" for s in SPECIFIQUES_INTERDITS if s in gabarit]
    ecarts += [
        f"  universel non demandé : « {u} »" for u in UNIVERSELS_GABARIT if u.lower() not in gabarit
    ]
    assert not ecarts, "Le gabarit de synthèse s'écarte de la règle :\n" + "\n".join(ecarts)
