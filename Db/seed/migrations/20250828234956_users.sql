-- migrate:up

-- Contraseñas en texto plano (para testing):
--   phosph   → admin123
--   alumno01 → alumno123

INSERT INTO usuarios (nombreCompleto, email, usr_name, usr_psw, statuss, usr_pronouns) VALUES
  ('Jesus Figueredo', 'jfigueredochirinos@frba.utn.edu.ar', 'phosph', '$2b$12$qrzh8bX0aRYN.seZmG5gSuiLvU79B8plpd3EY1OO3kzFnro.5yP/K', 'profe', 'el'),
  ('Alumno De Prueba', 'alumno@test.com', 'alumno01', '$2b$12$JYZLGTy0ufHe5oru7AuwtOW2bEyZQMgso6NOn1zBzphKHS7tfrA1K', 'alumno', null);

-- migrate:down

DELETE FROM usuarios WHERE usr_name IN ('phosph', 'alumno01');
