const net = require('net');

const PORT = 8080;
const HOST = '0.0.0.0';
const MAX_FRAME_SIZE = 10 * 1024 * 1024; // Límite de 10 MB por mensaje
const SOCKET_TIMEOUT = 120000; // 2 minutos de inactividad máxima

const connectedClients = new Set();

const server = net.createServer((socket) => {
    const clientAddress = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`Nuevo cliente conectado desde: ${clientAddress}`);
    connectedClients.add(socket);

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
                console.log(`Mensaje recibido de ${clientAddress}:`, jsonPayload);

                if (binaryPayload) {
                    console.log(`-> Se recibieron ${binaryPayload.length} bytes de datos binarios adjuntos.`);
                }
            } catch (err) {
                console.warn(`No se pudo parsear el buffer como JSON de ${clientAddress}:`, err.message);
            }

            buffer = buffer.subarray(totalFrameLen);
        }
    });

    socket.on('end', () => {
        console.log(`Cliente desconectado desde: ${clientAddress}`);
        connectedClients.delete(socket);
    });

    socket.on('error', (err) => {
        console.error(`Error de conexión de ${clientAddress}: ${err.message}`);
        connectedClients.delete(socket);
    });
});

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
