-- PostgreSQL-Schema für den späteren Produktivbetrieb (Kapitel 22 der Handlungsanweisung).
-- Die Anwendung läuft in der lokalen Entwicklung gegen SQLite (siehe app/models.py); dieses
-- Skript ist die verbindliche Referenz für ein PostgreSQL-Deployment und wurde 1:1 aus der
-- Handlungsanweisung übernommen, ergänzt um wenige, klar markierte Zusatzspalten, die die
-- SQLAlchemy-Modelle zusätzlich pflegen (slug/intervall_minuten/vorgegeben bei portals,
-- ki_relevanz_begruendung/ki_relevanz_quelle bei tenders, korrelierende Felder bei jobs).

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- fuer gen_random_uuid()

-- Portale
CREATE TABLE portals (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  slug          TEXT NOT NULL UNIQUE,               -- Zusatz: stabiler technischer Schluessel
  base_url      TEXT NOT NULL,
  betreiber     TEXT,
  aktiv         BOOLEAN NOT NULL DEFAULT TRUE,
  robots_status TEXT NOT NULL DEFAULT 'ungeprueft',  -- geprueft_ok | geprueft_einschraenkung | ungeprueft
  tos_hinweis   TEXT,
  intervall_minuten INTEGER NOT NULL DEFAULT 180,     -- Zusatz: Scheduler-Intervall, Kapitel 8.1
  vorgegeben    BOOLEAN NOT NULL DEFAULT FALSE,        -- Zusatz: vom Auftraggeber vorgegeben vs. ergaenzt (Kapitel 3)
  erstellt_am   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ausschreibungen (einheitliches Datenmodell, siehe Kapitel 6)
CREATE TABLE tenders (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id               UUID NOT NULL REFERENCES portals(id),
  externe_id              TEXT,
  titel                   TEXT NOT NULL,
  kurzbeschreibung        TEXT,
  volltext                TEXT,
  vergabestelle           TEXT,
  ort_region               TEXT,
  veroeffentlichungsdatum DATE,
  angebotsfrist           TIMESTAMPTZ,
  fragenfrist             TIMESTAMPTZ,
  verfahrensart           TEXT,
  cpv_codes                TEXT[],
  geschaetzter_wert        NUMERIC,
  direktlink               TEXT NOT NULL,
  status                   TEXT NOT NULL DEFAULT 'neu',
  zugangsart                TEXT NOT NULL DEFAULT 'oeffentlich',
  ki_relevanz_score         TEXT,      -- stark | moeglich | nicht
  ki_relevanz_konfidenz     NUMERIC,   -- 0..1
  ki_relevanz_begruendung   TEXT,      -- Zusatz: Begruendung der Einstufung (Kapitel 20.4 Transparenz)
  ki_relevanz_quelle        TEXT,      -- Zusatz: keyword | cpv | llm
  dedupe_hash               TEXT NOT NULL,
  erfasst_am                TIMESTAMPTZ NOT NULL DEFAULT now(),
  zuletzt_geprueft_am        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (portal_id, dedupe_hash)
);
CREATE INDEX idx_tenders_frist  ON tenders (angebotsfrist);
CREATE INDEX idx_tenders_status ON tenders (status);
CREATE INDEX idx_tenders_suche  ON tenders USING GIN (
  to_tsvector('german', coalesce(titel,'') || ' ' ||
              coalesce(kurzbeschreibung,'') || ' ' || coalesce(vergabestelle,'')));

CREATE TABLE tender_documents (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tender_id  UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
  titel      TEXT,
  url        TEXT NOT NULL
);

CREATE TABLE tender_history (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tender_id   UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
  feld        TEXT NOT NULL,
  alter_wert  TEXT,
  neuer_wert  TEXT,
  erkannt_am  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE categories (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name  TEXT NOT NULL UNIQUE
);

CREATE TABLE tender_categories (
  tender_id    UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
  category_id  UUID NOT NULL REFERENCES categories(id),
  PRIMARY KEY (tender_id, category_id)
);

-- Suchprofile (Kapitel 8.2)
CREATE TABLE search_profiles (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  portale      UUID[],
  keywords     TEXT[],
  filter_json  JSONB NOT NULL DEFAULT '{}',
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  erstellt_am  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE search_profile_hits (
  profile_id  UUID NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
  tender_id   UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
  gesehen     BOOLEAN NOT NULL DEFAULT FALSE,
  markiert_am TIMESTAMPTZ,
  PRIMARY KEY (profile_id, tender_id)
);

-- Agenten-Betriebsschicht (Kapitel 17-19)
CREATE TABLE jobs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  typ            TEXT NOT NULL,   -- discovery|analysis|normalization|duplicate|classification|search|source_health
  portal_id      UUID REFERENCES portals(id),
  ziel_id        TEXT,
  correlation_id UUID,           -- Zusatz: verweist auf dieselbe Ausschreibung ueber alle Schritte (Kapitel 19.4)
  payload        JSONB NOT NULL DEFAULT '{}',
  status         TEXT NOT NULL DEFAULT 'queued',  -- queued|running|succeeded|failed|waiting_for_decision
  versuch_nr     INTEGER NOT NULL DEFAULT 0,
  max_versuche   INTEGER NOT NULL DEFAULT 3,
  fehler         TEXT,
  erstellt_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  gestartet_am   TIMESTAMPTZ,
  beendet_am     TIMESTAMPTZ
);
CREATE INDEX idx_jobs_status ON jobs (status);

CREATE TABLE job_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  agent       TEXT NOT NULL,
  ereignis    TEXT NOT NULL,   -- started|succeeded|failed|escalated
  details     JSONB,
  dauer_ms    INTEGER,
  zeitstempel TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE escalations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id         UUID REFERENCES jobs(id),
  portal_id      UUID REFERENCES portals(id),  -- Zusatz: direkte Zuordnung fuers Dashboard
  kategorie      TEXT NOT NULL,  -- login_erforderlich|captcha|tos_verbot|ip_sperre|kategorisierung_unklar|sonstiges
  kontext        TEXT NOT NULL,
  optionen       JSONB NOT NULL DEFAULT '[]',
  empfehlung     TEXT,
  status         TEXT NOT NULL DEFAULT 'offen',  -- offen|beantwortet|geparkt
  entscheidung   TEXT,
  erstellt_am    TIMESTAMPTZ NOT NULL DEFAULT now(),
  beantwortet_am TIMESTAMPTZ
);

-- Source Health Monitoring (Kapitel 21)
CREATE TABLE source_health_metrics (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id      UUID NOT NULL REFERENCES portals(id),
  lauf_am        TIMESTAMPTZ NOT NULL DEFAULT now(),
  erfolgreich    BOOLEAN NOT NULL,
  treffer_anzahl INTEGER,
  neu_anzahl     INTEGER,        -- Zusatz
  aktualisiert_anzahl INTEGER,   -- Zusatz
  fehlerrate     NUMERIC,
  fehlertyp      TEXT,
  dauer_ms       INTEGER
);

-- Ranking Engine (Kapitel 20)
CREATE TABLE ranking_scores (
  tender_id           UUID PRIMARY KEY REFERENCES tenders(id) ON DELETE CASCADE,
  ki_relevanz_score   NUMERIC,
  dringlichkeit_score NUMERIC,
  profil_score        NUMERIC,
  aktualitaet_score   NUMERIC,
  gesamtscore         NUMERIC,
  berechnet_am        TIMESTAMPTZ NOT NULL DEFAULT now()
);
