"""Génère un jeu de données FICTIF (structure ENEM) pour tester l'application.

Usage : python tests/generer_donnees_test.py [dossier_destination]
"""

from __future__ import annotations

import sys
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from enem_core import references as R  # noqa: E402

rng = np.random.default_rng(2026)
SECTIONS = "COMP ED FP IM EM HAND LOG FT SE EMP CQ PL ES WKT WKI P RHE TP DI SRH R C".split()
AGENTS = {i: f"AGENT TERRAIN {i:03d}" for i in range(101, 150)}
AGENTS.update({i: f"TELEOPERATEUR {i:03d}" for i in range(201, 221)})


CODES_ABIDJAN = [1010100211, 1010100212, 1010100213, 1010100214, 1010100215,
                 1010100216, 1010100217, 1010100218, 1010100219, 1010100220]


def _cle():
    return "-".join(f"{rng.integers(0, 100):02d}" for _ in range(4))


def _hex():
    return "".join(rng.choice(list("0123456789abcdef"), 32))


def _ts(jour: dt.date, minute: int) -> str:
    return (dt.datetime.combine(jour, dt.time(8)) + dt.timedelta(minutes=int(minute))).strftime("%Y-%m-%dT%H:%M:%S")


def generer_trimestre(code: str, lundi: dt.date, regions: dict, nb_zd: int, rgmen_cohortes: dict,
                      references_precedentes: dict | None = None, date_max: dt.date | None = None):
    """rgmen_cohortes : {rgmen: nombre de ménages par ZD}. Retourne (menage, membres, activite)."""
    menages, membres, activites = [], [], []
    for code_reg, nom_reg in regions.items():
        for z in range(1, nb_zd + 1):
            for rg, nmen in rgmen_cohortes.items():
                if rg == 1 and nom_reg != "ABIDJAN" and z > 2 and rng.random() < 0.5:
                    continue  # régions en retard
                n = nmen + (int(rng.integers(0, 3)) if rg == 1 and rng.random() < 0.1 else 0)
                for m in range(n):
                    key, iid = _cle(), _hex()
                    jour = lundi + dt.timedelta(days=int(rng.integers(0, 60)))
                    if date_max:
                        jour = min(jour, date_max)
                    agent = int(rng.choice(list(range(101, 150)))) if rg == 1 else int(rng.choice(list(range(201, 221))))
                    hh12 = int(rng.integers(1, 34)) if rg == 1 else int(rng.choice([34, 35]))
                    debut = int(rng.integers(0, 300))
                    duree_men = int(rng.integers(3, 40))
                    ref = None
                    if rg != 1 and references_precedentes and rg in references_precedentes:
                        pool = references_precedentes[rg]
                        ref = pool[int(rng.integers(0, len(pool)))]
                    porte = f"00{m:03d}{code.replace('_', '')}" if rng.random() > 0.05 else f"00{m:03d}T12025"
                    menages.append({
                        "interview__key": key, "interview__id": iid, "rgmen": rg, "rghab": 1,
                        "HH01": 1, "HH0": "CI", "HH2A": 1, "HH1": int(str(code_reg)[:3]), "HH2": code_reg,
                        "HH3": code_reg * 1000 + 1, "HH4": int(rng.choice(CODES_ABIDJAN)) if rng.random() < 0.18 else code_reg * 100000 + 1,
                        "HH6": int(rng.integers(1, 3)),
                        "HH8": f"{code_reg}{z:03d}", "HH8A": f"QUARTIER {z}", "HH8B": int(rng.integers(0, 3)),
                        "HH7": 1, "HH7B": 1, "HH9": m + 1, "HH9_1": porte, "HH12": hh12, "HH13": agent,
                        "HH14": 1, "resultat_enqb": int(rng.choice([1, 1, 1, 2, 6, 11, 16])),
                        "resultat_enqb_aut": "", "HH14_Aut": "",
                        "hha": _ts(jour, debut), "HH15A": _ts(jour, debut + duree_men),
                        "date_fin": _ts(jour, debut + duree_men + int(rng.integers(2, 60))),
                        "V1interviewkey": ref[0] if ref else "",
                        "GPS__Latitude": 5.3 + rng.random(), "GPS__Longitude": -4.0 + rng.random(),
                        "GPS__Accuracy": 5.0, "GPS__Altitude": 20.0, "GPS__Timestamp": _ts(jour, debut),
                        "trimestreencours": code, "mois_en_cours": jour.month, "annee": jour.year,
                    })
                    nmem = int(rng.integers(1, 6))
                    for j in range(1, nmem + 1):
                        sexe = int(rng.choice([1, 2]))
                        emp = int(rng.choice([0, 1]))
                        if ref and rng.random() < 0.08:
                            sexe = 3 - ref[2]
                        elif ref:
                            sexe = ref[2]
                        row = {"interview__key": key, "interview__id": iid, "membres__id": j,
                               "M0": f"PERSONNE {j}", "M0__0": f"PERSONNE {j}", "M5": sexe,
                               "EN_EMP": emp, "Statut_Res": 1 if rng.random() > 0.05 else 0,
                               "AgeAnnee": float(rng.integers(0, 90)) if rng.random() > 0.02 else np.nan,
                               "M4Confirm": float(rng.integers(0, 90)),
                               "membre_id_v1": str(ref[1]) if ref else "",
                               "HH14a": float(rng.choice([1, 1, 1, 2, 6, 10])),
                               "hhaa": _ts(jour, debut + duree_men),
                               "EP1a": "COMMERCANT" if emp else "", "EP2b": "VENTE" if emp else "",
                               "ES1a": "", "SE1": float(rng.integers(1, 3)) if rng.random() > 0.03 else np.nan,
                               "SRH1": float(rng.integers(1, 3)) if rng.random() > 0.03 else np.nan}
                        row.update(variables_bulletin_fictives(rng, emp))
                        t0 = debut
                        for s in SECTIONS:
                            d = int(rng.integers(0, 6))
                            row[f"hha_{s}"] = _ts(jour, t0)
                            row[f"hhavf_{s}"] = _ts(jour + dt.timedelta(days=1 if rng.random() < 0.003 else 0), t0 + d)
                            t0 += d
                        membres.append(row)
                        if emp and rng.random() < 0.2:
                            activites.append({"interview__key": key, "interview__id": iid, "membres__id": j,
                                              "r_activite_s__id": 1, "PL3_B": "AGRICULTURE", "PL3_C": "MAIS"})
    return pd.DataFrame(menages), pd.DataFrame(membres), pd.DataFrame(activites)



