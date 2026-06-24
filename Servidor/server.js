const net = require('net');
const db = require('./database');
const fs = require('fs');
const path = require('path');

const PORT = 8080;
const HOST = '0.0.0.0';
const UPLOADS_DIR = path.join(__dirname, 'uploads');

if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}
const MAX_FRAME_SIZE = 10 * 1024 * 1024; // Límite de 10 MB por mensaje
const SOCKET_TIMEOUT = 120000; // 2 minutos de inactividad máxima

const activeRooms = new Map(); 
const waitingRooms = new Map(); 
const hostByRoom = new Map(); 
const socketSessions = new Map();

const server = net.createServer((socket) => {
    const clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Nuevo cliente conectado desde: ${clientAddress}`);

    socketSessions.set(socket, {
        userId: null,
        userName: null,
        correo: null
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
                console.error(`Error: Trama de ${clientAddress} excede el tamaño máximo permitido (${totalFrameLen} bytes). Cerrando conexión.`);
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
        handleDisconnect(socket);
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
        case 'CREATE_ROOM': 
            processCreateRoom(socket, jsonMsg);
            break;
        case 'JOIN_ROOM_REQUEST': 
            processJoinRoomRequest(socket, jsonMsg);
            break;
        case 'ADMIT_USER': 
            processAdmitUser(socket, jsonMsg);
            break;
        case 'CHAT_MESSAGE':
            processChatMessage(socket, jsonMsg);
            break;
        case 'LEAVE_ROOM':
            processLeaveRoom(socket);
            break;
        case 'FILE_CHUNK':
            processFileChunk(socket, jsonMsg, binaryMsg);
            break;
        case 'FILE_DOWNLOAD_REQUEST':
            processFileDownloadRequest(socket, jsonMsg);
            break;
        case 'KICK_USER':
            processKickUser(socket, jsonMsg);
            break;
        case 'CANCEL_JOIN_REQUEST':
            processCancelJoinRequest(socket);
            break;
        case 'GET_MY_ROOMS':
            processGetMyRooms(socket);
            break;
        case 'CAMERA_FRAME':
            processCameraFrame(socket, jsonMsg, binaryMsg);
            break;
        case 'CAMERA_TOGGLE':
            processCameraToggle(socket, jsonMsg);
            break;
        case 'DELETE_ROOM':
            processDeleteRoom(socket, jsonMsg);
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

        sendFramedMessage(socket, {
            type: 'LOGIN_RESPONSE',
            success: true,
            usuario: {
                id: user.IdUsuario,
                nombres: user.Nombres,
                correo: user.Correo
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

    const result = db.createUser(nombres, correo, password);
    if (result.success) {
        sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: true, message: 'Usuario registrado exitosamente.' });
        console.log(`Nuevo usuario registrado: ${nombres} (${correo})`);
    } else {
        sendFramedMessage(socket, { type: 'REGISTER_RESPONSE', success: false, message: 'Error en BD: ' + result.error });
    }
}

function processCreateRoom(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId) return;

    const { codigoSala, nombre } = jsonMsg;

    // Verificar si la sala ya existe en la base de datos
    const existing = db.obtenerSalaPorCodigo(codigoSala);
    if (existing.success && existing.sala) {
        if (existing.sala.IdHost === session.userId) {
            if (hostByRoom.has(codigoSala)) {
                sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'La sala ya está activa en otra sesión.' });
                return;
            }

            activeRooms.set(codigoSala, new Set([socket]));
            if (!waitingRooms.has(codigoSala)) {
                waitingRooms.set(codigoSala, []);
            }
            hostByRoom.set(codigoSala, socket);
            session.currentRoom = codigoSala;

            const historyRes = db.obtenerMensajesPorSala(existing.sala.IdSala);
            const chatHistory = historyRes.success ? historyRes.mensajes : [];
            const filesRes = db.obtenerArchivosPorSala(existing.sala.IdSala);
            const fileHistory = filesRes.success ? filesRes.archivos : [];

            sendFramedMessage(socket, { 
                type: 'CREATE_ROOM_RESPONSE', 
                success: true, 
                message: 'Sala reabierta con éxito.', 
                codigoSala: codigoSala, 
                nombreSala: nombre,
                chatHistory: chatHistory, // Enviamos el chat
                fileHistory: fileHistory  // Enviamos los archivos
            });
            console.log(`Sala existente ${codigoSala} reabierta por su host ${session.userName}`);
            
            // CORRECCIÓN: Avisar inmediatamente al host si ya había gente esperando
            const pendingList = waitingRooms.get(codigoSala);
            if (pendingList && pendingList.length > 0) {
                sendFramedMessage(socket, {
                    type: 'WAITING_ROOM_UPDATE',
                    usuariosPendientes: pendingList.map(u => ({ id: u.userId, nombre: u.userName }))
                });
            }

            broadcastParticipantsUpdate(codigoSala);
            return;
        } else {
            sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'El código de sala ya existe y pertenece a otro usuario.' });
            return;
        }
    }

    const result = db.crearSala(codigoSala, nombre, session.userId);
    
    if (!result.success) {
        sendFramedMessage(socket, { type: 'CREATE_ROOM_RESPONSE', success: false, message: 'Error al crear sala o el código ya existe.' });
    } else {
        activeRooms.set(codigoSala, new Set([socket]));
        waitingRooms.set(codigoSala, []);
        hostByRoom.set(codigoSala, socket);
        session.currentRoom = codigoSala;

        sendFramedMessage(socket, { 
            type: 'CREATE_ROOM_RESPONSE', 
            success: true, 
            message: 'Sala creada con éxito.', 
            codigoSala: codigoSala, 
            nombreSala: nombre,
            chatHistory: [],
            fileHistory: []
        });
        console.log(`Sala ${codigoSala} creada por ${session.userName}`);
    }
}

function processGetMyRooms(socket) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId) return;

    const result = db.obtenerSalasPorHost(session.userId);
    if (result.success) {
        sendFramedMessage(socket, {
            type: 'MY_ROOMS_RESPONSE',
            success: true,
            salas: result.salas
        });
    } else {
        sendFramedMessage(socket, {
            type: 'MY_ROOMS_RESPONSE',
            success: false,
            message: 'Error al obtener tus salas: ' + result.error
        });
    }
}

function processJoinRoomRequest(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId) return;

    const { codigoSala } = jsonMsg;

    const resultSala = db.obtenerSalaPorCodigo(codigoSala);
    
    if (!resultSala.success || !resultSala.sala) {
        sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: false, message: 'La sala no existe o no está activa.' });
        return;
    }

    const resultSol = db.registrarSolicitud(resultSala.sala.IdSala, session.userId);
    
    if (!resultSol.success) {
        sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: false, message: 'Error al registrar la solicitud.' });
    } else {
        sendFramedMessage(socket, { type: 'JOIN_ROOM_RESPONSE', success: true, estado: 'Pendiente' });
        
        const waitingList = waitingRooms.get(codigoSala) || [];
        waitingList.push({ userId: session.userId, socket: socket, userName: session.userName });
        waitingRooms.set(codigoSala, waitingList);

        const hostSocket = hostByRoom.get(codigoSala);
        if (hostSocket && !hostSocket.destroyed) {
            sendFramedMessage(hostSocket, {
                type: 'WAITING_ROOM_UPDATE',
                usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName }))
            });
        }
    }
}

function processCancelJoinRequest(socket) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId) return;

    for (const [roomCode, waitingList] of waitingRooms.entries()) {
        const index = waitingList.findIndex(u => u.socket === socket);
        if (index !== -1) {
            waitingList.splice(index, 1);
            console.log(`Usuario en espera ${session.userName || socket.remoteAddress} canceló su solicitud para la sala ${roomCode}`);
            
            const hostSocket = hostByRoom.get(roomCode);
            if (hostSocket && !hostSocket.destroyed) {
                sendFramedMessage(hostSocket, {
                    type: 'WAITING_ROOM_UPDATE',
                    usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName }))
                });
            }
        }
    }
}

function processAdmitUser(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    const { codigoSala, userIdToAdmit, accept } = jsonMsg;

    if (hostByRoom.get(codigoSala) !== socket) {
         return; 
    }

    const waitingList = waitingRooms.get(codigoSala);
    if (!waitingList) return;

    const userIndex = waitingList.findIndex(u => u.userId === userIdToAdmit);
    if (userIndex === -1) return;

    const userToAdmit = waitingList.splice(userIndex, 1)[0]; 
    const targetSocket = userToAdmit.socket;

    if (accept) {
        const roomSockets = activeRooms.get(codigoSala);
        if (roomSockets) {
            roomSockets.add(targetSocket);
        }
        
        const guestSession = socketSessions.get(targetSocket);
        if (guestSession) guestSession.currentRoom = codigoSala;

        const roomRes = db.obtenerSalaPorCodigo(codigoSala);
        const room = roomRes.success ? roomRes.sala : null;
        let chatHistory = [];
        let fileHistory = [];
        if (room) {
            const historyRes = db.obtenerMensajesPorSala(room.IdSala);
            chatHistory = historyRes.success ? historyRes.mensajes : [];
            const filesRes = db.obtenerArchivosPorSala(room.IdSala);
            fileHistory = filesRes.success ? filesRes.archivos : [];
        }

        sendFramedMessage(targetSocket, { 
            type: 'ADMIT_RESULT', 
            success: true, 
            codigoSala: codigoSala,
            chatHistory: chatHistory,
            fileHistory: fileHistory
        });
        
        if (guestSession) {
            const systemMsg = {
                type: 'CHAT_MESSAGE',
                userId: 0,
                userName: 'Sistema',
                message: `${guestSession.userName} se ha unido a la reunión.`,
                sentAt: new Date().toISOString()
            };
            if (roomSockets) {
                for (const clientSocket of roomSockets) {
                    sendFramedMessage(clientSocket, systemMsg);
                }
            }
        }
        
        broadcastParticipantsUpdate(codigoSala);

    } else {
         sendFramedMessage(targetSocket, { type: 'ADMIT_RESULT', success: false, message: "El anfitrión ha rechazado tu solicitud." });
    }

    sendFramedMessage(socket, {
        type: 'WAITING_ROOM_UPDATE',
        usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName }))
    });
}

function processChatMessage(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId || !session.currentRoom) return;

    const roomCode = session.currentRoom;
    const roomRes = db.obtenerSalaPorCodigo(roomCode);
    if (!roomRes.success || !roomRes.sala) return;

    const saveRes = db.guardarMensaje(roomRes.sala.IdSala, session.userId, jsonMsg.message);
    if (saveRes.success) {
        const chatMsg = {
            type: 'CHAT_MESSAGE',
            userId: session.userId,
            userName: session.userName,
            message: jsonMsg.message,
            sentAt: new Date().toISOString()
        };

        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            for (const clientSocket of roomSockets) {
                sendFramedMessage(clientSocket, chatMsg);
            }
        }
        console.log(`Chat en sala ${roomCode} de ${session.userName}: ${jsonMsg.message}`);
    }
}

function processLeaveRoom(socket) {
    const session = socketSessions.get(socket);
    if (!session || !session.currentRoom) return;

    if (session.upload && session.upload.fileStream) {
        session.upload.fileStream.destroy();
        session.upload = null;
        console.log(`Subida de archivo cancelada para ${session.userName} al salir de la sala.`);
    }

    const roomCode = session.currentRoom;
    const isHost = hostByRoom.get(roomCode) === socket;

    if (isHost) {
        console.log(`Anfitrión ${session.userName} saliendo. Cerrando sala ${roomCode}`);
        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            for (const clientSocket of roomSockets) {
                if (clientSocket !== socket && !clientSocket.destroyed) {
                    sendFramedMessage(clientSocket, {
                        type: 'ROOM_CLOSED',
                        message: 'El anfitrión ha salido de la sala. Sala cerrada.'
                    });
                    const clientSession = socketSessions.get(clientSocket);
                    if (clientSession) clientSession.currentRoom = null;
                }
            }
        }
        activeRooms.delete(roomCode);
        waitingRooms.delete(roomCode);
        hostByRoom.delete(roomCode);
    } else {
        const roomSockets = activeRooms.get(roomCode);
        if (roomSockets) {
            const systemMsg = {
                type: 'CHAT_MESSAGE',
                userId: 0,
                userName: 'Sistema',
                message: `${session.userName} ha salido de la reunión.`,
                sentAt: new Date().toISOString()
            };
            for (const clientSocket of roomSockets) {
                if (clientSocket !== socket && !clientSocket.destroyed) {
                    sendFramedMessage(clientSocket, systemMsg);
                }
            }
            roomSockets.delete(socket);
            broadcastParticipantsUpdate(roomCode);
            console.log(`Invitado ${session.userName} salió de la sala ${roomCode}`);
        }
    }

    session.currentRoom = null;
}

function processFileChunk(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId || !session.currentRoom) return;

    const { fileName, chunkIndex, totalChunks, isLast } = jsonMsg;

    if (chunkIndex === 0) {
        const safeName = `${Date.now()}_${path.basename(fileName)}`;
        const filePath = path.join(UPLOADS_DIR, safeName);
        const fileStream = fs.createWriteStream(filePath);
        session.upload = {
            fileName: fileName,
            safeName: safeName,
            filePath: filePath,
            fileStream: fileStream,
            expectedChunk: 0
        };
    }

    const upload = session.upload;
    if (!upload) {
        sendFramedMessage(socket, { type: 'FILE_UPLOAD_ERROR', message: 'Falta inicialización de fragmentos.' });
        return;
    }

    if (chunkIndex !== upload.expectedChunk) {
        sendFramedMessage(socket, { type: 'FILE_UPLOAD_ERROR', message: 'Fragmento fuera de orden.' });
        return;
    }

    if (binaryMsg && binaryMsg.length > 0) {
        upload.fileStream.write(binaryMsg);
    }
    upload.expectedChunk++;

    if (isLast) {
        upload.fileStream.end();
        
        const roomCode = session.currentRoom;
        const roomRes = db.obtenerSalaPorCodigo(roomCode);
        if (roomRes.success && roomRes.sala) {
            const dbRes = db.guardarArchivoCompartido(roomRes.sala.IdSala, session.userId, upload.fileName, upload.safeName);
            if (dbRes.success) {
                const fileId = dbRes.idArchivo;
                const roomSockets = activeRooms.get(roomCode);
                
                const fileMsg = {
                    type: 'FILE_SHARED',
                    fileId: fileId,
                    fileName: upload.fileName,
                    senderName: session.userName,
                    sentAt: new Date().toISOString()
                };

                const systemMsg = {
                    type: 'CHAT_MESSAGE',
                    userId: 0,
                    userName: 'Sistema',
                    message: `${session.userName} ha compartido el archivo "${upload.fileName}".`,
                    sentAt: new Date().toISOString()
                };

                if (roomSockets) {
                    for (const clientSocket of roomSockets) {
                        sendFramedMessage(clientSocket, fileMsg);
                        sendFramedMessage(clientSocket, systemMsg);
                    }
                }
                console.log(`Archivo compartido en sala ${roomCode}: ${upload.fileName} por ${session.userName}`);
            }
        }
        session.upload = null;
    }
}

function processFileDownloadRequest(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.currentRoom) return;

    const { fileId } = jsonMsg;
    const dbRes = db.obtenerArchivoPorId(fileId);
    if (!dbRes.success || !dbRes.archivo) {
        sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId: fileId, message: 'Archivo no encontrado.' });
        return;
    }

    const archivo = dbRes.archivo;
    const filePath = path.join(UPLOADS_DIR, archivo.RutaArchivo);

    if (!fs.existsSync(filePath)) {
        sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId: fileId, message: 'El archivo físico no existe en el servidor.' });
        return;
    }

    const stats = fs.statSync(filePath);
    const fileSize = stats.size;

    sendFramedMessage(socket, {
        type: 'FILE_DOWNLOAD_START',
        fileId: fileId,
        fileName: archivo.NombreArchivo,
        fileSize: fileSize
    });

    const readStream = fs.createReadStream(filePath, { highWaterMark: 16 * 1024 });
    let chunkIndex = 0;

    readStream.on('data', (chunk) => {
        readStream.pause();
        
        sendFramedMessage(socket, {
            type: 'FILE_DOWNLOAD_CHUNK',
            fileId: fileId,
            chunkIndex: chunkIndex++,
            isLast: false
        }, chunk);
        
        readStream.resume();
    });

    readStream.on('end', () => {
        sendFramedMessage(socket, {
            type: 'FILE_DOWNLOAD_CHUNK',
            fileId: fileId,
            chunkIndex: chunkIndex,
            isLast: true
        });
        console.log(`Archivo enviado con éxito a ${session.userName}: ${archivo.NombreArchivo}`);
    });

    readStream.on('error', (err) => {
        console.error(`Error al leer archivo para descarga:`, err.message);
        sendFramedMessage(socket, { type: 'FILE_DOWNLOAD_ERROR', fileId: fileId, message: 'Error de lectura en el servidor.' });
    });
}

function processCameraFrame(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId || !session.currentRoom) return;

    const roomCode = session.currentRoom;
    const roomSockets = activeRooms.get(roomCode);

    if (roomSockets && binaryMsg) {
        const broadcastMsg = {
            type: 'CAMERA_FRAME',
            userId: session.userId,
            userName: session.userName
        };
        
        for (const clientSocket of roomSockets) {
            // Reenviamos a todos en la sala EXCEPTO al que lo envió
            if (clientSocket !== socket && !clientSocket.destroyed) {
                sendFramedMessage(clientSocket, broadcastMsg, binaryMsg);
            }
        }
    }
}

function broadcastParticipantsUpdate(roomCode) {
    const roomSockets = activeRooms.get(roomCode);
    if (!roomSockets) return;
    
    const hostSocket = hostByRoom.get(roomCode);
    const participants = [];
    for (const clientSocket of roomSockets) {
        const session = socketSessions.get(clientSocket);
        if (session && session.userId) {
            participants.push({ 
                id: session.userId, 
                nombre: session.userName,
                isHost: clientSocket === hostSocket
            });
        }
    }
    
    for (const clientSocket of roomSockets) {
        if (!clientSocket.destroyed) {
            sendFramedMessage(clientSocket, { type: 'PARTICIPANTS_UPDATE', users: participants });
        }
    }
}

function processKickUser(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.currentRoom) return;

    const roomCode = session.currentRoom;
    if (hostByRoom.get(roomCode) !== socket) {
        return; // Only host can kick!
    }

    const { userIdToKick } = jsonMsg;
    const roomSockets = activeRooms.get(roomCode);
    if (!roomSockets) return;

    let targetSocket = null;
    for (const clientSocket of roomSockets) {
        const clientSession = socketSessions.get(clientSocket);
        if (clientSession && clientSession.userId === userIdToKick) {
            targetSocket = clientSocket;
            break;
        }
    }

    if (targetSocket) {
        const targetSession = socketSessions.get(targetSocket);
        sendFramedMessage(targetSocket, {
            type: 'KICKED',
            message: 'Has sido expulsado de la reunión por el anfitrión.'
        });

        roomSockets.delete(targetSocket);
        targetSession.currentRoom = null;

        const systemMsg = {
            type: 'CHAT_MESSAGE',
            userId: 0,
            userName: 'Sistema',
            message: `${targetSession.userName} ha sido expulsado de la reunión.`,
            sentAt: new Date().toISOString()
        };

        for (const clientSocket of roomSockets) {
            if (!clientSocket.destroyed) {
                sendFramedMessage(clientSocket, systemMsg);
            }
        }
        
        console.log(`Usuario ${targetSession.userName} expulsado de la sala ${roomCode} por el anfitrión.`);
        broadcastParticipantsUpdate(roomCode);
    }
}

function processCameraToggle(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.currentRoom) return;
    const roomSockets = activeRooms.get(session.currentRoom);
    if (roomSockets) {
        const msg = { type: 'CAMERA_TOGGLE', userId: session.userId, state: jsonMsg.state };
        for (const clientSocket of roomSockets) {
            if (clientSocket !== socket && !clientSocket.destroyed) {
                sendFramedMessage(clientSocket, msg);
            }
        }
    }
}

function handleDisconnect(socket) {
    const session = socketSessions.get(socket);
    if (!session) return;

    if (session.upload && session.upload.fileStream) {
        session.upload.fileStream.destroy();
        session.upload = null;
        console.log(`Subida de archivo cancelada para ${session.userName} debido a desconexión.`);
    }

    // 1. Remove from waiting lists
    for (const [roomCode, waitingList] of waitingRooms.entries()) {
        const index = waitingList.findIndex(u => u.socket === socket);
        if (index !== -1) {
            waitingList.splice(index, 1);
            console.log(`Usuario en espera removido de la sala ${roomCode}`);
            // Notify host of the updated waiting room
            const hostSocket = hostByRoom.get(roomCode);
            if (hostSocket && !hostSocket.destroyed) {
                sendFramedMessage(hostSocket, {
                    type: 'WAITING_ROOM_UPDATE',
                    usuariosPendientes: waitingList.map(u => ({ id: u.userId, nombre: u.userName }))
                });
            }
        }
    }

    // 2. Remove from activeRooms / close room if host
    if (session.currentRoom) {
        const roomCode = session.currentRoom;
        const isHost = hostByRoom.get(roomCode) === socket;

        if (isHost) {
            console.log(`Anfitrión desconectado. Cerrando sala ${roomCode}`);
            const roomSockets = activeRooms.get(roomCode);
            if (roomSockets) {
                for (const clientSocket of roomSockets) {
                    if (clientSocket !== socket && !clientSocket.destroyed) {
                        sendFramedMessage(clientSocket, {
                            type: 'ROOM_CLOSED',
                            message: 'El anfitrión se ha desconectado. Sala cerrada.'
                        });
                        const clientSession = socketSessions.get(clientSocket);
                        if (clientSession) clientSession.currentRoom = null;
                    }
                }
            }
            activeRooms.delete(roomCode);
            waitingRooms.delete(roomCode);
            hostByRoom.delete(roomCode);
        } else {
            // It's a guest
            const roomSockets = activeRooms.get(roomCode);
            if (roomSockets) {
                roomSockets.delete(socket);
                console.log(`Invitado ${session.userName} removido de la sala ${roomCode}`);
                
                const systemMsg = {
                    type: 'CHAT_MESSAGE',
                    userId: 0,
                    userName: 'Sistema',
                    message: `${session.userName} se ha desconectado.`,
                    sentAt: new Date().toISOString()
                };
                for (const clientSocket of roomSockets) {
                    if (!clientSocket.destroyed) {
                        sendFramedMessage(clientSocket, systemMsg);
                    }
                }
            }
        }
    }

    socketSessions.delete(socket);
}

function processDeleteRoom(socket, jsonMsg) {
    const session = socketSessions.get(socket);
    if (!session || !session.userId) return;

    const { codigoSala } = jsonMsg;

    // Medida de seguridad: No dejar que eliminen una sala que está en curso
    if (activeRooms.has(codigoSala)) {
        sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: false, message: 'No puedes eliminar una sala que está en curso. Ingrésala y ciérrala primero.' });
        return;
    }

    const res = db.eliminarSala(codigoSala, session.userId);
    if (res.success) {
        sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: true, codigoSala: codigoSala });
        console.log(`El usuario ${session.userName} ha eliminado la sala ${codigoSala}`);
    } else {
        sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: false, message: 'Error al eliminar o no tienes permisos.' });
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
