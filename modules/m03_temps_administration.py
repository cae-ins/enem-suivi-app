"""Temps d'administration des questionnaires et indicateurs de performance des agents.

Codes d'origine : Main_performance.do, Transformation_HH13.do,
Indicateur_performance_AG_claude3_Elodie.do, Modification_Elodie.do
Décisions : base dérivée au lieu d'écraser la base brute (V1), version claude3_Elodie (V2),
Diagnostics_PL_RHE abandonné (V3), entretiens commencés et finis à des dates différentes
exclus (TA3), alerte < 5 min (TA7), correction du bug « capture drop hhaa » (TA8),
moyenne des moyennes par agent et 10 sections téléopérateurs (N6, N7).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore", pd.errors.PerformanceWarning)

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Colonne, Liste, Reel, Tableau, Texte
from enem_core.trimestre import Trimestre

from ._communs import (G_BASES, charger_menage, charger_membres, nom_fichier_menage, num, p_fichier_menage,
                       p_sortie, p_trimestre, p_versions_menage)

SECTIONS_MEN = "COMP ED FP IM EM HAND LOG"
SECTIONS_IND = "FT SE EMP CQ PL ES WKT WKI P RHE TP DI SRH R C"
SECTIONS_TELEOP = "COMP ED FP SE EMP PL WKT WKI DI SRH"
HH13_BAD = ("109 111 112 113 114 119 120 116 117 118 126 127 134 121 122 123 124 125 128 129 130 "
            "131 132 133 135 136 137 138 139 140 141 142 143 144 145 146 147 148")

LIBELLES_SECTIONS = {
    "COMP": ("COMPOSITION DU MÉNAGE ET CARACTÉRISTIQUES DES MEMBRES", "Ménage"),
    "ED": ("EDUCATION ET FORMATION", "Ménage"),
    "FP": ("FORMATION PROFESSIONNELLE ET APPRENTISSAGE", "Ménage"),
    "IM": ("IMMIGRATION", "Ménage"),
    "EM": ("EMIGRATION", "Ménage"),
    "HAND": ("DIFFICULTES FONCTIONNELLES (DIF)", "Ménage"),
    "LOG": ("CARACTERISTIQUES DU LOGEMENT ET POSSESSIONS DU MENAGE", "Ménage"),
    "FT": ("AUTRES FORMES DE TRAVAIL (FT)", "Individuelle"),
    "SE": ("SITUATION D'EMPLOI (SE)", "Individuelle"),
    "EMP": ("EMPLOI PRINCIPAL (EP)", "Individuelle"),
    "CQ": ("COMPETENCES ET QUALIFICATIONS REQUISES POUR L'EMPLOI PRINCIPAL (CQ)", "Individuelle"),
    "PL": ("PLURIACTIVITE (PL)", "Individuelle"),
    "ES": ("EMPLOI SECONDAIRE (ES)", "Individuelle"),
    "WKT": ("TEMPS DE TRAVAIL DANS L'EMPLOI (WKT) ET ORGANISATION DU TRAVAIL", "Individuelle"),
    "WKI": ("SITUATIONS D'EMPLOI INADÉQUATES (WKI)", "Individuelle"),
    "P": ("EMPLOI ANTERIEUR (P)", "Individuelle"),
    "RHE": ("REVENU HORS EMPLOI (RHE)", "Individuelle"),
    "TP": ("ACTIVITE DES PARENTS (TP)", "Individuelle"),
    "DI": ("DISPONIBILITE DES INDIVIDUS (DI)", "Individuelle"),
    "SRH": ("RECHERCHE D'EMPLOI ET DISPONIBILITÉ (SRH)", "Individuelle"),
    "R": ("RECHERCHE D'UN AUTRE EMPLOI POUR LES PERSONNES EN EMPLOI (R)", "Individuelle"),
    "C": ("CHÔMAGE (C)", "Individuelle"),
}

LIB_INDICATEURS = {
    "nb_questionnaires": "Nb individus traités",
    "nb_menages": "Nb ménages traités",
    "interview_end": "Nb interview achevés",
    "interview_nojoin": "Nb interview injoignable",
    "interview_refus": "Nb interview refus",
    "interview_joignable_teleop": "Nb appels émis avec succès",
    "interview_partialend": "Nb interview achevés partiellement",
    "n_manquant": "Nb questions manquantes",
    "moy_duree_GL_MEN": "Durée moy. ménage (min)",
    "moy_duree_GL_IND": "Durée moy. individuel (min)",
    "moy_duree_GL_TOTAL": "Durée moy. totale (min)",
    "sd_duree_MEN": "Écart-type ménage", "sd_duree_IND": "Écart-type individuel",
    "min_duree_MEN": "Min ménage", "min_duree_IND": "Min individuel",
    "med_duree_MEN": "Médiane ménage", "med_duree_IND": "Médiane individuel",
    "max_duree_MEN": "Max ménage", "max_duree_IND": "Max individuel",
    "nb_exclus_2jours": "Nb durées exclues (début et fin à des dates différentes)",
}


# ---------------------------------------------------------------------------
# Calculs élémentaires
# ---------------------------------------------------------------------------
def _horodatage(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip()
    s = s.where(~s.isin(["", "##N/A##", "nan", "NaT", "None"]))
    return pd.to_datetime(s.str.slice(0, 19), errors="coerce", format="%Y-%m-%dT%H:%M:%S")


def duree_minutes(debut: pd.Series, fin: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Durée en minutes entre deux horodatages texte (AAAA-MM-JJTHH:MM:SS).

    Retourne (durée, indicateur « début et fin à des dates différentes »). Les durées
    sur deux dates sont mises à manquant (décision TA3). Les autres manquants valent 0,
    comme dans le code Stata.
    """
    d0, d1 = _horodatage(debut), _horodatage(fin)
    deux_jours = d0.notna() & d1.notna() & (d0.dt.date != d1.dt.date)
    duree = ((d1 - d0).dt.total_seconds() / 60).abs()
    duree = duree.fillna(0)
    duree[deux_jours] = np.nan
    return duree, deux_jours


