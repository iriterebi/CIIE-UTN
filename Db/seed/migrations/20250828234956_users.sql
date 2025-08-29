-- migrate:up

INSERT INTO usuarios (nombreCompleto, email, usr_name, usr_psw, statuss, usr_pronouns) VALUES ('Jesus Figueredo', 'jfigueredochirinos@frba.utn.edu.ar', 'phosph', '123456', 'alumno', 'el');

-- migrate:down

DELETE from usuarios u
WHEN u.usr_name = 'phosph'
