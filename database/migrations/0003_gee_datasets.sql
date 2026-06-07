CREATE TABLE IF NOT EXISTS core.gee_datasets (
    dataset_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    title TEXT NOT NULL,
    bands TEXT[] NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT gee_datasets_dataset_id_nonempty_chk CHECK (BTRIM(dataset_id) <> ''),
    CONSTRAINT gee_datasets_provider_nonempty_chk CHECK (BTRIM(provider) <> ''),
    CONSTRAINT gee_datasets_title_nonempty_chk CHECK (BTRIM(title) <> '')
);

INSERT INTO core.gee_datasets (dataset_id, provider, title, bands, is_active)
VALUES
    (
        'COPERNICUS/S2_SR_HARMONIZED',
        'gee',
        'Sentinel-2 SR Harmonized',
        ARRAY['B2', 'B3', 'B4', 'B8', 'QA60'],
        TRUE
    ),
    (
        'LANDSAT/LC08/C02/T1_L2',
        'gee',
        'Landsat 8 Collection 2 Level 2',
        ARRAY['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'QA_PIXEL'],
        FALSE
    )
ON CONFLICT (dataset_id) DO NOTHING;