def recoder_hh13(df: pd.DataFrame, codes_bad: list[int], codes_terrain, codes_tele) -> pd.DataFrame:
    """Transformation_HH13.do : HH13 -> HH13_es et type_agent (sans écraser la base brute)."""
    hh13 = num(df, "HH13")
    df["HH13_es"] = hh13.where(~hh13.isin(codes_bad), 999)
    df.loc[hh13.isna(), "HH13_es"] = 9998
    hh12 = num(df, "HH12")
    df["type_agent"] = np.select([hh12.isin(codes_terrain), hh12.isin(codes_tele)], [1, 2], default=np.nan)
    lv = df.attrs.setdefault(D.LV, {})
    lab = dict(lv.get("HH13", {}))
    lab.update({999: "Bad selection", 9998: "Non rempli"})
    lv["HH13_es"] = lab
    lv["type_agent"] = {1: "Agent terrain", 2: "Agent téléopérateur"}
    df.attrs.setdefault(D.LVAR, {}).update({"HH13_es": "Agent", "type_agent": "Type d'agent"})
    return df


def indicateurs_entretien(df: pd.DataFrame) -> pd.DataFrame:
    hh14a, res, hh14, rgmen = num(df, "HH14a"), num(df, "resultat_enqb"), num(df, "HH14"), num(df, "rgmen")
    aut14 = df["HH14_Aut"].astype(str) if "HH14_Aut" in df.columns else pd.Series("", index=df.index)
    autres = df["resultat_enqb_aut"].astype(str) if "resultat_enqb_aut" in df.columns else pd.Series("", index=df.index)
    rempli = lambda s: (s.str.strip() != "") & (s != "##N/A##") & (s != "nan")
    un = lambda cond: np.where(cond, 1.0, np.nan)
    df["entretient_end"] = un((hh14a == 1) | (hh14a.isna() & (res == 1)))
    nojoin = (hh14a.isin([3, 4, 5, 7, 8, 10, 11, 12, 13, 14, 16, 17])
              | ((hh14a == 9) & rempli(aut14))
              | (hh14a.isna() & res.isin([3, 4, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18]))
              | (hh14a.isna() & res.isin([9, 19]) & rempli(autres))
              | ((hh14a == 9) & res.isin([9, 19]) & rempli(autres)))
    df["entretient_nojoin"] = un(nojoin)
    df["entretient_refus"] = un(hh14a == 6)
    df["entretient_partialend"] = un((hh14a == 2) | (hh14a.isna() & (res == 2)))
    tele = rgmen != 1
    joign = ((res == 16) & (hh14.isin([1, 2, 6]) | hh14.isna()) & tele) | ((res == 6) & tele) | ((hh14 == 6) & tele)
    df["entretient_joignable_teleop"] = un(joign)
    return df


