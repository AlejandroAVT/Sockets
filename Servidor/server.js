const net = require('net');
const db = require('./database');
const fs = require('fs'), path = require('path');

// Configuración Global y Directorio de Archivos
const PORT = 8080, HOST = '0.0.0.0';
const UPLOADS_DIR = path.join(__dirname, 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const MAX_FRAME_SIZE = 10 * 1024 * 1024; // Límite máximo de trama: 10 MB
const SOCKET_TIMEOUT = 120000; // Inactividad máxima permitida: 2 minutos

// Estado en Memoria de Salas y Sesiones
const activeRooms = new Map();   // Sala -> Set de sockets activos
const waitingRooms = new Map();  // Sala -> Lista de espera [{userId, socket, userName}]
const hostByRoom = new Map();    // Sala -> Socket del host
const socketSessions = new Map(); // Socket -> {userId, userName, correo, currentRoom, upload}

// Creación del Servidor TCP y Manejo de Clientes
const server = net.createServer((socket) => {
    const clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Nuevo cliente conectado desde: ${clientAddress}`);
    socketSessions.set(socket, { userId: null, userName: null, correo: null });

    socket.setTimeout(SOCKET_TIMEOUT);
    socket.on('timeout', () => {
        console.warn(`Cerrando conexión inactiva de: ${clientAddress}`);
        socket.destroy();
    });

    let buffer = Buffer.alloc(0); // Acumulador de fragmentos TCP

    socket.on('data', (chunk) => {
        buffer = Buffer.concat([buffer, chunk]);
        console.log(`Recibidos ${chunk.length} bytes de ${clientAddress}`);

        while (buffer.length >= 8) {
            const jsonLen = buffer.readUInt32BE(0), binLen = buffer.readUInt32BE(4);
            const totalFrameLen = 8 + jsonLen + binLen;

            if (totalFrameLen > MAX_FRAME_SIZE) {
                console.error(`Error: Trama excede tamaño máximo (${totalFrameLen} bytes). Cerrando.`);
                return socket.destroy();
            }
            if (buffer.length < totalFrameLen) break;

            const jsonBuffer = buffer.subarray(8, 8 + jsonLen);
            const binaryPayload = binLen > 0 ? buffer.subarray(8 + jsonLen, totalFrameLen) : null;

            try {
                handleMessage(socket, JSON.parse(jsonBuffer.toString('utf8')), binaryPayload);
            } catch (err) {
                console.warn(`No se pudo procesar el mensaje de ${clientAddress}:`, err.message);
            }
            buffer = buffer.subarray(totalFrameLen);
        }
    });

    socket.on('close', (hadError) => {
        console.log(`Cliente desconectado desde: ${clientAddress} ${hadError ? 'debido a un error' : ''}`);
        handleDisconnect(socket);
    });

    socket.on('error', (err) => console.error(`Error de conexión de ${clientAddress}: ${err.message}`));
});

// Envía un mensaje estructurado (JSON + Binario) aplicando el protocolo de enmarcado (header de 8 bytes)
function sendFramedMessage(targetSocket, jsonObject, binaryBuffer = null) {
    if (targetSocket.destroyed) return;
    try {
        const jsonBytes = Buffer.from(JSON.stringify(jsonObject), 'utf8'), binLength = binaryBuffer ? binaryBuffer.length : 0;
        const header = Buffer.alloc(8);
        header.writeUInt32BE(jsonBytes.length, 0);
        header.writeUInt32BE(binLength, 4);

        targetSocket.write(header);
        targetSocket.write(jsonBytes);
        if (binaryBuffer) targetSocket.write(binaryBuffer);
    } catch (err) { console.error("Error al enviar trama:", err.message); }
}

// Enrutador de mensajes recibidos de los clientes
function handleMessage(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket), clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Mensaje recibido (${jsonMsg.type}) de ${session.userName || clientAddress}`);

    switch (jsonMsg.type) {
        case 'LOGIN_REQUEST': processLogin(socket, jsonMsg); break;
        case 'REGISTER_REQUEST': processRegister(socket, jsonMsg); break;
        case 'CREATE_ROOM': processCreateRoom(socket, jsonMsg); break;
        case 'JOIN_ROOM_REQUEST': processJoinRoomRequest(socket, jsonMsg); break;
        case 'ADMIT_USER': processAdmitUser(socket, jsonMsg); break;
        case 'CHAT_MESSAGE': processChatMessage(socket, jsonMsg); break;
        case 'LEAVE_ROOM': processLeaveRoom(socket); break;
        case 'FILE_CHUNK': processFileChunk(socket, jsonMsg, binaryMsg); break;
        case 'FILE_DOWNLOAD_REQUEST': processFileDownloadRequest(socket, jsonMsg); break;
        case 'KICK_USER': processKickUser(socket, jsonMsg); break;
        case 'CANCEL_JOIN_REQUEST': processCancelJoinRequest(socket); break;
        case 'GET_MY_ROOMS': processGetMyRooms(socket); break;
        case 'CAMERA_FRAME': processCameraFrame(socket, jsonMsg, binaryMsg); break;
        case 'CAMERA_TOGGLE': processCameraToggle(socket, jsonMsg); break;
        case 'DELETE_ROOM': processDeleteRoom(socket, jsonMsg); break;        
        default: console.warn(`Tipo de mensaje no admitido: ${jsonMsg.type}`);
    }
}

// Procesa el inicio de sesión del usuario
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

// Regristo de nuevo usuario en el sistema
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

// Crea una sala nueva o reactiva una sala existente
function processCreateRoom(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.userId) return;

    const { codigoSala, nombre } = jsonMsg, existing = db.obtenerSalaPorCodigo(codigoSala);
    if (existing.success && existing.sala) {
        if (existing.sala.IdHost !== session.userId) {
            return sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'Código ocupado por otro usuario.' });
        }
        if (hostByRoom.has(codigoSala)) return sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'Sala activa en otra sesión.' });

        activeRooms.set(codigoSala, new Set([socket]));
        if (!waitingRooms.has(codigoSala)) waitingRooms.set(codigoSala, []);
        hostByRoom.set(codigoSala, socket);
        session.currentRoom = codigoSala;

        const chatHistory = db.obtenerMensajesPorSala(existing.sala.IdSala).mensajes || [];
        const fileHistory = db.obtenerArchivosPorSala(existing.sala.IdSala).archivos || [];

        sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: true, message: 'Sala reabierta.', codigoSala, nombreSala: nombre, chatHistory, fileHistory });
        
        const pending = waitingRooms.get(codigoSala) || [];
        if (pending.length > 0) sendFramedMessage(socket, { type: 'WAITING_ROOM_UPDATE', usuariosPendientes: pending.map(u => ({ id: u.userId, nombre: u.userName })) });
        
        return broadcastParticipantsUpdate(codigoSala);
    }

    const result = db.crearSala(codigoSala, nombre, session.userId);
    if (!result.success) {
        sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'Error al crear la sala.' });
    } else {
        activeRooms.set(codigoSala, new Set([socket]));
        waitingRooms.set(codigoSala, []);
        hostByRoom.set(codigoSala, socket);
        session.currentRoom = codigoSala;
        sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: true, message: 'Sala creada.', codigoSala, nombreSala: nombre, chatHistory: [], fileHistory: [] });
    }
}

