-- Datos de Prueba para la Base de Datos --

INSERT INTO Usuarios (Nombres, Correo, PasswordHash) VALUES 
('Alejandro ', 'alejandro@test.com', '11a823815d8d5f553a662d08eb6258be:24c5d3098493b4b8b13ba3735f0522613340ea82337cb9ed953d74d46a42dc9cbfba00d3a12a3fa7ad98087c7162ec25d6118a5b06865a3eb67823e31cb909b7'), -- pass: admin123
('Nate ', 'Nate318@test.com', '1a8292f67d9c907db797fe61d5fec90d:3e1b02114e522f1e5a4f9eecf8be888d99e3a4b541b818e4ed3818f6b0ae1a20eaad7501241166a7fa94d0eba702c4ebaf8a8997fd26f70ee741f8a249ccca31'),       -- pass: user123
('Michelin ', 'Michelin@test.com', '82ab38572e2611320cc302461f1d9f7f:c9210ef29298682c77f04b1ccb5b45ff42fc59613daf328e378a2ad90f0682328012c66e4f1615a58584c872f4c1935c762ea9c00e7055b5914256cbfe77c920');      -- pass: guest123

-- Sala inicial de prueba -- Host: Alejandro
INSERT INTO Salas (CodigoSala, Nombre, IdHost, Estado) VALUES
('AULA123', 'Clase de Prueba de Alejandro', 1, 'Activa');

-- Participantes de la sala --
INSERT INTO ParticipantesSala (IdSala, IdUsuario, Estado) VALUES
(1, 1, 'Host');
