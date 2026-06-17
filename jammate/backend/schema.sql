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
  level       TEXT,                               -- livello "di testa" (il più alto fra gli strumenti)
  bio         TEXT,
  tagline     TEXT,
  instruments TEXT[] NOT NULL DEFAULT '{}',
  levels      JSONB  NOT NULL DEFAULT '{}',        -- livello per strumento: {"Sax":"Avanzato","Piano":"Principiante"}
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

-- ---------- Inviti in band (musicista invitato a entrare in formazione) ----------
-- Modella il quick-win frontend "Invita in band": un admin della band invita un
-- musicista a coprire un ruolo; lui accetta/rifiuta. All'accettazione diventa
-- una riga in band_members. Nel prototipo l'accettazione è simulata.
CREATE TABLE band_invites (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  band_id    UUID NOT NULL REFERENCES bands(id) ON DELETE CASCADE,
  invitee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  inviter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       TEXT,                                  -- strumento/ruolo proposto
  message    TEXT,
  status     TEXT NOT NULL DEFAULT 'pending'
             CHECK (status IN ('pending','accepted','declined','cancelled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  responded_at TIMESTAMPTZ,
  UNIQUE (band_id, invitee_id)
);

-- ---------- Jam geolocalizzate (mappa, #9) ----------
-- access_mode (DECISO: ibrido) — l'autore sceglie per ogni jam:
--   'open'     = ogni musicista idoneo partecipa subito;
--   'approval' = l'idoneo invia richiesta, l'autore conferma.
CREATE TABLE jams (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  host_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       TEXT,
  starts_at   TIMESTAMPTZ NOT NULL,
  lat         DOUBLE PRECISION,                     -- geolocalizzazione
  lng         DOUBLE PRECISION,
  place       TEXT,
  genres      TEXT[] NOT NULL DEFAULT '{}',
  -- idoneità: strumenti cercati e livello minimo richiesto
  instruments TEXT[] NOT NULL DEFAULT '{}',
  min_level   SMALLINT,                             -- indice su LEVELS (0..5)
  access_mode TEXT NOT NULL DEFAULT 'open' CHECK (access_mode IN ('open','approval')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jam_participants (
  jam_id    UUID NOT NULL REFERENCES jams(id) ON DELETE CASCADE,
  user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- per access_mode='open' nasce 'joined'; per 'approval' nasce 'requested'
  status    TEXT NOT NULL DEFAULT 'requested'
            CHECK (status IN ('requested','joined','declined')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (jam_id, user_id)
);

-- ---------- Lezioni (#12) — DECISO: prenotazione + pagamento da subito ----------
CREATE TABLE teacher_profiles (
  user_id     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  instruments TEXT[] NOT NULL DEFAULT '{}',
  bio         TEXT,
  hourly_cents INT NOT NULL,                        -- tariffa oraria
  city        TEXT,
  online      BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lesson_slots (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  starts_at  TIMESTAMPTZ NOT NULL,
  duration_min INT NOT NULL DEFAULT 60,
  is_booked  BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE lesson_bookings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_id     UUID NOT NULL REFERENCES lesson_slots(id) ON DELETE CASCADE,
  student_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status      TEXT NOT NULL DEFAULT 'pending_payment'
              CHECK (status IN ('pending_payment','confirmed','completed','cancelled','refunded')),
  -- pagamento online da subito (Stripe, stesso modello escrow/commissione delle serate)
  amount_cents INT NOT NULL,
  fee_cents    INT,
  stripe_pi_id TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (slot_id)
);

-- ---------- Feed sociale (#11) ----------
CREATE TABLE posts (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body       TEXT,
  image_url  TEXT,                                  -- media su Blob Storage (ADR 0010)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE post_comments (
  id         BIGSERIAL PRIMARY KEY,
  post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Una reazione per utente per post (emoji multiple: 👍 ❤️ 🔥 😂 …)
CREATE TABLE post_reactions (
  post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  emoji      TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (post_id, user_id)
);

-- ---------- Notifiche (#10) ----------
CREATE TABLE notifications (
  id         BIGSERIAL PRIMARY KEY,
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  icon       TEXT,
  text       TEXT NOT NULL,
  link_view  TEXT,                                  -- vista frontend da aprire al tap
  read       BOOLEAN NOT NULL DEFAULT false,
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
CREATE INDEX idx_band_invites_invitee ON band_invites(invitee_id, status);
CREATE INDEX idx_jams_starts       ON jams(starts_at);
CREATE INDEX idx_jams_geo          ON jams(lat, lng);
CREATE INDEX idx_jam_parts_user    ON jam_participants(user_id);
CREATE INDEX idx_lesson_slots_teacher ON lesson_slots(teacher_id, starts_at);
CREATE INDEX idx_posts_created     ON posts(created_at DESC);
CREATE INDEX idx_post_comments_post ON post_comments(post_id, created_at);
CREATE INDEX idx_post_reactions_post ON post_reactions(post_id);
CREATE INDEX idx_notifications_user ON notifications(user_id, read, created_at DESC);
