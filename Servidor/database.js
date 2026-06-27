// Patrón Facade (Fachada): database.js unifica y simplifica el acceso a SQLite para el resto de la aplicación
const { DatabaseSync } = require('node:sqlite');
const path = require('path'), fs = require('fs'), crypto = require('crypto');

// Configuración de Rutas de Archivos
const dbPath = path.join(__dirname, '../BaseDatos/videoconferencia.db');
const schemaPath = path.join(__dirname, '../BaseDatos/schema.sql'), seedPath = path.join(__dirname, '../BaseDatos/seed.sql');

// Crear el directorio de la base de datos si no existe e inicializar SQLite
const dbDir = path.dirname(dbPath);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

// Patrón Singleton (a nivel de módulo): Node.js almacena en caché las importaciones de este archivo,
// garantizando que todos los controladores compartan exactamente esta misma instancia de conexión a la base de datos.
const db = new DatabaseSync(dbPath);

// Inicializa base de datos con esquema y datos de prueba si la tabla Usuarios no existe
if (!db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='Usuarios'").get()) {
    console.log("Inicializando base de datos...");
    if (fs.existsSync(schemaPath)) db.exec(fs.readFileSync(schemaPath, 'utf8'));
    if (fs.existsSync(seedPath)) db.exec(fs.readFileSync(seedPath, 'utf8'));
} else {
    console.log("Base de datos conectada correctamente.");
}

// Genera un hash seguro para almacenar contraseñas utilizando PBKDF2 ("salt:hashHex")
function hashPassword(password) {
    const salt = crypto.randomBytes(16).toString('hex');
    return `${salt}:${crypto.pbkdf2Sync(password, salt, 1000, 64, 'sha512').toString('hex')}`;
}

// Verifica si la contraseña coincide con el hash guardado en formato "salt:hashHex"
function verifyPassword(password, storedHash) {
    if (!storedHash || !storedHash.includes(':')) return false;
    const [salt, originalHash] = storedHash.split(':');
    const hash = crypto.pbkdf2Sync(password, salt, 1000, 64, 'sha512').toString('hex');
    const bHash = Buffer.from(hash, 'hex'), bOriginal = Buffer.from(originalHash, 'hex');
    return bHash.length === bOriginal.length && crypto.timingSafeEqual(bHash, bOriginal);
}

// Busca un usuario registrado por su correo electrónico
const getUserByCorreo = (correo) => db.prepare('SELECT * FROM Usuarios WHERE Correo = ?').get(correo);

// Registra un nuevo usuario en la base de datos con contraseña cifrada
function createUser(nombres, correo, password) {
    try {
        const res = db.prepare('INSERT INTO Usuarios (Nombres, Correo, PasswordHash) VALUES (?, ?, ?)').run(nombres, correo, hashPassword(password));
        return { success: true, userId: Number(res.lastInsertRowid) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Crea una nueva sala de videoconferencia en la base de datos
function crearSala(codigoSala, nombre, idHost) {
    try {
        const res = db.prepare(`INSERT INTO Salas (CodigoSala, Nombre, IdHost, Estado) VALUES (?, ?, ?, 'Activa')`).run(codigoSala, nombre, idHost);
        return { success: true, idSala: Number(res.lastInsertRowid) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Busca una sala activa por su código único de acceso
function obtenerSalaPorCodigo(codigoSala) {
    try {
        return { success: true, sala: db.prepare(`SELECT IdSala, IdHost FROM Salas WHERE CodigoSala = ? AND Estado = 'Activa'`).get(codigoSala) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Registra una solicitud de ingreso (sala de espera) de un participante a una sala
function registrarSolicitud(idSala, idUsuario) {
    try {
        const res = db.prepare(`INSERT INTO SolicitudesSala (IdSala, IdUsuario, Estado) VALUES (?, ?, 'Pendiente')`).run(idSala, idUsuario);
        return { success: true, idSolicitud: Number(res.lastInsertRowid) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Retorna la lista de salas activas creadas por un usuario (anfitrión)
function obtenerSalasPorHost(idHost) {
    try {
        return { success: true, salas: db.prepare(`SELECT CodigoSala, Nombre, Estado FROM Salas WHERE IdHost = ? AND Estado != 'Eliminada'`).all(idHost) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Realiza un borrado lógico de una sala cambiando su estado a 'Eliminada'
function eliminarSala(codigoSala, idHost) {
    try {
        const res = db.prepare(`UPDATE Salas SET Estado = 'Eliminada' WHERE CodigoSala = ? AND IdHost = ?`).run(codigoSala, idHost);
        return { success: res.changes > 0 };
    } catch (err) { return { success: false, error: err.message }; }
}

// Guarda un mensaje del chat enviado dentro de una sala
function guardarMensaje(idSala, idUsuario, contenido) {
    try {
        const res = db.prepare("INSERT INTO Mensajes (IdSala, IdUsuario, Contenido, FechaEnvio) VALUES (?, ?, ?, datetime('now', 'localtime'))").run(idSala, idUsuario, contenido);
        return { success: true, idMensaje: Number(res.lastInsertRowid) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Recupera el historial de mensajes de chat de una sala en orden cronológico
function obtenerMensajesPorSala(idSala) {
    try {
        return { success: true, mensajes: db.prepare(`SELECT m.IdMensaje, m.IdUsuario, u.Nombres as userName, m.Contenido, m.FechaEnvio FROM Mensajes m JOIN Usuarios u ON m.IdUsuario = u.IdUsuario WHERE m.IdSala = ? ORDER BY m.FechaEnvio ASC`).all(idSala) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Registra un archivo subido en una reunión
function guardarArchivoCompartido(idSala, idUsuario, nombreArchivo, rutaArchivo) {
    try {
        const res = db.prepare('INSERT INTO ArchivosCompartidos (IdSala, IdUsuario, NombreArchivo, RutaArchivo) VALUES (?, ?, ?, ?)').run(idSala, idUsuario, nombreArchivo, rutaArchivo);
        return { success: true, idArchivo: Number(res.lastInsertRowid) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Obtiene la lista de archivos que se han compartido en una sala
function obtenerArchivosPorSala(idSala) {
    try {
        return { success: true, archivos: db.prepare(`SELECT a.IdArchivo, a.IdUsuario, u.Nombres as userName, a.NombreArchivo, a.FechaEnvio FROM ArchivosCompartidos a JOIN Usuarios u ON a.IdUsuario = u.IdUsuario WHERE a.IdSala = ? ORDER BY a.FechaEnvio ASC`).all(idSala) };
    } catch (err) { return { success: false, error: err.message }; }
}

// Obtiene la información detallada (incluyendo la ruta física) de un archivo específico por su ID
function obtenerArchivoPorId(idArchivo) {
    try {
        return { success: true, archivo: db.prepare('SELECT IdArchivo, IdSala, IdUsuario, NombreArchivo, RutaArchivo FROM ArchivosCompartidos WHERE IdArchivo = ?').get(idArchivo) };
    } catch (err) { return { success: false, error: err.message }; }
}

module.exports = {
    hashPassword, verifyPassword, getUserByCorreo, createUser, crearSala, obtenerSalaPorCodigo,
    registrarSolicitud, guardarMensaje, obtenerMensajesPorSala, obtenerSalasPorHost,
    guardarArchivoCompartido, obtenerArchivosPorSala, obtenerArchivoPorId, eliminarSala
};
