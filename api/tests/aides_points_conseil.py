"""Les aides des tests du point CS / Syndic — un point terminé, ses envois.

Elles vivaient dans `test_points_conseil_validation.py` ; les tests de #2082
(états, révisions, expédition) en ont besoin aussi : elles vivent ici plutôt
que d'être recopiées (#1495).
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.gouvernance import GenreCivilite, MembreCS, MembreSyndic
from tests.aides_base import compte
from tests.aides_suivi import affaire_ouverte


def intercepter_envois(monkeypatch) -> list[dict]:
    """Les courriels partis, interceptés ; le PDF rangé, remplacé par un faux."""
    envois: list[dict] = []

    async def _intercepter(code, to, context, session=None, **options):
        envois.append({"code": code, "to": to, "pieces": options.get("attachments"), **context})
        return True

    monkeypatch.setattr("app.utils.email.send_email", _intercepter)

    async def _intercepter_groupe(code, to_recipients, context, session=None, **options):
        cc = [e for _, e in options.get("cc_recipients") or []]
        envois.append(
            {
                "code": code,
                "to": [e for _, e in to_recipients],
                "cc": cc,
                "pieces": options.get("attachments"),
                **context,
            }
        )

    monkeypatch.setattr("app.utils.email.send_email_group", _intercepter_groupe)
    #  Le PDF rangé à la validation (#2082) : un faux document, pour que ces
    #  tests jugent la validation et non le moteur PDF, absent sous Windows.
    monkeypatch.setattr(
        "app.utils.points_conseil_expedition.pdf_du_point", lambda *a, **k: b"%PDF-1.4 essai"
    )
    return envois


def point_termine(
    moteur, cs, *, contenu="<p>Devis <b>attendu</b></p>", conseil_seul=False, etat_cible=None
):
    """Un point à deux présents joignables (CS, syndic) et un invité ; une affaire abordée."""
    with Session(moteur) as s:
        membre = compte(s, prefixe="membre-cs", nom="Martin", prenom="Reine")
        m_cs = MembreCS(genre=GenreCivilite.mme, prenom="Reine", nom="Martin", user_id=membre.id)
        m_sy = MembreSyndic(
            genre=GenreCivilite.mr, prenom="Paul", nom="Bernard", email="Gestion@Exemple.test"
        )
        s.add(m_cs)
        s.add(m_sy)
        s.commit()
        ids = (m_cs.id, m_sy.id, membre.email)
    t = affaire_ouverte(moteur, "Infiltration hall B", jours=40)
    affaire_ouverte(moteur, "Oubliée", jours=10)
    point = cs.post(
        "/points-conseil",
        json={
            "mode": "affaires",
            "debut": "2026-10-19T17:00:00",
            "presents": [
                {"nature": "cs", "membre_id": ids[0]},
                {"nature": "syndic", "membre_id": ids[1]},
                {"nature": "invite", "prenom": "Jean", "email": "invite@exemple.test"},
            ],
        },
    ).json()["point"]["id"]
    cs.put(
        f"/points-conseil/{point}/affaires/{t}",
        json={"contenu": contenu, "conseil_seul": conseil_seul, "etat_cible": etat_cible},
    )
    r = cs.post(f"/points-conseil/{point}/terminer")
    assert r.status_code == 200, r.text
    return point, t, ids[2]


def liens(envois) -> list[str]:
    return [e["jeton"] for e in envois]


def hors_annexe(affaires: list[dict]) -> list[dict]:
    """Les affaires d'un point, sans son affaire « Points annexes » — créée
    d'office à l'ouverture d'un point du Suivi affaires (#2084)."""
    return [a for a in affaires if not a["titre"].startswith("Points annexes CS & Syndic")]
