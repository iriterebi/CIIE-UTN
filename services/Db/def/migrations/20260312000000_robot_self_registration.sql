-- migrate:up

-- El nombre se asigna durante la aprobacion, no durante el registro
ALTER TABLE robots ALTER COLUMN name DROP NOT NULL;

-- Migrar status existentes antes de agregar constraint
UPDATE robots SET status = 'approved' WHERE status = 'Init';

ALTER TABLE robots ADD CONSTRAINT robots_status_check
    CHECK (status IN ('pending_approval', 'approved', 'rejected', 'disabled'));

-- migrate:down

ALTER TABLE robots DROP CONSTRAINT IF EXISTS robots_status_check;
UPDATE robots SET status = 'Init' WHERE status = 'approved';
ALTER TABLE robots ALTER COLUMN name SET NOT NULL;
