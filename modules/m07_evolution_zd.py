"""Évolution des ZD par cohorte et détection des régions en retard.

Code d'origine : Code_evolution_ZD.do (terminé selon les instructions laissées dans le code).
Règle (section 5.6 du document v1.2) : le trimestre compte 13 semaines de référence (lundi →
dimanche). Une ZD programmée sur une semaine n'est attendue comme réalisée qu'une fois cette
semaine terminée. Le calendrier des ZD vient de la feuille Automate_envoie (N3) ; à défaut,
ABIDJAN réalise 13 ZD (1 par semaine) et les autres régions 7 ZD (1 toutes les 2 semaines).
Une ZD est réalisée dès qu'un ménage y est enquêté (EZ3). 33 régions de label_region (N1).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from enem_core import donnees as D
from enem_core import references as R
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, DateP, Dossier, Entier, Fichier, Liste, Texte
from enem_core.trimestre import Trimestre

from ._communs import (exiger, nom_fichier_menage, num, p_cohortes, p_fichier_menage, p_sortie, p_trimestre,
                       p_versions_menage)

AIDE_COHORTES = ("La base du trimestre en cours contient déjà toutes les cohortes : l'application y fait un keep "
                 "sur la valeur de rgmen indiquée. Ne renseignez un dossier que si la cohorte se trouve dans une "
                 "base séparée (ex. sous-dossier 3ieme_passage_…).")

G_CAL = "Calendrier"


def calendrier_cible(cal: pd.DataFrame, lundi: dt.date, nom_abidjan: str, nb_abj: int, nb_aut: int) -> dict:
    """Retourne {"ABIDJAN": [dates de fin], "AUTRES": [dates de fin]} ancrées sur ``lundi``."""
    res = {}
    if cal is not None and not cal.empty:
        origine = min(cal["debut"])
        for groupe, sub in cal.groupby("REGION"):
            fins = [lundi + dt.timedelta(days=(d - origine).days + 6) for d in sub["debut"]]
            res["ABIDJAN" if groupe == R.normaliser_nom(nom_abidjan) else "AUTRES"] = sorted(fins)
    if "ABIDJAN" not in res:
        res["ABIDJAN"] = [lundi + dt.timedelta(days=7 * k + 6) for k in range(nb_abj)]
    if "AUTRES" not in res:
        res["AUTRES"] = [lundi + dt.timedelta(days=7 * 2 * k + 6) for k in range(nb_aut)]
    return res


def cible(fins: list, date_ref: dt.date) -> int:
    return sum(1 for f in fins if f < date_ref)


class EvolutionZD(ModuleBase):
    id = "evolution_zd"
    nom = "Évolution des ZD par cohorte (régions en retard)"
    nom_court = "Évolution des ZD (retards)"
    description = ("Compte, pour chaque cohorte (passage 1 et réinterrogations), le nombre de ZD commencées par "
                   "région et le compare à la cible attendue à la date du jour selon le calendrier des semaines "
                   "de référence. Les régions en retard sont signalées.")
    equipe = "Terrain et téléopérateurs"
    frequence_jours = 7
    frequence_libelle = "Hebdomadaire"
    couleur = "#D9762B"
    entrees = "Base du trimestre (versions) et bases par passage ; Semaine_ref.xlsx (Automate_envoie, label_region)"
    sorties = "Evolution_ZD_<T>_<date>.xlsx (un tableau par cohorte + liste des ZD) et historique hebdomadaire"
    code_origine = ["Code_suivi_ZD/Code_evolution_ZD.do"]
    mots_cles = "ZD retard région cohorte semaine de référence avancement"
    ordre = 60
    sous_dossier = "Coordination"

    @staticmethod
    def _cohortes():
        param = p_cohortes(libelle="Cohortes de réinterrogation (dossier facultatif)")
        param.aide = AIDE_COHORTES
        param.note = ("La base du trimestre en cours contient déjà toutes les cohortes : indiquez seulement le "
                      "trimestre d'origine et sa valeur de rgmen. Le dossier ne sert que si la cohorte se trouve "
                      "dans une base séparée.")
        return param

    @property
    def parametres(self):
        return [
            p_trimestre(),
            DateP("lundi_semaine1", "Lundi de la semaine de référence 1", "", groupe=G_CAL, globale="lundi_semaine1",
                  aide="Date de début du trimestre de collecte (bouton calendrier)."),
            DateP("date_reference", "Date du point (vide = aujourd'hui)", "", groupe=G_CAL, obligatoire=False),
            Fichier("semaine_ref", "Fichier Semaine_ref.xlsx", "", groupe=G_CAL, globale="semaine_ref",
                    types=[("Excel", "*.xlsx")]),
            Entier("nb_zd_abidjan", "ZD à réaliser dans le trimestre : ABIDJAN (secours)", 13, groupe=G_CAL, mini=1,
                   maxi=100, aide="Utilisé seulement si le trimestre est absent de la feuille Automate_envoie."),
            Entier("nb_zd_autres", "ZD à réaliser : chacune des 32 autres régions (secours)", 7, groupe=G_CAL,
                   mini=1, maxi=100),
            Texte("nom_abidjan", "Nom de la région ABIDJAN dans les fichiers", "ABIDJAN", groupe=G_CAL),
            Booleen("inclure_courante", "Inclure la cohorte du trimestre en cours", True, groupe="Cohortes"),
            Entier("rgmen_courant", "Valeur de rgmen de la cohorte en cours", 1, groupe="Cohortes", mini=1, maxi=9),
            p_versions_menage("Dossiers des versions de la base du trimestre en cours"),
            p_fichier_menage(),
            self._cohortes(),
            Booleen("sauver_sous_bases", "Enregistrer les sous-bases par cohorte (keep sur rgmen)", True,
                    groupe="Cohortes"),
            Dossier("dossier_travail", "Dossier de travail des sous-bases (vide = dossier de sortie)", "",
                    groupe="Cohortes", obligatoire=False, doit_exister=False),
            Liste("cle_zd", "Variables de déduplication d'une ZD", "HH2A HH1 HH2 HH3 HH4 HH6 HH8",
                  groupe="Règle", aide="La ZD est répétée autant de fois qu'elle a de ménages : on dédoublonne "
                                       "avant de compter."),
            p_sortie(),
        ]

    def _nom_region(self, base, ref_regions):
        par_nom = {R.normaliser_nom(v): v for v in ref_regions.values()}

        def f(code):
            lab = D.libelle_valeur(base, "HH2", code)
            if isinstance(lab, str) and R.normaliser_nom(lab) in par_nom:
                return par_nom[R.normaliser_nom(lab)]
            try:
                c = int(float(code))
                if c in ref_regions:
                    return ref_regions[c]
            except (TypeError, ValueError):
                pass
            return f"Hors référentiel ({lab})"
        return f

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        lundi = p["lundi_semaine1"]
        date_ref = p.get("date_reference") or dt.date.today()
        semaine = (date_ref - lundi).days // 7 + 1
        ref_regions = R.regions(p["semaine_ref"])
        cal = R.calendrier_zd(p["semaine_ref"], t.code)
        if cal.empty:
            ctx.journal(f"  {t.code} absent de la feuille Automate_envoie : calendrier de secours "
                        f"({p['nb_zd_abidjan']} / {p['nb_zd_autres']} ZD).")
        fins = calendrier_cible(cal, lundi, p["nom_abidjan"], p["nb_zd_abidjan"], p["nb_zd_autres"])
        abj = R.normaliser_nom(p["nom_abidjan"])
        ctx.journal(f"Date du point : {date_ref:%d/%m/%Y} – semaine de référence {semaine} "
                    f"– cible ABIDJAN = {cible(fins['ABIDJAN'], date_ref)}, autres = {cible(fins['AUTRES'], date_ref)}")
        lots = []
        if p["inclure_courante"]:
            lots.append({"libelle": t.libelle + " (en cours)", "rgmen": p["rgmen_courant"], "dossier": ""})
        for c in p.get("cohortes") or []:
            lots.append({"libelle": c["libelle"], "rgmen": c["rgmen"], "dossier": c.get("dossier") or ""})
        if not lots:
            raise D.ErreurDonnees("Aucune cohorte à traiter.")
        fichier = nom_fichier_menage(p)
        for lot in lots:                      # un dossier qui ne contient pas la base est ignoré
            d = lot["dossier"]
            if d and not (Path(d) / fichier).exists() and not list(Path(d).glob(f"*/{fichier}")):
                ctx.journal(f"  ⚠ {fichier} absent de {d} : la cohorte {lot['libelle']} sera extraite de la base "
                            f"du trimestre en cours (keep if rgmen == {lot['rgmen']}).")
                ctx.alerte(lot["libelle"], f"Dossier ignoré ({fichier} introuvable) : cohorte extraite de la base "
                                           "du trimestre en cours", "Basse")
                lot["dossier"] = ""
        # La base du trimestre en cours (versions empilées) contient toutes les cohortes :
        # chaque cohorte est obtenue par un keep sur sa valeur de rgmen.
        base_courante = None
        if any(not lot["dossier"] for lot in lots):
            ctx.progression(5, "Lecture et empilement de la base du trimestre en cours")
            base_courante = D.lire_versions(p["versions_menage"], fichier, journal=ctx.journal)
            exiger(base_courante, ["HH2", "HH8", "rgmen"], "la base du trimestre en cours")
            ctx.journal(f"  Base du trimestre : {len(base_courante):,} ménages".replace(",", " "))
            ctx.journal("  Répartition par rgmen : " + ", ".join(
                f"{int(v)} → {n}" for v, n in num(base_courante, "rgmen").value_counts().sort_index().items()))
        travail = Path(p.get("dossier_travail") or ctx.dossier / "Base_cohortes")
        feuilles, resume, zds = {}, [], []
        for k, lot in enumerate(lots):
            ctx.progression(10 + 75 * k / len(lots), f"Cohorte {lot['libelle']} (rgmen = {lot['rgmen']})")
            if lot["dossier"]:
                base = D.lire_versions([lot["dossier"]], fichier, journal=ctx.journal)
                exiger(base, ["HH2", "HH8", "rgmen"], f"la base de la cohorte {lot['libelle']}")
            else:
                base = base_courante
            cle = D.colonnes_presentes(base, p["cle_zd"])
            sub = base[num(base, "rgmen") == lot["rgmen"]]
            ctx.journal(f"  keep if rgmen == {lot['rgmen']} → {len(sub):,} ménage(s)".replace(",", " "))
            if sub.empty:
                ctx.alerte(lot["libelle"], f"Aucun ménage avec rgmen = {lot['rgmen']} dans la base", "Haute")
            if p["sauver_sous_bases"] and not sub.empty:
                chemin = travail / f"{t.nom_base}_cohorte_rgmen{lot['rgmen']}.dta"
                sous = sub.copy()
                sous.attrs = base.attrs
                D.sauver_dta(sous, chemin)
                ctx.fichier_produit(chemin)
                ctx.journal(f"  ✓ Sous-base enregistrée : {chemin.name}")
            uniques = sub.drop_duplicates(cle)
            nommer = self._nom_region(base, ref_regions)
            uniques = uniques.assign(Region=uniques["HH2"].map(nommer))
            realise = uniques.groupby("Region").size()
            lignes = []
            noms = sorted(set(ref_regions.values()) | set(realise.index))
            for nom in noms:
                fin = fins["ABIDJAN"] if R.normaliser_nom(nom) == abj else fins["AUTRES"]
                c = cible(fin, date_ref)
                r = int(realise.get(nom, 0))
                statut = "En retard" if r < c else ("En avance" if r > c else "À jour")
                if nom.startswith("Hors référentiel"):
                    statut = "À vérifier"
                lignes.append({"Region": nom, "ZD_prevues_trimestre": len(fin), "ZD_cible_a_date": c,
                               "ZD_realisees": r, "Ecart": r - c, "Statut": statut})
            tab = pd.DataFrame(lignes).sort_values(["Statut", "Ecart", "Region"])
            nom_f = f"{lot['libelle']} (rgmen {lot['rgmen']})"
            feuilles[nom_f] = tab
            det = D.appliquer_libelles(uniques[D.colonnes_presentes(uniques, cle + ["Region", "HH8A"])],
                                       source=base)
            det.insert(0, "Cohorte", lot["libelle"])
            zds.append(det)
            n_ret = int((tab["Statut"] == "En retard").sum())
            resume.append({"Cohorte": lot["libelle"], "rgmen": lot["rgmen"], "ZD_realisees": int(tab["ZD_realisees"].sum()),
                           "ZD_cible": int(tab["ZD_cible_a_date"].sum()), "Regions_en_retard": n_ret,
                           "Regions_a_zero": int((tab["ZD_realisees"] == 0).sum())})
            for _, r in tab.iterrows():
                cle_ind = f"{lot['libelle']}|{r['Region']}"
                ctx.indicateur("zd_realisees", r["ZD_realisees"], "region", cle_ind, date_ref.isoformat())
                ctx.indicateur("zd_cible", r["ZD_cible_a_date"], "region", cle_ind, date_ref.isoformat())
                if r["Statut"] == "En retard":
                    ctx.alerte(f"{r['Region']} ({lot['libelle']})",
                               f"{r['ZD_realisees']} ZD réalisée(s) pour une cible de {r['ZD_cible_a_date']} "
                               f"(semaine {semaine})", "Haute" if r["ZD_realisees"] == 0 else "Moyenne")
            ctx.indicateur("regions_en_retard", n_ret, "cohorte", lot["libelle"], date_ref.isoformat())
            ctx.graphique(f"ZD réalisées vs cible – {lot['libelle']}", nom_f, "Region",
                          ["ZD_cible_a_date", "ZD_realisees"], "barh")
        parametres = pd.DataFrame([
            ("Trimestre", t.libelle), ("Lundi semaine 1", f"{lundi:%d/%m/%Y}"),
            ("Date du point", f"{date_ref:%d/%m/%Y}"), ("Semaine de référence", semaine),
            ("Source du calendrier", "Automate_envoie" if not cal.empty else "Paramètres de secours"),
            ("Cible ABIDJAN à date", cible(fins["ABIDJAN"], date_ref)),
            ("Cible autres régions à date", cible(fins["AUTRES"], date_ref)),
            ("Clé de déduplication", " ".join(p["cle_zd"])),
        ], columns=["Paramètre", "Valeur"])
        couleur = lambda r: {"En retard": "ROUGE", "À jour": "VERT", "En avance": "VERT",
                             "À vérifier": "ORANGE"}.get(r.get("Statut"))
        ctx.exporter(f"Evolution_ZD_{t.code}_{date_ref:%Y%m%d}.xlsx",
                     {"Resume": pd.DataFrame(resume), **feuilles, "Liste_ZD": pd.concat(zds, ignore_index=True),
                      "Parametres": parametres},
                     titre=f"Avancement des ZD au {date_ref:%d/%m/%Y} (semaine de référence {semaine})",
                     surlignage={k: couleur for k in feuilles})
        tot = sum(x["Regions_en_retard"] for x in resume)
        ctx.resultat.resume = f"Semaine {semaine} : {tot} situation(s) de retard sur {len(lots)} cohorte(s)"


MODULE = EvolutionZD()
