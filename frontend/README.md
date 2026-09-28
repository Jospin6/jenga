# Frontend Jenga

Interface Next.js App Router de création de sites : accueil, prompts, streaming SSE, code, aperçu isolé, vue mobile et export ZIP.

Consulter le [guide du projet](../README.md) pour démarrer FastAPI, configurer le modèle et connaître le périmètre de l’aperçu.

```bash
npm install
npm run dev
```

Ouvrir http://localhost:3000. Le proxy `/api` communique avec `http://127.0.0.1:8000` par défaut ; `BACKEND_URL` dans `.env.local` permet de changer cette adresse.

## Déployer le frontend sur Vercel

Importer le dépôt dans un projet Vercel distinct du backend, avec ces réglages :

| Réglage | Valeur |
| --- | --- |
| Framework Preset | Next.js |
| Root Directory | `frontend` |
| Node.js Version | `24.x` |
| Build Command | `npm run build` |
| Output Directory | Valeur par défaut de Next.js |
| Install Command | `npm ci` |

Ajouter `BACKEND_URL=https://jenga-beta.vercel.app` dans les variables d’environnement du **projet frontend**, pour Production et Preview, puis déployer. Le fichier `.env.local` est ignoré par Git et n’est pas transféré par un déploiement depuis le dépôt. Changer l’URL uniquement dans cette variable, puis redéployer ; aucun changement de code n’est nécessaire. Le navigateur passe toujours par `/api` sur le domaine du frontend.

Le proxy autorise des requêtes jusqu’à 300 secondes, la [limite de l’offre Hobby avec Fluid Compute](https://vercel.com/docs/functions/configuring-functions/duration). Les générations plus longues seront interrompues.

Après déploiement, ouvrir `/api/health` sur le domaine du frontend : la réponse attendue pour un backend configuré est `{"status":"ok","configured":true}`. Si `configured` vaut `false`, ajouter `OPENAI_API_KEY` aux variables du **projet backend** et redéployer ce dernier. Une redirection vers une connexion Vercel indique que le backend n’est pas accessible au proxy sans authentification.

Le backend actuel sauvegarde les projets dans `generated_projects/` à côté du code. Ce stockage doit être adapté avant une utilisation complète sur Vercel, dont les [fonctions ont un système de fichiers en lecture seule hors `/tmp`](https://vercel.com/docs/functions/runtimes). Un stockage persistant externe est nécessaire pour conserver et retrouver les projets entre instances ; un simple contrôle `/api/health` ne valide pas la génération.

## Vérifications

```bash
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Les tests démarrent leur propre backend simulé et vérifient le flux de bout en bout sans appel payant au modèle. Python et les dépendances de `backend/requirements.txt` doivent être installés dans `backend/.venv`.