// Retorna las salas de las cuales el usuario es dueño (Host)
function processGetMyRooms(socket) {
    const session = socketSessions.get(socket);
    if (!session?.userId) return;
    const res = db.obtenerSalasPorHost(session.userId);
    sendFramedMessage(socket, { type: 'MY_ROOMS_RESPONSE', success: res.success, salas: res.salas, message: res.error });
}

// Gestiona la solicitud de un usuario invitado para unirse a una sala (lo sitúa en sala de espera)
function processJoinRoomRequest(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.userId) return;

    const { codigoSala } = jsonMsg, resSala = db.obtenerSalaPorCodigo(codigoSala);
    if (!resSala.success || !resSala.sala) return sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: false, message: 'Sala inexistente o inactiva.' });

    const resSol = db.registrarSolicitud(resSala.sala.IdSala, session.userId);
    if (!resSol.success) {
        sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: false, message: 'Error al registrar solicitud.' });
    } else {
        sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: true, estado: 'Pendiente' });
        const waitingList = waitingRooms.get(codigoSala) || [];
        waitingList.push({ userId: session.userId, socket, userName: session.userName });
        waitingRooms.set(codigoSala, waitingList);

        const hostSocket = hostByRoom.get(codigoSala);
        if (hostSocket && !hostSocket.destroyed) {
            sendFramedMessage(hostSocket, { type: 'WAITING_ROOM_UPDATE', usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName })) });
        }
    }
}

