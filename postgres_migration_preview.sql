BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 19fc0e5404d9

CREATE TABLE projects (
    id SERIAL NOT NULL, 
    title VARCHAR NOT NULL, 
    description TEXT, 
    github_url VARCHAR NOT NULL, 
    demo_url VARCHAR, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    is_published BOOLEAN NOT NULL, 
    PRIMARY KEY (id)
);

INSERT INTO alembic_version (version_num) VALUES ('19fc0e5404d9') RETURNING alembic_version.version_num;

-- Running upgrade 19fc0e5404d9 -> 19a80d91046e

CREATE TABLE users (
    username VARCHAR NOT NULL, 
    email VARCHAR NOT NULL, 
    hashed_password VARCHAR NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    is_admin BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email), 
    UNIQUE (username)
);

ALTER TABLE projects ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE projects ALTER COLUMN updated_at SET NOT NULL;

UPDATE alembic_version SET version_num='19a80d91046e' WHERE alembic_version.version_num = '19fc0e5404d9';

-- Running upgrade 19a80d91046e -> 40b016ca58ef

ALTER TABLE projects ADD COLUMN deleted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE alembic_version SET version_num='40b016ca58ef' WHERE alembic_version.version_num = '19a80d91046e';

-- Running upgrade 40b016ca58ef -> 9d5c0637f98d

CREATE TABLE refresh_tokens (
    jti VARCHAR NOT NULL, 
    user_id INTEGER NOT NULL, 
    family_id VARCHAR NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(7) NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    id SERIAL NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT refresh_token_status CHECK (status IN ('active', 'used', 'revoked'))
);

CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens (family_id);

CREATE UNIQUE INDEX ix_refresh_tokens_jti ON refresh_tokens (jti);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);

ALTER TABLE projects DROP COLUMN deleted_at;

ALTER TABLE users DROP COLUMN deleted_at;

UPDATE alembic_version SET version_num='9d5c0637f98d' WHERE alembic_version.version_num = '40b016ca58ef';

-- Running upgrade 9d5c0637f98d -> 627a31e10de3

CREATE TABLE images (
    id SERIAL NOT NULL, 
    url VARCHAR NOT NULL, 
    project_id INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

UPDATE alembic_version SET version_num='627a31e10de3' WHERE alembic_version.version_num = '9d5c0637f98d';

COMMIT;

