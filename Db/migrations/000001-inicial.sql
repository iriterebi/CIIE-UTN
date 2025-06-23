CREATE DATABASE IF NOT EXISTS ciie_db;

drop table if EXISTS ciie_db.ciie_table;

CREATE TABLE ciie_db.ciie_table (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombreCompleto VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    usr_name VARCHAR(255) NOT NULL UNIQUE,
    usr_psw VARCHAR(255) NOT NULL, -- TODO guarda en md5 y en otra tabla
    statuss ENUM('profe', 'alumno'),
    usr_pronouns VARCHAR(255),
    Accion ENUM('Girar', 'Pinzar', 'Reverencia') -- Se asume que 'Girar' es el valor por defecto deseado
);

CREATE UNIQUE INDEX idx_ciie_table_usr_name
    ON ciie_db.ciie_table (usr_name);