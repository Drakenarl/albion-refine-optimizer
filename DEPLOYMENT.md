# Deploiement — Backend Railway + Frontend Vercel

Deux services independants, deux plateformes gratuites au demarrage. Compte l'ordre : **backend d'abord, frontend ensuite** (le frontend a besoin de l'URL du backend).

## 1. Backend sur Railway

### Pre-requis

- Compte GitHub avec ce repo pushe.
- Compte Railway ([railway.com](https://railway.com)) — inscription gratuite, credit initial d'environ 5 $ ou plan Hobby a 5 $/mois selon les changements de tarification.

### Etapes

1. **Nouveau projet Railway** → *Deploy from GitHub repo* → selectionne `Drakenarl/albion-refine-optimizer`.
2. Railway detecte automatiquement le [Dockerfile](Dockerfile) et le [railway.toml](railway.toml). Le healthcheck sera sur `/api/health`.
3. **Variables d'environnement** (onglet *Variables*) : rien d'obligatoire pour un premier deploiement — le port est injecte, CORS accepte tout en developpement. Tu ajouteras `ALBION_ALLOWED_ORIGINS` a l'etape 5.
4. Lance le premier *Deploy*. Suit les logs — la build Docker prend 2-3 min.
5. Recupere l'URL publique dans l'onglet *Settings* → *Networking* → *Public Networking*. Exemple : `https://albion-refine-api-production.up.railway.app`.
6. Verifie manuellement :
   ```
   curl https://<ton-url-railway>/api/health
   → {"status":"ok","version":"2.1.0"}
   ```

### Notes Railway

- Le cache diskcache ecrit dans `/root/.cache/albion-refine`. Ephemere (perdu au redemarrage) — c'est acceptable, il se remplit au fil des requetes.
- Pas de base de donnees a provisionner : l'app ne persiste rien.
- Cout attendu : le service dort au ralenti, environ 1-3 $/mois selon le trafic.

---

## 2. Frontend sur Vercel

### Pre-requis

- Meme compte GitHub.
- Compte Vercel ([vercel.com](https://vercel.com)) — plan Hobby gratuit largement suffisant.

### Etapes

1. **Nouveau projet Vercel** → *Import Git Repository* → selectionne le meme repo.
2. **Root Directory** : `web` (important, ne pas laisser la racine).
3. Framework : Vercel detecte *Vite* automatiquement grace au [web/vercel.json](web/vercel.json). Build command et output directory sont pre-remplis.
4. **Environment Variables** :
   - `VITE_API_URL` = URL Railway sans slash final (ex. `https://albion-refine-api-production.up.railway.app`)
5. Lance le *Deploy*. Build TypeScript + Vite en 30-60 s.
6. Recupere l'URL publique. Exemple : `https://albion-refine-optimizer.vercel.app`.

### Notes Vercel

- Cold start negligeable (fichiers statiques servis via CDN).
- HTTPS et compression bruli gratuits.
- Domaine personnalise possible dans *Settings* → *Domains* si tu en as un.

---

## 3. Fermer la boucle CORS

Le backend refuse par defaut les origines qu'il ne connait pas. Ajoute l'URL Vercel a la whitelist :

1. Retourne dans Railway → onglet *Variables*.
2. Ajoute :
   ```
   ALBION_ALLOWED_ORIGINS=https://albion-refine-optimizer.vercel.app
   ```
   Plusieurs origines separees par des virgules si besoin (custom domain, preview URLs).
3. Railway redemarre automatiquement le service en 30 s.
4. Ouvre l'URL Vercel dans un navigateur, lance une optimisation. Si tu vois les cards → tout marche. Si tu vois `CORS error` dans la console browser → l'URL Vercel n'est pas exactement celle whitelistee (verifie protocole `https://`, pas de slash final).

---

## Preview URLs Vercel

Vercel cree une URL par branche et par pull request. Si tu veux qu'elles marchent aussi, ajoute leur wildcard a `ALBION_ALLOWED_ORIGINS` :

```
ALBION_ALLOWED_ORIGINS=https://albion-refine-optimizer.vercel.app,https://albion-refine-optimizer-*.vercel.app
```

Note : FastAPI/Starlette ne gere pas le wildcard `*` dans les origins par defaut. Pour supporter les previews, il faut passer par `allow_origin_regex`. A ajouter dans une iteration ulterieure si le besoin se presente.

---

## Redeployer

- **Backend** : chaque push sur `main` declenche un nouveau build Railway.
- **Frontend** : chaque push sur `main` declenche un nouveau build Vercel. Les branches produisent des URLs de preview automatiquement.

---

## Debug

| Symptome | Cause probable | Fix |
|---|---|---|
| Frontend charge, mais "Chargement config..." infini | CORS, ou VITE_API_URL vide | Verifie la console browser + variables Vercel |
| `502 AODP indisponible` dans le frontend | AODP down, ou probleme reseau Railway | Reessayer, verifier [status Albion Data](https://www.albion-online-data.com/) |
| Railway `Application failed to respond` | Le port n'est pas bindé sur $PORT | Verifie que `PORT` n'est pas overridée dans les vars |
| Vercel build echoue `Cannot find module` | `web/package-lock.json` obsolete | `npm install` en local puis commit |

---

## Verification finale post-deploiement

1. `curl https://<railway>/api/health` → 200 OK
2. `curl https://<railway>/api/config` → JSON avec tiers/villes
3. `curl -X POST https://<railway>/api/optimize -H "Content-Type: application/json" -d '{"tier":7,"mode":"capital","capital":3000000,"station_rate":50,"focus":true,"seuil_marge_min_pct":-100}'` → JSON de routes
4. Ouvrir `https://<vercel>` → formulaire visible, submit -> cards ou alternatives affichees
5. Devtools -> Network -> voir que la requete part bien vers `<railway>/api/optimize`
