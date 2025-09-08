-- migrate:up

-- UUID PRIMARY KEY DEFAULT gen_random_uuid()

CREATE TABLE robots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_identifier VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    psw VARCHAR(255) NOT NULL,

    status VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE robot_status_history (
    id SERIAL PRIMARY KEY,
    status VARCHAR(255) NOT NULL,
    -- function VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    robot_id UUID REFERENCES robots(id) ON DELETE CASCADE NOT NULL,
    user_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- === TRIGGER: Guardar historial en cada INSERT o UPDATE ===
-- Función que inserta un registro en la tabla de historial.
CREATE OR REPLACE FUNCTION log_robot_status_change_function()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO robot_status_history (
        robot_id,
        user_id,
        status,
        timestamp
    )
    VALUES (
        NEW.id,
        NEW.user_id,
        NEW.status,
        NOW()
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
DROP TABLE IF EXISTS robot_status_history;
DROP TABLE IF EXISTS robots;
