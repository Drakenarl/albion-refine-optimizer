# Bundle albion-refine-optimizer — Index

Contenu du bundle et instructions d'utilisation.

## Fichiers fournis

| Fichier | Destination dans le repo | Rôle |
|---|---|---|
| `SPEC.md` (déjà envoyé séparément) | racine | Cahier des charges complet, source de vérité pour Claude Code |
| `items.json` | racine | Extract réduit AODP des items bois/planks T4-T8, évite le téléchargement du fichier complet |
| `pyproject.toml` | racine | Config projet Python avec toutes les deps déclarées |
| `.gitignore` | racine | Ignore Python + spécificités projet |
| `README.md` | racine | Template avec sections à compléter par Claude Code |
| `CLAUDE_CODE_PROMPT.md` | **NE PAS COMMIT** — usage local | Prompt d'ouverture à copier-coller dans Claude Code |
| `COMMIT_CONVENTIONS.md` | racine ou `docs/` | Charte des messages de commit à faire respecter |
| `fixtures/aodp_prices_t7.json` | `tests/fixtures/` | Fixture prix T7 pour tests unitaires |
| `fixtures/aodp_history_t7.json` | `tests/fixtures/` | Fixture historique 24h T7 pour tests |
| `fixtures/aodp_stale_data.json` | `tests/fixtures/` | Fixture cas limites (stale, prix zéro) |
| `BUNDLE_INDEX.md` (ce fichier) | **NE PAS COMMIT** — usage local | Ton guide |

## Procédure de démarrage

### Étape 1 — Créer le repo GitHub

Sur github.com, connecté en tant que `Drakenarl` :
- New repository → `albion-refine-optimizer`
- Public ou privé selon ta préférence
- Ne pas initialiser avec un README (on met le nôtre)
- Créer

### Étape 2 — Cloner localement

```bash
cd C:\Users\duval\projets    # ou ton dossier de projets habituel
git clone https://github.com/Drakenarl/albion-refine-optimizer.git
cd albion-refine-optimizer
```

### Étape 3 — Placer les fichiers du bundle

Depuis le dossier du repo cloné :

```
albion-refine-optimizer/
├── SPEC.md                     ← à copier depuis le bundle
├── items.json                  ← à copier depuis le bundle
├── pyproject.toml              ← à copier depuis le bundle
├── .gitignore                  ← à copier depuis le bundle
├── README.md                   ← à copier depuis le bundle
├── COMMIT_CONVENTIONS.md       ← à copier depuis le bundle
└── tests/
    └── fixtures/
        ├── aodp_prices_t7.json      ← à copier depuis le bundle
        ├── aodp_history_t7.json     ← à copier depuis le bundle
        └── aodp_stale_data.json     ← à copier depuis le bundle
```

Note : le dossier `tests/fixtures/` n'existe pas encore, il faut le créer manuellement OU laisser Claude Code le créer et lui indiquer où placer les fixtures.

### Étape 4 — Commit initial

```bash
git add .
git commit -m "chore: initialise le projet avec SPEC et bundle de démarrage"
git push origin main
```

### Étape 5 — Lancer Claude Code

Depuis le dossier du repo, lance Claude Code (via Desktop Commander ou en direct selon ton setup) et donne-lui **le contenu de `CLAUDE_CODE_PROMPT.md`** comme premier message.

### Étape 6 — Superviser

Claude Code va probablement :
1. Lire le SPEC (peut prendre 1-2 minutes)
2. Éventuellement créer un `QUESTIONS.md` si des points ambigus subsistent — **réponds-y avant qu'il continue**
3. Commencer par `config.py` et progresser module par module
4. Faire un commit atomique par module

Reste dispo pour répondre aux questions et valider les décisions importantes. Ne le laisse pas trop longtemps sans supervision — la qualité est meilleure quand tu réponds vite aux ambiguïtés.

## Rappels importants

- **Ne commit PAS `CLAUDE_CODE_PROMPT.md` et `BUNDLE_INDEX.md`** dans le repo. Ce sont des artefacts pour toi.
- **Ne modifie pas le SPEC** en cours de développement sans en discuter avec Claude Code d'abord (via `QUESTIONS.md`).
- **Garde une copie du bundle** ailleurs au cas où tu veuilles relancer un nouveau projet sur le même modèle.
- **Après V1**, reviens vers moi (chat) pour préparer les specs V2 et V3.

## Si tu bloques

Cas classiques :

- **Claude Code fait des trucs bizarres** → arrête-le, ouvre le SPEC, cherche le point qu'il a mal compris, et clarifie dans QUESTIONS.md
- **Un test échoue et tu ne comprends pas pourquoi** → copie l'erreur ET la formule concernée du SPEC, envoie-moi ça dans le chat
- **Tu veux ajouter une feature** → note-la dans un `IDEAS_FROM_DUVALIER.md` local et on l'intégrera à V2 ou V3
- **L'API AODP ne répond pas comme prévu** → capture la vraie réponse dans un nouveau fichier fixtures/ et ajuste le code (ou signale-moi si c'est un souci de spec)

Bon dev.
