"""Suivi de présence des agents à partir des paradata Survey Solutions.

Code d'origine : suivi_presence_agents_v2.py
Décisions : cumul depuis le début du trimestre (PR2), week-ends inclus (PR3),
événements AnswerSet uniquement (PR4), détection automatique des dossiers (PR7),
fuseau horaire paramétrable (N10).
"""

from __future__ import annotations

import calendar
import datetime as dt
from pathlib import Path

import pandas as pd

from enem_core import donnees as D
from enem_core import references as R
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, DateP, Dossier, Entier, Fichier, Reel, Texte, Versions
from enem_core.trimestre import Trimestre

from ._communs import G_BASES, G_GENERAL, p_sortie, p_trimestre

MOIS = {1: "Janvier", 2: "Fevrier", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin", 7: "Juillet",
        8: "Aout", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Decembre"}
ROLES = {"0": "<UNKNOWN ROLE>", "1": "Interviewer", "2": "Supervisor", "3": "Headquarter",
         "4": "Administrator", "5": "API User"}


class PresenceAgents(ModuleBase):
    id = "presence_agents"
    nom = "Présence des agents (paradata)"
    nom_court = "Présence des agents"
    description = ("Calcule, pour chaque agent et chaque jour, la présence (1/0) et les heures travaillées "
                   "(premier → dernier événement de saisie), puis produit les tableaux mensuels et les résumés "
                   "(jours travaillés, journées de faible activité).")
    equipe = "Terrain et téléopérateurs"
    frequence_jours = 7
    frequence_libelle = "Chaque fin de semaine"
    couleur = "#E8891A"
    entrees = "paradata.tab (dossiers *_Paradata_All) + information_agent.xlsx"
    sorties = "Equipe_<équipe>_<Mois>.xlsx, Resume_<équipe>_<Mois>.xlsx, synthèse de la période"
    code_origine = ["Code_suici_presence_agent/suivi_presence_agents_v2.py"]
    mots_cles = "présence heures travaillées paradata agents jours"
    ordre = 10
    sous_dossier = "Coordination"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            DateP("date_debut", "Début de la période (cumul)", "", groupe=G_GENERAL, globale="lundi_semaine1",
                  aide="Cumul depuis le début du trimestre : lundi de la semaine de référence 1."),
            DateP("date_fin", "Fin de la période (vide = aujourd'hui)", "", groupe=G_GENERAL, obligatoire=False),
            Dossier("dossier_paradata", "Dossier contenant les dossiers paradata", "", groupe=G_BASES,
                    obligatoire=False,
                    aide="Détection automatique des sous-dossiers ENEM_<AAAA>T<q>_*_Paradata_All."),
            Versions("versions_paradata", "Ou : dossiers paradata choisis manuellement", [""], groupe=G_BASES,
                     obligatoire=False, fichier_attendu="paradata.tab"),
            Fichier("information_agent", "Fichier des agents (information_agent.xlsx)", "", groupe=G_BASES,
                    globale="information_agent", types=[("Excel", "*.xlsx")]),
            Texte("evenements", "Événements pris en compte (séparés par des virgules)", "AnswerSet",
                  groupe="Calcul", aide="Décision PR4 : AnswerSet uniquement. Laisser vide = tous les événements."),
            Reel("seuil_heures", "Seuil de journée faible (heures)", 2, groupe="Calcul", mini=0),
            Booleen("inclure_weekend", "Inclure les week-ends dans le taux de présence", True, groupe="Calcul"),
            Entier("decalage_horaire", "Décalage horaire par rapport à UTC (heures)", 0, groupe="Calcul",
                   mini=-12, maxi=14),
            p_sortie(),
        ]

    # ------------------------------------------------------------------
    def _dossiers(self, p):
        dossiers = [Path(v) for v in p.get("versions_paradata") or []]
        racine = p.get("dossier_paradata")
        if racine and Path(racine).is_dir():
            t = Trimestre.depuis(p["trimestre"])
            motif = f"{t.nom_base}_*Paradata*"
            trouves = sorted(Path(racine).glob(motif)) or sorted(Path(racine).glob("*Paradata*"))
            dossiers += [d for d in trouves if d.is_dir() and d not in dossiers]
        if not dossiers:
            raise D.ErreurDonnees("Aucun dossier paradata : indiquez le dossier parent ou les dossiers manuellement.")
        return dossiers

    def _lire(self, ctx, dossiers):
        morceaux = []
        for i, d in enumerate(dossiers):
            ctx.progression(5 + 30 * i / len(dossiers), f"Lecture de {d.name}")
            f = d / "paradata.tab"
            if not f.exists():
                trouves = list(d.rglob("paradata.tab"))
                if not trouves:
                    raise D.ErreurDonnees(f"paradata.tab introuvable dans {d}")
                f = trouves[0]
            df = pd.read_csv(f, sep="\t", dtype=str, usecols=lambda c: c in {
                "interview__id", "event", "responsible", "role", "timestamp_utc", "tz_offset"})
            df["source_dossier"] = d.name
            ctx.journal(f"  - {f} : {len(df):,} lignes".replace(",", " "))
            morceaux.append(df)
        return pd.concat(morceaux, ignore_index=True)

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        debut = p["date_debut"]
        fin = p.get("date_fin") or dt.date.today()
        seuil = p["seuil_heures"]
        para = self._lire(ctx, self._dossiers(p))
        if "role" in para.columns:
            para["role_label"] = para["role"].map(ROLES).fillna(para["role"])
        evts = [e.strip() for e in (p.get("evenements") or "").split(",") if e.strip()]
        ctx.progression(40, "Calcul des présences et des heures")
        df = para.dropna(subset=["responsible", "timestamp_utc"])
        df = df[df["responsible"].str.strip() != ""]
        if evts and "event" in df.columns:
            df = df[df["event"].isin(evts)]
        df = df.assign(ts=pd.to_datetime(df["timestamp_utc"], errors="coerce") + pd.Timedelta(hours=p["decalage_horaire"]))
        df = df.dropna(subset=["ts"])
        df = df[(df["ts"].dt.date >= debut) & (df["ts"].dt.date <= fin)]
        if df.empty:
            raise D.ErreurDonnees("Aucun événement dans la période choisie.")
        df["date"] = df["ts"].dt.date
        agg = (df.groupby(["responsible", "date"])["ts"]
               .agg(premier_evt="min", dernier_evt="max", nb_evenements="count").reset_index())
        agg["heures_travail"] = ((agg["dernier_evt"] - agg["premier_evt"]).dt.total_seconds() / 3600).round(2)
        agg["presence"] = 1
        agg["annee"] = pd.to_datetime(agg["date"]).dt.year
        agg["mois"] = pd.to_datetime(agg["date"]).dt.month
        agg["jour"] = pd.to_datetime(agg["date"]).dt.day

        tele, terrain = R.equipes(p["information_agent"])
        equipes = [("Equipe_teleoperateur", tele, [c for c in ("Nom_agent", "Nom_supervieur") if c in tele.columns]),
                   ("Equipe_terrain", terrain, [c for c in ("Region", "Dr", "Nom_agent") if c in terrain.columns])]
        # agents présents dans les paradata mais absents des listes
        connus = set(tele["responsible"]) | set(terrain["responsible"])
        inconnus = sorted(set(agg["responsible"]) - connus)
        n_jours_periode = self._nb_jours(debut, fin, p["inclure_weekend"])
        syntheses = {}
        for k, (nom, equipe, idc) in enumerate(equipes):
            ctx.progression(50 + 20 * k, f"Fichiers {nom}")
            equipe = equipe.drop_duplicates(subset="responsible").set_index("responsible")
            self._fichiers_mensuels(ctx, nom, equipe, idc, agg, seuil, p["inclure_weekend"])
            sub = agg[agg["responsible"].isin(equipe.index)]
            s = equipe[idc].copy()
            s["Nb_jours_travailles"] = sub.groupby("responsible")["date"].nunique()
            s["Nb_jours_travailles"] = s["Nb_jours_travailles"].fillna(0).astype(int)
            s["Nb_jours_periode"] = n_jours_periode
            s["Taux_presence_pct"] = (100 * s["Nb_jours_travailles"] / max(n_jours_periode, 1)).round(1)
            s["Heures_totales"] = sub.groupby("responsible")["heures_travail"].sum().round(2)
            s["Heures_moy_par_jour"] = sub.groupby("responsible")["heures_travail"].mean().round(2)
            s[f"Nb_jours_moins_{seuil:g}h"] = sub[sub["heures_travail"] < seuil].groupby("responsible").size()
            s = s.fillna({"Heures_totales": 0, f"Nb_jours_moins_{seuil:g}h": 0}).reset_index()
            s = s.sort_values("Nb_jours_travailles")
            syntheses[nom] = s
            for _, r in s[s["Nb_jours_travailles"] == 0].iterrows():
                ctx.alerte(f"{r['responsible']} {r.get('Nom_agent', '')}".strip(),
                           f"Aucun jour travaillé entre le {debut:%d/%m} et le {fin:%d/%m}", "Haute")
            ctx.indicateur(f"taux_presence_moyen_{nom}", s["Taux_presence_pct"].mean())
            for _, r in s.iterrows():
                ctx.indicateur("taux_presence", r["Taux_presence_pct"], "agent", r["responsible"])
        feuilles = {f"Synthese_{k.split('_')[1]}": v for k, v in syntheses.items()}
        if inconnus:
            feuilles["Agents_non_references"] = pd.DataFrame({"responsible": inconnus})
            ctx.alerte("information_agent.xlsx", f"{len(inconnus)} compte(s) présents dans les paradata mais absents "
                                                 "du fichier des agents", "Basse")
        feuilles["Detail_journalier"] = agg[["responsible", "date", "premier_evt", "dernier_evt",
                                              "nb_evenements", "heures_travail"]]
        rouge = lambda r: "ROUGE" if r.get("Nb_jours_travailles", 1) == 0 else (
            "ORANGE" if r.get("Taux_presence_pct", 100) < 50 else None)
        ctx.exporter(f"Synthese_presence_{t.code}_{debut:%Y%m%d}_{fin:%Y%m%d}.xlsx", feuilles,
                     titre=f"Présence des agents du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}",
                     surlignage={k: rouge for k in feuilles if k.startswith("Synthese")})
        for k in feuilles:
            if k.startswith("Synthese"):
                ctx.graphique(f"Taux de présence – {k}", k, "responsible", "Taux_presence_pct", "barh")
        ctx.resultat.resume = (f"{agg['responsible'].nunique()} agents actifs, {len(agg)} journées de travail "
                               f"du {debut:%d/%m} au {fin:%d/%m}")

    @staticmethod
    def _nb_jours(debut, fin, weekend):
        jours = pd.date_range(debut, fin, freq="D")
        return int(len(jours) if weekend else (jours.weekday < 5).sum())

    def _fichiers_mensuels(self, ctx, nom, equipe, idc, agg, seuil, weekend):
        for (annee, mois), sub in agg.groupby(["annee", "mois"]):
            nb = calendar.monthrange(annee, mois)[1]
            jours = list(range(1, nb + 1))
            pres = sub.pivot_table(index="responsible", columns="jour", values="presence", fill_value=0)
            heures = sub.pivot_table(index="responsible", columns="jour", values="heures_travail",
                                     fill_value=0, aggfunc="sum")
            pres = equipe[idc].join(pres.reindex(columns=jours, fill_value=0))
            heures = equipe[idc].join(heures.reindex(columns=jours, fill_value=0))
            pres[jours] = pres[jours].fillna(0).astype(int)
            heures[jours] = heures[jours].fillna(0).round(2)
            pres, heures = pres.reset_index(), heures.reset_index()
            pres.columns = [str(c) for c in pres.columns]
            heures.columns = [str(c) for c in heures.columns]
            s = sub[sub["responsible"].isin(equipe.index)]
            jt = equipe[idc].copy()
            jt["Nb_jours_travailles"] = s.groupby("responsible")["jour"].nunique()
            jt["Nb_jours_travailles"] = jt["Nb_jours_travailles"].fillna(0).astype(int)
            jours_mois = nb if weekend else sum(1 for j in jours if dt.date(annee, mois, j).weekday() < 5)
            jt["Nb_jours_mois"] = jours_mois
            jt["Taux_presence_pct"] = (100 * jt["Nb_jours_travailles"] / jours_mois).round(1)
            jt = jt.reset_index().sort_values("Nb_jours_travailles")
            col = f"Nb_jours_moins_de_{seuil:g}h"
            faibles = s[(s["heures_travail"] > 0) & (s["heures_travail"] < seuil)]
            rh = equipe[idc].copy()
            rh[col] = faibles.groupby("responsible").size()
            rh[col] = rh[col].fillna(0).astype(int)
            rh = rh.reset_index().sort_values(col, ascending=False)
            detail = faibles.merge(equipe[idc].reset_index(), on="responsible", how="left")
            detail = detail[["responsible"] + idc + ["jour", "heures_travail"]].rename(
                columns={"heures_travail": "Heures_travaillees"}).sort_values(["responsible", "jour"])
            m = MOIS[mois]
            ctx.exporter(f"{nom}_{m}_{annee}.xlsx", {"JourMois": pres, "Hour_work_mois": heures}, afficher=False)
            ctx.exporter(f"Resume_{nom}_{m}_{annee}.xlsx",
                         {"Jours_travailles": jt, f"Moins_{seuil:g}h_resume": rh, f"Moins_{seuil:g}h_detail": detail},
                         afficher=False)


MODULE = PresenceAgents()
