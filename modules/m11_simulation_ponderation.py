"""Simulation de la pondération du trimestre en cours (bloc « Simulation indicateur », étape 1).

Principe : en cours de collecte, la pondération du trimestre en cours n'existe pas encore.
On ajuste donc une loi sur la pondération observée au trimestre de même rang de l'année
précédente (T3-2025 pour T3-2026), on tire un vecteur de poids de même densité pour la base
du trimestre en cours, puis on enregistre la base de travail utilisée par le module
« Tableaux du bulletin ».

Code d'origine : ``simulation_pmencor_ind_T3_2026.do``
Méthode du do-file, reproduite à l'identique : loi Gamma ajustée par la méthode des moments
(forme = moyenne² / variance, échelle = variance / moyenne), graine 12345.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from enem_core import donnees as D
from enem_core import indicateurs as I
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Choix, Entier, Fichier, Liste, Texte, TrimestreP
from enem_core.trimestre import Trimestre

from ._communs import (G_BASES, charger_membres, charger_menage, p_fichier_menage, p_sortie,
                       p_trimestre, p_versions_menage)

GAMMA = "Loi Gamma ajustée par la méthode des moments (do-file d'origine)"
METHODES = [GAMMA,
            "Tirage dans la distribution observée (bootstrap)",
            "Loi log-normale ajustée",
            "Moyenne de la strate"]


def simuler(poids_ref: pd.Series, n: int, methode: str, alea: np.random.Generator) -> np.ndarray:
    """Tire n pondérations à partir de la distribution de référence."""
    poids = pd.to_numeric(poids_ref, errors="coerce").dropna()
    poids = poids[poids > 0]
    if poids.empty or n == 0:
        return np.full(n, np.nan)
    if methode == GAMMA:
        moyenne = float(poids.mean())
        variance = float(poids.var(ddof=1)) if len(poids) > 1 else 0.0
        if variance <= 0:
            return np.full(n, moyenne)
        forme, echelle = moyenne ** 2 / variance, variance / moyenne
        return alea.gamma(forme, echelle, n)
    if methode.startswith("Moyenne"):
        return np.full(n, float(poids.mean()))
    if methode.startswith("Loi log-normale"):
        logs = np.log(poids.to_numpy(dtype=float))
        if len(logs) < 3 or logs.std() == 0:
            return np.full(n, float(poids.mean()))
        return np.exp(alea.normal(logs.mean(), logs.std(ddof=1), n))
    return alea.choice(poids.to_numpy(dtype=float), size=n, replace=True)


def parametres_gamma(poids_ref: pd.Series) -> dict:
    p = pd.to_numeric(poids_ref, errors="coerce").dropna()
    p = p[p > 0]
    if len(p) < 2:
        return {}
    moyenne, variance = float(p.mean()), float(p.var(ddof=1))
    if variance <= 0:
        return {}
    return {"Moyenne observée": round(moyenne, 4), "Variance observée": round(variance, 4),
            "Paramètre de forme (a)": round(moyenne ** 2 / variance, 4),
            "Paramètre d'échelle (b)": round(variance / moyenne, 4),
            "Nb obs. de référence": len(p)}


def resume(poids: pd.Series) -> dict:
    p = pd.to_numeric(poids, errors="coerce").dropna()
    if p.empty:
        return {"Effectif": 0}
    return {"Effectif": len(p), "Somme": round(p.sum(), 1), "Moyenne": round(p.mean(), 2),
            "Écart-type": round(p.std(ddof=1), 2) if len(p) > 1 else 0.0, "Minimum": round(p.min(), 2),
            "P25": round(p.quantile(0.25), 2), "Médiane": round(p.median(), 2),
            "P75": round(p.quantile(0.75), 2), "Maximum": round(p.max(), 2)}


class SimulationPonderation(ModuleBase):
    id = "simulation_ponderation"
    nom = "Simulation indicateur – 1. Pondération simulée"
    nom_court = "Pondération simulée"
    description = ("Ajuste une loi Gamma sur la pondération du trimestre de référence (même rang, année "
                   "précédente), tire une pondération de même densité pour la base du trimestre en cours "
                   "et enregistre la base de travail du bulletin.")
    equipe = "Coordination"
    frequence_jours = 30
    frequence_libelle = "À mi-parcours de la collecte"
    couleur = "#6A4C93"
    entrees = ("Base de travail du trimestre de référence (pondérée) + base ménage et membres du trimestre "
               "en cours (versions)")
    sorties = ("Base_Travail_BT_vf_<AA>T<q>.dta (base de travail pondérée), "
               "Simulation_ponderation_<T>.xlsx (ajustement et comparaison des distributions)")
    code_origine = ["Simulation_Indicateur/simulation_pmencor_ind_T3_2026.do"]
    mots_cles = "pondération simulation gamma bulletin indicateurs mi-parcours"
    ordre = 75
    sous_dossier = "Simulation_Indicateur"

    @property
    def parametres(self):
        base = Fichier("base_historique", "Base de travail du trimestre de référence (.dta, pondérée)", "",
                       groupe=G_BASES, types=[("Stata", "*.dta")],
                       aide="Ex. Base_Travail_BT_vf_25T3.dta : base déjà pondérée du trimestre de référence.")
        base.note = ("La pondération du trimestre en cours n'existe pas encore : elle est simulée à partir du "
                     "trimestre de référence (même rang, année précédente) puis appliquée à la base en cours. "
                     "Les résultats du bulletin qui en découlent sont des estimations provisoires.")
        return [
            p_trimestre(),
            TrimestreP("trimestre_reference", "Trimestre de référence (pondération existante)", "", groupe="Général",
                       obligatoire=False, aide="Vide = même rang, année précédente (ex. T3_2025 pour T3_2026)."),
            base,
            Texte("var_ponderation", "Variable de pondération dans la base de référence", "pmencor_ind",
                  groupe=G_BASES),
            Texte("var_trimestre", "Variable identifiant le trimestre", "trimestre", groupe=G_BASES),
            Texte("valeur_trimestre", "Valeur du trimestre de référence dans cette variable (vide = automatique)",
                  "", groupe=G_BASES, obligatoire=False,
                  aide="Ex. 25T3, T3_2025 ou 2025T3 selon le codage de votre base."),
            p_versions_menage("Dossiers des versions de la base du trimestre en cours"),
            p_fichier_menage(),
            Choix("methode", "Méthode de simulation", GAMMA, groupe="Méthode", options=METHODES,
                  aide="Le do-file d'origine utilise la loi Gamma ajustée par la méthode des moments."),
            Liste("strates", "Variables de strate (vide = simulation nationale, comme le do-file)", "",
                  groupe="Méthode", obligatoire=False,
                  aide="Si renseigné, la pondération est ajustée séparément dans chaque strate "
                       "(ex. hh2 hh6). Le do-file d'origine n'utilise pas de strate."),
            Booleen("caler", "Caler la somme des pondérations sur le trimestre de référence", False,
                    groupe="Méthode",
                    aide="Le do-file d'origine ne cale pas : décocher pour reproduire son résultat."),
            Entier("graine", "Graine aléatoire", 12345, groupe="Méthode", mini=0, maxi=10 ** 9),
            Texte("nom_variable", "Nom de la variable créée", "pmencor_ind", groupe="Sortie"),
            Texte("nom_base_travail", "Nom de la base de travail produite (vide = automatique)", "",
                  groupe="Sortie", obligatoire=False,
                  aide="Par défaut Base_Travail_BT_vf_<AA>T<q>.dta (ex. Base_Travail_BT_vf_26T3.dta)."),
            Booleen("construire_variables", "Construire les variables du bulletin (1_1, 1_2, CISE)", True,
                    groupe="Sortie",
                    aide="Comme dans 1_Tabulation_DG_Bulletin : les variables objectives, les indicateurs "
                         "du bulletin et la CISE 18 sont créés puis enregistrés dans la base de travail."),
            p_sortie(),
        ]

    # ------------------------------------------------------------------
    @staticmethod
    def code_court(t: Trimestre) -> str:
        """Codage « 26T3 » utilisé par les bases de travail du bulletin."""
        return f"{t.annee % 100:02d}T{t.numero}"

    def _masque_reference(self, serie: pd.Series, t: Trimestre, valeur: str) -> pd.Series:
        s = serie.map(lambda v: "" if pd.isna(v) else str(v).strip().upper())
        if valeur:
            return s == valeur.strip().upper()
        formes = {t.code.upper(), t.libelle.upper(), t.nom_base.upper(), self.code_court(t).upper(),
                  f"{t.annee}T{t.numero}", f"T{t.numero}{t.annee}", f"{t.annee}{t.numero}"}
        return s.isin(formes)

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        ref = Trimestre.depuis(p["trimestre_reference"]) if p.get("trimestre_reference") else t.decale(-4)
        var_p, nom = p["var_ponderation"], p["nom_variable"]
        var_t = p["var_trimestre"]
        alea = np.random.default_rng(p["graine"])
        ctx.journal(f"Trimestre en cours : {t.libelle}   •   pondération simulée d'après {ref.libelle}")

        # --- Partie 1 : ajustement sur le trimestre de référence
        ctx.progression(5, "Lecture de la base de référence")
        hist = D.lire_dta(p["base_historique"])
        hist = I.normaliser_noms(hist)
        for c in (var_p, var_t):
            if c not in hist.columns:
                raise D.ErreurDonnees(f"Variable « {c} » absente de la base de référence "
                                      f"({', '.join(list(hist.columns)[:12])}…)")
        hist_ref = hist[self._masque_reference(hist[var_t], ref, p.get("valeur_trimestre"))]
        if hist_ref.empty:
            valeurs = sorted({str(v) for v in hist[var_t].dropna().unique()})[:15]
            raise D.ErreurDonnees(f"Aucune ligne du trimestre {ref.libelle} dans la base de référence. "
                                  f"Valeurs trouvées dans « {var_t} » : {', '.join(valeurs)}")
        manquants = int(pd.to_numeric(hist_ref[var_p], errors="coerce").isna().sum())
        if manquants:
            ctx.journal(f"  {manquants} valeur(s) manquante(s) sur {var_p} : exclue(s) de l'ajustement")
            hist_ref = hist_ref[pd.to_numeric(hist_ref[var_p], errors="coerce").notna()]
        ctx.journal(f"  Base de référence : {len(hist_ref):,} ligne(s)".replace(",", " "))
        ajust = parametres_gamma(hist_ref[var_p])
        if p["methode"] == GAMMA and ajust:
            echelle = ajust["Paramètre d'échelle (b)"]
            ctx.journal(f"  Ajustement Gamma : forme a = {ajust['Paramètre de forme (a)']}, "
                        f"échelle b = {echelle}")

        # --- Partie 2 : base du trimestre en cours (ménage 1:m membres)
        ctx.progression(25, "Lecture de la base du trimestre en cours")
        men = charger_menage(ctx, p)
        ctx.verifier_arret()
        mem = charger_membres(ctx, p)
        base = D.fusion_menage_membres(men, mem)
        ctx.journal(f"  Fusion ménage × membres : {len(men):,} ménages → {len(base):,} individus"
                    .replace(",", " "))
        base = I.normaliser_noms(base)
        if base.attrs.get("conflits_noms"):
            ctx.journal("  Conflits de noms après normalisation (non renommés) : "
                        + " ".join(base.attrs["conflits_noms"]))
        base = base.reset_index(drop=True)

        # trimestre / année : indispensables aux tabulations
        if var_t not in base.columns:
            base[var_t] = self.code_court(t)
            ctx.journal(f"  Variable « {var_t} » absente de la base en cours : créée à « {self.code_court(t)} »")
        if "annee" not in base.columns:
            base["annee"] = float(t.annee)
            ctx.journal(f"  Variable « annee » créée à {t.annee}")

        # --- Simulation
        ctx.progression(45, f"Simulation de la pondération ({p['methode']})")
        simule = pd.Series(np.nan, index=base.index, dtype=float)
        strates = [c.lower() for c in p["strates"]]
        strates = [c for c in strates if c in base.columns and c in hist_ref.columns]
        ignorees = [c for c in p["strates"] if c.lower() not in strates]
        if ignorees:
            ctx.journal(f"  Strate(s) ignorée(s) (absentes d'une des bases) : {' '.join(ignorees)}")
        lignes_rapport, hors_strate = [], 0
        if strates:
            cles_ref = {cle: sub[var_p] for cle, sub in hist_ref.groupby(strates, dropna=False)}
            for cle, sub in base.groupby(strates, dropna=False):
                poids_ref = cles_ref.get(cle)
                if poids_ref is None:
                    poids_ref, hors_strate = hist_ref[var_p], hors_strate + len(sub)
                simule.loc[sub.index] = simuler(poids_ref, len(sub), p["methode"], alea)
                lignes_rapport.append({"Strate": " / ".join(str(x) for x in (cle if isinstance(cle, tuple) else (cle,))),
                                       **{f"Réf. {k}": v for k, v in resume(poids_ref).items()},
                                       **{f"Sim. {k}": v for k, v in resume(simule.loc[sub.index]).items()}})
        else:
            simule[:] = simuler(hist_ref[var_p], len(base), p["methode"], alea)
        if hors_strate:
            ctx.alerte("Simulation", f"{hors_strate} ligne(s) dans une strate absente du trimestre de référence : "
                                     "pondération simulée au niveau national", "Basse")
        if p["caler"]:
            total_ref, total_sim = pd.to_numeric(hist_ref[var_p], errors="coerce").sum(), simule.sum()
            if total_sim > 0:
                simule *= total_ref / total_sim
                ctx.journal(f"  Calage sur le total du trimestre de référence : facteur {total_ref / total_sim:.4f}")
        base[nom] = simule

        # --- Variables du bulletin
        if p["construire_variables"]:
            ctx.progression(65, "Construction des variables du bulletin")
            base = I.construire_variables(base, journal=ctx.journal)

        # --- Rapport
        ctx.progression(80, "Rapport de comparaison")
        feuilles = {}
        if ajust:
            feuilles["Ajustement"] = pd.DataFrame([{"Paramètre": k, "Valeur": v} for k, v in ajust.items()])
        feuilles["Comparaison"] = pd.DataFrame([
            {"Série": f"Référence {ref.libelle} ({var_p})", **resume(hist_ref[var_p])},
            {"Série": f"Simulée {t.libelle} ({nom})", **resume(base[nom])}])
        if lignes_rapport:
            feuilles["Par_strate"] = pd.DataFrame(lignes_rapport)
        ctx.exporter(f"Simulation_ponderation_{t.code}.xlsx", feuilles,
                     titre=f"Pondération simulée pour {t.libelle} d'après {ref.libelle} – estimations provisoires")

        # --- Base de travail
        nom_base = (p.get("nom_base_travail") or "").strip() or f"Base_Travail_BT_vf_{self.code_court(t)}.dta"
        if not nom_base.lower().endswith(".dta"):
            nom_base += ".dta"
        chemin = ctx.chemin(nom_base)
        D.sauver_dta(base, chemin)
        ctx.fichier_produit(chemin)
        ctx.journal(f"  ✓ Base de travail : {chemin.name} ({len(base):,} lignes)".replace(",", " "))
        ctx.indicateur("ponderation_simulee_totale", float(base[nom].sum()))
        ctx.indicateur("ponderation_simulee_moyenne", float(base[nom].mean()))
        if lignes_rapport:
            ctx.graphique("Pondération : référence vs simulée (moyenne par strate)", "Par_strate", "Strate",
                          ["Réf. Moyenne", "Sim. Moyenne"], "barh", etiquettes=True)
        ctx.resultat.resume = (f"Pondération simulée d'après {ref.libelle} : total {base[nom].sum():,.0f} "
                               f"sur {len(base):,} lignes".replace(",", " "))


MODULE = SimulationPonderation()
