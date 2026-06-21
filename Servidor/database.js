const { DatabaseSync } = require('node:sqlite');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const dbPath = path.join(__dirname, '../BaseDatos/videoconferencia.db');
const schemaPath = path.join(__dirname, '../BaseDatos/schema.sql');
const seedPath = path.join(__dirname, '../BaseDatos/seed.sql');

const dbDir = path.dirname(dbPath);
if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
}

const db = new DatabaseSync(dbPath);

const checkTable = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='Usuarios'");
const tableExists = checkTable.get();

if (!tableExists) {
    console.log("Inicializando base de datos...");
    if (fs.existsSync(schemaPath)) {
        const schema = fs.readFileSync(schemaPath, 'utf8');
        db.exec(schema);
        console.log("Esquema de base de datos cargado correctamente.");
    } else {
        console.error("No se encontró el archivo schema.sql en:", schemaPath);
    }

    if (fs.existsSync(seedPath)) {
        const seed = fs.readFileSync(seedPath, 'utf8');
        db.exec(seed);
        console.log("Datos de prueba cargados correctamente.");
    } else {
        console.error("No se encontró el archivo seed.sql en:", seedPath);
    }
} else {
    console.log("Base de datos conectada correctamente.");
}

function hashPassword(password) {
    const salt = crypto.randomBytes(16).toString('hex');
    const hash = crypto.pbkdf2Sync(password, salt, 1000, 64, 'sha512').toString('hex');
    return `${salt}:${hash}`;
}

function verifyPassword(password, storedHash) {
    if (!storedHash || !storedHash.includes(':')) return false;
    const [salt, originalHash] = storedHash.split(':');
    const hash = crypto.pbkdf2Sync(password, salt, 1000, 64, 'sha512').toString('hex');
    
    const bufferHash = Buffer.from(hash, 'hex');
    const bufferOriginal = Buffer.from(originalHash, 'hex');
    
    if (bufferHash.length !== bufferOriginal.length) return false;
    return crypto.timingSafeEqual(bufferHash, bufferOriginal);
}

function getUserByCorreo(correo) {
    const stmt = db.prepare('SELECT * FROM Usuarios WHERE Correo = ?');
    return stmt.get(correo);
}

function createUser(nombres, correo, password, rol = 'Usuario') {
    const hash = hashPassword(password);
    const stmt = db.prepare('INSERT INTO Usuarios (Nombres, Correo, PasswordHash, Rol) VALUES (?, ?, ?, ?)');
    try {
        const res = stmt.run(nombres, correo, hash, rol);
        return { success: true, userId: res.lastInsertRowid };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

function crearSala(codigoSala, nombre, idHost) {
    const stmt = db.prepare(`INSERT INTO Salas (CodigoSala, Nombre, IdHost, Estado) VALUES (?, ?, ?, 'Activa')`);
    try {
        const res = stmt.run(codigoSala, nombre, idHost);
        return { success: true, idSala: res.lastInsertRowid }; 
    } catch (err) {
        return { success: false, error: err.message };
    }
}

function obtenerSalaPorCodigo(codigoSala) {
    const stmt = db.prepare(`SELECT IdSala, IdHost FROM Salas WHERE CodigoSala = ? AND Estado = 'Activa'`);
    try {
        const row = stmt.get(codigoSala);
        return { success: true, sala: row }; 
    } catch (err) {
        return { success: false, error: err.message };
    }
}

function registrarSolicitud(idSala, idUsuario) {
    const stmt = db.prepare(`INSERT INTO SolicitudesSala (IdSala, IdUsuario, Estado) VALUES (?, ?, 'Pendiente')`);
    try {
        const res = stmt.run(idSala, idUsuario);
        return { success: true, idSolicitud: res.lastInsertRowid };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

module.exports = {
    hashPassword,
    verifyPassword,
    getUserByCorreo,
    createUser, 
    crearSala, 
    obtenerSalaPorCodigo, 
    registrarSolicitud
};
