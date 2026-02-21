-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Schemas for data pipeline stages
CREATE SCHEMA IF NOT EXISTS raw;       -- Raw ingested FIA data
CREATE SCHEMA IF NOT EXISTS staging;   -- dbt staging models
CREATE SCHEMA IF NOT EXISTS marts;     -- dbt mart models
CREATE SCHEMA IF NOT EXISTS qa;        -- QA/QC results

-- Raw FIA tables (populated by ingestion pipeline)

CREATE TABLE raw.fia_plot (
    cn BIGINT PRIMARY KEY,
    statecd INTEGER NOT NULL,
    unitcd INTEGER,
    countycd INTEGER,
    plot INTEGER,
    invyr INTEGER NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    elev INTEGER,
    ecosubcd VARCHAR(10),
    geom GEOMETRY(Point, 4326),
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fia_plot_geom ON raw.fia_plot USING GIST (geom);
CREATE INDEX idx_fia_plot_state ON raw.fia_plot (statecd);
CREATE INDEX idx_fia_plot_invyr ON raw.fia_plot (invyr);

CREATE TABLE raw.fia_cond (
    cn BIGINT PRIMARY KEY,
    plt_cn BIGINT REFERENCES raw.fia_plot(cn),
    condid INTEGER,
    statecd INTEGER NOT NULL,
    fortypcd INTEGER,
    fortypcdname VARCHAR(100),
    stdage INTEGER,
    stdszcd INTEGER,
    siteclcd INTEGER,
    slope INTEGER,
    aspect INTEGER,
    owncd INTEGER,
    owngrpcd INTEGER,
    condprop_unadj DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fia_cond_plt ON raw.fia_cond (plt_cn);
CREATE INDEX idx_fia_cond_fortyp ON raw.fia_cond (fortypcd);

CREATE TABLE raw.fia_tree (
    cn BIGINT PRIMARY KEY,
    plt_cn BIGINT REFERENCES raw.fia_plot(cn),
    condid INTEGER,
    subp INTEGER,
    tree INTEGER,
    statecd INTEGER NOT NULL,
    spcd INTEGER NOT NULL,
    dia DOUBLE PRECISION,
    ht DOUBLE PRECISION,
    actualht DOUBLE PRECISION,
    cr INTEGER,
    statuscd INTEGER,
    drybio_ag DOUBLE PRECISION,
    drybio_bg DOUBLE PRECISION,
    carbon_ag DOUBLE PRECISION,
    carbon_bg DOUBLE PRECISION,
    tpa_unadj DOUBLE PRECISION,
    volcfnet DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fia_tree_plt ON raw.fia_tree (plt_cn);
CREATE INDEX idx_fia_tree_spcd ON raw.fia_tree (spcd);
CREATE INDEX idx_fia_tree_dia ON raw.fia_tree (dia);

-- QA/QC results table
CREATE TABLE qa.validation_results (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    check_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- 'error', 'warning', 'info'
    records_checked INTEGER,
    records_failed INTEGER,
    failure_rate DOUBLE PRECISION,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