// Permite a un usuario cancelar su solicitud de espera antes de ser admitido
function processCancelJoinRequest(socket) {
    const session = socketSessions.get(socket);
    if (!session?.userId) return;

    for (const [roomCode, waitingList] of waitingRooms.entries()) {
        const index = waitingList.findIndex(u => u.socket === socket);
        if (index !== -1) {
            waitingList.splice(index, 1);
            const hostSocket = hostByRoom.get(roomCode);
            if (hostSocket && !hostSocket.destroyed) {
                sendFramedMessage(hostSocket, { type: 'WAITING_ROOM_UPDATE', usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName })) });
            }
        }
    }
}

// El anfitrión admite o rechaza a un usuario en espera
function processAdmitUser(socket, jsonMsg) {
    const { codigoSala, userIdToAdmit, accept } = jsonMsg;
    if (hostByRoom.get(codigoSala) !== socket) return;

    const waitingList = waitingRooms.get(codigoSala);
    if (!waitingList) return;

    const index = waitingList.findIndex(u => u.userId === userIdToAdmit);
    if (index === -1) return;

    const { socket: targetSocket, userName: targetName } = waitingList.splice(index, 1)[0];
    const guestSession = socketSessions.get(targetSocket);

    if (accept) {
        const roomSockets = activeRooms.get(codigoSala);
        if (roomSockets) roomSockets.add(targetSocket);
        if (guestSession) guestSession.currentRoom = codigoSala;

        const room = db.obtenerSalaPorCodigo(codigoSala).sala;
        const chatHistory = room ? (db.obtenerMensajesPorSala(room.IdSala).mensajes || []) : [];
        const fileHistory = room ? (db.obtenerArchivosPorSala(room.IdSala).archivos || []) : [];

        sendFramedMessage(targetSocket, { type: 'ADMIT_RESULT', success: true, codigoSala, chatHistory, fileHistory });
        
        const systemMsg = { type: 'CHAT_MESSAGE', userId: 0, userName: 'Sistema', message: `${targetName} se ha unido.`, sentAt: new Date().toISOString() };
        if (roomSockets) {
            for (const s of roomSockets) sendFramedMessage(s, systemMsg);
        }
        broadcastParticipantsUpdate(codigoSala);
    } else {
        sendFramedMessage(targetSocket, { type: 'ADMIT_RESULT', success: false, message: "El anfitrión ha rechazado tu solicitud." });
    }

    sendFramedMessage(socket, { type: 'WAITING_ROOM_UPDATE', usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName })) });
}

// Envía y retransmite un mensaje de chat a todos los miembros de la sala
function processChatMessage(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    const roomCode = session.currentRoom, room = db.obtenerSalaPorCodigo(roomCode).sala;
    if (!room) return;

    if (db.guardarMensaje(room.IdSala, session.userId, jsonMsg.message).success) {
        const chatMsg = { type: 'CHAT_MESSAGE', userId: session.userId, userName: session.userName, message: jsonMsg.message, sentAt: new Date().toISOString() };
        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            for (const s of roomSockets) sendFramedMessage(s, chatMsg);
        }
    }
}

// Maneja la salida voluntaria de un usuario de una sala
function processLeaveRoom(socket) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    if (session.upload?.fileStream) {
        session.upload.fileStream.destroy();
        session.upload = null;
    }

    const roomCode = session.currentRoom, isHost = hostByRoom.get(roomCode) === socket;

    if (isHost) {
        console.log(`Cerrando sala ${roomCode} por salida del host.`);
        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            for (const s of roomSockets) {
                if (s !== socket && !s.destroyed) {
                    sendFramedMessage(s, { type: 'ROOM_CLOSED', message: 'El anfitrión cerró la sala.' });
                    if (socketSessions.get(s)) socketSessions.get(s).currentRoom = null;
                }
            }
        }
        activeRooms.delete(roomCode);
        waitingRooms.delete(roomCode);
        hostByRoom.delete(roomCode);
    } else {
        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            const systemMsg = { type: 'CHAT_MESSAGE', userId: 0, userName: 'Sistema', message: `${session.userName} ha salido.`, sentAt: new Date().toISOString() };
            for (const s of roomSockets) {
                if (s !== socket && !s.destroyed) sendFramedMessage(s, systemMsg);
            }
            roomSockets.delete(socket);
            broadcastParticipantsUpdate(roomCode);
        }
    }
    session.currentRoom = null;
}