def variables_bulletin_fictives(rng, emp: int) -> dict:
    """Variables des sections emploi / éducation / handicap utilisées par les tableaux du bulletin."""
    ch = lambda *v: float(rng.choice(list(v)))          # noqa: E731
    v = {
        # Section SE : emploi présent / absent
        "SE2": ch(1, 2, 3, 10), "SE3": ch(1, 2, 3, 4, 5), "SE4": ch(1, 2), "SE5": ch(1, 2),
        "SE7": ch(1, 2, 3, 4), "SE8": ch(1, 2), "SE9": ch(1, 2, 5, 10, 14), "SE9A": ch(1, 2),
        "SE9B": ch(1, 2), "SE10": ch(1, 2), "SE11": ch(1, 2),
        # Section SRH : recherche d'emploi et disponibilité
        "SRH2": ch(1, 2), "SRH2A": ch(1, 2), "SRH6": ch(1, 2), "SRH7": ch(1, 2, 18),
        "SRH8": ch(1, 2), "SRH9": ch(1, 2), "SRH11": ch(1, 2),
        # Section EF : éducation
        "EF1": ch(1, 2), "EF3": ch(1, 2, 3, 5, 7, 8), "EF4": ch(4, 8, 12, 16, 18), "EF4_1": ch(1, 2, 3),
        "EF6": ch(1, 2), "EF7": ch(1, 2, 3, 5), "EF8": ch(4, 8, 12), "EF10": ch(1, 2),
        "EF11": ch(1, 2, 3, 5), "EF12": ch(4, 8, 12),
        # Section FP : formation professionnelle
        "FP1": ch(1, 2), "FP6": ch(1, 2),
        # Section EP : emploi principal
        "EP3": ch(1, 2, 3, 4, 5, 6, 8, 9, 10), "EP4": ch(1, 2, 3), "EP5": ch(1, 2),
        "EP6_1": ch(1, 2), "EP6a": ch(1, 2), "EP10c": ch(1, 2, 3),
        "EP11": ch(1, 2, 3, 4, 5, 6, 7, 8), "EP13": ch(1, 2, 3), "EP14B": ch(1, 2, 9998),
        "EP20": ch(1, 2), "EP22": ch(1, 2), "EP26a": ch(1, 2), "EP27a": ch(1, 2),
        "EP26b": ch(1, 2), "EP27b": ch(1, 2), "EP28": ch(1, 2, 9998),
        "EP29": ch(1, 2, 3, 4), "EP30": float(rng.integers(1, 24)), "EP30b": ch(1, 2, 3),
        "EP30c": ch(1, 2, 3, 5, 8), "EP31_1": ch(1, 2), "EP31_2": ch(1, 2), "EP31_3": ch(1, 2),
        "EP31_4": ch(1, 2), "EP31_5": ch(1, 2), "EP32": ch(1, 2), "EP33": ch(1, 2), "EP35": ch(1, 2),
        "EP37": ch(1, 2), "EP38": ch(1, 2), "EP39": ch(1, 2), "EP44": ch(1, 2),
        # Pluriactivité, heures, branche
        "PL1": ch(1, 2), "PL2": ch(1, 2), "WKI4": ch(1, 2), "WKI5": ch(1, 2),
        "nb_heure_travail_total": float(rng.integers(5, 70)),
        "branche1": ch(1, 2, 3, 4, 5),
        # Handicap
        "DIF1a": ch(1, 2, 3, 4), "DIF2a": ch(1, 2, 3, 4), "DIF3b": ch(1, 2, 3, 4),
        "DIF3d": ch(1, 2, 3, 4), "DIF5": ch(1, 2, 3, 4), "DIF3_aut": "",
    }
    for k in range(1, 7):
        v[f"DIF3_{k}"] = ch(1, 2)
    if not emp:
        for cle in list(v):
            if cle.upper().startswith("EP") and rng.random() < 0.7:
                v[cle] = np.nan
    return v


