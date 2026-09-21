"""Exécute tous les modules sur le jeu de données fictif (sans interface).

Usage : python tests/test_modules.py [dossier_donnees_fictives]
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from enem_core.configuration import GLOBAUX_DEFAUT  # noqa: E402
from enem_core.execution import lancer  # noqa: E402
from enem_core.stockage import Stockage  # noqa: E402
from modules import ERREURS_CHARGEMENT, charger_modules  # noqa: E402


def valeurs_test(d: Path, sortie: Path) -> dict:
    ver = [str(d / "Base_menage_individuel" / f"ENEM_2026T3_{i}_STATA_All") for i in (1, 2, 3)]
    ref = RACINE / "reference"
    cohortes = [{"libelle": "T3-2025", "rgmen": 3, "dossier": str(d / "Base_brute_T3_2025")},
                {"libelle": "T2-2025", "rgmen": 4, "dossier": str(d / "Base_brute_T2_2025")}]
    communs = {"trimestre": "T3_2026", "versions_menage": ver, "dossier_sortie": str(sortie)}
    return {
        "preparation_bases": {**communs, "versions": ver, "dossier_destination": str(sortie / "fusion")},
        "presence_agents": {**communs, "date_debut": "29/06/2026", "date_fin": "15/09/2026",
                            "dossier_paradata": str(d / "Paradata"),
                            "information_agent": str(ref / "information_agent.xlsx")},
        "temps_administration": {**communs, "comparaison": [{"trimestre": "T3_2025",
                                                             "dossier": str(d / "Base_brute_T3_2025")}]},
        "numero_porte": {**communs, "versions_denombrement": [str(p) for p in sorted((d / "Base_denombrement").iterdir())]},
        "coherence_passages": {**communs, "cohortes": cohortes, "variable": "SEXE (M5)"},
        "coherence_emploi": {**communs, "cohortes": cohortes, "variable": "EMPLOI (EN_EMP)"},
        "menages_par_zd": communs,
        "evolution_zd": {**communs, "lundi_semaine1": "29/06/2026", "date_reference": "14/09/2026",
                         "semaine_ref": str(ref / "Semaine_ref.xlsx"),
                         "cohortes": [{"libelle": "T3-2025", "rgmen": 3,
                                       "dossier": str(d / "Base_agent_teleoperateur" / "3ieme_passage_ENEMT3_2025")},
                                      {"libelle": "T2-2025", "rgmen": 4,
                                       "dossier": str(d / "Base_agent_teleoperateur" / "4ieme_passage_ENEMT2_2025")}]},
        "codification_emploi": communs,
        "controles_base": communs,
        "simulation_ponderation": {**communs, "base_historique": str(d / "Base_Travail" / "Base_Travail_BT_vf_25T3.dta"),
                                   "trimestre_reference": "T3_2025", "valeur_trimestre": "25T3"},
        "tableaux_bulletin": {**communs, "base_courante": "",
                              "bases_empilees": [{"fichier": str(d / "Base_Travail" / "Base_Travail_BT_vf_25T3.dta")},
                                                 {"fichier": str(d / "Base_Travail" / "Base_Travail_BT_vf_24T3.dta")}],
                              "reconstruire": True,
                              "maquette": str(ref / "Tableaux_Indicateurs_ENEM_template_DG.xlsx")},
        "gantt": {**communs, "fichier_taches": str(ref / "Fichier_Gant.xlsx"), "trimestre": "T1_2026",
                  "debut_points": "29/12/2025"},
    }


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "tests" / "donnees_fictives"
    sortie = Path(tempfile.mkdtemp(prefix="enem_resultats_"))
    st = Stockage(sortie / "test.sqlite")
    mods = {m.id: m for m in charger_modules()}
    if ERREURS_CHARGEMENT:
        print(ERREURS_CHARGEMENT)
    vals = valeurs_test(d, sortie)
    echecs = 0
    produits: dict = {}
    for cle, v in vals.items():
        if cle == "tableaux_bulletin" and not v["base_courante"]:
            base_sim = produits.get("simulation_ponderation")
            if not base_sim:
                print("IGNORÉ tableaux_bulletin : la simulation de pondération n'a pas produit de base")
                continue
            v["base_courante"] = str(base_sim)
        mid = "coherence_passages" if cle == "coherence_emploi" else cle
        m = mods[mid]
        base = {p.cle: p.defaut for p in m.parametres}
        base.update(v)
        journal = []
        res = lancer(m, base, dict(GLOBAUX_DEFAUT), st, journal=journal.append)
        ok = res.statut == "terminé"
        echecs += not ok
        print(f"{'OK ' if ok else 'ÉCHEC'} {cle:22s} {res.resume}  [{len(res.fichiers)} fichiers, "
              f"{len(res.alertes)} alertes, {len(res.tables)} tables]")
        dta = [f for f in res.fichiers if str(f).lower().endswith(".dta")]
        if dta:
            produits[cle] = dta[0]
        if not ok:
            print("\n".join(journal[-25:]))
    print(f"Résultats dans {sortie}")
    print(st.historique()[["module", "statut", "duree_s"]].to_string())
    return echecs


if __name__ == "__main__":
    sys.exit(main())
