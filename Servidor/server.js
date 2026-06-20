const net = require('net');
const db = require('./database');

const PORT = 8080;
const HOST = '0.0.0.0';
const MAX_FRAME_SIZE = 10 * 1024 * 1024; // Límite de 10 MB por mensaje
const SOCKET_TIMEOUT = 120000; // 2 minutos de inactividad máxima

const socketSessions = new Map();

const server = net.createServer((socket) => {
    const clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Nuevo cliente conectado desde: ${clientAddress}`);

    socketSessions.set(socket, {
        userId: null,
        userName: null,
        correo: null,
        rol: null
    });

    socket.setTimeout(SOCKET_TIMEOUT);
    socket.on('timeout', () => {
        console.warn(`Cerrando conexión inactiva de: ${clientAddress}`);
        socket.destroy();
    });

    let buffer = Buffer.alloc(0);

    socket.on('data', (chunk) => {
        buffer = Buffer.concat([buffer, chunk]);
        console.log(`Recibidos ${chunk.length} bytes de ${clientAddress}`);

        while (buffer.length >= 8) {
            const jsonLen = buffer.readUInt32BE(0);
            const binLen = buffer.readUInt32BE(4);
            const totalFrameLen = 8 + jsonLen + binLen;

            if (totalFrameLen > MAX_FRAME_SIZE) {
                console.error(`[ERROR] Trama de ${clientAddress} excede el tamaño máximo permitido (${totalFrameLen} bytes). Cerrando conexión.`);
                socket.destroy();
                return;
            }

            if (buffer.length < totalFrameLen) {
                break;
            }

            const jsonStart = 8;
            const jsonEnd = 8 + jsonLen;
            const jsonBuffer = buffer.subarray(jsonStart, jsonEnd);
            const jsonStr = jsonBuffer.toString('utf8');

            let binaryPayload = null;
            if (binLen > 0) {
                binaryPayload = buffer.subarray(jsonEnd, totalFrameLen);
            }

            try {
                const jsonPayload = JSON.parse(jsonStr);
                handleMessage(socket, jsonPayload, binaryPayload);
            } catch (err) {
                console.warn(`No se pudo procesar el mensaje de ${clientAddress}:`, err.message);
            }

            buffer = buffer.subarray(totalFrameLen);
        }
    });

    socket.on('close', (hadError) => {
        console.log(`Cliente desconectado desde: ${clientAddress} ${hadError ? 'debido a un error' : ''}`);
        socketSessions.delete(socket);
    });

    socket.on('error', (err) => {
        console.error(`Error de conexión de ${clientAddress}: ${err.message}`);
    });
});

function sendFramedMessage(targetSocket, jsonObject, binaryBuffer = null) {
    if (targetSocket.destroyed) return;
    try {
        const jsonStr = JSON.stringify(jsonObject);
        const jsonBytes = Buffer.from(jsonStr, 'utf8');
        const binLength = binaryBuffer ? binaryBuffer.length : 0;

        const header = Buffer.alloc(8);
        header.writeUInt32BE(jsonBytes.length, 0);
        header.writeUInt32BE(binLength, 4);

        targetSocket.write(header);
        targetSocket.write(jsonBytes);
        if (binaryBuffer) {
            targetSocket.write(binaryBuffer);
        }
    } catch (err) {
        console.error("Error al enviar trama:", err.message);
    }
}

function handleMessage(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket);
    const clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Mensaje recibido (${jsonMsg.type}) de ${session.userName || clientAddress}`);

    switch (jsonMsg.type) {
        case 'LOGIN_REQUEST':
            processLogin(socket, jsonMsg);
            break;
        case 'REGISTER_REQUEST':
            processRegister(socket, jsonMsg);
            break;
        default:
            console.warn(`Tipo de mensaje no admitido en esta fase: ${jsonMsg.type}`);
    }
}

function processLogin(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (session && session.userId) {
        sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Ya has iniciado sesión en esta conexión.' });
        return;
    }

    const { correo, password } = jsonMsg;
    const user = db.getUserByCorreo(correo);

    if (user && db.verifyPassword(password, user.PasswordHash)) {
        if (!user.Activo) {
            sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Usuario inactivo' });
            return;
        }

        const session = socketSessions.get(socket);
        session.userId = user.IdUsuario;
        session.userName = user.Nombres;
        session.correo = user.Correo;
        session.rol = user.Rol;

        sendFramedMessage(socket, {
            type: 'LOGIN_RESPONSE',
            success: true,
            usuario: {
                id: user.IdUsuario,
                nombres: user.Nombres,
                correo: user.Correo,
                rol: user.Rol
            }
        });
        console.log(`Usuario autenticado: ${user.Nombres} (${user.Correo})`);
    } else {
        sendFramedMessage(socket, { type: 'LOGIN_RESPONSE', success: false, message: 'Correo o contraseña incorrectos.' });
        console.log(`Intento de login fallido para: ${correo}`);
    }
}

function processRegister(socket, jsonMsg) {
    const { nombres, correo, password } = jsonMsg;
    const existing = db.getUserByCorreo(correo);

    if (existing) {
        sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: false, message: 'El correo ya está registrado.' });
        return;
    }

    const result = db.createUser(nombres, correo, password, 'Usuario');
    if (result.success) {
        sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: true, message: 'Usuario registrado exitosamente.' });
        console.log(`Nuevo usuario registrado: ${nombres} (${correo})`);
    } else {
        sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: false, message: 'Error en BD: ' + result.error });
    }
}

server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
        console.error(`El puerto ${PORT} esta siendo ocupado por otra aplicacion.`);
    } else {
        console.error(`Error en el servidor: ${err.message}`);
    }
    process.exit(1);
});

server.listen(PORT, HOST, () => {
    console.log(`SERVIDOR DE SOCKETS INICIADO`);
    console.log(`Puerto: ${PORT}`);
    console.log(`HOST: ${HOST}`);
});
