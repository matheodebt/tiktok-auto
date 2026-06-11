# TikTok Auto 🎬

Pipeline automatique : Script → Voix → Vidéo → TikTok

## Variables d'environnement à configurer sur Railway

| Variable | Valeur |
|----------|--------|
| TIKTOK_ACCESS_TOKEN | Token OAuth TikTok (voir ci-dessous) |
| PEXELS_KEY | (optionnel) Clé API Pexels pour vidéos de fond |

## Obtenir le token TikTok

1. Va sur https://developers.tiktok.com
2. Dans ton app → Sandbox → Generate token
3. Copie le token et colle-le dans Railway comme variable TIKTOK_ACCESS_TOKEN

## Déploiement Railway

```bash
# Dans le dossier du projet
railway login
railway init
railway up
```

## Ce que fait le système

- Toutes les nuits à 19h : génère un script via Claude
- Synthèse vocale via ElevenLabs
- Assemble une vidéo 1080x1920 avec ffmpeg
- Publie automatiquement sur TikTok
