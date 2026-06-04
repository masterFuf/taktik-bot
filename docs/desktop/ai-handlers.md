# AI Handlers Electron

Statut : canonique, reverifie le 2026-06-04.

Sources verifiees :

- `front/electron/handlers/ai/`
- `front/electron/services/app/ai/providers/ai-provider.ts`
- `front/electron/services/app/ai/taxonomy/niche-taxonomy.ts`
- `front/package.json`

## Frontiere

Les handlers IA Electron gerent :

- completion texte et vision cote desktop ;
- providers et cles IA ;
- generation media image/video ;
- TTS et cache audio ;
- fonctions IA appelees par certaines pages front.

Les workflows Python du bot utilisent surtout OpenRouter via
`bot/taktik/core/app/ai/providers/openrouter.py` quand ils executent eux-memes
de la qualification ou generation IA.

## Fichiers actifs

| Fichier | Role |
|---|---|
| `front/electron/handlers/ai/ai.ts` | Reponses DM simples et bulk responses. |
| `front/electron/handlers/ai/ai-provider.ts` | Gestion providers/modeles/cles, completion texte/vision, classification. |
| `front/electron/handlers/ai/ai-content.ts` | Generation image/video/caption/hashtags, analyse image, qualification batch. |
| `front/electron/handlers/ai/tts.ts` | TTS via fal.ai ElevenLabs et cache MP3. |
| `front/electron/services/app/ai/providers/ai-provider.ts` | Abstraction multi-provider texte/vision. |
| `front/electron/services/app/ai/taxonomy/niche-taxonomy.ts` | Normalisation niche et prompts de qualification. |

## Providers

| Provider | Usage actuel |
|---|---|
| OpenRouter | Provider texte/vision par defaut pour les flux modernes et le bot Python. |
| OpenAI | BYOK texte/vision direct. |
| Anthropic | BYOK texte/vision direct. |
| Google Gemini | BYOK texte/vision direct. |
| fal.ai | Toujours present pour image/video/TTS et certains fallbacks media ; dependance `@fal-ai/client` dans `front/package.json`. |

Ne pas supprimer fal.ai de la documentation tant que `@fal-ai/client`,
`ai-content.ts`, `tts.ts` ou les settings IA l'utilisent encore.

## Canaux principaux

| Famille | Exemples |
|---|---|
| Provider | `ai-provider:*` pour providers, modeles, cles, OpenRouter balance. |
| Content | `ai-content:*` pour image/video/caption/hashtags/analyse image/pricing. |
| TTS | `ai:tts`, cache MP3 sous `userData`. |
| DM / Smart text | handlers `ai:*` selon les flux engagement. |

## OpenRouter vs fal.ai

| Besoin | Chemin actuel |
|---|---|
| Texte / vision LLM moderne | OpenRouter par defaut, ou BYOK OpenAI/Anthropic/Google. |
| Scraping IA / Deep Qualify bot | OpenRouter cote Python. |
| Cold DM IA runtime | OpenRouter cote bridge Python. |
| Image / video / TTS desktop | fal.ai cote Electron. |

## Points d'attention

- Les chemins historiques `front/electron/services/ai/**` sont obsoletes ;
  utiliser `front/electron/services/app/ai/**`.
- Les credits OpenRouter/fal.ai sont des credits provider, pas des quotas
  d'actions automation.
- Les cles et preferences restent gerees cote desktop/config ; les flux bot
  recoivent la cle OpenRouter dans leur config quand necessaire.
