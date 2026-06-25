import socket
import threading
import json
import struct
import queue
import time
import os
import winsound
import cv2
from PIL import Image, ImageDraw
import io
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

# Configuración de Red por Defecto y Apariencia
DEFAULT_HOST, DEFAULT_PORT = 'localhost', 8080
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Paleta de Colores
BG_WINDOW, BG_CARD, BORDER_CARD = "#0c0d0f", "#16181c", "#23272d"
COLOR_ACCENT, COLOR_ACCENT_HOVER, BG_ENTRY, COLOR_TEXT = "#7d5fff", "#575fcf", "#1e2124", "#ffffff"

class SocketsZoomClient:
    # Conexión TCP con el servidor usando protocolo de enmarcado (header 8 bytes)
    def __init__(self, host, port, on_message_callback, on_disconnect_callback):
        self.host, self.port = host, port
        self.on_message_callback, self.on_disconnect_callback = on_message_callback, on_disconnect_callback
        self.sock, self.connected, self.receive_thread = None, False, None
        self.write_lock = threading.Lock()

    def connect(self):
        # Establece conexión TCP e inicia hilo de recepción
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
        # Cierra socket y recursos
        self.connected = False
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None

    def send_message(self, json_obj, binary_data=None):
        # Envía mensaje estructurado (Cabecera 8 bytes + JSON + Binario)
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
        # Lee un bloque exacto de bytes
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
        # Bucle de recepción de tramas
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

