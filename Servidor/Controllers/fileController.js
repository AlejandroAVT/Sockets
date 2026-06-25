const fs = require('fs');
const path = require('path');

module.exports = function(dependencies) {
    const { db, socketSessions, activeRooms, sendFramedMessage, UPLOADS_DIR } = dependencies;

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

    return { processFileChunk, processFileDownloadRequest };
};