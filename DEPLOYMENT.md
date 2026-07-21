# Deploiement — Tout sur Vercel (monorepo)

Setup actuel : **un seul deploiement Vercel**, backend (Python serverless) et
frontend (React static) sur le meme domaine. Zero configuration CORS, zero
service tiers a gerer.

## Architecture

```
albion-optimizer.vercel.app
├── /                → frontend Vite (static, servi par CDN Vercel)
└── /api/*           → api/index.py (fonction serverless Python 3.12)
                       expose FastAPI health / config / optimize
```

## Pre-requis

- Compte GitHub avec ce repo pushe.
- Compte Vercel ([vercel.com](https://vercel.com)) — plan Hobby gratuit.

## Etapes

1. **Nouveau projet Vercel** → *Import Git Repository* → selectionne
   `Drakenarl/albion-refine-optimizer`.
2. **Configure** (Vercel devrait auto-detecter grace au [vercel.json](vercel.json)) :
   - Root Directory : **laisse la racine** (pas `web/` cette fois).
   - Build Command : pre-rempli par vercel.json (`cd web && npm install && npm run build`).
   - Output Directory : `web/dist`.
   - Install Command : Vercel installera automatiquement les deps Python via
     [requirements.txt](requirements.txt).
3. **Environment Variables** : rien a definir. Le frontend et le backend sont
   sur le meme domaine, les appels sont same-origin.
4. Lance le *Deploy*. Premiere build ~2-3 min (npm install + build Vite + pip
   install des deps Python).
5. Recupere l'URL publique. Exemple : `https://albion-refine-optimizer.vercel.app`.

## Verification finale

```bash
# Health check
curl https://<ton-url>/api/health
→ {"status":"ok","version":"2.1.0"}

# Config
curl https://<ton-url>/api/config
→ tiers, villes, defauts...

# Optimize (T7 focus, seuil -100 pour toujours avoir des routes)
curl -X POST https://<ton-url>/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"tier":7,"mode":"capital","capital":3000000,"station_rate":50,"focus":true,"seuil_marge_min_pct":-100}'
→ JSON de routes
```

Puis ouvre `https://<ton-url>` dans un navigateur, lance une optimisation, tu
dois voir les cards s'afficher.

## Contraintes du plan Hobby

| Limite | Impact |
|---|---|
| **10 s max** par requete serverless | Le calcul d'optimize prend 2-5 s, marge OK sauf si AODP rame |
| **Pas de cache persistant** entre invocations | Chaque requete refait tous les appels AODP (500 ms chacun, acceptable) |
| **Cold start ~1-2 s** | Premier click apres inactivite un peu lent, ensuite instantane |
| **10 GB bandwidth/mois** | Largement suffisant sauf trafic massif |
| **100 GB-hours compute/mois** | Idem, pour un usage entre potes c'est enorme |

Si un jour tu depasses (ex. le calcul depasse 10 s regulierement), tu peux
migrer le backend sur Railway/Render avec les fichiers [Dockerfile](Dockerfile)
et [railway.toml](railway.toml) toujours presents dans le repo — il suffit
alors de definir `VITE_API_URL` cote frontend.

## Redeployer

- Chaque push sur `main` declenche un build Vercel automatique.
- Chaque push sur une branche cree une preview URL du type
  `https://albion-refine-optimizer-git-<branche>-<user>.vercel.app`.

## Debug

| Symptome | Cause probable | Fix |
|---|---|---|
| Frontend charge, "Chargement config…" infini | La fonction Python a plante au demarrage | Vercel → onglet *Functions* → logs de `api/index.py` |
| `504 Gateway Timeout` | AODP trop lent, calcul > 10 s | Retry, ou reduire tier / capital |
| `500 Internal Server Error` sur /api/* | Import Python casse, deps manquantes | Verifier requirements.txt, logs Vercel |
| Build echoue `Cannot find package.json` | Vercel cherche package.json a la racine | Verifier que buildCommand inclut `cd web` |
| `Function Payload Too Large` | Reponse > 4.5 MB | Reduire top_n dans OptimizerParams |

## Fichiers cles

| Fichier | Role |
|---|---|
| [vercel.json](vercel.json) | Config monorepo (build, functions, rewrites) |
| [api/index.py](api/index.py) | Handler serverless qui expose FastAPI |
| [requirements.txt](requirements.txt) | Deps Python installees par Vercel |
| [web/vite.config.ts](web/vite.config.ts) | Proxy dev /api → :8000 (uniquement local) |
| [Dockerfile](Dockerfile) + [railway.toml](railway.toml) | Backup pour redeploy backend ailleurs si besoin |

## Setup local pour le dev

Le mode dev reste identique — Vercel n'intervient qu'au deploiement :

```bash
# Terminal 1 : backend FastAPI
python -m uvicorn albion_refine.api:app --reload

# Terminal 2 : frontend Vite
cd web
npm run dev
```

Ouvre `http://localhost:5173`.
