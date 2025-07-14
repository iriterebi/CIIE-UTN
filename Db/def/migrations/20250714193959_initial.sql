-- migrate:up

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombreCompleto VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    usr_name VARCHAR(255) NOT NULL UNIQUE,
    usr_psw VARCHAR(255) NOT NULL, -- TODO guarda en bcrypt o Argon2
    statuss ENUM('profe', 'alumno'),
    usr_pronouns VARCHAR(255),
    Accion ENUM('Girar', 'Pinzar', 'Reverencia') -- Se asume que 'Girar' es el valor por defecto deseado
);

-- migrate:down

DROP TABLE IF EXISTS usuarios;