class App(ctk.CTk):
    # Ventana principal, controla vistas y cola de GUI
    def __init__(self):
        super().__init__()
        self.title("El Prototipo")
        self.geometry("600x550")
        self.minsize(500, 450)
        self.client, self.user_session = None, None
        self.gui_queue = queue.Queue()
        self.after(50, self._process_queue)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        self.show_login_screen()

    def _create_control_icon(self, name, show_x=False):
        # Dibuja iconos de micrófono y cámara en PIL
        try:
            img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            if name == "mic":
                draw.rounded_rectangle([(19, 10), (29, 26)], radius=5, fill="#ffffff")
                draw.arc([(14, 18), (34, 32)], start=0, end=180, fill="#ffffff", width=3)
                draw.line([(24, 32), (24, 38)], fill="#ffffff", width=3)
                draw.line([(18, 38), (30, 38)], fill="#ffffff", width=3)
            elif name == "cam":
                draw.rounded_rectangle([(12, 16), (30, 32)], radius=3, fill="#ffffff")
                draw.polygon([(30, 20), (38, 16), (38, 32), (30, 28)], fill="#ffffff")
            if show_x:
                draw.line([(10, 10), (38, 38)], fill="#e74c3c", width=4)
                draw.line([(38, 10), (10, 38)], fill="#e74c3c", width=4)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
        except Exception as e:
            print(f"[ICON ERROR] {e}")
            return None

    def show_login_screen(self):
        # Vista de inicio de sesión
        self._clear_container()
        self.geometry("600x550")
        self.configure(fg_color=BG_WINDOW)
        card = ctk.CTkFrame(self.main_container, width=380, height=440, corner_radius=15, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        ctk.CTkFrame(card, height=4, fg_color=COLOR_ACCENT, corner_radius=0).place(relx=0, rely=0, relwidth=1)
        ctk.CTkLabel(card, text="MiniMiniMeet", font=("Inter", 24, "bold"), text_color=COLOR_TEXT).pack(pady=(40, 5))
        
        self.email_entry = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Correo Electrónico")
        self.email_entry.pack(pady=10)
        self.pass_entry = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Contraseña", show="*")
        self.pass_entry.pack(pady=10)
        self.ip_entry = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Servidor IP (def: localhost)")
        self.ip_entry.insert(0, DEFAULT_HOST)
        self.ip_entry.pack(pady=10)
        
        self.btn_login = ctk.CTkButton(card, text="Ingresar", width=280, height=40, corner_radius=8, font=("Inter", 14, "bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.on_login_click)
        self.btn_login.pack(pady=(20, 10))
        self.btn_reg_login = ctk.CTkButton(card, text="Registrar Nuevo Usuario", width=280, height=35, fg_color="transparent", text_color=COLOR_ACCENT, font=("Inter", 12, "bold"), hover_color="#23272d", command=self.show_register_screen)
        self.btn_reg_login.pack(pady=10)

    def show_register_screen(self):
        # Vista de registro de usuario
        self._clear_container()
        self.geometry("600x550")
        self.configure(fg_color=BG_WINDOW)
        card = ctk.CTkFrame(self.main_container, width=380, height=440, corner_radius=15, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        ctk.CTkFrame(card, height=4, fg_color=COLOR_ACCENT, corner_radius=0).place(relx=0, rely=0, relwidth=1)
        ctk.CTkLabel(card, text="Crear Cuenta", font=("Inter", 24, "bold"), text_color=COLOR_TEXT).pack(pady=(35, 15))
        
        self.reg_name = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Nombres y Apellidos")
        self.reg_name.pack(pady=8)
        self.reg_email = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Correo Electrónico")
        self.reg_email.pack(pady=8)
        self.reg_pass = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Contraseña", show="*")
        self.reg_pass.pack(pady=8)
        self.reg_ip = ctk.CTkEntry(card, width=280, height=40, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Servidor IP (def: localhost)")
        self.reg_ip.insert(0, DEFAULT_HOST)
        self.reg_ip.pack(pady=8)
        
        self.btn_register = ctk.CTkButton(card, text="Registrarse", width=280, height=40, corner_radius=8, font=("Inter", 14, "bold"), fg_color="#2ecc71", hover_color="#27ae60", command=self.on_register_click)
        self.btn_register.pack(pady=(15, 10))
        self.btn_back_reg = ctk.CTkButton(card, text="Volver al Login", width=280, height=35, fg_color="transparent", text_color=COLOR_ACCENT, font=("Inter", 12, "bold"), hover_color="#23272d", command=self.show_login_screen)
        self.btn_back_reg.pack(pady=5)

    def _set_login_state(self, state):
        # Modifica el estado interactivo de los controles del login
        for attr in ['email_entry', 'pass_entry', 'ip_entry', 'btn_login', 'btn_reg_login']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.winfo_exists(): w.configure(state=state)

    def _set_register_state(self, state):
        # Modifica el estado interactivo del registro
        for attr in ['reg_name', 'reg_email', 'reg_pass', 'reg_ip', 'btn_register', 'btn_back_reg']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.winfo_exists(): w.configure(state=state)

    def on_login_click(self):
        # Clic de login, conecta e inicia sesión en hilo
        if self.client and self.client.connected: return
        email, password, ip = self.email_entry.get().strip(), self.pass_entry.get(), self.ip_entry.get().strip() or 'localhost'
        if not email or not password:
            messagebox.showerror("Error", "Por favor completa todos los campos obligatorios.")
            return
        self._set_login_state("disabled")
        def connect_login():
            self.client = SocketsZoomClient(ip, DEFAULT_PORT, self.on_socket_message, self.on_socket_disconnect)
            if self.client.connect():
                self.client.send_message({'type': 'LOGIN_REQUEST', 'correo': email, 'password': password})
            else:
                self.gui_queue.put(({'type': 'CONNECT_FAILED', 'context': 'login', 'ip': ip}, None))
        threading.Thread(target=connect_login, daemon=True).start()

    def on_register_click(self):
        # Registro de usuario en hilo
        if self.client and self.client.connected: return
        n, em, pw, ip = self.reg_name.get().strip(), self.reg_email.get().strip(), self.reg_pass.get(), self.reg_ip.get().strip() or 'localhost'
        if not n or not em or not pw:
            messagebox.showerror("Error", "Todos los campos son requeridos para el registro.")
            return
        self._set_register_state("disabled")
        def connect_register():
            self.client = SocketsZoomClient(ip, DEFAULT_PORT, self.on_socket_message, self.on_socket_disconnect)
            if self.client.connect():
                self.client.send_message({'type': 'REGISTER_REQUEST', 'nombres': n, 'correo': em, 'password': pw})
            else:
                self.gui_queue.put(({'type': 'CONNECT_FAILED', 'context': 'register', 'ip': ip}, None))
        threading.Thread(target=connect_register, daemon=True).start()

    def on_logout_click(self):
        # Desconecta y vuelve al Login
        if self.client: self.client.disconnect()
        self.user_session = None
        self.show_login_screen()
    
    def on_socket_message(self, json_msg, bin_data):
        self.gui_queue.put((json_msg, bin_data))

    def on_socket_disconnect(self, message):
        self.gui_queue.put(({'type': 'LOCAL_DISCONNECT', 'message': message}, None))

    def _process_queue(self):
        # Polling de mensajes de red para actualizacion de GUI
        try:
            while True:
                json_msg, bin_data = self.gui_queue.get_nowait()
                self._handle_ui_message(json_msg, bin_data)
                self.gui_queue.task_done()
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def _handle_ui_message(self, json_msg, bin_data):
        # Modifica la interfaz gráfica a partir de las tramas recibidas
        msg_type = json_msg.get('type')
        if msg_type == 'CONNECT_FAILED':
            self._set_login_state("normal") if json_msg.get('context') == 'login' else self._set_register_state("normal")
            messagebox.showerror("Error de conexión", f"No se pudo conectar en {json_msg['ip']}:{DEFAULT_PORT}.")
            if self.client: self.client.disconnect()
            return
        if msg_type == 'LOCAL_DISCONNECT':
            messagebox.showwarning("Desconectado", json_msg['message'])
            self.show_login_screen()
            return
        if msg_type == 'LOGIN_RESPONSE':
            if json_msg['success']:
                self.user_session = json_msg['usuario']
                self.show_lobby_screen()
            else:
                self._set_login_state("normal")
                messagebox.showerror("Error de Inicio", json_msg.get('message', 'Credenciales incorrectas'))
                if self.client: self.client.disconnect()
        elif msg_type == 'REGISTER_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Registro Exitoso", json_msg['message'])
                self.show_login_screen()
            else:
                self._set_register_state("normal")
                messagebox.showerror("Error de Registro", json_msg['message'])
            if self.client: self.client.disconnect()
        elif msg_type == 'CREATE_ROOM_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Éxito", json_msg['message'])
                self.is_host, self.current_room_code = True, json_msg['codigoSala']
                self.show_meeting_room(json_msg['codigoSala'])
                for m in json_msg.get('chatHistory', []): self.append_chat_message(m['userName'], m['Contenido'], m['FechaEnvio'])
                for f in json_msg.get('fileHistory', []): self.add_file_to_list(int(f.get('IdArchivo', 0)), f['NombreArchivo'], f['userName'])
            else: messagebox.showerror("Error", json_msg.get('message', 'Error al crear sala.'))
        elif msg_type == 'JOIN_ROOM_RESPONSE':
            if json_msg['success']: self.show_waiting_room_guest()
            else: messagebox.showerror("Error", json_msg.get('message', 'No se pudo ingresar.'))
        elif msg_type == 'WAITING_ROOM_UPDATE':
            self.pending_users = json_msg.get('usuariosPendientes', [])
            if len(self.pending_users) > 0 and not self.show_participants:
                if hasattr(self, 'btn_participants') and self.btn_participants.winfo_exists():
                    self.btn_participants.configure(fg_color="#e74c3c", hover_color="#c0392b")
            self.refresh_popup_list()
        elif msg_type == 'ADMIT_RESULT':
            if json_msg['success']:
                self.is_host, self.current_room_code = False, json_msg['codigoSala']
                self.show_meeting_room(json_msg['codigoSala'])
                for m in json_msg.get('chatHistory', []): self.append_chat_message(m['userName'], m['Contenido'], m['FechaEnvio'])
                for f in json_msg.get('fileHistory', []): self.add_file_to_list(int(f.get('IdArchivo', 0)), f['NombreArchivo'], f['userName'])
            else:
                messagebox.showwarning("Acceso Denegado", json_msg.get('message', 'Has sido rechazado.'))
                self.show_lobby_screen()
        elif msg_type == 'CHAT_MESSAGE':
            sender = json_msg['userName']
            self.append_chat_message(sender, json_msg['message'], json_msg.get('sentAt', ''))
            if sender != self.user_session['nombres'] and sender != 'Sistema':
                try: winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception as e: print(f"Error playing sound: {e}")
        elif msg_type == 'ROOM_CLOSED':
            messagebox.showinfo("Sala Cerrada", json_msg.get('message', 'La sala ha sido cerrada.'))
            self.show_lobby_screen(); self.geometry("600x550")
        elif msg_type == 'MY_ROOMS_RESPONSE':
            if json_msg['success']: self.populate_my_rooms_list(json_msg['salas'])
            else: messagebox.showerror("Error", json_msg.get('message', 'Error al cargar salas.'))
        elif msg_type == 'FILE_SHARED':
            self.add_file_to_list(int(json_msg.get('fileId', 0)), json_msg['fileName'], json_msg['senderName'])
        elif msg_type == 'FILE_DOWNLOAD_START':
            print(f"Descargando {json_msg['fileName']} ({json_msg['fileSize']} bytes)")
        elif msg_type == 'FILE_DOWNLOAD_CHUNK':
            f_id, is_last = int(json_msg.get('fileId', 0)), json_msg['isLast']
            download = getattr(self, 'active_downloads', {}).get(f_id)
            if download:
                if bin_data and len(bin_data) > 0: download['fileObj'].write(bin_data)
                if is_last:
                    download['fileObj'].close(); del self.active_downloads[f_id]
                    messagebox.showinfo("Descarga Exitosa", f"Archivo \"{download['fileName']}\" descargado.")
        elif msg_type == 'FILE_DOWNLOAD_ERROR':
            f_id, msg = int(json_msg.get('fileId', 0)) if json_msg.get('fileId') else None, json_msg.get('message', 'Error.')
            messagebox.showerror("Error de Descarga", f"No se pudo descargar: {msg}")
            if f_id and hasattr(self, 'active_downloads') and f_id in self.active_downloads:
                download = self.active_downloads[f_id]
                download['fileObj'].close()
                try: os.remove(download['filePath'])
                except: pass
                del self.active_downloads[f_id]
        elif msg_type == 'UPLOAD_PROGRESS':
            fn, prg = json_msg['fileName'], json_msg['progress']
            if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists():
                if prg < 100: self.lbl_upload_status.configure(text=f"Subiendo {fn}: {prg}%")
                else:
                    self.lbl_upload_status.configure(text="Subida completada.")
                    self.after(3000, lambda: self.lbl_upload_status.configure(text="") if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists() else None)
        elif msg_type == 'UPLOAD_ERROR':
            messagebox.showerror("Error de Subida", f"Error al subir {json_msg['fileName']}: {json_msg['error']}")
            if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists():
                self.lbl_upload_status.configure(text="Error al subir.")
                self.after(3000, lambda: self.lbl_upload_status.configure(text="") if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists() else None)
        elif msg_type == 'CAMERA_FRAME' or msg_type == 'LOCAL_CAMERA_FRAME':
            if bin_data:
                u_id = json_msg.get('userId')
                if not self.users_cam_state.get(u_id, True): return
                try:
                    image = Image.open(io.BytesIO(bin_data))
                    self.update_camera_frame(u_id, json_msg.get('userName', 'Desconocido'), ctk_image=ctk.CTkImage(light_image=image, dark_image=image, size=(320, 240)))
                except: pass
        elif msg_type == 'CAMERA_TOGGLE':
            u_id, state = json_msg.get('userId'), json_msg.get('state')
            self.users_cam_state[u_id] = state
            if not state: self.update_camera_frame(u_id, "", is_off=True)
        elif msg_type == 'PARTICIPANTS_UPDATE':
            self.active_participants = json_msg.get('users', [])
            if hasattr(self, 'btn_participants') and self.btn_participants.winfo_exists():
                self.btn_participants.configure(text=f"👥 Participantes ({len(self.active_participants)})")
            self.refresh_participants_popup_list(); self.rebuild_grid()
        elif msg_type == 'KICKED':
            messagebox.showwarning("Expulsado", json_msg.get('message', 'Has sido expulsado.'))
            self.show_lobby_screen(); self.geometry("600x550")
        elif msg_type == 'DELETE_ROOM_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Eliminada", "Sala eliminada con éxito."); self.refresh_my_rooms()
            else: messagebox.showerror("Error", json_msg.get('message', 'No se pudo eliminar.'))
                    
    def _clear_container(self):
        # Limpia todos los widgets del contenedor principal
        for widget in self.main_container.winfo_children(): widget.destroy()

    def on_closing(self):
        # Manejador del evento de cierre de ventana física
        if self.client: self.client.disconnect()
        self.destroy()       

    def show_lobby_screen(self):
        # Crea la interfaz del lobby (crear, unirse y ver salas registradas)
        self._clear_container()
        self.geometry("750x550")
        self.configure(fg_color=BG_WINDOW)
        header = ctk.CTkFrame(self.main_container, height=60, corner_radius=8, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1)
        header.pack(fill="x", pady=(0, 10))
        
        # Iniciales avatar
        parts = self.user_session.get('nombres', 'Usuario').split()
        initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "U"
        avatar_frame = ctk.CTkFrame(header, width=36, height=36, corner_radius=18, fg_color=COLOR_ACCENT)
        avatar_frame.pack(side="left", padx=(15, 10), pady=12); avatar_frame.pack_propagate(False)
        ctk.CTkLabel(avatar_frame, text=initials, font=("Inter", 13, "bold"), text_color="white").pack(expand=True)
        ctk.CTkLabel(header, text=f"Bienvenido, {self.user_session.get('nombres')}", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(side="left", pady=15)
        ctk.CTkButton(header, text="Cerrar Sesión", width=100, height=30, corner_radius=6, fg_color="#e74c3c", hover_color="#c0392b", font=("Inter", 12, "bold"), command=self.on_logout_click).pack(side="right", padx=15, pady=15)
        
        content = ctk.CTkFrame(self.main_container, fg_color="transparent")
        content.pack(fill="both", expand=True, pady=10)
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Crear sala
        card_create = ctk.CTkFrame(left_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_create.pack(pady=(0, 15), fill="x", ipady=10)
        ctk.CTkLabel(card_create, text="➕ Crear una Nueva Sala", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=15, pady=(12, 5))
        self.entry_room_code = ctk.CTkEntry(card_create, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Código de Sala Único (Ej: REUNION1)")
        self.entry_room_code.pack(fill="x", pady=5, padx=15)
        self.entry_room_name = ctk.CTkEntry(card_create, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Nombre de la Sala")
        self.entry_room_name.pack(fill="x", pady=5, padx=15)
        ctk.CTkButton(card_create, text="Crear Sala", height=32, corner_radius=8, font=("Inter", 12, "bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.on_create_room).pack(pady=(8, 5), padx=15, anchor="e")

        # Unirse sala
        card_join = ctk.CTkFrame(left_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_join.pack(pady=5, fill="x", ipady=10)
        ctk.CTkLabel(card_join, text="🚪 Unirse a una Sala", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=15, pady=(12, 5))
        self.entry_join_code = ctk.CTkEntry(card_join, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Ingrese el Código de la Sala")
        self.entry_join_code.pack(fill="x", pady=5, padx=15)
        ctk.CTkButton(card_join, text="Solicitar Ingreso", height=32, corner_radius=8, font=("Inter", 12, "bold"), fg_color="#2ecc71", hover_color="#27ae60", command=self.on_join_room).pack(pady=(8, 5), padx=15, anchor="e")

        # Salas registradas
        card_rooms = ctk.CTkFrame(right_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_rooms.pack(fill="both", expand=True)
        title_frame = ctk.CTkFrame(card_rooms, fg_color="transparent")
        title_frame.pack(fill="x", pady=(12, 5), padx=15)
        ctk.CTkLabel(title_frame, text="📁 Mis Salas Registradas", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(side="left")

        self.my_rooms_scroll = ctk.CTkScrollableFrame(card_rooms, fg_color="transparent")
        self.my_rooms_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_my_rooms()

    def refresh_my_rooms(self):
        # Solicita al servidor el listado de salas asociadas a nuestro ID
        if self.client and self.client.connected: self.client.send_message({'type': 'GET_MY_ROOMS'})

    def on_start_existing_room(self, code, name):
        # Lanza una reunión que ya estaba creada previamente en la base de datos
        if self.client and self.client.connected:
            self.is_host = True
            self.client.send_message({'type': 'CREATE_ROOM', 'codigoSala': code, 'nombre': name})

    def populate_my_rooms_list(self, salas):
        # Rellena visualmente la lista de salas registradas
        if not hasattr(self, 'my_rooms_scroll') or not self.my_rooms_scroll.winfo_exists(): return
        for w in self.my_rooms_scroll.winfo_children(): w.destroy()
        if not salas:
            ctk.CTkLabel(self.my_rooms_scroll, text="No tienes salas registradas.", font=("Inter", 12, "italic"), text_color="gray").pack(pady=20)
            return
            
        for sala in salas:
            frame = ctk.CTkFrame(self.my_rooms_scroll, fg_color="#1e2124", border_color="#23272d", border_width=1, corner_radius=10)
            frame.pack(fill="x", pady=4, padx=5)
            info_frame = ctk.CTkFrame(frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=12, pady=8)
            ctk.CTkLabel(info_frame, text=sala['CodigoSala'], font=("Inter", 13, "bold"), text_color=COLOR_ACCENT, anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=sala['Nombre'], font=("Inter", 11), text_color="gray", anchor="w").pack(fill="x")
            
            # Botones de sala
            ctk.CTkButton(frame, text="🗑", width=32, height=32, corner_radius=6, fg_color="#e74c3c", hover_color="#c0392b", font=("Segoe UI Symbol", 12), anchor="center", command=lambda code=sala['CodigoSala']: self.on_delete_room_click(code)).pack(side="right", padx=(0, 8), pady=8)
            ctk.CTkButton(frame, text="▶", width=32, height=32, corner_radius=6, fg_color="#2ecc71", hover_color="#27ae60", font=("Segoe UI Symbol", 12), anchor="center", command=lambda code=sala['CodigoSala'], name=sala['Nombre']: self.on_start_existing_room(code, name)).pack(side="right", padx=8, pady=8)

    def on_create_room(self):
        # Envía solicitud para registrar una nueva sala al servidor
        code, name = self.entry_room_code.get().strip(), self.entry_room_name.get().strip()
        if not code or not name:
            messagebox.showerror("Error", "Debe proporcionar un código y un nombre para la sala.")
            return
        self.client.send_message({'type': 'CREATE_ROOM', 'codigoSala': code, 'nombre': name})

    def on_delete_room_click(self, code):
        # Muestra ventana de confirmación antes de borrar una sala
        if messagebox.askyesno("Confirmar", f"¿Deseas eliminar permanentemente la sala {code}?"):
            if self.client and self.client.connected: self.client.send_message({'type': 'DELETE_ROOM', 'codigoSala': code})

    def on_join_room(self):
        # Envía solicitud para ingresar a la sala (se entra a sala de espera)
        code = self.entry_join_code.get().strip()
        if not code:
            messagebox.showerror("Error", "Debe proporcionar el código de la sala.")
            return
        self.client.send_message({'type': 'JOIN_ROOM_REQUEST', 'codigoSala': code})

    def show_waiting_room_guest(self):
        # Pantalla transitoria para usuarios en espera de admisión
        self._clear_container()
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        ctk.CTkLabel(content, text="Sala de Espera", font=("Inter", 24, "bold")).pack(pady=(80, 20))
        ctk.CTkLabel(content, text="Por favor, espere a que el anfitrión le permita el ingreso...", font=("Inter", 14)).pack()
        ctk.CTkButton(content, text="Cancelar Espera", fg_color="#e74c3c", hover_color="#c0392b", command=self.on_cancel_join).pack(pady=20)

    def on_cancel_join(self):
        #Cancela la solicitud de espera activa.
        if self.client and self.client.connected: self.client.send_message({'type': 'CANCEL_JOIN_REQUEST'})
        self.show_lobby_screen()

    def update_camera_frame(self, user_id, user_name, ctk_image=None, is_off=False):
        # Actualiza el recuadro de vídeo o avatar de un usuario
        if not hasattr(self, 'cameras_frame') or not self.cameras_frame.winfo_exists(): return
        if user_id not in self.camera_widgets: self.rebuild_grid()
        if user_id not in self.camera_widgets: return
            
        vid_label = self.camera_widgets[user_id]['label']
        avatar = self.camera_widgets[user_id]['avatar']
        badge_frame = self.camera_widgets[user_id]['badge'].master
        
        if is_off:
            vid_label.place_forget()
            avatar.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        elif ctk_image:
            vid_label.configure(image=ctk_image)
            vid_label.place(relx=0.5, rely=0.5, relwidth=1, relheight=1, anchor=tk.CENTER)
            avatar.place_forget(); badge_frame.lift()

    def rebuild_grid(self):
        # Reconstruye dinámicamente la cuadrícula según el número de participantes activos
        active_ids = {u['id'] for u in self.active_participants}
        my_id = self.user_session['id']
        active_ids.add(my_id)
        
        for u_id in list(self.camera_widgets.keys()):
            if u_id not in active_ids:
                if 'frame' in self.camera_widgets[u_id]:
                    try: self.camera_widgets[u_id]['frame'].destroy()
                    except: pass
                del self.camera_widgets[u_id]
 
        participants_to_render = [(my_id, 'Tú')]
        for p in self.active_participants:
            if p['id'] != my_id: participants_to_render.append((p['id'], p['nombre']))

        num_participants = len(participants_to_render)
        if num_participants == 0: return

        if num_participants == 1: cols, rows = 1, 1
        elif num_participants == 2: cols, rows = 2, 1
        elif num_participants <= 4: cols, rows = 2, 2
        else: cols, rows = 3, (num_participants + 2) // 3

        for i in range(rows): self.cameras_frame.rowconfigure(i, weight=1)
        for j in range(cols): self.cameras_frame.columnconfigure(j, weight=1)

        colors = ["#4a3b32", "#a15c71", "#344a5e", "#2c5e43", "#4e3b5e", "#5e4a3b"]

        for index, (u_id, u_name) in enumerate(participants_to_render):
            r, c = index // cols, index % cols
            if u_id not in self.camera_widgets:
                card = ctk.CTkFrame(self.cameras_frame, fg_color=colors[u_id % len(colors)], corner_radius=15)
                badge_bg = ctk.CTkFrame(card, fg_color="#121214", corner_radius=6)
                badge_bg.pack(side="bottom", anchor="sw", padx=15, pady=15)
                lbl_name = ctk.CTkLabel(badge_bg, text=u_name, font=("Inter", 12, "bold"), text_color="white")
                lbl_name.pack(padx=8, pady=4)
                
                avatar_container = ctk.CTkFrame(card, fg_color="transparent")
                avatar_container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                initials = "".join([part[0].upper() for part in u_name.split() if part])[:2] or "?"
                avatar_circle = ctk.CTkFrame(avatar_container, width=100, height=100, corner_radius=50, fg_color="#2f3136")
                avatar_circle.pack(); avatar_circle.pack_propagate(False)
                ctk.CTkLabel(avatar_circle, text=initials, font=("Inter", 32, "bold"), text_color="white").place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
                lbl_vid = ctk.CTkLabel(card, text="")
                self.camera_widgets[u_id] = {'frame': card, 'label': lbl_vid, 'avatar': avatar_container, 'badge': lbl_name}
            
            card = self.camera_widgets[u_id]['frame']
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            if not self.users_cam_state.get(u_id, False):
                self.camera_widgets[u_id]['label'].place_forget()
                self.camera_widgets[u_id]['avatar'].place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def show_meeting_room(self, room_code):
        # Inicializa la pantalla principal de la videollamada
        self._clear_container()
        self.geometry("1100x700")
        self.configure(fg_color="#0e0f12")
        self.active_participants, self.mic_muted = [], True
        self.show_participants, self.show_chat, self.show_files = False, True, False
        
        self.img_mic_on, self.img_mic_off = self._create_control_icon("mic", False), self._create_control_icon("mic", True)
        self.img_cam_on, self.img_cam_off = self._create_control_icon("cam", False), self._create_control_icon("cam", True)
        
        layout = ctk.CTkFrame(self.main_container, fg_color="transparent")
        layout.pack(fill="both", expand=True)
        
        self.video_panel = ctk.CTkFrame(layout, corner_radius=10, fg_color="#121212")
        self.video_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.cameras_frame = ctk.CTkFrame(self.video_panel, fg_color="transparent")
        self.cameras_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.camera_widgets, self.cam_running, self.users_cam_state = {}, False, {}
        self.sidebar_frame = ctk.CTkFrame(layout, width=320, corner_radius=10, fg_color="#1a1a1e")
        self.sidebar_frame.pack_propagate(False)
        
        # 1. Pestaña de Participantes
        self.sidebar_participants = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        title_frame_part = ctk.CTkFrame(self.sidebar_participants, fg_color="transparent")
        title_frame_part.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(title_frame_part, text="👥 Participantes", font=("Inter", 14, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame_part, text="✕", width=28, height=28, fg_color="transparent", hover_color="#e74c3c", text_color="gray", font=("Inter", 12, "bold"), command=self.toggle_participants_sidebar).pack(side="right", padx=10)
        
        self.waiting_section_frame = ctk.CTkFrame(self.sidebar_participants, fg_color="#2b2b30", corner_radius=8)
        self.waiting_lbl = ctk.CTkLabel(self.waiting_section_frame, text="Sala de Espera (0 pendientes)", font=("Inter", 12, "bold"), text_color="#e74c3c")
        self.waiting_lbl.pack(pady=5)
        self.waiting_list_frame = ctk.CTkScrollableFrame(self.waiting_section_frame, height=100)
        self.active_section_lbl = ctk.CTkLabel(self.sidebar_participants, text="Participantes Activos", font=("Inter", 12, "bold"))
        self.active_section_lbl.pack(pady=(10, 5))
        self.active_list_frame = ctk.CTkScrollableFrame(self.sidebar_participants, fg_color="#121214")
        self.active_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 2. Pestaña de Chat
        self.sidebar_chat = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        title_frame_chat = ctk.CTkFrame(self.sidebar_chat, fg_color="transparent")
        title_frame_chat.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(title_frame_chat, text="💬 Chat de la Reunión", font=("Inter", 14, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame_chat, text="✕", width=28, height=28, fg_color="transparent", hover_color="#e74c3c", text_color="gray", font=("Inter", 12, "bold"), command=self.toggle_chat_sidebar).pack(side="right", padx=10)
        self.chat_display = ctk.CTkTextbox(self.sidebar_chat, state="disabled", wrap="word", fg_color="#121214")
        self.chat_display.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        input_frame = ctk.CTkFrame(self.sidebar_chat, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Escribe un mensaje...")
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self.on_send_chat()); self.chat_entry.focus()
        ctk.CTkButton(input_frame, text="Enviar", width=60, command=self.on_send_chat).pack(side="right")
        
        # 3. Pestaña de Archivos Compartidos
        self.sidebar_files = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        title_frame_files = ctk.CTkFrame(self.sidebar_files, fg_color="transparent")
        title_frame_files.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(title_frame_files, text="📂 Archivos Compartidos", font=("Inter", 14, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame_files, text="✕", width=28, height=28, fg_color="transparent", hover_color="#e74c3c", text_color="gray", font=("Inter", 12, "bold"), command=self.toggle_files_sidebar).pack(side="right", padx=10)
        self.files_frame = ctk.CTkScrollableFrame(self.sidebar_files, fg_color="#121214")
        self.files_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        # Scroll horizontal en archivos
        self.files_frame._parent_canvas.unbind("<Configure>")
        def update_files_frame_width(event=None):
            if not self.files_frame.winfo_exists(): return
            self.files_frame._parent_canvas.itemconfigure(self.files_frame._create_window_id, width=max(self.files_frame._parent_canvas.winfo_width(), self.files_frame.winfo_reqwidth()))
        self.files_frame._parent_canvas.bind("<Configure>", lambda e: update_files_frame_width())
        self.files_frame.bind("<Configure>", lambda e: (self.files_frame._parent_canvas.configure(scrollregion=self.files_frame._parent_canvas.bbox("all")), update_files_frame_width()), add="+")
        
        border_spacing = self.files_frame._apply_widget_scaling(self.files_frame._parent_frame.cget("corner_radius") + self.files_frame._parent_frame.cget("border_width"))
        h_sb = ctk.CTkScrollbar(master=self.files_frame._parent_frame, orientation="horizontal", command=self.files_frame._parent_canvas.xview)
        h_sb.grid(row=2, column=0, sticky="ew", padx=(border_spacing, 0), pady=(0, border_spacing))
        self.files_frame._parent_canvas.configure(xscrollcommand=h_sb.set)
        
        file_actions_frame = ctk.CTkFrame(self.sidebar_files, fg_color="transparent")
        file_actions_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_upload_status = ctk.CTkLabel(file_actions_frame, text="", font=("Inter", 11, "italic"), text_color="#1abc9c")
        self.lbl_upload_status.pack(pady=(0, 5))
        ctk.CTkButton(file_actions_frame, text="📤 Compartir Archivo", fg_color="#2ecc71", hover_color="#27ae60", text_color="white", font=("Inter", 12, "bold"), command=self.on_share_file_click).pack(fill="x")
        
        # Barra Inferior Controles (Estilo Zoom)
        self.controls_bar = ctk.CTkFrame(self.main_container, height=60, fg_color="#16161a", corner_radius=10)
        self.controls_bar.pack(side="bottom", fill="x", pady=(10, 0))
        left_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        left_controls.pack(side="left", padx=15, fill="y")
        center_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        center_controls.place(relx=0.5, rely=0.5, anchor="center")
        right_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        right_controls.pack(side="right", padx=15, fill="y")
        
        self.btn_mic = ctk.CTkButton(left_controls, text="" if self.img_mic_off else "❌\n🎙️", image=self.img_mic_off, width=50, height=46, font=("Inter", 13), fg_color="#e74c3c", hover_color="#c0392b", command=self.toggle_mic)
        self.btn_mic.pack(side="left", padx=5, pady=7)
        self.btn_cam = ctk.CTkButton(left_controls, text="" if self.img_cam_off else "❌\n📹", image=self.img_cam_off, width=50, height=46, font=("Inter", 13), fg_color="#e74c3c", hover_color="#c0392b", command=self.toggle_camera)
        self.btn_cam.pack(side="left", padx=5, pady=7)
        
        self.lbl_room_info = ctk.CTkLabel(center_controls, text=f"Reunión: {room_code}", font=("Inter", 13, "bold"), text_color="gray")
        self.lbl_room_info.pack(side="left", padx=15)
        self.btn_participants = ctk.CTkButton(center_controls, text="👥 Participantes", width=130, height=36, font=("Inter", 12), fg_color="transparent", hover_color="#2b2b30", command=self.toggle_participants_sidebar)
        self.btn_participants.pack(side="left", padx=5, pady=12)
        self.btn_chat = ctk.CTkButton(center_controls, text="💬 Chat", width=90, height=36, font=("Inter", 12), fg_color="#3a3a40", hover_color="#4f4f55", command=self.toggle_chat_sidebar)
        self.btn_chat.pack(side="left", padx=5, pady=12)
        self.btn_files = ctk.CTkButton(center_controls, text="📁 Archivos", width=110, height=36, font=("Inter", 12), fg_color="#3a3a40", hover_color="#4f4f55", command=self.toggle_files_sidebar)
        self.btn_files.pack(side="left", padx=5, pady=12)
        
        ctk.CTkButton(right_controls, text="Salir de la Reunión", width=130, height=36, font=("Inter", 12, "bold"), fg_color="#e74c3c", hover_color="#c0392b", command=self.on_leave_meeting).pack(side="right", padx=5, pady=12)
        if self.is_host: self.pending_users = []
        self.update_sidebar_layout(); self.rebuild_grid()
        self.lbl_participants = ctk.CTkLabel(self.video_panel, text="")

    def on_send_chat(self):
        # Envía un mensaje de chat de texto escrito al socket
        text = self.chat_entry.get().strip()
        if not text: return
        self.chat_entry.delete(0, tk.END)
        self.client.send_message({'type': 'CHAT_MESSAGE', 'message': text})

    def on_share_file_click(self):
        # Abre cuadro de diálogo para compartir un archivo local
        file_path = filedialog.askopenfilename(title="Seleccionar archivo para compartir")
        if not file_path: return
        threading.Thread(target=self.bg_upload_file, args=(file_path, os.path.basename(file_path), os.path.getsize(file_path)), daemon=True).start()

    def bg_upload_file(self, file_path, file_name, file_size):
        # Hilo de subida incremental: lee archivos en trozos de 4KB y los transmite
        try:
            self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': 0}, None))
            chunk_size = 4 * 1024 
            total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
            with open(file_path, 'rb') as f:
                for chunk_idx in range(total_chunks):
                    if not self.client or not self.client.connected: break
                    data = f.read(chunk_size)
                    self.client.send_message({
                        'type': 'FILE_CHUNK', 'fileName': file_name, 'chunkIndex': chunk_idx, 'totalChunks': total_chunks, 'isLast': chunk_idx == total_chunks - 1
                    }, binary_data=data)
                    self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': int(((chunk_idx + 1) / total_chunks) * 100)}, None))
                    time.sleep(0.01)
        except Exception as e:
            self.gui_queue.put(({'type': 'UPLOAD_ERROR', 'fileName': file_name, 'error': str(e)}, None))

    def add_file_to_list(self, file_id, file_name, sender_name):
        # Agrega un componente visual de archivo a la pestaña de archivos compartidos
        if not hasattr(self, 'files_frame') or not self.files_frame.winfo_exists(): return
        row = ctk.CTkFrame(self.files_frame, fg_color="#222222")
        row.pack(fill="x", pady=2, padx=5)
        ctk.CTkButton(row, text="Descargar", width=70, height=22, font=("Inter", 10), command=lambda f_id=file_id, f_name=file_name: self.on_download_file_click(f_id, f_name)).pack(side="left", padx=5, pady=4)
        ctk.CTkLabel(row, text=f"{file_name} ( {sender_name} )", font=("Inter", 11), anchor="w").pack(side="left", padx=8, pady=4)

    def on_download_file_click(self, file_id, file_name):
        # Solicita la descarga de un archivo compartido seleccionando destino local
        file_path = filedialog.asksaveasfilename(title="Guardar archivo", initialfile=file_name, defaultextension=os.path.splitext(file_name)[1])
        if not file_path: return
        if not hasattr(self, 'active_downloads'): self.active_downloads = {}
        file_id_key = int(file_id)
        self.active_downloads[file_id_key] = {'filePath': file_path, 'fileName': file_name, 'expectedChunk': 0, 'fileObj': open(file_path, 'wb')}
        self.client.send_message({'type': 'FILE_DOWNLOAD_REQUEST', 'fileId': file_id_key})

    def append_chat_message(self, sender, text, timestamp=""):
        #Escribe un mensaje en el panel de texto del chat
        self.chat_display.configure(state="normal")
        time_str = timestamp.split(' ')[1][:5] if timestamp and ' ' in timestamp else time.strftime('%H:%M')
        self.chat_display.insert(tk.END, f"[{time_str}] {sender}: {text}\n")
        self.chat_display.configure(state="disabled"); self.chat_display.see(tk.END)

    def on_leave_meeting(self):
        # Aborta la cámara y notifica salida al servidor
        self.cam_running = False
        if self.client and self.client.connected: self.client.send_message({'type': 'LEAVE_ROOM'})
        self.show_lobby_screen(); self.geometry("600x550") 

    def toggle_mic(self):
        #Cambia el estado de silencio/activado del micrófono (prototipo local)
        self.mic_muted = not self.mic_muted
        if self.mic_muted:
            self.btn_mic.configure(text="" if self.img_mic_off else "❌\n🎙️", image=self.img_mic_off, fg_color="#e74c3c", hover_color="#c0392b")
        else:
            self.btn_mic.configure(text="" if self.img_mic_on else "🎙️", image=self.img_mic_on, fg_color="#2b2b30", hover_color="#3a3a40")

    def toggle_camera(self):
        #Enciende o apaga la webcam del cliente local
        self.cam_running = not self.cam_running
        if self.cam_running:
            self.btn_cam.configure(text="" if self.img_cam_on else "📹", image=self.img_cam_on, fg_color="#2b2b30", hover_color="#3a3a40")
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': True})
            self.users_cam_state[self.user_session['id']] = True
            threading.Thread(target=self._camera_capture_loop, daemon=True).start()
        else:
            self.btn_cam.configure(text="" if self.img_cam_off else "❌\n📹", image=self.img_cam_off, fg_color="#e74c3c", hover_color="#c0392b")
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': False})
            self.users_cam_state[self.user_session['id']] = False
            self.update_camera_frame(self.user_session['id'], 'Tú', is_off=True)

    def _camera_capture_loop(self):
        #Bucle continuo de captura de frames mediante OpenCV (Corre en un hilo secundario)
        cap = cv2.VideoCapture(0)
        while self.cam_running and self.client and self.client.connected:
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (320, 240))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result, buffer = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                if result and self.cam_running:
                    binary_data = buffer.tobytes()
                    self.client.send_message({'type': 'CAMERA_FRAME', 'userId': self.user_session['id'], 'userName': self.user_session['nombres']}, binary_data)
                    self.gui_queue.put(({'type': 'LOCAL_CAMERA_FRAME', 'userId': self.user_session['id'], 'userName': 'Tú'}, binary_data))
            time.sleep(0.1)
        cap.release()

    def refresh_popup_list(self):
        # Actualiza y vuelve a dibujar la lista de usuarios pendientes en la sala de espera
        pending = getattr(self, 'pending_users', [])
        if hasattr(self, 'waiting_lbl') and self.waiting_lbl.winfo_exists(): self.waiting_lbl.configure(text=f"Sala de Espera ({len(pending)} pendientes)")
        if not hasattr(self, 'waiting_list_frame') or not self.waiting_list_frame.winfo_exists(): return
        for w in self.waiting_list_frame.winfo_children(): w.destroy()
        
        self.waiting_section_frame.pack_forget(); self.waiting_list_frame.pack_forget()
        self.active_section_lbl.pack_forget(); self.active_list_frame.pack_forget()
        if pending:
            self.waiting_section_frame.pack(fill="x", pady=(0, 10), padx=5); self.waiting_list_frame.pack(fill="x", padx=5, pady=5)
        self.active_section_lbl.pack(pady=(10, 5)); self.active_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        for user in pending:
            frame = ctk.CTkFrame(self.waiting_list_frame, fg_color="gray25")
            frame.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(frame, text=user['nombre'], font=("Inter", 11)).pack(side="left", padx=5)
            ctk.CTkButton(frame, text="Rechazar", width=55, height=22, font=("Inter", 10), fg_color="#e74c3c", hover_color="#c0392b", command=lambda u=user['id']: self.on_admit_user(u, False)).pack(side="right", padx=2)
            ctk.CTkButton(frame, text="Admitir", width=50, height=22, font=("Inter", 10), fg_color="#2ecc71", hover_color="#27ae60", command=lambda u=user['id']: self.on_admit_user(u, True)).pack(side="right", padx=2)

    def on_admit_user(self, user_id, accept):
        # Envía la acción del host (admitir/rechazar) al servidor
        self.client.send_message({'type': 'ADMIT_USER', 'codigoSala': self.current_room_code, 'userIdToAdmit': user_id, 'accept': accept})
        if hasattr(self, 'pending_users'):
            self.pending_users = [u for u in self.pending_users if u['id'] != user_id]
            self.refresh_popup_list()

    def toggle_participants_sidebar(self):
        # Muestra/Oculta la pestaña de participantes y cierra las demás
        self.show_participants = not self.show_participants
        if self.show_participants: self.show_chat = self.show_files = False
        self.update_sidebar_layout()

    def toggle_chat_sidebar(self):
        # Muestra/Oculta la pestaña del chat
        self.show_chat = not self.show_chat
        if self.show_chat: self.show_participants = self.show_files = False
        self.update_sidebar_layout()

    def toggle_files_sidebar(self):
        # Muestra/Oculta la pestaña de compartición de archivos
        self.show_files = not self.show_files
        if self.show_files: self.show_participants = self.show_chat = False
        self.update_sidebar_layout()

    def update_sidebar_layout(self):
        # Ajusta las dimensiones del grid principal y empaquetado del Sidebar según el panel visible
        if not hasattr(self, 'sidebar_frame') or not self.sidebar_frame.winfo_exists(): return
        self.sidebar_frame.pack_forget(); self.sidebar_participants.pack_forget(); self.sidebar_chat.pack_forget(); self.sidebar_files.pack_forget()
        
        self.btn_participants.configure(fg_color="#3a3a40" if self.show_participants else "transparent", hover_color="#4f4f55" if self.show_participants else "#2b2b30")
        self.btn_chat.configure(fg_color="#3a3a40" if self.show_chat else "transparent", hover_color="#4f4f55" if self.show_chat else "#2b2b30")
        self.btn_files.configure(fg_color="#3a3a40" if self.show_files else "transparent", hover_color="#4f4f55" if self.show_files else "#2b2b30")
        
        if not self.show_participants and not self.show_chat and not self.show_files: return
        self.sidebar_frame.pack(side="right", fill="both", padx=(5, 0))
        if self.show_participants: self.sidebar_participants.pack(side="top", fill="both", expand=True, pady=5)
        if self.show_chat: self.sidebar_chat.pack(side="top", fill="both", expand=True, pady=5)
        if self.show_files: self.sidebar_files.pack(side="top", fill="both", expand=True, pady=5)

    def refresh_participants_popup_list(self):
        # Vuelve a rellenar la lista de participantes activos en el panel correspondiente
        if not hasattr(self, 'active_list_frame') or not self.active_list_frame.winfo_exists(): return
        for w in self.active_list_frame.winfo_children(): w.destroy()
        
        for user in getattr(self, 'active_participants', []):
            frame = ctk.CTkFrame(self.active_list_frame, fg_color="gray20")
            frame.pack(fill="x", pady=2, padx=5)
            name_text = user['nombre'] + (" (Anfitrión)" if user.get('isHost') else (" (Tú)" if user['id'] == self.user_session['id'] else ""))
            ctk.CTkLabel(frame, text=name_text, font=("Inter", 11)).pack(side="left", padx=10, pady=4)
            if self.is_host and not user.get('isHost') and user['id'] != self.user_session['id']:
                ctk.CTkButton(frame, text="Expulsar", width=60, height=20, font=("Inter", 9), fg_color="#e74c3c", hover_color="#c0392b", command=lambda u=user['id']: self.on_kick_user(u)).pack(side="right", padx=5, pady=4)

    def on_kick_user(self, user_id):
        # Envía petición para expulsar a un usuario de la sala
        if messagebox.askyesno("Confirmar", "¿Estás seguro que deseas expulsar a este participante?"):
            self.client.send_message({'type': 'KICK_USER', 'userIdToKick': user_id})

    def toggle_participants_popup(self): self.toggle_participants_sidebar()
    def toggle_waiting_room_popup(self): self.toggle_participants_sidebar()

#  Punto de Entrada de la Aplicación 
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