def nb_manquants(df: pd.DataFrame, colonnes) -> pd.Series:
    """Nombre de variables manquantes par ligne (numérique : NaN ; texte : "." ou ".a")."""
    total = pd.Series(0, index=df.index, dtype="int64")
    for c in colonnes:
        if c == "interview__key" or c not in df.columns:
            continue
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            total += s.isna().astype("int64")
        elif s.dtype == object or pd.api.types.is_string_dtype(s):
            total += s.isin([".", ".a"]).astype("int64")
    return total


def agreger(df: pd.DataFrame, par: list[str]) -> pd.DataFrame:
    g = df.groupby(par, dropna=False)
    res = pd.DataFrame({
        "nb_questionnaires": g["id_unique"].count(),
        "nb_menages": g["id_men_unique"].count(),
        "interview_end": g["entretient_end"].count(),
        "interview_nojoin": g["entretient_nojoin"].count(),
        "interview_refus": g["entretient_refus"].count(),
        "interview_joignable_teleop": g["entretient_joignable_teleop"].count(),
        "interview_partialend": g["entretient_partialend"].count(),
        "n_manquant": g["nb_miss"].sum(),
        "moy_duree_GL_MEN": g["duree_GL_MEN"].mean(),
        "moy_duree_GL_IND": g["duree_GL_IND"].mean(),
        "moy_duree_GL_TOTAL": g["duree_QUEST_GL_TOTAL"].mean(),
        "sd_duree_MEN": g["duree_GL_MEN"].std(),
        "sd_duree_IND": g["duree_GL_IND"].std(),
        "min_duree_MEN": g["duree_GL_MEN"].min(),
        "min_duree_IND": g["duree_GL_IND"].min(),
        "med_duree_MEN": g["duree_GL_MEN"].median(),
        "med_duree_IND": g["duree_GL_IND"].median(),
        "max_duree_MEN": g["duree_GL_MEN"].max(),
        "max_duree_IND": g["duree_GL_IND"].max(),
        "nb_exclus_2jours": g["exclu_2jours"].sum(),
    }).reset_index()
    cols = [c for c in res.columns if c.startswith(("moy_", "sd_", "min_", "med_", "max_"))]
    res[cols] = res[cols].round(2)
    return res


