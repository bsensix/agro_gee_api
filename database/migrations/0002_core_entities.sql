CREATE TABLE IF NOT EXISTS core.users (
    user_id BIGSERIAL PRIMARY KEY,
    parent_user_id BIGINT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT users_parent_user_fk
        FOREIGN KEY (parent_user_id)
        REFERENCES core.users(user_id)
        ON DELETE SET NULL,
    CONSTRAINT users_name_nonempty_chk CHECK (BTRIM(name) <> ''),
    CONSTRAINT users_email_nonempty_chk CHECK (BTRIM(email) <> ''),
    CONSTRAINT users_role_nonempty_chk CHECK (BTRIM(role) <> ''),
    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS core.farms (
    farm_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    geometry GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    area_ha NUMERIC(14, 4) NOT NULL,
    CONSTRAINT farms_user_fk
        FOREIGN KEY (user_id)
        REFERENCES core.users(user_id),
    CONSTRAINT farms_name_nonempty_chk CHECK (BTRIM(name) <> ''),
    CONSTRAINT farms_area_nonnegative_chk CHECK (area_ha >= 0)
);

CREATE TABLE IF NOT EXISTS core.fields (
    field_id BIGSERIAL PRIMARY KEY,
    farm_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    geometry GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    area_ha NUMERIC(14, 4) NOT NULL,
    CONSTRAINT fields_farm_fk
        FOREIGN KEY (farm_id)
        REFERENCES core.farms(farm_id),
    CONSTRAINT fields_name_nonempty_chk CHECK (BTRIM(name) <> ''),
    CONSTRAINT fields_area_nonnegative_chk CHECK (area_ha >= 0)
);

CREATE INDEX IF NOT EXISTS farms_geometry_gix
    ON core.farms
    USING GIST (geometry);

CREATE INDEX IF NOT EXISTS fields_geometry_gix
    ON core.fields
    USING GIST (geometry);
