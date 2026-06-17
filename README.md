# Prototipo de Videoconferencia Tipo Zoom con Sockets

Este proyecto es un prototipo académico funcional de un sistema de videoconferencias similar a Zoom. Implementa comunicación de red mediante sockets, control de usuarios, persistencia en base de datos, chat, transferencia de archivos y transmisión básica de cámara (o simulación).

El sistema demuestra **interoperabilidad multilenguaje** en red:
- **Servidor**: Desarrollado en **Node.js** con base de datos SQLite y sockets TCP puros.
- **Cliente**: Desarrollado en **Python 3** con interfaz gráfica nativa mediante `customtkinter`, soporte de captura de cámara mediante OpenCV y comunicación TCP mediante hilos en segundo plano.

## Estructura del Proyecto

El repositorio está organizado en las siguientes carpetas:
- **`Servidor/`**: Servidor de sockets TCP en Node.js, lógica de negocio y persistencia en base de datos.
- **`Cliente/`**: Cliente de escritorio en Python, captura de cámara y renderizado de interfaz.
- **`BaseDatos/`**: Scripts de creación de base de datos (`schema.sql`) y datos iniciales de prueba (`seed.sql`).
- **`Documentacion/`**: Análisis, diseño, protocolo de comunicación e informe técnico.

## Tecnologías Utilizadas

### Servidor
- **Node.js (v24.14.0)**: Entorno de ejecución de servidor.
- **`net` (nativo)**: Sockets TCP de alto rendimiento.
- **`node:sqlite` (nativo)**: Base de datos SQLite integrada.
- **`crypto` (nativo)**: Cifrado y hashing de contraseñas.

### Cliente
- **Python (3.14+)**: Lenguaje del cliente.
- **`customtkinter`**: Interfaz de usuario moderna con soporte nativo de modo oscuro y alta resolución.
- **`opencv-python` (`cv2`)**: Captura de webcam y compresión de frames a JPG.
- **`Pillow` (`PIL`)**: Conversión y renderizado de imágenes en la GUI.
- **`socket` y `threading` (nativo)**: Comunicación en red concurrente sin congelar la interfaz.

---

Desarrollado para la materia de **Desarrollo de Software en Red**.
