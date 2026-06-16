-- JamMate — Schema database (PostgreSQL) — Tappa 2
-- Per Azure Database for PostgreSQL (Flexible Server), regione UE.
-- Mappa fedele dello stato del prototipo (app.js/gigs.js/affinity.js) su un
-- modello multi-utente reale. Eseguibile così com'è per creare lo schema.

-- Estensioni utili
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ---------- Utenti ----------
-- L'identità (password, MFA, social login) è gestita da Microsoft Entra
-- External ID. Qui teniamo solo il profilo applicativo, legato al "subject"
-- (sub) del token Entra.
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entra_sub     TEXT UNIQUE NOT NULL,            -- identificativo dal token Entra
  email         TEXT UNIQUE NOT NULL,
  display_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ                       -- GDPR: cancellazione logica
);

-- ---------- Profilo musicista ----------
CREATE TABLE musician_profiles (
  user_id     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  avatar      TEXT,
  photo_url   TEXT,                               -- punta a Blob Storage
  color       TEXT,
  city        TEXT,
  distance_km INT DEFAULT 0,
  level       TEXT,                               -- Principiante/Intermedio/Avanzato/Pro
  bio         TEXT,
  tagline     TEXT,
  instruments TEXT[] NOT NULL DEFAULT '{}',
  genres      TEXT[] NOT NULL DEFAULT '{}',
  links       JSONB  NOT NULL DEFAULT '{}',       -- {youtube, spotify, instagram}
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repertoire (
  id         BIGSERIAL PRIMARY KEY,
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  song       TEXT NOT NULL,
  artist     TEXT,
  song_key   TEXT
);

-- Reputazione/endorsement (puntualità, tecnica, attitudine)
CREATE TABLE endorsements (
  id            BIGSERIAL PRIMARY KEY,
  target_user   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  author_user   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  puntualita    SMALLINT CHECK (puntualita BETWEEN 0 AND 5),
  tecnica       SMALLINT CHECK (tecnica    BETWEEN 0 AND 5),
  attitudine    SMALLINT CHECK (attitudine BETWEEN 0 AND 5),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (target_user, author_user)               -- un endorsement per coppia
);

-- ---------- Profilo profondo (motore "Sintonia") ----------
-- Dati di personalità: cifrati a livello colonna a riposo + minimizzati (GDPR).
CREATE TABLE deep_profiles (
  user_id   UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  done      BOOLEAN NOT NULL DEFAULT false,
  values    JSONB,    -- 10 valori di Schwartz (Autodirezione, Stimolazione, ...)
  big5      JSONB,    -- {O,C,E,A,N}
  ipc       JSONB,    -- {D: dominanza, W: calore} — modello interpersonale
  goal      JSONB,    -- obiettivi/impegno
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Swipe / match ----------
CREATE TABLE swipes (
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_user UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  decision   TEXT NOT NULL CHECK (decision IN ('liked','passed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, target_user)
);

CREATE TABLE matches (
  id         BIGSERIAL PRIMARY KEY,
  user_a     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_b     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_a, user_b)
);

-- ---------- Band ----------
CREATE TABLE bands (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  avatar     TEXT,
  color      TEXT,
  city       TEXT,
  fee        TEXT,                                 -- compenso indicativo (testo libero, es. "400€")
  tagline    TEXT,
  genres     TEXT[] NOT NULL DEFAULT '{}',
  available  BOOLEAN NOT NULL DEFAULT true,        -- "Pronta & Disponibile"
  rating     NUMERIC(3,2) DEFAULT 0,
  ratings    INT DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE band_members (
  band_id  UUID NOT NULL REFERENCES bands(id) ON DELETE CASCADE,
  user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role     TEXT,                                   -- es. "chitarra", "voce"
  is_admin BOOLEAN NOT NULL DEFAULT false,         -- chi può gestire la band
  PRIMARY KEY (band_id, user_id)
);

CREATE TABLE band_repertoire (
  id       BIGSERIAL PRIMARY KEY,
  band_id  UUID NOT NULL REFERENCES bands(id) ON DELETE CASCADE,
  song     TEXT NOT NULL,
  artist   TEXT
);

-- ---------- Locali ----------
CREATE TABLE venues (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  avatar     TEXT,
  color      TEXT,
  type       TEXT,                                 -- es. "Live club", "Pub"
  city       TEXT,
  capacity   INT,
  genres     TEXT[] NOT NULL DEFAULT '{}',
  rating     NUMERIC(3,2) DEFAULT 0,
  ratings    INT DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Serate aperte pubblicate da un locale ("openNight")
CREATE TABLE open_nights (
  id        BIGSERIAL PRIMARY KEY,
  venue_id  UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
  night_date DATE NOT NULL,
  genre     TEXT,
  budget    TEXT
);

-- ---------- Prenotazioni (marketplace band <-> locale) ----------
-- Stati: requested -> quoted -> confirmed -> completed -> reviewed (allineato a gigs.js)
CREATE TABLE bookings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind        TEXT NOT NULL CHECK (kind IN ('band','venue')),  -- chi ha iniziato
  band_id     UUID REFERENCES bands(id)  ON DELETE SET NULL,
  venue_id    UUID REFERENCES venues(id) ON DELETE SET NULL,
  gig_date    DATE NOT NULL,
  budget      TEXT,
  quote       TEXT,
  status      TEXT NOT NULL DEFAULT 'requested'
              CHECK (status IN ('requested','quoted','confirmed','completed','reviewed','cancelled')),
  -- Pagamenti (Tappa 6, Stripe): riferimenti, non dati carta
  amount_cents     INT,
  fee_cents        INT,        -- commissione JamMate (5% al locale)
  deposit_cents    INT,        -- acconto in escrow
  stripe_pi_id     TEXT,       -- PaymentIntent
  stripe_transfer_id TEXT,     -- payout alla band
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recensioni a doppio cieco (rivelate solo quando entrambe le parti hanno recensito)
CREATE TABLE reviews (
  id          BIGSERIAL PRIMARY KEY,
  booking_id  UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  author_side TEXT NOT NULL CHECK (author_side IN ('band','venue')),
  rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  text        TEXT,
  revealed    BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (booking_id, author_side)
);

-- ---------- Messaggi (chat) ----------
CREATE TABLE threads (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind       TEXT NOT NULL DEFAULT 'dm',           -- 'dm' | 'booking'
  booking_id UUID REFERENCES bookings(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE thread_participants (
  thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (thread_id, user_id)
);

CREATE TABLE messages (
  id         BIGSERIAL PRIMARY KEY,
  thread_id  UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  sender_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Indici per le query più frequenti ----------
CREATE INDEX idx_profiles_city     ON musician_profiles(city);
CREATE INDEX idx_profiles_genres   ON musician_profiles USING GIN (genres);
CREATE INDEX idx_profiles_instr    ON musician_profiles USING GIN (instruments);
CREATE INDEX idx_bands_city        ON bands(city);
CREATE INDEX idx_venues_city       ON venues(city);
CREATE INDEX idx_bookings_band     ON bookings(band_id);
CREATE INDEX idx_bookings_venue    ON bookings(venue_id);
CREATE INDEX idx_bookings_status   ON bookings(status);
CREATE INDEX idx_messages_thread   ON messages(thread_id, created_at);
