module.exports = function(dependencies) {
    const { db, activeRooms, waitingRooms, hostByRoom, socketSessions, sendFramedMessage } = dependencies;

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

    function processGetMyRooms(socket) {
        const session = socketSessions.get(socket);
        if (!session?.userId) return;
        const res = db.obtenerSalasPorHost(session.userId);
        sendFramedMessage(socket, { type: 'MY_ROOMS_RESPONSE', success: res.success, salas: res.salas, message: res.error });
    }

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

    function processDeleteRoom(socket, jsonMsg) {
        const session = socketSessions.get(socket);
        if (!session?.userId) return;

        const { codigoSala } = jsonMsg;
        if (activeRooms.has(codigoSala)) return sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: false, message: 'Sala en curso.' });

        const res = db.eliminarSala(codigoSala, session.userId);
        sendFramedMessage(socket, { type: 'DELETE_ROOM_RESPONSE', success: res.success, codigoSala, message: res.success ? null : 'Error o sin permisos.' });
    }

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

    return { 
        processCreateRoom, processGetMyRooms, processJoinRoomRequest, 
        processCancelJoinRequest, processAdmitUser, processLeaveRoom, 
        processKickUser, processDeleteRoom 
    };
};