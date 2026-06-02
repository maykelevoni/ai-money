CREATE TABLE IF NOT EXISTS offers (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    network           TEXT    NOT NULL,
    network_offer_id  TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    vertical          TEXT    NOT NULL,
    payout            REAL    NOT NULL,
    geo               TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'candidate'
                              CHECK(status IN ('candidate','testing','winner','loser','excluded')),
    tracking_url      TEXT    NOT NULL DEFAULT '',
    first_seen        TEXT    NOT NULL DEFAULT (datetime('now')),
    last_tested       TEXT
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id              INTEGER NOT NULL REFERENCES offers(id),
    traffic_campaign_id   TEXT,
    lander_path           TEXT    NOT NULL DEFAULT '',
    status                TEXT    NOT NULL DEFAULT 'pending'
                                  CHECK(status IN ('pending','active','paused','killed')),
    daily_cap             REAL    NOT NULL DEFAULT 0.0,
    created_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    notes                 TEXT
);

CREATE TABLE IF NOT EXISTS creatives (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id           INTEGER NOT NULL REFERENCES campaigns(id),
    traffic_creative_id   TEXT,
    title                 TEXT    NOT NULL,
    description           TEXT    NOT NULL DEFAULT '',
    icon_path             TEXT,
    status                TEXT    NOT NULL DEFAULT 'active'
                                  CHECK(status IN ('active','paused')),
    clicks                INTEGER NOT NULL DEFAULT 0,
    ctr                   REAL    NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS clicks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    click_id     TEXT    NOT NULL UNIQUE,
    campaign_id  INTEGER NOT NULL REFERENCES campaigns(id),
    zone         TEXT    NOT NULL DEFAULT '',
    cost         REAL    NOT NULL DEFAULT 0.0,
    country      TEXT    NOT NULL DEFAULT '',
    ts           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    click_id  TEXT NOT NULL REFERENCES clicks(click_id),
    payout    REAL NOT NULL,
    ts        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS spend_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id  INTEGER NOT NULL REFERENCES campaigns(id),
    zone         TEXT    NOT NULL DEFAULT '',
    spend        REAL    NOT NULL DEFAULT 0.0,
    clicks       INTEGER NOT NULL DEFAULT 0,
    ts           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL DEFAULT (datetime('now')),
    scope      TEXT NOT NULL CHECK(scope IN ('zone','creative','campaign','offer')),
    target_id  TEXT NOT NULL,
    action     TEXT NOT NULL CHECK(action IN ('pause','scale','blacklist','kill','launch')),
    reason     TEXT NOT NULL,
    data_json  TEXT
);

CREATE TABLE IF NOT EXISTS budget_ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL DEFAULT (datetime('now')),
    amount         REAL NOT NULL,
    kind           TEXT NOT NULL CHECK(kind IN ('deposit','spend')),
    running_total  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clicks_click_id             ON clicks(click_id);
CREATE INDEX IF NOT EXISTS idx_conversions_click_id        ON conversions(click_id);
CREATE INDEX IF NOT EXISTS idx_spend_snapshots_campaign_id ON spend_snapshots(campaign_id);

-- Runtime settings (API keys, budgets, thresholds) managed from the dashboard.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