# ---------------------------------------------------------------------------
class TempsAdministration(ModuleBase):
    id = "temps_administration"
    nom = "Temps d'administration et performance des agents"
    nom_court = "Temps d'administration"
    description = ("Calcule le temps passé par chaque agent sur chaque section du questionnaire, la durée globale "
                   "des questionnaires ménage et individuel, les résultats d'entretien (achevés, partiels, refus, "
                   "injoignables) et produit les synthèses par agent, par région et par type d'agent.")
    equipe = "Terrain et téléopérateurs"
    frequence_jours = 14
    frequence_libelle = "Toutes les 2 semaines"
    couleur = "#2F7D5B"
    entrees = "ENEM_AAAATq.dta + membres.dta (une ou plusieurs versions), trimestres de comparaison facultatifs"
    sorties = ("performance_agents, performance_regions, temps_sections, synthèse par sections, "
               "alertes de durée, base dérivée (HH13_es, type_agent, durées)")
    code_origine = ["Code_temps_administration_quest/Main_performance.do",
                    "Code_temps_administration_quest/Transformation_HH13.do",
                    "Code_temps_administration_quest/Indicateur_performance_AG_claude3_Elodie.do",
                    "Code_temps_administration_quest/Modification_Elodie.do"]
    mots_cles = "durée temps section performance agent HH13 téléopérateur"
    ordre = 20
    sous_dossier = "Coordination"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            p_versions_menage(),
            p_fichier_menage(),
            Tableau("comparaison", "Trimestres de comparaison (facultatif)", [], groupe="Comparaison",
                    obligatoire=False,
                    colonnes=[Colonne("trimestre", "Trimestre (ex. T2_2026)", "texte", 14),
                              Colonne("dossier", "Dossier des bases de ce trimestre", "dossier", 44)],
                    aide="Chaque trimestre ajouté est traité de la même façon et consolidé avec le trimestre en cours."),
            Reel("seuil_men", "Alerte : entretien ménage de moins de (minutes)", 5, groupe="Alertes", mini=0),
            Reel("seuil_ind", "Alerte : entretien individuel de moins de (minutes)", 5, groupe="Alertes", mini=0),
            Liste("sections_menage", "Sections du questionnaire ménage", SECTIONS_MEN, groupe="Sections"),
            Liste("sections_individuel", "Sections du questionnaire individuel", SECTIONS_IND, groupe="Sections"),
            Liste("sections_teleop", "Sections prises en compte pour les téléopérateurs", SECTIONS_TELEOP,
                  groupe="Sections"),
            Liste("codes_bad", "Codes HH13 recodés « Bad selection » (999)", HH13_BAD, groupe="Codes agents"),
            Texte("hh12_terrain", "Codes HH12 des agents terrain (ex. 1-33)", "1-33", groupe="Codes agents"),
            Texte("hh12_tele", "Codes HH12 des téléopérateurs (ex. 34-35)", "34-35", groupe="Codes agents"),
            Booleen("sauver_base", "Enregistrer la base dérivée (.dta) avec les durées", True, groupe="Sortie"),
            Booleen("exporter_individus", "Exporter aussi la base individuelle en Excel (volumineux)", False,
                    groupe="Sortie"),
            p_sortie(),
        ]

    @staticmethod
    def _plage(texte):
        codes = []
        for morceau in str(texte).replace(";", ",").split(","):
            morceau = morceau.strip()
            if "-" in morceau:
                a, b = morceau.split("-", 1)
                codes += list(range(int(a), int(b) + 1))
            elif morceau:
                codes.append(int(morceau))
        return codes

    # ------------------------------------------------------------------
    def traiter_trimestre(self, ctx, p, trimestre, dossiers, fichier, pct0, pct1):
        sm, si = p["sections_menage"], p["sections_individuel"]
        ctx.progression(pct0, f"[{trimestre}] Lecture des bases")
        garder = (["membres__id", "HH14a", "EP1a", "M4Confirm", "HH15A", "hhaa"]
                  + [f"{a}_{s}" for s in sm + si for a in ("hha", "hhavf")])
        men = D.lire_versions(dossiers, fichier, journal=ctx.journal)
        ctx.verifier_arret()
        # comme le « merge … keepusing() » de Stata : seules ces variables de membres sont lues
        mem = D.lire_versions(dossiers, "membres.dta", colonnes=["interview__key"] + garder, journal=ctx.journal)
        df = D.fusion_menage_membres(men, mem, garder)
        ctx.journal(f"  Individus après fusion : {len(df):,}".replace(",", " "))
        colonnes_origine = list(df.columns)
        recoder_hh13(df, [int(x) for x in p["codes_bad"]], self._plage(p["hh12_terrain"]),
                     self._plage(p["hh12_tele"]))
        ctx.progression(pct0 + (pct1 - pct0) * 0.3, f"[{trimestre}] Durées par section")
        exclus = pd.Series(False, index=df.index)
        absentes = []
        for s in sm + si:
            a, b = f"hha_{s}", f"hhavf_{s}"
            if a in df.columns and b in df.columns:
                df[f"duree_{s}"], ex = duree_minutes(df[a], df[b])
                exclus |= ex
            else:
                df[f"duree_{s}"] = 0.0
                absentes.append(s)
        if absentes:
            ctx.journal(f"  Sections sans variables début/fin (durée = 0) : {' '.join(absentes)}")
        df["duree_QUEST_MEN"] = df[[f"duree_{s}" for s in sm]].sum(axis=1, min_count=1).fillna(0)
        df["duree_QUEST_IND"] = df[[f"duree_{s}" for s in si]].sum(axis=1, min_count=1).fillna(0)
        df["duree_QUEST_TOTAL"] = df["duree_QUEST_MEN"] + df["duree_QUEST_IND"]
        vide = pd.Series("", index=df.index)
        df["duree_GL_MEN"], ex1 = duree_minutes(df.get("hha", vide), df.get("HH15A", vide))
        # Correction TA8 : hhaa n'est plus supprimée avant son utilisation
        df["duree_GL_IND"], ex2 = duree_minutes(df.get("hhaa", vide), df.get("date_fin", vide))
        df["duree_QUEST_GL_TOTAL"] = df["duree_GL_MEN"] + df["duree_GL_IND"]
        df["exclu_2jours"] = (exclus | ex1 | ex2).astype(int)
        df = df.copy()
        df["trimestre"] = trimestre
        df["id_unique"] = 1
        df["id_men_unique"] = np.where(num(df, "membres__id") == 1, 1.0, np.nan)
        ctx.progression(pct0 + (pct1 - pct0) * 0.5, f"[{trimestre}] Indicateurs d'entretien")
        indicateurs_entretien(df)
        df["nb_miss"] = nb_manquants(df, colonnes_origine)
        ctx.verifier_arret()
        # ---- performances par agent / région
        agents = agreger(df, ["HH13_es", "type_agent"])
        agents.insert(0, "trimestre", trimestre)
        agents.insert(2, "Agent", agents["HH13_es"].map(lambda v: D.libelle_valeur(df, "HH13_es", v)))
        agents["type_agent"] = agents["type_agent"].map({1: "Agent terrain", 2: "Agent téléopérateur"})
        regions = agreger(df, ["HH2", "type_agent"]) if "HH2" in df.columns else pd.DataFrame()
        if not regions.empty:
            regions.insert(0, "trimestre", trimestre)
            regions.insert(2, "Region", regions["HH2"].map(lambda v: D.libelle_valeur(df, "HH2", v)))
            regions["type_agent"] = regions["type_agent"].map({1: "Agent terrain", 2: "Agent téléopérateur"})
        # ---- temps moyens par section (0 exclus)
        dcols = [f"duree_{s}" for s in sm + si]
        tmp = df[["HH13_es", "type_agent"] + dcols].copy()
        tmp[dcols] = tmp[dcols].where(tmp[dcols] > 0)
        sections = tmp.groupby(["HH13_es", "type_agent"], dropna=False)[dcols].mean().round(2).reset_index()
        sections.insert(0, "Agent", sections["HH13_es"].map(lambda v: D.libelle_valeur(df, "HH13_es", v)))
        sections = sections.rename(columns={f"duree_{s}": f"moy_duree_{s}" for s in sm + si})
        sections = sections.sort_values(["type_agent", "HH13_es"])
        # ---- synthèse par section (Modification_Elodie : moyenne des moyennes)
        synth = []
        for s in sm + si:
            lib, typ = LIBELLES_SECTIONS.get(s, (s, "Ménage" if s in sm else "Individuelle"))
            col = f"moy_duree_{s}"
            terr = sections.loc[sections["type_agent"] == 1, col].mean()
            tele = sections.loc[sections["type_agent"] == 2, col].mean() if s in p["sections_teleop"] else np.nan
            synth.append({"Section": s, "Etiquette_des_sections": lib, "Type_de_section": typ,
                          "Agent_terrain": round(terr, 2) if pd.notna(terr) else np.nan,
                          "Agent_teleoperateur": round(tele, 2) if pd.notna(tele) else np.nan})
        synth = pd.DataFrame(synth)
        sections["type_agent"] = sections["type_agent"].map({1: "Agent terrain", 2: "Agent téléopérateur"})
        # ---- alertes de durée (un ménage = une ligne pour la durée ménage)
        al = []
        m1 = df.drop_duplicates("interview__key")
        cond = (m1["duree_GL_MEN"] > 0) & (m1["duree_GL_MEN"] < p["seuil_men"])
        for _, r in m1[cond].iterrows():
            al.append({"trimestre": trimestre, "Questionnaire": "Ménage", "interview__key": r["interview__key"],
                       "membres__id": "", "HH2": D.libelle_valeur(df, "HH2", r.get("HH2")),
                       "Agent": D.libelle_valeur(df, "HH13_es", r["HH13_es"]),
                       "Duree_min": round(r["duree_GL_MEN"], 2)})
        cond = (df["duree_GL_IND"] > 0) & (df["duree_GL_IND"] < p["seuil_ind"])
        for _, r in df[cond].iterrows():
            al.append({"trimestre": trimestre, "Questionnaire": "Individuel", "interview__key": r["interview__key"],
                       "membres__id": r.get("membres__id", ""), "HH2": D.libelle_valeur(df, "HH2", r.get("HH2")),
                       "Agent": D.libelle_valeur(df, "HH13_es", r["HH13_es"]),
                       "Duree_min": round(r["duree_GL_IND"], 2)})
        alertes = pd.DataFrame(al, columns=["trimestre", "Questionnaire", "interview__key", "membres__id",
                                            "HH2", "Agent", "Duree_min"])
        return df, agents, regions, sections, synth, alertes

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        lots = [(t.code, p["versions_menage"], nom_fichier_menage(p))]
        for ligne in p.get("comparaison") or []:
            tc = Trimestre.depuis(ligne["trimestre"])
            lots.append((tc.code, [ligne["dossier"]], tc.fichier_menage))
        tous = {k: [] for k in ("agents", "regions", "sections", "synth", "alertes")}
        base_courante = None
        for i, (code, dossiers, fichier) in enumerate(lots):
            pct0, pct1 = 5 + 75 * i / len(lots), 5 + 75 * (i + 1) / len(lots)
            df, ag, rg, se, sy, al = self.traiter_trimestre(ctx, p, code, dossiers, fichier, pct0, pct1)
            if i == 0:
                base_courante = df
            else:
                del df
            sy.insert(0, "trimestre", code)
            for k, v in zip(tous, (ag, rg, se, sy, al)):
                tous[k].append(v)
            ctx.exporter(f"temps_sections_{code}.xlsx", {"Temps_sections": se}, afficher=(i == 0))
        ctx.progression(82, "Consolidation et exports")
        cat = {k: pd.concat(v, ignore_index=True) if v else pd.DataFrame() for k, v in tous.items()}
        ren = lambda d: d.rename(columns=LIB_INDICATEURS)
        seuil_rouge = lambda r: "ROUGE" if (0 < (r.get("Durée moy. individuel (min)") or 0) < p["seuil_ind"]) else None
        ctx.exporter(f"performance_agents_{t.code}.xlsx",
                     {"Par_agent": ren(cat["agents"]), "Par_region": ren(cat["regions"])},
                     titre=f"Performance des agents – {t.libelle}",
                     surlignage={"Par_agent": seuil_rouge})
        ctx.exporter(f"Synthese_temps_sections_{t.code}.xlsx", {"Synthese_sections": cat["synth"]},
                     titre="Temps moyen par section (moyenne des moyennes par agent)")
        ctx.exporter(f"Alertes_durees_{t.code}.xlsx", {"Entretiens_courts": cat["alertes"]},
                     titre=f"Entretiens de moins de {p['seuil_men']:g} min (ménage) / {p['seuil_ind']:g} min (individuel)")
        if len(lots) > 1:
            synthese = (cat["agents"].groupby(["HH13_es", "Agent"], dropna=False)
                        .agg(nb_total=("nb_questionnaires", "sum"),
                             moy_globale_MEN=("moy_duree_GL_MEN", "mean"),
                             moy_globale_IND=("moy_duree_GL_IND", "mean"),
                             moy_globale_TOTAL=("moy_duree_GL_TOTAL", "mean")).round(2)
                        .reset_index().sort_values("nb_total", ascending=False))
            ctx.exporter("synthese_globale_agents.xlsx", {"Synthese_globale": synthese})
        bc = base_courante
        rapport = (bc.groupby("trimestre").agg(n=("id_unique", "count"), n_menage=("id_men_unique", "count"),
                                               moy_quest_men=("duree_GL_MEN", "mean"),
                                               moy_quest_ind=("duree_GL_IND", "mean"),
                                               moy_quest_total=("duree_QUEST_GL_TOTAL", "mean"),
                                               med_quest_men=("duree_GL_MEN", "median"),
                                               med_quest_ind=("duree_GL_IND", "median")).round(2).reset_index())
        ctx.exporter(f"rapport_synthese_trimestre_{t.code}.xlsx", {"Synthese_trimestre": rapport})
        if p["sauver_base"]:
            garder = ["interview__key", "membres__id", "trimestre", "HH2", "HH12", "HH13", "HH13_es", "type_agent",
                      "id_unique", "id_men_unique", "duree_QUEST_MEN", "duree_QUEST_IND", "duree_QUEST_TOTAL",
                      "duree_GL_MEN", "duree_GL_IND", "duree_QUEST_GL_TOTAL", "exclu_2jours", "entretient_end",
                      "entretient_nojoin", "entretient_partialend", "entretient_refus",
                      "entretient_joignable_teleop", "nb_miss"]
            garder += [c for c in bc.columns if c.startswith("duree_") and c not in garder]
            finale = bc[D.colonnes_presentes(bc, garder)].copy()
            finale.attrs = bc.attrs
            chemin = ctx.chemin(f"base_finale_durees_{t.code}.dta")
            D.sauver_dta(finale, chemin)
            ctx.fichier_produit(chemin)
            ctx.journal(f"  ✓ Base dérivée : {chemin.name}")
            if p["exporter_individus"]:
                ctx.exporter_csv(f"base_finale_durees_{t.code}.csv", finale, sep=",")
        # indicateurs et alertes
        ag0 = tous["agents"][0]
        ctx.indicateur("duree_moy_menage", bc.drop_duplicates("interview__key")["duree_GL_MEN"].mean())
        ctx.indicateur("duree_moy_individuel", bc["duree_GL_IND"].mean())
        for _, r in ag0.iterrows():
            ctx.indicateur("duree_moy_individuel", r["moy_duree_GL_IND"], "agent", r["Agent"])
        al0 = tous["alertes"][0]
        for agent, n in al0.groupby("Agent").size().items():
            ctx.alerte(agent, f"{n} entretien(s) plus court(s) que le seuil", "Moyenne")
        nex = int(bc["exclu_2jours"].sum())
        if nex:
            ctx.alerte("Durées", f"{nex} ligne(s) exclue(s) : début et fin à des dates différentes", "Basse")
        ctx.graphique("Durée moyenne du questionnaire individuel par agent (min)", "Par_agent", "Agent",
                      "Durée moy. individuel (min)", "barh")
        ctx.graphique("Temps moyen par section (min)", "Synthese_sections", "Section",
                      ["Agent_terrain", "Agent_teleoperateur"], "bar")
        ctx.resultat.resume = (f"{len(ag0)} agents, {len(al0)} entretien(s) court(s), "
                               f"{nex} durée(s) exclue(s) – {t.libelle}")


MODULE = TempsAdministration()
