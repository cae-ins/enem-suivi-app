# Deploiement sur le serveur interne

Ce document decrit la cible de production sans enregistrer dans Git l'adresse du serveur, les comptes ou
les secrets. La mise en production doit etre validee avec l'administrateur de l'infrastructure.

## Prerequis

- serveur avec Docker Engine et Docker Compose ;
- nom DNS interne et certificat TLS ;
- volumes persistants sauvegardes pour PostgreSQL et MinIO ;
- regles pare-feu limitant PostgreSQL, Redis et l'API S3 aux seuls services autorises.

## Configuration

Creer un fichier `.env` hors Git a partir de `.env.example`. En production :

- `DJANGO_DEBUG=false` ;
- `DJANGO_ALLOWED_HOSTS` contient uniquement le nom DNS interne ;
- `CORS_ORIGINS` contient uniquement l'URL HTTPS du frontend ;
- `MINIO_ENDPOINT` utilise le reseau interne Docker ;
- `MINIO_PUBLIC_ENDPOINT` utilise le nom HTTPS visible par le navigateur ;
- les mots de passe PostgreSQL, MinIO et la cle Django sont distincts ;
- le fichier `.env` est lisible uniquement par le compte de service.

Le demarrage est volontairement refuse en mode production si la cle Django ou les mots de passe de
developpement par defaut sont encore presents.

## Reverse proxy

Le reverse proxy publie uniquement le frontend, `/api/`, `/admin/` et un endpoint S3 HTTPS pour les URL
temporaires. PostgreSQL, Redis et la console MinIO ne doivent pas etre exposes aux postes utilisateurs.

## Installation

```bash
git clone https://github.com/cae-ins/enem-suivi-app.git
cd enem-suivi-app
git switch ameliorations-tkinter
cp .env.example .env
# renseigner les secrets avant de continuer
docker compose pull
docker compose up -d --build
docker compose exec api python -m web.backend.manage createsuperuser
```

Verifier ensuite :

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/api/v1/health/
curl -fsS http://127.0.0.1:8080/
docker compose exec worker celery -A web.backend.config inspect ping
```

## Sauvegardes et mises a jour

- sauvegarde PostgreSQL quotidienne avec tests de restauration ;
- versionnement et retention des buckets MinIO ;
- copie des sauvegardes sur un stockage distinct ;
- sauvegarde chiffree des secrets dans le coffre institutionnel ;
- sauvegarde avant toute migration et conservation de l'image precedente.

Tester regulierement une restauration sur un environnement isole. Une sauvegarde non restauree au moins
une fois ne doit pas etre consideree comme valide.
