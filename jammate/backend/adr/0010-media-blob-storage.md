# ADR 0010 — Media/foto: Azure Blob Storage

**Stato:** Accettato · **Data:** 2026-06-16

## Contesto
Foto profilo, immagini band e media dell'EPK vanno archiviati. Oggi il prototipo
salva la foto come dataURL dentro lo stato (`localStorage`): non scala e gonfia
il database. I file binari non vanno messi nel DB relazionale.

## Decisione
Archiviamo i media su **Azure Blob Storage** (regione UE). Nel DB salviamo solo
l'**URL/riferimento** (es. `photo_url`). L'upload passa da una Function che
**valida e ri‑codifica** l'immagine (vedi `SECURITY.md`).

## Razionale
- **Storage oggetti** è il posto giusto per i binari: economico e scalabile.
- **DB snello**: niente blob nelle tabelle, query più veloci.
- **Sicurezza upload**: validazione tipo/dimensione + ri‑codifica server‑side
  contro file malevoli; servizio isolato dagli altri dati.
- Integrazione con CDN/Front Door per servire le immagini velocemente.

## Conseguenze
- (+) Scalabilità, costi bassi, DB pulito, upload controllati.
- (−) Gestione di accessi/URL (SAS o accesso tramite Function) e ciclo di vita
  dei file (cancellazione coerente con l'account utente — GDPR).

## Alternative considerate
- **Immagini nel DB (bytea/dataURL)**: semplice ma non scala, appesantisce
  backup e query. Scartata.
- **CDN/terze parti (Cloudinary, ecc.)**: comode per trasformazioni, ma
  fornitore in più; Blob + Function coprono i nostri bisogni restando in Azure.
