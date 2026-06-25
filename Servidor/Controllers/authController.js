module.exports = function(dependencies) {
    // Importamos tus variables globales para no romper tu código
    const { db, socketSessions, sendFramedMessage } = dependencies;

    function processLogin(socket, jsonMsg) {
        const session = socketSessions.get(socket);
        if (session?.userId) return sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Ya has iniciado sesión.' });

        const { correo, password } = jsonMsg, user = db.getUserByCorreo(correo);
        if (user && db.verifyPassword(password, user.PasswordHash)) {
            if (!user.Activo) return sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Usuario inactivo' });

            session.userId = user.IdUsuario;
            session.userName = user.Nombres;
            session.correo = user.Correo;

            sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: true, usuario: { id: user.IdUsuario, nombres: user.Nombres, correo: user.Correo } });
            console.log(`Usuario autenticado: ${user.Nombres} (${user.Correo})`);
        } else {
            sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Correo o contraseña incorrectos.' });
        }
    }

    function processRegister(socket, jsonMsg) {
        const { nombres, correo, password } = jsonMsg;
        if (db.getUserByCorreo(correo)) return sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: false, message: 'El correo ya está registrado.' });

        const result = db.createUser(nombres, correo, password);
        if (result.success) {
            sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: true, message: 'Usuario registrado exitosamente.' });
        } else {
            sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: false, message: 'Error en BD: ' + result.error });
        }
    }

    return { processLogin, processRegister };
};