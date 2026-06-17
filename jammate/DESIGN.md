# JamMate — Design System

Riferimento per mantenere l'app coerente e professionale. Token implementati in `styles.css` (`:root`).

## Principi
- **Dark, premium, musicale.** Sfondo profondo con bagliori colorati; superfici "a vetro" (glassmorphism) e profondità via ombre morbide.
- **Un solo accento a gradiente** (viola→rosa) usato con parsimonia per le azioni primarie e gli stati attivi.
- **Onestà visiva.** La "Sintonia" non urla numeri: mostra il *perché*. Niente dark pattern.
- **Mobile-first**, tocco generoso (target ≥ 44px), animazioni brevi (120–250ms) e `prefers-reduced-motion` rispettato.

## Token colore
| Token | Valore | Uso |
|---|---|---|
| `--bg` | `#0b0c14` | sfondo base |
| `--surface-solid` | `#171a2b` | card, modali |
| `--border-soft` | `#ffffff14` | bordi sottili su vetro |
| `--text` | `#f1f3ff` | testo principale |
| `--muted` | `#969cc4` | testo secondario |
| `--accent` | `#8b6cff` | accento primario (viola) |
| `--accent-2` | `#ff5c9d` | accento secondario (rosa) |
| `--accent-3` | `#36d1dc` | accento freddo (ciano) |
| `--accent-grad` | viola→rosa 135° | azioni primarie, stati attivi |
| `--ok` `--warn` `--red` | verde/ambra/rosso | esiti, avvisi, errori |

## Tipografia
- Font: **Plus Jakarta Sans** (fallback system stack).
- Titoli: 800, `letter-spacing -.02em`. Sottotitoli/UI: 600–700. Corpo: 400–500.
- Scala indicativa: titolo 1.5rem · h2 1.25rem · corpo .95rem · micro .8rem.

## Spaziatura & forma
- Raggi: `--radius` 18px (card), 14px (bottoni), 999px (chip/pill).
- Ombre: `--shadow-sm` (riposo), `--shadow` (hover/elevazione), `--glow` (accento).
- Griglia max contenuto: 680px centrato.

## Componenti
- **Bottone primario** `.btn`: gradiente, glow, riflesso superiore, lift all'hover, pressione allo `:active`.
- **Bottone secondario** `.btn.secondary`: vetro + bordo soft.
- **Card** `.card`: vetro su superficie solida, lift all'hover (non per `.flat`).
- **Chip** `.chip`/`.chip.on`: pill selezionabili; stato attivo a gradiente.
- **Segmented** `.segmented`: switch a due/tre vie, attivo a gradiente con glow.
- **Swipe card** `.swipe-card`: hero a gradiente + overlay, emoji "float", badge compatibilità in alto a destra.
- **Tab bar** `.tabbar`: 5 voci, indicatore attivo a barretta gradiente, badge `.dot` per notifiche.
- **Modale** `.modal`: bottom-sheet con grip, slide-up.
- **Sintonia**: header `.aff-score` a gradiente, barre `.endo`, motivazioni `.aff-note`, avvisi `.warn-chip`.

## Accessibilità
- Contrasto AA sul testo principale; focus ring accentato sugli input.
- Animazioni disattivate con `prefers-reduced-motion`.
- Aree di tocco ampie; niente informazione veicolata dal solo colore (icone + testo).

## TODO design (prossimi affinamenti)
- Icone vettoriali coerenti al posto di alcune emoji (mantenere emoji per gli avatar è una scelta voluta, "amichevole").
- Foto profilo reali (upload) con fallback all'avatar a gradiente.
- Modalità chiara opzionale.
- Schermata splash + onboarding illustrato.
