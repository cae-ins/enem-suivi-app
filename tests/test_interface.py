"""Test automatique de l'interface (ouvre chaque écran, lance des modules, captures d'écran).

Usage (Linux, sans écran) : xvfb-run -s "-screen 0 1440x900x24" python tests/test_interface.py <donnees> <captures>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

donnees = Path(sys.argv[1])
captures = Path(sys.argv[2])
captures.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="enem_ui_"))
ver = [str(donnees / "Base_menage_individuel" / f"ENEM_2026T3_{i}_STATA_All") for i in (1, 2, 3)]
profil = {
    "globaux": {
        "utilisateur": "Beverlin", "trimestre": "T3_2026", "lundi_semaine1": "29/06/2026",
        "dossier_sortie": str(tmp / "Resultats"), "base_donnees": str(tmp / "suivi.sqlite"),
        "semaine_ref": str(RACINE / "reference" / "Semaine_ref.xlsx"),
        "information_agent": str(RACINE / "reference" / "information_agent.xlsx"),
        "fichier_gantt": str(RACINE / "reference" / "Fichier_Gant.xlsx"),
        "dossier_codes_origine": str(donnees.parent / "codes_origine"),
        "versions_menage": ver,
        "versions_denombrement": [str(p) for p in sorted((donnees / "Base_denombrement").iterdir())],
        "cohortes": [{"libelle": "T3-2025", "rgmen": 3, "dossier": str(donnees / "Base_brute_T3_2025")},
                     {"libelle": "T2-2025", "rgmen": 4, "dossier": str(donnees / "Base_brute_T2_2025")}],
    },
    "modules": {"simulation_ponderation": {
                    "base_historique": str(donnees / "Base_Travail" / "Base_Travail_BT_vf_25T3.dta"),
                    "trimestre_reference": "T3_2025", "valeur_trimestre": "25T3"},
                "tableaux_bulletin": {
                    "base_courante": str(donnees / "Base_Travail" / "Base_Travail_BT_vf_25T3.dta"),
                    "bases_empilees": [{"fichier": str(donnees / "Base_Travail" / "Base_Travail_BT_vf_24T3.dta")}],
                    "reconstruire": True,
                    "maquette": str(RACINE / "reference" / "Tableaux_Indicateurs_ENEM_template_DG.xlsx")},
                "presence_agents": {"dossier_paradata": str(donnees / "Paradata"), "date_fin": "15/09/2026"},
                "evolution_zd": {"date_reference": "14/09/2026",
                                 "cohortes": [{"libelle": "T3-2025", "rgmen": 3, "dossier": str(
                                     donnees / "Base_agent_teleoperateur" / "3ieme_passage_ENEMT3_2025")},
                                     {"libelle": "T2-2025", "rgmen": 4, "dossier": str(
                                         donnees / "Base_agent_teleoperateur" / "4ieme_passage_ENEMT2_2025")}]}},
}
(tmp / "profil.json").write_text(json.dumps(profil), encoding="utf-8")
os.environ["ENEM_PROFIL"] = str(tmp / "profil.json")

import tkinter.messagebox as mb  # noqa: E402

MESSAGES = []
for nom in ("showinfo", "showwarning", "showerror"):
    setattr(mb, nom, lambda titre, msg, _n=nom, **k: MESSAGES.append((_n, titre, msg)))
mb.askyesno = lambda *a, **k: True

from app.application import Application  # noqa: E402

app = Application()
app.geometry("1440x900+0+0")
ERREURS = []
app.report_callback_exception = lambda *a: ERREURS.append(a)


def pause(s=0.4):
    fin = time.time() + s
    while time.time() < fin:
        app.update()
        time.sleep(0.02)


def capture(nom):
    pause(0.6)
    subprocess.run(["import", "-window", "root", str(captures / f"{nom}.png")], check=False)


def fenetres():
    res, pile = [], [app]
    while pile:
        w = pile.pop()
        for c in w.winfo_children():
            if c.winfo_class() == "Toplevel":
                res.append(c)
            pile.append(c)
    return res


def attendre(vue, limite=120):
    fin = time.time() + limite
    while time.time() < fin:
        pause(0.2)
        if vue.thread is None:
            raise RuntimeError(f"module non lancé (paramètres refusés) : {MESSAGES[-1] if MESSAGES else ''}")
        if vue.thread and not vue.thread.is_alive() and vue.resultat is not None:
            return vue.resultat
    raise TimeoutError


capture("01_tableau_de_bord")
for cle, nom in (("catalogue", "02_catalogue"), ("parametres", "03_parametres"), ("taches", "04_taches_gantt"),
                 ("aide", "05_aide")):
    v = app.afficher(cle)
    if cle == "catalogue":
        v.arbre.selection_set("evolution_zd")
        pause()
    capture(nom)

resultats = {}
for mid in [m.id for m in app.modules]:
    vue = app.ouvrir_module(app.module_par_id(mid))
    pause()
    if mid == "preparation_bases":
        vue.formulaire.widgets["versions"].set(ver)
        vue.formulaire.widgets["dossier_destination"].set(str(tmp / "fusion"))
    if mid == "gantt":
        vue.formulaire.widgets["trimestre"].set("T1_2026")
        vue.formulaire.widgets["debut_points"].set("29/12/2025")
    if mid == "evolution_zd":
        capture("06_module_evolution_zd_parametres")
    vue.lancer()
    res = attendre(vue)
    resultats[mid] = (res.statut, res.resume)
    if mid == "evolution_zd":
        capture("07_module_evolution_zd_termine")
        vue.visualiser()
        pause(1)
        fen = fenetres()[-1]
        fen.geometry("1300x800+60+40")
        capture("08_resultats_grille")
        fen.destroy()
        vue.visualiser(onglet="graph")
        fen = fenetres()[-1]
        fen.geometry("1300x800+60+40")
        capture("09_resultats_graphique")
        fen.destroy()
    if mid in ("controles_base", "codification_emploi"):
        t0 = time.time()
        vue.visualiser()
        pause(0.5)
        fen = fenetres()[-1]
        # on ouvre chaque onglet de tableaux pour vérifier qu'aucun ne fige l'application
        for onglet in fen.sous.tabs():
            fen.sous.select(onglet)
            pause(0.35)
        resultats[f"affichage_{mid}"] = ("ouvert", f"{len(fen.sous.tabs())} onglets en {time.time() - t0:.1f} s")
        capture(f"15_resultats_{mid}")
        fen.destroy()
    if mid == "coherence_passages":
        capture("16_module_coherence_note")
        vue.visualiser(onglet="graph")
        pause(1)
        fen = fenetres()[-1]
        fen.geometry("1300x800+60+40")
        capture("10_resultats_coherence_graphique")
        fen.destroy()
    if mid == "simulation_ponderation":
        capture("17_module_simulation")
        vue.visualiser()
        pause(0.6)
        fen = fenetres()[-1]
        fen.geometry("1300x800+60+40")
        capture("18_resultats_simulation")
        fen.destroy()

# deux points hebdomadaires supplémentaires pour l'écran Évolution
vue = app.ouvrir_module(app.module_par_id("evolution_zd"))
for d in ("31/08/2026", "07/09/2026"):
    vue.formulaire.widgets["date_reference"].set(d)
    vue.lancer()
    attendre(vue)

# arrêt en cours de traitement
vue = app.ouvrir_module(app.module_par_id("temps_administration"))
vue.lancer()
pause(0.3)
vue.arreter()
res = attendre(vue)
resultats["arret_temps_administration"] = (res.statut, res.resume)

for cle, nom in (("historique", "11_historique"), ("alertes", "12_alertes"), ("evolution", "13_evolution"),
                 ("accueil", "14_tableau_de_bord_apres")):
    app.afficher(cle)
    capture(nom)
app.afficher("historique")
h = app.vues["historique"]
h.arbre.selection_set(h.arbre.get_children()[1])
h.resultats()
pause(1)

# rapidité de changement d'écran (deuxième passage : les écrans sont déjà construits)
for cle in ("accueil", "catalogue", "historique", "alertes", "accueil", "parametres"):
    app.afficher(cle)
    pause(0.05)
t0 = time.time()
for cle in ("accueil", "catalogue", "historique", "alertes", "accueil", "parametres", "accueil"):
    app.afficher(cle)
    app.update()
resultats["changement_ecran"] = ("7 écrans", f"{1000 * (time.time() - t0) / 7:.0f} ms par écran")

for k, v in resultats.items():
    print(f"{k:28s} {v[0]:10s} {v[1]}")
print("Messages :", MESSAGES)
print("Erreurs Tk :", len(ERREURS))
for e in ERREURS:
    import traceback
    traceback.print_exception(*e)
app.destroy()