// Procesa la subida incremental de fragmentos binarios de archivos (File Transfer)
function processFileChunk(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    const { fileName, chunkIndex, isLast } = jsonMsg;

    if (chunkIndex === 0) {
        const safeName = `${Date.now()}_${path.basename(fileName)}`, filePath = path.join(UPLOADS_DIR, safeName);
        session.upload = { fileName, safeName, filePath, fileStream: fs.createWriteStream(filePath), expectedChunk: 0 };
    }

    const upload = session.upload;
    if (!upload) return sendFramedMessage(socket, { type: 'FILE_UPLOAD_ERROR', message: 'Falta inicialización.' });
    if (chunkIndex !== upload.expectedChunk) return sendFramedMessage(socket, { type: 'FILE_UPLOAD_ERROR', message: 'Fragmento fuera de orden.' });

    if (binaryMsg?.length > 0) upload.fileStream.write(binaryMsg);
    upload.expectedChunk++;

    if (isLast) {
        upload.fileStream.end();
        const roomCode = session.currentRoom, room = db.obtenerSalaPorCodigo(roomCode).sala;
        if (room && db.guardarArchivoCompartido(room.IdSala, session.userId, upload.fileName, upload.safeName).success) {
            const fileMsg = { type: 'FILE_SHARED', fileId: db.guardarArchivoCompartido(room.IdSala, session.userId, upload.fileName, upload.safeName).idArchivo || Date.now(), fileName: upload.fileName, senderName: session.userName, sentAt: new Date().toISOString() };
            const systemMsg = { type: 'CHAT_MESSAGE', userId: 0, userName: 'Sistema', message: `${session.userName} compartió "${upload.fileName}".`, sentAt: new Date().toISOString() };
            const roomSockets = activeRooms.get(roomCode);
            if (roomSockets) {
                for (const s of roomSockets) { sendFramedMessage(s, fileMsg); sendFramedMessage(s, systemMsg); }
            }
        }
        session.upload = null;
    }
}

// Lee un archivo almacenado en el disco del servidor y lo transmite en fragmentos al cliente que solicitó la descarga
function processFileDownloadRequest(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    const { fileId } = jsonMsg, dbRes = db.obtenerArchivoPorId(fileId);
    if (!dbRes.success || !dbRes.archivo) return sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId, message: 'Archivo no encontrado.' });

    const filePath = path.join(UPLOADS_DIR, dbRes.archivo.RutaArchivo);
    if (!fs.existsSync(filePath)) return sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId, message: 'El archivo físico no existe.' });

    const fileSize = fs.statSync(filePath).size;
    sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_START', fileId, fileName: dbRes.archivo.NombreArchivo, fileSize });

    const readStream = fs.createReadStream(filePath, { highWaterMark: 16 * 1024 });
    let chunkIndex = 0;

    readStream.on('data', (chunk) => {
        readStream.pause();
        sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_CHUNK', fileId, chunkIndex: chunkIndex++, isLast: false }, chunk);
        readStream.resume();
    });

    readStream.on('end', () => sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_CHUNK', fileId, chunkIndex, isLast: true }));
    readStream.on('error', (err) => sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId, message: 'Error de lectura.' }));
}

// Distribuye de forma instantánea el frame binario de la cámara web a todos los participantes activos de la sala
function processCameraFrame(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    const roomSockets = activeRooms.get(session.currentRoom);
    if (roomSockets && binaryMsg) {
        const msg = { type: 'CAMERA_FRAME', userId: session.userId, userName: session.userName };
        for (const s of roomSockets) {
            if (s !== socket && !s.destroyed) sendFramedMessage(s, msg, binaryMsg);
        }
    }
}

// Notifica si un usuario encendió o apagó su cámara para actualizar la GUI de otros
function processCameraToggle(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;
    const roomSockets = activeRooms.get(session.currentRoom);
    if (roomSockets) {
        const msg = { type: 'CAMERA_TOGGLE', userId: session.userId, state: jsonMsg.state };
        for (const s of roomSockets) {
            if (s !== socket && !s.destroyed) sendFramedMessage(s, msg);
        }
    }
}

