const net = require('net');
const db = require('./database');
const fs = require('fs'), path = require('path');

// Configuración Global y Directorio de Archivos
const PORT = 8080, HOST = '0.0.0.0';
const UPLOADS_DIR = path.join(__dirname, 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const MAX_FRAME_SIZE = 10 * 1024 * 1024; // Límite máximo de trama: 10 MB
const SOCKET_TIMEOUT = 120000; // Inactividad máxima permitida: 2 minutos

// Estado en Memoria de Salas y Sesiones EXACTAMENTE COMO LO TENÍAS
const activeRooms = new Map();   
const waitingRooms = new Map();  
const hostByRoom = new Map();    
const socketSessions = new Map(); 

// --- INYECCIÓN DE TUS VARIABLES ORIGINALES A LOS MÓDULOS ---
const dependencias = { db, activeRooms, waitingRooms, hostByRoom, socketSessions, sendFramedMessage, UPLOADS_DIR };

const authController = require('./Controllers/authController')(dependencias);
const roomController = require('./Controllers/roomController')(dependencias);
const mediaController = require('./Controllers/mediaController')(dependencias);
const fileController = require('./Controllers/fileController')(dependencias);

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

    // Patrón Adapter (Adaptador): Convierte / acumula fragmentos TCP de bytes crudos a tramas estructuradas
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

// Envía un mensaje estructurado (JSON + Binario)
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

// Patrón Mediator (Mediador): Esta función y switch centralizan y enrutan todas las peticiones
// entrantes a los controladores correspondientes sin acoplar directamente el servidor con la lógica de negocio
function handleMessage(socket, jsonMsg, binaryMsg) {
    const session = socketSessions.get(socket), clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Mensaje recibido (${jsonMsg.type}) de ${session.userName || clientAddress}`);

    switch (jsonMsg.type) {
        case 'LOGIN_REQUEST': authController.processLogin(socket, jsonMsg); break;
        case 'REGISTER_REQUEST': authController.processRegister(socket, jsonMsg); break;
        case 'CREATE_ROOM': roomController.processCreateRoom(socket, jsonMsg); break;
        case 'JOIN_ROOM_REQUEST': roomController.processJoinRoomRequest(socket, jsonMsg); break;
        case 'ADMIT_USER': roomController.processAdmitUser(socket, jsonMsg); break;
        case 'CHAT_MESSAGE': mediaController.processChatMessage(socket, jsonMsg); break;
        case 'LEAVE_ROOM': roomController.processLeaveRoom(socket); break;
        case 'FILE_CHUNK': fileController.processFileChunk(socket, jsonMsg, binaryMsg); break;
        case 'FILE_DOWNLOAD_REQUEST': fileController.processFileDownloadRequest(socket, jsonMsg); break;
        case 'KICK_USER': roomController.processKickUser(socket, jsonMsg); break;
        case 'CANCEL_JOIN_REQUEST': roomController.processCancelJoinRequest(socket); break;
        case 'GET_MY_ROOMS': roomController.processGetMyRooms(socket); break;
        case 'CAMERA_FRAME': mediaController.processCameraFrame(socket, jsonMsg, binaryMsg); break;
        case 'CAMERA_TOGGLE': mediaController.processCameraToggle(socket, jsonMsg); break;
        case 'DELETE_ROOM': roomController.processDeleteRoom(socket, jsonMsg); break;        
        default: console.warn(`Tipo de mensaje no admitido: ${jsonMsg.type}`);
    }
}

// Manejo de la desconexión abrupta (LÓGICA ORIGINAL)
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