def ecrire(df, chemin, labels):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].fillna("").astype(str).astype(object)
    lv = {k: v for k, v in labels.items() if k in df.columns}
    df.to_stata(chemin, write_index=False, version=118, value_labels=lv,
                variable_labels={"HH2": "Région", "HH13": "Nom de l'agent", "HH8": "Numéro de la ZD"})


def main(dest: Path):
    regions = R.regions(RACINE / "reference" / "Semaine_ref.xlsx")
    labels = {"HH2": {int(k): v for k, v in regions.items()}, "HH13": AGENTS,
              "M5": {1: "Masculin", 2: "Féminin"}, "rgmen": {1: "Passage 1", 3: "Passage 3", 4: "Passage 4"}}
    # trimestres d'origine (passage 1) -> pools de référence
    pools = {}
    for rg, code, lundi in ((3, "T3_2025", dt.date(2025, 6, 30)), (4, "T2_2025", dt.date(2025, 3, 31))):
        men, mem, act = generer_trimestre(code, lundi, dict(list(regions.items())[:8]), 2, {1: 6})
        d = dest / f"Base_brute_{code}"
        ecrire(men, d / f"ENEM_{code[3:]}T{code[1]}.dta", labels)
        ecrire(mem, d / "membres.dta", labels)
        pools[rg] = list(mem[["interview__key", "membres__id", "M5"]].itertuples(index=False, name=None))
    lundi = dt.date(2026, 6, 29)
    men, mem, act = generer_trimestre("T3_2026", lundi, regions, 3, {1: 12, 3: 2, 4: 2}, pools,
                                      date_max=dt.date(2026, 9, 15))
    # 3 versions
    parts = np.array_split(np.arange(len(men)), 3)
    for i, idx in enumerate(parts, 1):
        d = dest / "Base_menage_individuel" / f"ENEM_2026T3_{i}_STATA_All"
        m = men.iloc[idx]
        ecrire(m, d / "ENEM_2026T3.dta", labels)
        ecrire(mem[mem["interview__key"].isin(m["interview__key"])], d / "membres.dta", labels)
        ecrire(act[act["interview__key"].isin(m["interview__key"])], d / "r_activite_s.dta", labels)
    # bases distinctes par passage (EZ2)
    for rg, nom in ((3, "3ieme_passage_ENEMT3_2025"), (4, "4ieme_passage_ENEMT2_2025")):
        d = dest / "Base_agent_teleoperateur" / nom
        ecrire(men[men["rgmen"] == rg], d / "ENEM_2026T3.dta", labels)
    # dénombrement (2 versions)
    for i, idx in enumerate(np.array_split(np.arange(len(men)), 2), 1):
        d = dest / "Base_denombrement" / f"ENEM_2026T3_Denom_{i}"
        m = men.iloc[idx]
        dm = pd.DataFrame({"interview__key": m["interview__key"], "ilot__id": 1, "batiment__id": 1,
                           "menage__id": range(1, len(m) + 1),
                           "adresse_menage": [p if rng.random() > 0.04 else "00001T22026" for p in m["HH9_1"]]})
        dm["interview__key"] = m["interview__key"].values
        ecrire(dm, d / "menage.dta", labels)
        ecrire(pd.DataFrame({"interview__key": m["interview__key"], "ilot__id": 1, "batiment__id": 1,
                             "gps__Latitude": 5.3, "gps__Longitude": -4.0, "gps__Accuracy": 3.0,
                             "gps__Altitude": 10.0, "gps__Timestamp": "", "adresse": "RUE", "bat_habite": 1,
                             "nom__0": "CHEF", "nb_men_num_bat": 1, "nb_men_a_num": 1}), d / "batiment.dta", labels)
        ecrire(pd.DataFrame({"interview__key": m["interview__key"], "ilot__id": 1, "code_ilot": "IL01"}),
               d / "ilot.dta", labels)
        ecrire(m[["interview__key", "HH01", "HH0", "HH2A", "HH1", "HH2", "HH3", "HH4", "HH6", "HH8", "HH8A",
                  "HH7", "HH8B", "trimestreencours", "mois_en_cours", "HH12", "HH13"]],
               d / "ENEM_2026T3_DenomVF.dta", labels)
    # paradata (2 versions)
    info = pd.read_excel(RACINE / "reference" / "information_agent.xlsx", sheet_name=None)
    comptes = list(info["Equipe_teleoperateur"]["responsible"]) + list(info["Equipe_terrain"]["responsible"])
    for i in (1, 2):
        lignes = []
        for c in comptes:
            if rng.random() < 0.05:
                continue
            for jour in pd.date_range(lundi, dt.date(2026, 9, 15)):
                if rng.random() < 0.3:
                    continue
                h0 = rng.integers(7, 11)
                for k in range(int(rng.integers(2, 20))):
                    ts = dt.datetime.combine(jour.date(), dt.time(int(h0))) + dt.timedelta(minutes=int(k * rng.integers(5, 30)))
                    lignes.append((_hex(), k, "AnswerSet" if k else "InterviewCreated", c, "1",
                                   ts.strftime("%Y-%m-%dT%H:%M:%S.000"), "00:00:00", ""))
        d = dest / "Paradata" / f"ENEM_2026T3_{i}_Paradata_All"
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(lignes, columns=["interview__id", "order", "event", "responsible", "role", "timestamp_utc",
                                      "tz_offset", "parameters"]).to_csv(d / "paradata.tab", sep="\t", index=False)
    # base historique empilée avec pondération (pour la simulation de pondération)
    lignes = []
    for code_hist, mult in (("T3_2025", 1.0), ("T2_2025", 0.98), ("T3_2024", 0.95)):
        m, mm, _ = generer_trimestre(code_hist, dt.date(2025, 6, 30), dict(list(regions.items())[:12]), 2, {1: 8})
        ind = mm.merge(m[["interview__key", "HH2", "HH6"]], on="interview__key", how="left")
        ind["trimestre"] = code_hist
        ind["pmencor_ind"] = (rng.lognormal(6.2, 0.55, len(ind)) * mult).round(2)
        lignes.append(ind[["interview__key", "membres__id", "HH2", "HH6", "trimestre", "pmencor_ind"]])
    ecrire(pd.concat(lignes, ignore_index=True), dest / "Base_historique" / "ENEM_historique_ponderations.dta", labels)

    # bases de travail du bulletin (chaîne « Simulation indicateur »)
    for code_bt, jour_bt, annee_bt, court in (("T3_2024", dt.date(2024, 6, 24), 2024, "24T3"),
                                              ("T3_2025", dt.date(2025, 6, 30), 2025, "25T3")):
        m, mm, _ = generer_trimestre(code_bt, jour_bt, dict(list(regions.items())[:12]), 3, {1: 10})
        bt = mm.merge(m.drop(columns=["annee"]), on=["interview__key", "interview__id"], how="left")
        bt.columns = [c.lower().replace("__", "_") for c in bt.columns]
        bt["trimestre"] = court
        bt["annee"] = float(annee_bt)
        bt["pmencor_ind"] = rng.lognormal(6.2, 0.55, len(bt)).round(2)
        bt["pmencor_ind_annuel"] = bt["pmencor_ind"]
        ecrire(bt, dest / "Base_Travail" / f"Base_Travail_BT_vf_{court}.dta", labels)

    print(f"Jeu de test créé dans {dest} : {len(men)} ménages, {len(mem)} individus")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "tests" / "donnees_fictives")