// Recopila y difunde la lista completa de participantes activos de una sala
function broadcastParticipantsUpdate(roomCode) {
    const roomSockets = activeRooms.get(roomCode);
    if (!roomSockets) return;
    
    const hostSocket = hostByRoom.get(roomCode), participants = [];
    for (const s of roomSockets) {
        const session = socketSessions.get(s);
        if (session?.userId) participants.push({ id: session.userId, nombre: session.userName, isHost: s === hostSocket });
    }
    for (const s of roomSockets) {
        if (!s.destroyed) sendFramedMessage(s, { type: 'PARTICIPANTS_UPDATE', users: participants });
    }
}

// Permite al anfitrión forzar la salida (Expulsar) de un participante de la sala
function processKickUser(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.currentRoom) return;

    const roomCode = session.currentRoom;
    if (hostByRoom.get(roomCode) !== socket) return;

    const { userIdToKick } = jsonMsg, roomSockets = activeRooms.get(roomCode);
    if (!roomSockets) return;

    let targetSocket = null;
    for (const s of roomSockets) {
        if (socketSessions.get(s)?.userId === userIdToKick) { targetSocket = s; break; }
    }

    if (targetSocket) {
        const targetSession = socketSessions.get(targetSocket);
        sendFramedMessage(targetSocket, { type: 'KICKED', message: 'Expulsado por el anfitrión.' });
        roomSockets.delete(targetSocket);
        targetSession.currentRoom = null;

        const systemMsg = { type: 'CHAT_MESSAGE', userId: 0, userName: 'Sistema', message: `${targetSession.userName} ha sido expulsado.`, sentAt: new Date().toISOString() };
        for (const s of roomSockets) {
            if (!s.destroyed) sendFramedMessage(s, systemMsg);
        }
        broadcastParticipantsUpdate(roomCode);
    }
}

// Elimina lógicamente una sala si no está activa
function processDeleteRoom(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session?.userId) return;

    const { codigoSala } = jsonMsg;
    if (activeRooms.has(codigoSala)) return sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: false, message: 'Sala en curso.' });

    const res = db.eliminarSala(codigoSala, session.userId);
    sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: res.success, codigoSala, message: res.success ? null : 'Error o sin permisos.' });
}

// Manejo de la desconexión abrupta o accidental de un socket TCP
function handleDisconnect(socket) {
    const session = socketSessions.get(socket);
    if (!session) return;

    if (session.upload?.fileStream) {
        session.upload.fileStream.destroy();
        session.upload = null;
    }

    for (const [roomCode, waitingList] of waitingRooms.entries()) {
        const index = waitingList.findIndex(u => u.socket === socket);
        if (index !== -1) {
            waitingList.splice(index, 1);
            const hostSocket = hostByRoom.get(roomCode);
            if (hostSocket && !hostSocket.destroyed) {
                sendFramedMessage(hostSocket, { type: 'WAITING_ROOM_UPDATE', usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName })) });
            }
        }
    }

    if (session.currentRoom) {
        const roomCode = session.currentRoom, isHost = hostByRoom.get(roomCode) === socket;
        if (isHost) {
            console.log(`Anfitrión desconectado. Cerrando sala ${roomCode}`);
            const roomSockets = activeRooms.get(roomCode);
            if (roomSockets) {
                for (const s of roomSockets) {
                    if (s !== socket && !s.destroyed) {
                        sendFramedMessage(s, { type: 'ROOM_CLOSED', message: 'Anfitrión desconectado. Sala cerrada.' });
                        if (socketSessions.get(s)) socketSessions.get(s).currentRoom = null;
                    }
                }
            }
            activeRooms.delete(roomCode);
            waitingRooms.delete(roomCode);
            hostByRoom.delete(roomCode);
        } else {
            const roomSockets = activeRooms.get(roomCode);
            if (roomSockets) {
                roomSockets.delete(socket);
                const systemMsg = { type: 'CHAT_MESSAGE', userId: 0, userName: 'Sistema', message: `${session.userName} se ha desconectado.`, sentAt: new Date().toISOString() };
                for (const s of roomSockets) { if (!s.destroyed) sendFramedMessage(s, systemMsg); }
            }
        }
    }
    socketSessions.delete(socket);
}

// Manejo General de Errores e Inicio
server.on('error', (err) => {
    console.error(err.code === 'EADDRINUSE' ? `Puerto ${PORT} ocupado.` : `Error: ${err.message}`);
    process.exit(1);
});

server.listen(PORT, HOST, () => {
    console.log(`SERVIDOR DE SOCKETS INICIADO\nPuerto: ${PORT}\nHOST: ${HOST}`);
});
