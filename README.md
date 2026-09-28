# Jenga — générateur de sites avec aperçu en direct

Interface Next.js reliée à l’agent LangGraph existant : prompt → planificateur → architecte → codeur. L’API FastAPI diffuse les étapes et le contenu des fichiers en SSE. L’interface affiche la conversation, le code et un aperçu qui se met à jour pendant la création.

## Démarrer en local

Prérequis : Python 3.11+ et Node.js 20.9+.

Depuis la racine du dépôt, dans un premier terminal PowerShell :

```powershell
# Si l’environnement Python n’existe pas encore :
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt

# Seulement si backend/.env n’existe pas encore :
Copy-Item backend/.env.example backend/.env
# Renseigner OPENAI_API_KEY dans backend/.env.

backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Le fichier `backend/.env` existant est conservé. `OPENAI_MODEL` permet de changer le modèle (par défaut `gpt-4o`). La clé reste uniquement côté serveur. Sur macOS/Linux, utiliser `backend/.venv/bin/python` à la place de `backend/.venv/Scripts/python.exe`.

Dans un deuxième terminal :

```powershell
cd frontend
npm install
npm run dev
```

Ouvrir **http://localhost:3000**. L’API et sa documentation sont accessibles sur **http://127.0.0.1:8000/docs**.

Le proxy Next.js utilise `http://127.0.0.1:8000` par défaut. Pour changer cette adresse, copier `frontend/.env.example` vers `frontend/.env.local` et modifier `BACKEND_URL`. Aucune variable publique ni configuration CORS n’est nécessaire : le navigateur appelle `/api` sur le même domaine que l’interface.

## Utilisation

- Décrire un site, ou sélectionner une suggestion pour préremplir le prompt.
- Suivre la planification, les fichiers en cours d’écriture et l’aperçu automatique.
- Basculer entre Aperçu et Code, puis entre les vues ordinateur et mobile.
- Arrêter une génération ; les fichiers déjà écrits sont conservés.
- Demander des modifications dans la même conversation.
- Télécharger les fichiers dans une archive ZIP, ou rouvrir un projet depuis la barre latérale.

Les fichiers et la conversation sont sauvegardés dans `generated_projects/<uuid>/`. La liste des projets récents est conservée dans le stockage local du navigateur. Les générations précédentes de `generated_project/` ne sont pas modifiées ni importées automatiquement.

Sur Vercel (`VERCEL=1`), le backend utilise automatiquement `/tmp/jenga/generated_projects/`, car le dossier du déploiement est en lecture seule. `PROJECTS_DIR` permet de choisir un autre dossier accessible en écriture via les variables d’environnement du backend ; utiliser un chemin absolu puis redéployer après modification. En local, cette variable peut être placée dans `backend/.env`.

Le stockage `/tmp` est **temporaire et propre à chaque instance** : un projet peut disparaître au redémarrage ou être introuvable si la requête suivante arrive sur une autre instance, y compris pour une modification ou un téléchargement. Ce correctif permet la génération et son aperçu dans la requête en cours. La sauvegarde durable, la réouverture et l’export fiable des projets nécessitent un stockage externe partagé.

## Mémoire de conversation

Le graphe LangGraph utilise une mémoire courte par projet (`thread_id = project_id`). Il conserve la demande initiale et les 12 messages récents, avec leurs rôles utilisateur/assistant. Chaque nouvelle demande reçoit aussi le plan précédent et des extraits limités des fichiers actuels ; le codeur peut lire les fichiers complets avec ses outils. Les étapes de travail sont réinitialisées à chaque tour pour exécuter réellement les modifications demandées.

Le contexte textuel de conversation est limité à 32 000 caractères et les extraits de fichiers à 24 000 caractères. L’historique complet reste sauvegardé dans le projet et réhydrate la mémoire lorsqu’il est rouvert ou que le processus redémarre. Les checkpoints `InMemorySaver` sont propres au processus : cette mémoire ne remplace pas un stockage partagé. Sur Vercel, la continuité entre instances reste conditionnée à la disponibilité des fichiers et de l’historique du projet (voir la limite du stockage `/tmp` ci-dessus).

## Périmètre de cette version

