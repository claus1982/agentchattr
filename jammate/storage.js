/* JamMate — Data Layer (Tappa 1).
 *
 * Questo modulo è il "seam" (giuntura) tra l'app e dove vivono i dati.
 * Oggi i dati stanno nel browser (localStorage); domani, senza riscrivere
 * la UI, basterà attivare il backend "api" che parla con Azure Functions.
 *
 * L'app NON usa più localStorage direttamente: passa sempre da JM.Storage.
 * Così la migrazione al backend reale è un cambio di backend, non un rewrite.
 */
(function () {
  "use strict";
  window.JM = window.JM || {};

  // --- Backend locale (default): chiave/valore su localStorage del browser ---
  const localBackend = {
    name: "local",
    available() { try { return typeof localStorage !== "undefined"; } catch (e) { return false; } },
    get(key) { return localStorage.getItem(key); },
    set(key, value) { localStorage.setItem(key, value); },
    remove(key) { localStorage.removeItem(key); }
  };

  // --- Backend di riserva in memoria (se localStorage è bloccato) ---
  const memory = {};
  const memoryBackend = {
    name: "memory",
    available() { return true; },
    get(key) { return key in memory ? memory[key] : null; },
    set(key, value) { memory[key] = String(value); },
    remove(key) { delete memory[key]; }
  };

  let active = localBackend.available() ? localBackend : memoryBackend;

  /* API pubblica del data layer.
   * In futuro: JM.Storage.use(apiBackend) per puntare ad Azure (vedi API_CONTRACT). */
  JM.Storage = {
    get backend() { return active.name; },
    use(backend) { active = backend; },
    get(key) { return active.get(key); },
    set(key, value) { active.set(key, value); },
    remove(key) { active.remove(key); }
  };
})();
