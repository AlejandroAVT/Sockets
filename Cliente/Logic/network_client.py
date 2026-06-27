import socket
import threading
import json
import struct

# Patrón Adapter (Adaptador): Adapta el flujo continuo de bytes TCP de sockets a tramas estructuradas (JSON + Binario)
class SocketsZoomClient:
    # Patrón Observer / Callback: Recibe funciones callback para notificar de forma desacoplada los eventos de red a la interfaz gráfica
    def __init__(self, host, port, on_message_callback, on_disconnect_callback):
        self.host, self.port = host, port
        self.on_message_callback, self.on_disconnect_callback = on_message_callback, on_disconnect_callback
        self.sock, self.connected, self.receive_thread = None, False, None
        self.write_lock = threading.Lock()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.connected = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            return True
        except Exception as e:
            if self.connected: print(f"[ERROR CONEXIÓN] {e}")
            return False

    def disconnect(self):
        self.connected = False
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None

    def send_message(self, json_obj, binary_data=None):
        if not self.connected or not self.sock: return False
        try:
            json_bytes = json.dumps(json_obj).encode('utf-8')
            bin_len = len(binary_data) if binary_data else 0
            header = struct.pack('>II', len(json_bytes), bin_len)
            with self.write_lock:
                self.sock.sendall(header)
                self.sock.sendall(json_bytes)
                if binary_data: self.sock.sendall(binary_data)
            return True
        except Exception as e:
            if self.connected: print(f"[ERROR ENVÍO] {e}")
            self.disconnect()
            self.on_disconnect_callback("Conexión perdida con el servidor.")
            return False

    def _receive_all(self, length):
        data = b''
        while len(data) < length:
            try:
                packet = self.sock.recv(length - len(data))
                if not packet: return None
                data += packet
            except Exception as e:
                if self.connected: print(f"[ERROR RECUPERAR PAQUETE] {e}")
                return None
        return data

    def _receive_loop(self):
        while self.connected:
            try:
                header = self._receive_all(8)
                if not header: break
                json_len, bin_len = struct.unpack('>II', header)
                json_bytes = self._receive_all(json_len)
                if not json_bytes: break
                json_obj = json.loads(json_bytes.decode('utf-8'))
                bin_data = self._receive_all(bin_len) if bin_len > 0 else None
                if bin_len > 0 and not bin_data: break
                self.on_message_callback(json_obj, bin_data)
            except Exception as e:
                if self.connected: print(f"[RECEIVE THREAD ERROR] {e}")
                break
        if self.connected:
            self.disconnect()
            self.on_disconnect_callback("Servidor desconectado.")