Le **frontend de l’outil est en Next.js**. Les **sites générés sont des sites statiques HTML/CSS/JavaScript**, avec `index.html` comme point d’entrée, des scripts classiques et une navigation sur une seule page. Cette contrainte est ajoutée aux prompts de l’agent pour garantir un aperçu immédiat sans installer ou exécuter du code serveur généré.

L’aperçu assemble les fichiers en mémoire dans une iframe isolée (`sandbox="allow-scripts"` et CSP). HTML et CSS apparaissent progressivement ; seuls les scripts enregistrés en entier sont exécutés. L’aperçu ne permet pas les appels réseau JavaScript, le stockage local, les cookies, les imports de modules ni l’exécution d’un backend. Les interactions en mémoire, les styles et les images HTTPS fonctionnent. Un aperçu de projets React/Next.js générés demanderait un environnement de compilation et d’exécution isolé supplémentaire.

Il s’agit d’un outil local : pas d’authentification ni de contrôle d’accès entre comptes. Exécuter **un seul worker FastAPI** ; les verrous de génération sont en mémoire. Avant une mise en ligne partagée, ajouter comptes et autorisations, limites d’utilisation, verrous partagés et un stockage adapté. Une coupure du flux annule la génération ; il n’y a pas de reprise automatique des événements. Les fichiers déjà sauvegardés restent disponibles pour une nouvelle demande. La durée maximale d’une génération est de 15 minutes ; l’hébergement et les proxies doivent autoriser les connexions longues sans buffering.

## API et streaming

| Route | Rôle |
| --- | --- |
| `GET /api/health` | Disponibilité et présence de la configuration du modèle |
| `POST /api/generate` | `{ "prompt": "…", "project_id": null }`, réponse SSE |
| `GET /api/projects/{uuid}` | Métadonnées, conversation et fichiers sauvegardés |
| `GET /api/projects/{uuid}/download` | Archive ZIP des fichiers |

Pour modifier un projet, envoyer son `project_id` avec le nouveau prompt. Le flux contient des trames `data: <JSON>\n\n`, plus des commentaires keepalive toutes les 15 secondes sans événement.

| Événement | Contenu |
| --- | --- |
| `start` | `project_id` |
| `stage` | Étape, message et fichier en cours |
| `plan` | Plan structuré |
| `tasks` | Liste ordonnée des tâches |
| `file_delta` | `path`, `content` : contenu partiel **complet à remplacer**, pas un fragment à concaténer |
| `file` | `path`, `content` : fichier effectivement sauvegardé |
| `task_done` | Fichier terminé et progression |
| `done` | Projet terminé et instantané des fichiers |
| `error` | Erreur présentable à l’utilisateur, sans détails sensibles du fournisseur |

Le proxy transmet le corps de la réponse sans le bufferiser. Le client décode les trames SSE même lorsqu’elles sont coupées au milieu d’un caractère UTF-8. `AbortController` propage l’arrêt au backend et aux appels asynchrones du graphe. Les flux `messages` et `custom` de [LangGraph](https://docs.langchain.com/oss/python/langgraph/streaming) servent respectivement aux brouillons et aux événements métier.

## Vérifications

```powershell
# À la racine : tests de l’API et du véritable graphe, avec modèle simulé.
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v

cd frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Les tests navigateur démarrent un backend déterministe sur le port 8011 et Next.js sur le port 3100. Ils vérifient le streaming via le vrai proxy, l’aperçu avant la fin, les scripts/CSS, le code, l’export ZIP, les modifications, la restauration, les erreurs, l’annulation et l’interface mobile. Aucune requête payante au modèle n’est effectuée. Les fichiers de test et captures sont placés dans `.test-artifacts/`, ignoré par Git. `PLAYWRIGHT_CHROMIUM_EXECUTABLE` peut pointer vers une installation Chromium existante.

## Fichiers principaux

- `backend/agent/graph.py` : étapes asynchrones de l’agent et contraintes d’aperçu.
- `backend/agent/workspace.py` : contexte de fichiers isolé par génération.
- `backend/main.py` : API, annulation, erreurs et keepalive SSE.
- `backend/streaming.py` : extraction du code depuis les arguments d’outils streamés.
- `frontend/app/api/[...path]/route.ts` : proxy serveur vers FastAPI.
- `frontend/lib/use-builder.ts` : état de génération et projets récents.
- `frontend/lib/preview.ts` : assemblage de l’aperçu isolé.
- `frontend/components/builder.tsx` : interface de création.
