# Architecture web ENEM Suivi

Cette implementation est developpee en parallele de l'interface Tkinter. Elle ne remplace pas encore
la version bureau.

## Composants

- `web/frontend` : Angular 22, servi par Nginx en conteneur ;
- `web/backend` : Django 5.2 et Django REST Framework ;
- PostgreSQL : utilisateurs, permissions, metadonnees, executions et indicateurs ;
- MinIO : bases d'entree, references et fichiers produits ;
- Redis et Celery : file d'attente des traitements longs ;
- `enem_core` et `modules` : moteur metier commun avec Tkinter.

## Demarrage local

1. Copier `.env.example` vers `.env` et remplacer toutes les valeurs `change-me`.
2. Lancer `docker compose up --build`.
3. Ouvrir `http://localhost:8080`.
4. L'API est disponible sur `http://localhost:8000/api/v1/` et sa documentation sur
   `http://localhost:8000/api/docs/`.
5. Creer le premier administrateur avec :
   `docker compose exec api python -m web.backend.manage createsuperuser`.

L'API utilise des jetons JWT. Un client obtient ses jetons avec `POST /api/v1/auth/token/` puis transmet
le jeton d'acces dans l'en-tete `Authorization: Bearer <jeton>`. Le endpoint de sante reste public.

Les valeurs par defaut du fichier Compose sont reservees au developpement local. Elles ne doivent pas
etre reprises sur le serveur.

`MINIO_ENDPOINT` est l'adresse interne utilisee par Django. `MINIO_PUBLIC_ENDPOINT` est l'adresse que
le navigateur peut joindre pour les URL temporaires. En production, cette derniere doit etre une URL
HTTPS publiee par le reverse proxy et autorisee par la politique CORS de MinIO.

## Tester avec les donnees Tkinter

Renseigner dans `.env` le dossier qui contient les bases de l'iteration, par exemple :

```text
ENEM_LOCAL_DATA_PATH=D:/ENEM_Working/Activite_quotidienne_trimestre_3_2026/Base
```

Recreer ensuite l'API pour monter ce dossier en lecture seule, inspecter les fichiers puis les importer :

```bash
docker compose up -d --force-recreate api worker
docker compose exec api python -m web.backend.manage import_local_files /data/import --dry-run
docker compose exec api python -m web.backend.manage import_local_files /data/import --quarter T3_2026
```

Seuls les formats `.dta`, `.csv`, `.xlsx`, `.xls`, `.sav` et `.parquet` sont acceptes. L'import calcule
une empreinte SHA-256, ignore les doublons, copie les fichiers vers MinIO et enregistre leurs metadonnees
dans PostgreSQL. Le montage etant en lecture seule, les fichiers utilises par Tkinter ne sont pas modifies.

## Fichiers

Le navigateur demande a Django un ticket de depot temporaire. Il envoie ensuite directement le fichier
vers MinIO, puis confirme le depot a l'API. PostgreSQL conserve le nom original, la cle d'objet, la taille,
le statut, l'auteur et l'empreinte SHA-256 lorsqu'elle provient de l'import local. Le bouton de telechargement
demande une URL MinIO signee valable cinq minutes : aucune cle MinIO n'est exposee au navigateur.

## Parcours web disponible

1. connexion Angular avec le compte Django et stockage du JWT dans la session du navigateur ;
2. consultation des 12 modules metier partages avec Tkinter ;
3. import d'un fichier dans MinIO ou consultation des fichiers importes depuis le poste ;
4. lancement d'un module depuis un formulaire genere avec ses parametres declares (dates, nombres,
   choix, fichiers, dossiers, versions et tableaux) ;
5. suivi de la progression Celery, rafraichie toutes les trois secondes ;
6. consultation de l'historique PostgreSQL et telechargement signe des resultats.

Pour un premier essai reproductible avec le fichier fourni dans `reference`, lancer le module `gantt`
avec le trimestre `T4_2026` et les parametres suivants :

```json
{
  "trimestre": "T4_2026",
  "fichier_taches": "/data/import/Fichier_Gant.xlsx",
  "ajouter_points": false,
  "debut_points": "2026-09-28",
  "nb_semaines": 13
}
```

Le resultat attendu est un fichier `Diagramme_Gantt_T4_2026.xlsx` disponible dans la liste des fichiers.

Les parametres sont controles une premiere fois par Django avant la creation d'une execution. Une saisie
incomplete reste donc dans le formulaire avec un message exploitable et n'encombre pas la file Celery.

## Limites de cette premiere version

- les champs de fichiers et dossiers attendent un chemin visible dans le conteneur, sous `/data/import` ;
- les droits utilisent pour l'instant les comptes Django authentifies, sans matrice de roles metier ;
- le rafraichissement de progression repose sur une interrogation periodique, sans WebSocket.
