-- migrate:up

-- PostgreSQL requiere que los tipos ENUM se creen por separado primero.
CREATE TYPE user_status AS ENUM ('profe', 'alumno');
CREATE TYPE user_action AS ENUM ('Girar', 'Pinzar', 'Reverencia');

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY, -- 'SERIAL' es el equivalente de 'AUTO_INCREMENT' en PostgreSQL.
    nombreCompleto VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    usr_name VARCHAR(255) NOT NULL UNIQUE,
    usr_psw VARCHAR(255) NOT NULL, -- TODO: Hashear con password_hash() (bcrypt) o Argon2.
    statuss user_status,
    usr_pronouns VARCHAR(255),
    Accion user_action
);

-- migrate:down

DROP TABLE IF EXISTS usuarios;
DROP TYPE IF EXISTS user_status;
DROP TYPE IF EXISTS user_action;
