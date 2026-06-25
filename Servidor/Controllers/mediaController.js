module.exports = function(dependencies) {
    const { db, activeRooms, socketSessions, sendFramedMessage } = dependencies;

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

    return { processChatMessage, processCameraFrame, processCameraToggle };
};