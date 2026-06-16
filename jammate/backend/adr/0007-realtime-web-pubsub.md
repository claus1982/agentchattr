# ADR 0007 — Chat realtime: Azure Web PubSub

**Stato:** Proposto · **Data:** 2026-06-16

## Contesto
La chat (sbloccata dal match e legata alle trattative di prenotazione) trarrebbe
beneficio da messaggi **in tempo reale**, senza ricaricare. Le Functions sono
HTTP stateless: non mantengono connessioni persistenti.

## Decisione (proposta)
Usare **Azure Web PubSub** per il canale realtime (WebSocket gestiti), con i
messaggi **persistiti su PostgreSQL** (tabelle `threads`/`messages`). Le
Functions autorizzano e pubblicano; il client si connette a Web PubSub.

## Razionale
- **WebSocket gestiti**: niente server di connessioni da mantenere noi.
- **Si sposa con le Functions**: pattern serverless + servizio realtime.
- **Tier free** per iniziare; scala con gli utenti.
- Persistendo su Postgres manteniamo storico e fonte di verità unica.

## Conseguenze
- (+) Tempo reale senza gestire infrastruttura di socket.
- (−) Un servizio Azure in più da configurare; complessità giustificata solo
  quando la chat diventa prioritaria.
- Stato **Proposto**: è una funzionalità da **Tappa 7**. Fino ad allora la chat
  può funzionare in modalità semplice (richiesta periodica/polling) sulle stesse
  tabelle, e si attiva il realtime quando serve.

## Alternative considerate
- **Azure SignalR Service**: equivalente, più orientato a client .NET/SDK
  specifici; Web PubSub è più neutro (WebSocket puri) per una PWA in JS.
- **Polling via Functions**: semplicissimo per partire, ma non "vero" realtime;
  ottimo come fallback iniziale.
