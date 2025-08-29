-- migrate:up

CREATE TABLE robots (
    r_id SERIAL PRIMARY KEY,
    r_name VARCHAR(255) NOT NULL,
    r_description VARCHAR(255),
    r_status VARCHAR(255) NOT NULL,
    r_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    r_user_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);
CREATE TABLE robot_status_history (
    rsh_id SERIAL PRIMARY KEY,
    rsh_status VARCHAR(255) NOT NULL,
    -- rsh_function VARCHAR(255),
    rsh_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    rsh_robot_id INTEGER REFERENCES robots(r_id) ON DELETE CASCADE NOT NULL,
    rsh_user_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- ==== triggers ====

-- === TRIGGER 1: Actualizar timestamp en cada UPDATE ===
-- Actualiza el campo `rs_timestamp` a la fecha y hora actual.
CREATE OR REPLACE FUNCTION update_robot_status_timestamp_function()
RETURNS TRIGGER AS $$
BEGIN
   NEW.r_timestamp = NOW();
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Creación del trigger para actualizar el timestamp.
CREATE TRIGGER update_robot_status_timestamp_trigger
BEFORE UPDATE ON robots
FOR EACH ROW
EXECUTE FUNCTION update_robot_status_timestamp_function();

-- === TRIGGER 2: Guardar historial en cada INSERT o UPDATE ===
-- Función que inserta un registro en la tabla de historial.
CREATE OR REPLACE FUNCTION log_robot_status_change_function()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO robot_status_history (
        rsh_robot_id,
        rsh_user_id,
        rsh_status,
        rsh_timestamp
    )
    VALUES (
        NEW.r_id,
        NEW.r_user_id,
        NEW.r_status,
        NEW.r_timestamp
    );
    RETURN NEW; -- El valor de retorno se ignora en triggers AFTER, pero es buena práctica.
END;
$$ LANGUAGE plpgsql;

-- Creación del trigger para el historial.
CREATE TRIGGER log_robot_status_change_trigger
AFTER INSERT OR UPDATE ON robots
FOR EACH ROW
EXECUTE FUNCTION log_robot_status_change_function();

-- migrate:down
DROP TRIGGER IF EXISTS log_robot_status_change_trigger ON robots;
DROP FUNCTION IF EXISTS log_robot_status_change_function();
DROP TRIGGER IF EXISTS update_robot_status_timestamp_trigger ON robots;
DROP FUNCTION IF EXISTS update_robot_status_timestamp_function();
DROP TABLE IF EXISTS robot_status_history;
DROP TABLE IF EXISTS robots;
