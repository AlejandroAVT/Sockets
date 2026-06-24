import socket
import threading
import json
import struct
import queue
import time
import os
import winsound
import cv2
from PIL import Image, ImageDraw, ImageFont
import io
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8080
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SocketsZoomClient:
    def __init__(self, host, port, on_message_callback, on_disconnect_callback):
        self.host = host
        self.port = port
        self.on_message_callback = on_message_callback
        self.on_disconnect_callback = on_disconnect_callback
        
        self.sock = None
        self.connected = False
        self.receive_thread = None
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
            if self.connected:
                print(f"[ERROR CONEXIÓN] {e}")
            return False

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None

    def send_message(self, json_obj, binary_data=None):
        if not self.connected or not self.sock:
            return False
        
        try:
            json_str = json.dumps(json_obj)
            json_bytes = json_str.encode('utf-8')
            bin_len = len(binary_data) if binary_data else 0
            
            header = struct.pack('>II', len(json_bytes), bin_len)
            
            with self.write_lock:
                self.sock.sendall(header)
                self.sock.sendall(json_bytes)
                if binary_data:
                    self.sock.sendall(binary_data)
            return True
        except Exception as e:
            if self.connected:
                print(f"[ERROR ENVÍO] {e}")
            self.disconnect()
            self.on_disconnect_callback("Conexión perdida con el servidor.")
            return False

    def _receive_all(self, length):
        data = b''
        while len(data) < length:
            try:
                packet = self.sock.recv(length - len(data))
                if not packet:
                    return None
                data += packet
            except Exception as e:
                # Solo loguear si la desconexión no fue voluntaria
                if self.connected:
                    print(f"[ERROR RECUPERAR PAQUETE] {e}")
                return None
        return data

    def _receive_loop(self):
        while self.connected:
            try:
                header = self._receive_all(8)
                if not header:
                    break
                
                json_len, bin_len = struct.unpack('>II', header)
                
                json_bytes = self._receive_all(json_len)
                if not json_bytes:
                    break
                
                json_obj = json.loads(json_bytes.decode('utf-8'))
                
                bin_data = None
                if bin_len > 0:
                    bin_data = self._receive_all(bin_len)
                    if not bin_data:
                        break
                
                self.on_message_callback(json_obj, bin_data)
                
            except Exception as e:
                if self.connected:
                    print(f"[RECEIVE THREAD ERROR] {e}")
                break
        
        if self.connected:
            self.disconnect()
            self.on_disconnect_callback("Servidor desconectado.")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Prototipo Videoconferencia - Sockets Zoom (Paso 4)")
        self.geometry("600x550")
        self.minsize(500, 450)
        
        self.client = None
        self.user_session = None
        
        self.gui_queue = queue.Queue()
        self.after(50, self._process_queue)
        
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.show_login_screen()

    def _create_control_icon(self, name, show_x=False):
        try:
            img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            if name == "mic":
                # Dibujar cuerpo del micrófono (cápsula)
                draw.rounded_rectangle([(19, 10), (29, 26)], radius=5, fill="#ffffff")
                # Dibujar soporte en U
                draw.arc([(14, 18), (34, 32)], start=0, end=180, fill="#ffffff", width=3)
                # Dibujar pie vertical
                draw.line([(24, 32), (24, 38)], fill="#ffffff", width=3)
                # Dibujar base horizontal
                draw.line([(18, 38), (30, 38)], fill="#ffffff", width=3)
            elif name == "cam":
                # Dibujar cuerpo de la cámara
                draw.rounded_rectangle([(12, 16), (30, 32)], radius=3, fill="#ffffff")
                # Dibujar lente trapezoidal
                draw.polygon([(30, 20), (38, 16), (38, 32), (30, 28)], fill="#ffffff")
                
            if show_x:
                # Dibujar la equis encima
                draw.line([(10, 10), (38, 38)], fill="#e74c3c", width=4)
                draw.line([(38, 10), (10, 38)], fill="#e74c3c", width=4)
                
            return ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
        except Exception as e:
            print(f"[ICON ERROR] {e}")
            return None

    def show_login_screen(self):
        self._clear_container()
        self.geometry("600x550")
        
        card = ctk.CTkFrame(self.main_container, width=380, height=420, corner_radius=15)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        title = ctk.CTkLabel(card, text="Iniciar Sesión", font=("Inter", 24, "bold"))
        title.pack(pady=(40, 20))
        
        self.email_entry = ctk.CTkEntry(card, width=280, placeholder_text="Correo Electrónico")
        self.email_entry.pack(pady=10)
        
        self.pass_entry = ctk.CTkEntry(card, width=280, placeholder_text="Contraseña", show="*")
        self.pass_entry.pack(pady=10)
        
        self.ip_entry = ctk.CTkEntry(card, width=280, placeholder_text="Servidor IP (def: localhost)")
        self.ip_entry.insert(0, DEFAULT_HOST)
        self.ip_entry.pack(pady=10)
        
        self.btn_login = ctk.CTkButton(card, text="Ingresar", width=280, height=40, font=("Inter", 14, "bold"), command=self.on_login_click)
        self.btn_login.pack(pady=(20, 10))
        
        self.btn_reg_login = ctk.CTkButton(card, text="Registrar Nuevo Usuario", width=280, height=35, fg_color="transparent", border_width=1, font=("Inter", 12), command=self.show_register_screen)
        self.btn_reg_login.pack(pady=10)

    def show_register_screen(self):
        self._clear_container()
        self.geometry("600x550")
        
        card = ctk.CTkFrame(self.main_container, width=380, height=420, corner_radius=15)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        title = ctk.CTkLabel(card, text="Crear Cuenta", font=("Inter", 24, "bold"))
        title.pack(pady=(35, 15))
        
        self.reg_name = ctk.CTkEntry(card, width=280, placeholder_text="Nombres y Apellidos")
        self.reg_name.pack(pady=8)
        
        self.reg_email = ctk.CTkEntry(card, width=280, placeholder_text="Correo Electrónico")
        self.reg_email.pack(pady=8)
        
        self.reg_pass = ctk.CTkEntry(card, width=280, placeholder_text="Contraseña", show="*")
        self.reg_pass.pack(pady=8)
        
        self.reg_ip = ctk.CTkEntry(card, width=280, placeholder_text="Servidor IP (def: localhost)")
        self.reg_ip.insert(0, DEFAULT_HOST)
        self.reg_ip.pack(pady=8)
        
        self.btn_register = ctk.CTkButton(card, text="Registrarse", width=280, height=40, font=("Inter", 14, "bold"), fg_color="#2ecc71", hover_color="#27ae60", command=self.on_register_click)
        self.btn_register.pack(pady=(15, 10))
        
        self.btn_back_reg = ctk.CTkButton(card, text="Volver al Login", width=280, height=35, fg_color="transparent", border_width=1, font=("Inter", 12), command=self.show_login_screen)
        self.btn_back_reg.pack(pady=5)

    def _set_login_state(self, state):
        if hasattr(self, 'email_entry') and self.email_entry.winfo_exists():
            self.email_entry.configure(state=state)
        if hasattr(self, 'pass_entry') and self.pass_entry.winfo_exists():
            self.pass_entry.configure(state=state)
        if hasattr(self, 'ip_entry') and self.ip_entry.winfo_exists():
            self.ip_entry.configure(state=state)
        if hasattr(self, 'btn_login') and self.btn_login.winfo_exists():
            self.btn_login.configure(state=state)
        if hasattr(self, 'btn_reg_login') and self.btn_reg_login.winfo_exists():
            self.btn_reg_login.configure(state=state)

    def _set_register_state(self, state):
        if hasattr(self, 'reg_name') and self.reg_name.winfo_exists():
            self.reg_name.configure(state=state)
        if hasattr(self, 'reg_email') and self.reg_email.winfo_exists():
            self.reg_email.configure(state=state)
        if hasattr(self, 'reg_pass') and self.reg_pass.winfo_exists():
            self.reg_pass.configure(state=state)
        if hasattr(self, 'reg_ip') and self.reg_ip.winfo_exists():
            self.reg_ip.configure(state=state)
        if hasattr(self, 'btn_register') and self.btn_register.winfo_exists():
            self.btn_register.configure(state=state)
        if hasattr(self, 'btn_back_reg') and self.btn_back_reg.winfo_exists():
            self.btn_back_reg.configure(state=state)

    def on_login_click(self):
        if self.client and self.client.connected:
            return
            
        email = self.email_entry.get().strip()
        password = self.pass_entry.get()
        ip = self.ip_entry.get().strip() or 'localhost'
        
        if not email or not password:
            messagebox.showerror("Error", "Por favor completa todos los campos obligatorios.")
            return
            
        self._set_login_state("disabled")
        
        def connect_login():
            self.client = SocketsZoomClient(ip, DEFAULT_PORT, self.on_socket_message, self.on_socket_disconnect)
            if self.client.connect():
                self.client.send_message({
                    'type': 'LOGIN_REQUEST',
                    'correo': email,
                    'password': password
                })
            else:
                self.gui_queue.put(({'type': 'CONNECT_FAILED', 'context': 'login', 'ip': ip}, None))
                
        threading.Thread(target=connect_login, daemon=True).start()

    def on_register_click(self):
        if self.client and self.client.connected:
            return
            
        nombres = self.reg_name.get().strip()
        email = self.reg_email.get().strip()
        password = self.reg_pass.get()
        ip = self.reg_ip.get().strip() or 'localhost'
        
        if not nombres or not email or not password:
            messagebox.showerror("Error", "Todos los campos son requeridos para el registro.")
            return
            
        self._set_register_state("disabled")
        
        def connect_register():
            self.client = SocketsZoomClient(ip, DEFAULT_PORT, self.on_socket_message, self.on_socket_disconnect)
            if self.client.connect():
                self.client.send_message({
                    'type': 'REGISTER_REQUEST',
                    'nombres': nombres,
                    'correo': email,
                    'password': password
                })
            else:
                self.gui_queue.put(({'type': 'CONNECT_FAILED', 'context': 'register', 'ip': ip}, None))
                
        threading.Thread(target=connect_register, daemon=True).start()

    def on_logout_click(self):
        if self.client:
            self.client.disconnect()
        self.user_session = None
        self.show_login_screen()
    
    def on_socket_message(self, json_msg, bin_data):
        self.gui_queue.put((json_msg, bin_data))

    def on_socket_disconnect(self, message):
        self.gui_queue.put(({'type': 'LOCAL_DISCONNECT', 'message': message}, None))

    def _process_queue(self):
        try:
            while True:
                json_msg, bin_data = self.gui_queue.get_nowait()
                self._handle_ui_message(json_msg, bin_data)
                self.gui_queue.task_done()
        except queue.Empty:
            pass
        self.after(50, self._process_queue)

    def _handle_ui_message(self, json_msg, bin_data):
        msg_type = json_msg.get('type')
        
        if msg_type == 'CONNECT_FAILED':
            if json_msg.get('context') == 'login':
                self._set_login_state("normal")
            else:
                self._set_register_state("normal")
            messagebox.showerror("Error de conexión", f"No se pudo establecer conexión con el servidor TCP en {json_msg['ip']}:{DEFAULT_PORT}.")
            if self.client:
                self.client.disconnect()
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
                if self.client:
                    self.client.disconnect()
                    
        elif msg_type == 'REGISTER_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Registro Exitoso", json_msg['message'])
                self.show_login_screen()
            else:
                self._set_register_state("normal")
                messagebox.showerror("Error de Registro", json_msg['message'])
            if self.client:
                self.client.disconnect()
        
        elif msg_type == 'CREATE_ROOM_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Éxito", json_msg['message'])
                self.is_host = True
                self.current_room_code = json_msg['codigoSala']
                self.show_meeting_room(json_msg['codigoSala'])
                
                for msg in json_msg.get('chatHistory', []):
                    self.append_chat_message(msg['userName'], msg['Contenido'], msg['FechaEnvio'])
                    
                for f in json_msg.get('fileHistory', []):
                    file_id = int(f['IdArchivo']) if f.get('IdArchivo') is not None else 0
                    self.add_file_to_list(file_id, f['NombreArchivo'], f['userName'])
                    
            else:
                messagebox.showerror("Error", json_msg.get('message', 'Error al crear sala.'))
                
        elif msg_type == 'JOIN_ROOM_RESPONSE':
            if json_msg['success']:
                self.show_waiting_room_guest()
            else:
                messagebox.showerror("Error", json_msg.get('message', 'No se pudo ingresar.'))
                
        elif msg_type == 'WAITING_ROOM_UPDATE':
            self.pending_users = json_msg.get('usuariosPendientes', [])
            if len(self.pending_users) > 0 and not self.show_participants:
                if hasattr(self, 'btn_participants') and self.btn_participants.winfo_exists():
                    self.btn_participants.configure(fg_color="#e74c3c", hover_color="#c0392b")
            self.refresh_popup_list()
                
        elif msg_type == 'ADMIT_RESULT':
            if json_msg['success']:
                self.is_host = False
                self.current_room_code = json_msg['codigoSala']
                self.show_meeting_room(json_msg['codigoSala'])
                
                # Cargar historial de chat
                for msg in json_msg.get('chatHistory', []):
                    self.append_chat_message(msg['userName'], msg['Contenido'], msg['FechaEnvio'])
                    
                # Cargar historial de archivos
                for f in json_msg.get('fileHistory', []):
                    file_id = int(f['IdArchivo']) if f.get('IdArchivo') is not None else 0
                    self.add_file_to_list(file_id, f['NombreArchivo'], f['userName'])
            else:
                messagebox.showwarning("Acceso Denegado", json_msg.get('message', 'Has sido rechazado.'))
                self.show_lobby_screen()

        elif msg_type == 'CHAT_MESSAGE':
            sender = json_msg['userName']
            self.append_chat_message(sender, json_msg['message'], json_msg.get('sentAt', ''))
            if sender != self.user_session['nombres'] and sender != 'Sistema':
                try:
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception as e:
                    print(f"Error playing notification sound: {e}")

        elif msg_type == 'ROOM_CLOSED':
            messagebox.showinfo("Sala Cerrada", json_msg.get('message', 'La sala ha sido cerrada.'))
            self.show_lobby_screen()
            self.geometry("600x550")
            
        elif msg_type == 'MY_ROOMS_RESPONSE':
            if json_msg['success']:
                self.populate_my_rooms_list(json_msg['salas'])
            else:
                messagebox.showerror("Error", json_msg.get('message', 'Error al cargar tus salas.'))

        elif msg_type == 'FILE_SHARED':
            file_id = int(json_msg['fileId']) if json_msg.get('fileId') is not None else 0
            self.add_file_to_list(file_id, json_msg['fileName'], json_msg['senderName'])
            
        elif msg_type == 'FILE_DOWNLOAD_START':
            file_name = json_msg['fileName']
            file_size = json_msg['fileSize']
            print(f"Iniciando descarga de {file_name} ({file_size} bytes)")
            
        elif msg_type == 'FILE_DOWNLOAD_CHUNK':
            file_id = int(json_msg['fileId']) if json_msg.get('fileId') is not None else 0
            is_last = json_msg['isLast']
            
            download = getattr(self, 'active_downloads', {}).get(file_id)
            if download:
                if bin_data and len(bin_data) > 0:
                    download['fileObj'].write(bin_data)
                if is_last:
                    download['fileObj'].close()
                    del self.active_downloads[file_id]
                    messagebox.showinfo("Descarga Exitosa", f"El archivo \"{download['fileName']}\" se ha descargado correctamente.")
                    
        elif msg_type == 'FILE_DOWNLOAD_ERROR':
            file_id = int(json_msg['fileId']) if json_msg.get('fileId') is not None else None
            msg = json_msg.get('message', 'Error desconocido.')
            messagebox.showerror("Error de Descarga", f"No se pudo descargar el archivo: {msg}")
            if file_id and hasattr(self, 'active_downloads') and file_id in self.active_downloads:
                download = self.active_downloads[file_id]
                download['fileObj'].close()
                try:
                    os.remove(download['filePath'])
                except:
                    pass
                del self.active_downloads[file_id]
                
        elif msg_type == 'UPLOAD_PROGRESS':
            file_name = json_msg['fileName']
            progress = json_msg['progress']
            if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists():
                if progress < 100:
                    self.lbl_upload_status.configure(text=f"Subiendo {file_name}: {progress}%")
                else:
                    self.lbl_upload_status.configure(text="Subida completada con éxito.")
                    self.after(3000, lambda: self.lbl_upload_status.configure(text="") if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists() else None)
                    
        elif msg_type == 'UPLOAD_ERROR':
            file_name = json_msg['fileName']
            err = json_msg['error']
            messagebox.showerror("Error de Subida", f"Error al subir {file_name}: {err}")
            if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists():
                self.lbl_upload_status.configure(text="Error al subir archivo.")
                self.after(3000, lambda: self.lbl_upload_status.configure(text="") if hasattr(self, 'lbl_upload_status') and self.lbl_upload_status.winfo_exists() else None)

        elif msg_type == 'CAMERA_FRAME' or msg_type == 'LOCAL_CAMERA_FRAME':
            if bin_data:
                u_id = json_msg.get('userId')
                # BLOQUEO ANTI-LAG: Si sabemos que está apagada, ignoramos el frame retrasado
                if not self.users_cam_state.get(u_id, True):
                    return 
                    
                try:
                    image = Image.open(io.BytesIO(bin_data))
                    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(320, 240))
                    u_name = json_msg.get('userName', 'Desconocido')
                    self.update_camera_frame(u_id, u_name, ctk_image=ctk_image)
                except Exception as e:
                    pass

        elif msg_type == 'CAMERA_TOGGLE':
            u_id = json_msg.get('userId')
            state = json_msg.get('state')
            self.users_cam_state[u_id] = state # Guardamos el nuevo estado en memoria
            if not state: 
                self.update_camera_frame(u_id, "", is_off=True)
                
        elif msg_type == 'PARTICIPANTS_UPDATE':
            self.active_participants = json_msg.get('users', [])
            if hasattr(self, 'btn_participants') and self.btn_participants.winfo_exists():
                self.btn_participants.configure(text=f"👥 Participantes ({len(self.active_participants)})")
            self.refresh_participants_popup_list()
            self.rebuild_grid()

        elif msg_type == 'KICKED':
            messagebox.showwarning("Expulsado", json_msg.get('message', 'Has sido expulsado de la reunión.'))
            self.show_lobby_screen()
            self.geometry("600x550")
        
        elif msg_type == 'DELETE_ROOM_RESPONSE':
            if json_msg['success']:
                messagebox.showinfo("Eliminada", "Sala eliminada con éxito.")
                self.refresh_my_rooms() # Recargamos la lista automáticamente
            else:
                messagebox.showerror("Error", json_msg.get('message', 'No se pudo eliminar la sala.'))
                    
    def _clear_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def on_closing(self):
        if self.client:
            self.client.disconnect()
        self.destroy()
        
    def show_lobby_screen(self):
        self._clear_container()
        self.geometry("750x550")
        
        header = ctk.CTkFrame(self.main_container, height=60, corner_radius=8)
        header.pack(fill="x", pady=(0, 10))
        
        lbl_welcome = ctk.CTkLabel(header, text=f"Bienvenido, {self.user_session['nombres']}", font=("Inter", 16, "bold"))
        lbl_welcome.pack(side="left", padx=20, pady=15)
        
        btn_logout = ctk.CTkButton(header, text="Cerrar Sesión", width=100, height=30, fg_color="#e74c3c", hover_color="#c0392b", command=self.on_logout_click)
        btn_logout.pack(side="right", padx=20, pady=15)
        
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)

        # Diseño de dos columnas
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        # Columna Izquierda: Crear
        frame_create = ctk.CTkFrame(left_col, fg_color="transparent")
        frame_create.pack(pady=(0, 10), fill="x")
        
        ctk.CTkLabel(frame_create, text="Crear una Nueva Sala", font=("Inter", 16, "bold")).pack(anchor="w")
        
        self.entry_room_code = ctk.CTkEntry(frame_create, placeholder_text="Código de Sala Único (Ej: REUNION1)")
        self.entry_room_code.pack(fill="x", pady=(10, 5))
        
        self.entry_room_name = ctk.CTkEntry(frame_create, placeholder_text="Nombre de la Sala")
        self.entry_room_name.pack(fill="x", pady=5)
        
        btn_create = ctk.CTkButton(frame_create, text="Crear Sala", command=self.on_create_room)
        btn_create.pack(pady=5, anchor="e")

        ctk.CTkFrame(left_col, height=2, fg_color="gray30").pack(fill="x", pady=10) # Divisor

        # Columna Izquierda: Unirse
        frame_join = ctk.CTkFrame(left_col, fg_color="transparent")
        frame_join.pack(pady=10, fill="x")
        
        ctk.CTkLabel(frame_join, text="Unirse a una Sala", font=("Inter", 16, "bold")).pack(anchor="w")
        
        self.entry_join_code = ctk.CTkEntry(frame_join, placeholder_text="Ingrese el Código de la Sala")
        self.entry_join_code.pack(fill="x", pady=(10, 5))
        
        btn_join = ctk.CTkButton(frame_join, text="Solicitar Ingreso", command=self.on_join_room)
        btn_join.pack(pady=5, anchor="e")

        # Columna Derecha: Mis Salas Registradas
        title_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(title_frame, text="Mis Salas Registradas", font=("Inter", 16, "bold")).pack(side="left")
        
        btn_refresh = ctk.CTkButton(title_frame, text="🔄", width=30, height=26, fg_color="transparent", hover_color="gray30", command=self.refresh_my_rooms)
        btn_refresh.pack(side="right")

        self.my_rooms_scroll = ctk.CTkScrollableFrame(right_col, fg_color="#181818")
        self.my_rooms_scroll.pack(fill="both", expand=True)

        self.refresh_my_rooms()

    def refresh_my_rooms(self):
        if self.client and self.client.connected:
            self.client.send_message({
                'type': 'GET_MY_ROOMS'
            })

    def on_start_existing_room(self, code, name):
        if self.client and self.client.connected:
            self.is_host = True
            self.client.send_message({
                'type': 'CREATE_ROOM',
                'codigoSala': code,
                'nombre': name
            })

    def populate_my_rooms_list(self, salas):
        if not hasattr(self, 'my_rooms_scroll') or not self.my_rooms_scroll.winfo_exists():
            return
            
        for w in self.my_rooms_scroll.winfo_children():
            w.destroy()
            
        if not salas:
            ctk.CTkLabel(self.my_rooms_scroll, text="No tienes salas registradas.", font=("Inter", 12, "italic")).pack(pady=20)
            return
            
        for sala in salas:
            frame = ctk.CTkFrame(self.my_rooms_scroll, fg_color="gray25")
            frame.pack(fill="x", pady=4, padx=5)
            
            info_frame = ctk.CTkFrame(frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
            
            ctk.CTkLabel(info_frame, text=sala['CodigoSala'], font=("Inter", 13, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=sala['Nombre'], font=("Inter", 11), text_color="gray", anchor="w").pack(fill="x")
            
            btn_del = ctk.CTkButton(
                frame, 
                text="X", 
                width=30, 
                height=28,
                fg_color="#e74c3c", 
                hover_color="#c0392b",
                command=lambda code=sala['CodigoSala']: self.on_delete_room_click(code)
            )
            btn_del.pack(side="right", padx=(0, 5), pady=5)
            
            btn_start = ctk.CTkButton(
                frame, 
                text="Iniciar", 
                width=60, 
                height=28,
                fg_color="#2ecc71", 
                hover_color="#27ae60",
                command=lambda code=sala['CodigoSala'], name=sala['Nombre']: self.on_start_existing_room(code, name)
            )
            btn_start.pack(side="right", padx=10, pady=5)

    def on_create_room(self):
        code = self.entry_room_code.get().strip()
        name = self.entry_room_name.get().strip()
        
        if not code or not name:
            messagebox.showerror("Error", "Debe proporcionar un código y un nombre para la sala.")
            return
            
        self.client.send_message({
            'type': 'CREATE_ROOM',
            'codigoSala': code,
            'nombre': name
        })

    def on_delete_room_click(self, code):
        if messagebox.askyesno("Confirmar", f"¿Estás seguro que deseas eliminar permanentemente la sala {code}?"):
            if self.client and self.client.connected:
                self.client.send_message({
                    'type': 'DELETE_ROOM',
                    'codigoSala': code
                })

    def on_join_room(self):
        code = self.entry_join_code.get().strip()
        
        if not code:
            messagebox.showerror("Error", "Debe proporcionar el código de la sala.")
            return
            
        self.client.send_message({
            'type': 'JOIN_ROOM_REQUEST',
            'codigoSala': code
        })

    def show_waiting_room_guest(self):
        self._clear_container()
        
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(content, text="Sala de Espera", font=("Inter", 24, "bold")).pack(pady=(80, 20))
        ctk.CTkLabel(content, text="Por favor, espere a que el anfitrión le permita el ingreso...", font=("Inter", 14)).pack()
        
        btn_cancel = ctk.CTkButton(content, text="Cancelar Espera", fg_color="#e74c3c", hover_color="#c0392b", command=self.on_cancel_join)
        btn_cancel.pack(pady=20)

    def on_cancel_join(self):
        if self.client and self.client.connected:
            self.client.send_message({
                'type': 'CANCEL_JOIN_REQUEST'
            })
        self.show_lobby_screen()
        
    def update_camera_frame(self, user_id, user_name, ctk_image=None, is_off=False):
        if not hasattr(self, 'cameras_frame') or not self.cameras_frame.winfo_exists():
            return
            
        if user_id not in self.camera_widgets:
            self.rebuild_grid()
            
        if user_id not in self.camera_widgets:
            return
            
        vid_label = self.camera_widgets[user_id]['label']
        avatar = self.camera_widgets[user_id]['avatar']
        badge_frame = self.camera_widgets[user_id]['badge'].master
        
        if is_off:
            vid_label.place_forget()
            avatar.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        elif ctk_image:
            vid_label.configure(image=ctk_image)
            vid_label.place(relx=0.5, rely=0.5, relwidth=1, relheight=1, anchor=tk.CENTER)
            avatar.place_forget()
            badge_frame.lift()

    def rebuild_grid(self):
        active_ids = {u['id'] for u in self.active_participants}
        my_id = self.user_session['id']
        active_ids.add(my_id)
        
        # Eliminar widgets de usuarios que ya no están en la llamada
        for u_id in list(self.camera_widgets.keys()):
            if u_id not in active_ids:
                if 'frame' in self.camera_widgets[u_id]:
                    try:
                        self.camera_widgets[u_id]['frame'].destroy()
                    except:
                        pass
                del self.camera_widgets[u_id]

        participants_to_render = []
        # 1. Nosotros mismos
        participants_to_render.append((my_id, 'Tú'))
        
        # 2. Los demás
        for p in self.active_participants:
            if p['id'] != my_id:
                participants_to_render.append((p['id'], p['nombre']))

        num_participants = len(participants_to_render)
        if num_participants == 0:
            return

        # Calcular filas y columnas para el grid
        if num_participants == 1:
            cols = 1
            rows = 1
        elif num_participants == 2:
            cols = 2
            rows = 1
        elif num_participants <= 4:
            cols = 2
            rows = 2
        else:
            cols = 3
            rows = (num_participants + 2) // 3

        # Configurar pesos de grid para que las celdas se expandan equitativamente
        for i in range(rows):
            self.cameras_frame.rowconfigure(i, weight=1)
        for j in range(cols):
            self.cameras_frame.columnconfigure(j, weight=1)

        colors = ["#4a3b32", "#a15c71", "#344a5e", "#2c5e43", "#4e3b5e", "#5e4a3b"]

        # Crear o mover las tarjetas de los participantes
        for index, (u_id, u_name) in enumerate(participants_to_render):
            r = index // cols
            c = index % cols
            
            # Si la tarjeta no existe, la creamos
            if u_id not in self.camera_widgets:
                card_bg = colors[u_id % len(colors)]
                card = ctk.CTkFrame(self.cameras_frame, fg_color=card_bg, corner_radius=15)
                
                # Nombre en la esquina inferior izquierda (como badge)
                badge_bg = ctk.CTkFrame(card, fg_color="#121214", corner_radius=6)
                badge_bg.pack(side="bottom", anchor="sw", padx=15, pady=15)
                
                lbl_name = ctk.CTkLabel(badge_bg, text=u_name, font=("Inter", 12, "bold"), text_color="white")
                lbl_name.pack(padx=8, pady=4)
                
                # Contenedor para el avatar central / cámara apagada
                avatar_container = ctk.CTkFrame(card, fg_color="transparent")
                avatar_container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
                initials = "".join([part[0].upper() for part in u_name.split() if part])[:2]
                if not initials:
                    initials = "?"
                    
                avatar_circle = ctk.CTkFrame(avatar_container, width=100, height=100, corner_radius=50, fg_color="#2f3136")
                avatar_circle.pack()
                avatar_circle.pack_propagate(False)
                
                lbl_avatar = ctk.CTkLabel(avatar_circle, text=initials, font=("Inter", 32, "bold"), text_color="white")
                lbl_avatar.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
                lbl_vid = ctk.CTkLabel(card, text="")
                
                self.camera_widgets[u_id] = {
                    'frame': card, 
                    'label': lbl_vid, 
                    'avatar': avatar_container,
                    'badge': lbl_name
                }
            
            # Colocar en el grid
            card = self.camera_widgets[u_id]['frame']
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            
            # Asegurar visualización correcta inicial del avatar o del vídeo
            is_active = self.users_cam_state.get(u_id, False)
            if not is_active:
                self.camera_widgets[u_id]['label'].place_forget()
                self.camera_widgets[u_id]['avatar'].place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def show_meeting_room(self, room_code):
        self._clear_container()
        self.geometry("1100x700") # Aumentar tamaño para simular Zoom
        self.configure(fg_color="#0e0f12") # Background oscuro de Zoom
        
        self.active_participants = []
        self.mic_muted = True
        
        # Sidebar visibility flags
        self.show_participants = False
        self.show_chat = True # Por defecto mostrar el chat
        self.show_files = False # Por defecto no mostrar los archivos
        
        self.img_mic_on = self._create_control_icon("mic", False)
        self.img_mic_off = self._create_control_icon("mic", True)
        self.img_cam_on = self._create_control_icon("cam", False)
        self.img_cam_off = self._create_control_icon("cam", True)
        
        # Main Layout: divided horizontally
        layout = ctk.CTkFrame(self.main_container, fg_color="transparent")
        layout.pack(fill="both", expand=True)
        
        # Left Panel (Video Grid)
        self.video_panel = ctk.CTkFrame(layout, corner_radius=10, fg_color="#121212")
        self.video_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Video grid area inside the video panel
        self.cameras_frame = ctk.CTkFrame(self.video_panel, fg_color="transparent")
        self.cameras_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.camera_widgets = {} 
        self.cam_running = False
        self.users_cam_state = {} 
        
        # Right Sidebar Frame (collapsible container)
        self.sidebar_frame = ctk.CTkFrame(layout, width=320, corner_radius=10, fg_color="#1a1a1e")
        self.sidebar_frame.pack_propagate(False)
        
        # 1. Participants Sidebar Panel
        self.sidebar_participants = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        
        title_frame_part = ctk.CTkFrame(self.sidebar_participants, fg_color="transparent")
        title_frame_part.pack(fill="x", pady=(5, 10))
        lbl_part_title = ctk.CTkLabel(title_frame_part, text="👥 Participantes", font=("Inter", 14, "bold"))
        lbl_part_title.pack(side="left", padx=10)
        btn_close_part = ctk.CTkButton(
            title_frame_part, 
            text="✕", 
            width=28, 
            height=28, 
            fg_color="transparent", 
            hover_color="#e74c3c", 
            text_color="gray",
            font=("Inter", 12, "bold"),
            command=self.toggle_participants_sidebar
        )
        btn_close_part.pack(side="right", padx=10)
        
        # WAITING ROOM SECTION (For Host only)
        self.waiting_section_frame = ctk.CTkFrame(self.sidebar_participants, fg_color="#2b2b30", corner_radius=8)
        self.waiting_lbl = ctk.CTkLabel(self.waiting_section_frame, text="Sala de Espera (0 pendientes)", font=("Inter", 12, "bold"), text_color="#e74c3c")
        self.waiting_lbl.pack(pady=5)
        self.waiting_list_frame = ctk.CTkScrollableFrame(self.waiting_section_frame, height=100)
        
        # ACTIVE PARTICIPANTS SECTION
        self.active_section_lbl = ctk.CTkLabel(self.sidebar_participants, text="Participantes Activos", font=("Inter", 12, "bold"))
        self.active_section_lbl.pack(pady=(10, 5))
        
        self.active_list_frame = ctk.CTkScrollableFrame(self.sidebar_participants, fg_color="#121214")
        self.active_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 2. Chat Sidebar Panel
        self.sidebar_chat = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        
        title_frame_chat = ctk.CTkFrame(self.sidebar_chat, fg_color="transparent")
        title_frame_chat.pack(fill="x", pady=(5, 10))
        lbl_chat_title = ctk.CTkLabel(title_frame_chat, text="💬 Chat de la Reunión", font=("Inter", 14, "bold"))
        lbl_chat_title.pack(side="left", padx=10)
        btn_close_chat = ctk.CTkButton(
            title_frame_chat, 
            text="✕", 
            width=28, 
            height=28, 
            fg_color="transparent", 
            hover_color="#e74c3c", 
            text_color="gray",
            font=("Inter", 12, "bold"),
            command=self.toggle_chat_sidebar
        )
        btn_close_chat.pack(side="right", padx=10)
        
        self.chat_display = ctk.CTkTextbox(self.sidebar_chat, state="disabled", wrap="word", fg_color="#121214")
        self.chat_display.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        input_frame = ctk.CTkFrame(self.sidebar_chat, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Escribe un mensaje...")
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self.on_send_chat())
        self.chat_entry.focus()
        
        btn_send = ctk.CTkButton(input_frame, text="Enviar", width=60, command=self.on_send_chat)
        btn_send.pack(side="right")
        
        # 3. Files Sidebar Panel
        self.sidebar_files = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        
        title_frame_files = ctk.CTkFrame(self.sidebar_files, fg_color="transparent")
        title_frame_files.pack(fill="x", pady=(5, 10))
        lbl_files_title = ctk.CTkLabel(title_frame_files, text="📂 Archivos Compartidos", font=("Inter", 14, "bold"))
        lbl_files_title.pack(side="left", padx=10)
        btn_close_files = ctk.CTkButton(
            title_frame_files, 
            text="✕", 
            width=28, 
            height=28, 
            fg_color="transparent", 
            hover_color="#e74c3c", 
            text_color="gray",
            font=("Inter", 12, "bold"),
            command=self.toggle_files_sidebar
        )
        btn_close_files.pack(side="right", padx=10)
        
        self.files_frame = ctk.CTkScrollableFrame(self.sidebar_files, fg_color="#121214")
        self.files_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        # Habilitar scroll horizontal en la sección de archivos
        self.files_frame._parent_canvas.unbind("<Configure>")
        
        def update_files_frame_width(event=None):
            if not self.files_frame.winfo_exists():
                return
            canvas_width = self.files_frame._parent_canvas.winfo_width()
            req_width = self.files_frame.winfo_reqwidth()
            width_to_set = max(canvas_width, req_width)
            self.files_frame._parent_canvas.itemconfigure(self.files_frame._create_window_id, width=width_to_set)
            
        self.files_frame._parent_canvas.bind("<Configure>", lambda e: update_files_frame_width())
        self.files_frame.bind("<Configure>", lambda e: (
            self.files_frame._parent_canvas.configure(scrollregion=self.files_frame._parent_canvas.bbox("all")),
            update_files_frame_width()
        ), add="+")
        
        border_spacing = self.files_frame._apply_widget_scaling(
            self.files_frame._parent_frame.cget("corner_radius") + self.files_frame._parent_frame.cget("border_width")
        )
        h_sb = ctk.CTkScrollbar(master=self.files_frame._parent_frame, orientation="horizontal", command=self.files_frame._parent_canvas.xview)
        h_sb.grid(row=2, column=0, sticky="ew", padx=(border_spacing, 0), pady=(0, border_spacing))
        self.files_frame._parent_canvas.configure(xscrollcommand=h_sb.set)
        
        file_actions_frame = ctk.CTkFrame(self.sidebar_files, fg_color="transparent")
        file_actions_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.lbl_upload_status = ctk.CTkLabel(file_actions_frame, text="", font=("Inter", 11, "italic"), text_color="#1abc9c")
        self.lbl_upload_status.pack(pady=(0, 5))
        
        btn_share_file = ctk.CTkButton(
            file_actions_frame, 
            text="📤 Compartir Archivo", 
            fg_color="#2ecc71", 
            hover_color="#27ae60", 
            text_color="white",
            font=("Inter", 12, "bold"),
            command=self.on_share_file_click
        )
        btn_share_file.pack(fill="x")
        
        # Bottom Unified Control Bar (styled like Zoom)
        self.controls_bar = ctk.CTkFrame(self.main_container, height=60, fg_color="#16161a", corner_radius=10)
        self.controls_bar.pack(side="bottom", fill="x", pady=(10, 0))
        
        left_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        left_controls.pack(side="left", padx=15, fill="y")
        
        center_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        center_controls.place(relx=0.5, rely=0.5, anchor="center")
        
        right_controls = ctk.CTkFrame(self.controls_bar, fg_color="transparent")
        right_controls.pack(side="right", padx=15, fill="y")
        
        # Left controls: Mic & Camera
        self.btn_mic = ctk.CTkButton(
            left_controls, 
            text="" if self.img_mic_off else "❌\n🎙️",
            image=self.img_mic_off,
            width=50, 
            height=46,
            font=("Inter", 13),
            fg_color="#e74c3c",
            hover_color="#c0392b",
            command=self.toggle_mic
        )
        self.btn_mic.pack(side="left", padx=5, pady=7)
        
        self.btn_cam = ctk.CTkButton(
            left_controls, 
            text="" if self.img_cam_off else "❌\n📹",
            image=self.img_cam_off,
            width=50, 
            height=46,
            font=("Inter", 13),
            fg_color="#e74c3c",
            hover_color="#c0392b",
            command=self.toggle_camera
        )
        self.btn_cam.pack(side="left", padx=5, pady=7)
        
        # Center controls: Sidebar Toggles & Room details
        self.lbl_room_info = ctk.CTkLabel(center_controls, text=f"Reunión: {room_code}", font=("Inter", 13, "bold"), text_color="gray")
        self.lbl_room_info.pack(side="left", padx=15)
        
        self.btn_participants = ctk.CTkButton(
            center_controls,
            text="👥 Participantes",
            width=130,
            height=36,
            font=("Inter", 12),
            fg_color="transparent",
            hover_color="#2b2b30",
            command=self.toggle_participants_sidebar
        )
        self.btn_participants.pack(side="left", padx=5, pady=12)
        
        self.btn_chat = ctk.CTkButton(
            center_controls,
            text="💬 Chat",
            width=90,
            height=36,
            font=("Inter", 12),
            fg_color="#3a3a40",
            hover_color="#4f4f55",
            command=self.toggle_chat_sidebar
        )
        self.btn_chat.pack(side="left", padx=5, pady=12)

        self.btn_files = ctk.CTkButton(
            center_controls,
            text="📁 Archivos",
            width=110,
            height=36,
            font=("Inter", 12),
            fg_color="#3a3a40",
            hover_color="#4f4f55",
            command=self.toggle_files_sidebar
        )
        self.btn_files.pack(side="left", padx=5, pady=12)
        
        # Right controls: End / Leave Meeting
        btn_leave = ctk.CTkButton(
            right_controls, 
            text="Salir de la Reunión", 
            width=130, 
            height=36,
            font=("Inter", 12, "bold"),
            fg_color="#e74c3c", 
            hover_color="#c0392b", 
            command=self.on_leave_meeting
        )
        btn_leave.pack(side="right", padx=5, pady=12)
        
        if self.is_host:
            self.pending_users = []
            
        self.update_sidebar_layout()
        self.rebuild_grid()
        self.lbl_participants = ctk.CTkLabel(self.video_panel, text="")

    def on_send_chat(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
            
        self.chat_entry.delete(0, tk.END)
        self.client.send_message({
            'type': 'CHAT_MESSAGE',
            'message': text
        })

    def on_share_file_click(self):
        file_path = filedialog.askopenfilename(title="Seleccionar archivo para compartir")
        if not file_path:
            return
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        threading.Thread(target=self.bg_upload_file, args=(file_path, file_name, file_size), daemon=True).start()

    def bg_upload_file(self, file_path, file_name, file_size):
        try:
            self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': 0}, None))
            
            chunk_size = 4 * 1024 # 4KB
            total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
            
            with open(file_path, 'rb') as f:
                for chunk_idx in range(total_chunks):
                    if not self.client or not self.client.connected:
                        break
                        
                    data = f.read(chunk_size)
                    is_last = (chunk_idx == total_chunks - 1)
                    
                    self.client.send_message({
                        'type': 'FILE_CHUNK',
                        'fileName': file_name,
                        'chunkIndex': chunk_idx,
                        'totalChunks': total_chunks,
                        'isLast': is_last
                    }, binary_data=data)
                    
                    progress = int(((chunk_idx + 1) / total_chunks) * 100)
                    self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': progress}, None))
                    
                    time.sleep(0.01)
                    
        except Exception as e:
            self.gui_queue.put(({'type': 'UPLOAD_ERROR', 'fileName': file_name, 'error': str(e)}, None))

    def add_file_to_list(self, file_id, file_name, sender_name):
        if not hasattr(self, 'files_frame') or not self.files_frame.winfo_exists():
            return
        row = ctk.CTkFrame(self.files_frame, fg_color="#222222")
        row.pack(fill="x", pady=2, padx=5)
        
        btn_dl = ctk.CTkButton(row, text="Descargar", width=70, height=22, font=("Inter", 10),
                               command=lambda f_id=file_id, f_name=file_name: self.on_download_file_click(f_id, f_name))
        btn_dl.pack(side="left", padx=5, pady=4)
        
        lbl = ctk.CTkLabel(row, text=f"{file_name} (por {sender_name})", font=("Inter", 11), anchor="w")
        lbl.pack(side="left", padx=8, pady=4)

    def on_download_file_click(self, file_id, file_name):
        file_path = filedialog.asksaveasfilename(
            title="Guardar archivo",
            initialfile=file_name,
            defaultextension=os.path.splitext(file_name)[1]
        )
        if not file_path:
            return
            
        if not hasattr(self, 'active_downloads'):
            self.active_downloads = {}
            
        file_id_key = int(file_id)
        self.active_downloads[file_id_key] = {
            'filePath': file_path,
            'fileName': file_name,
            'expectedChunk': 0,
            'fileObj': open(file_path, 'wb')
        }
        
        self.client.send_message({
            'type': 'FILE_DOWNLOAD_REQUEST',
            'fileId': file_id_key
        })

    def append_chat_message(self, sender, text, timestamp=""):
        self.chat_display.configure(state="normal")
        
        time_str = ""
        if timestamp:
            
            if ' ' in timestamp:
                time_str = timestamp.split(' ')[1][:5]
            else:
                time_str = time.strftime('%H:%M')
        else:
            time_str = time.strftime('%H:%M')
            
        self.chat_display.insert(tk.END, f"[{time_str}] {sender}: {text}\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)

    def on_leave_meeting(self):
        
        self.cam_running = False
        
        if self.client and self.client.connected:
            self.client.send_message({
                'type': 'LEAVE_ROOM'
            })
        self.show_lobby_screen()
        self.geometry("600x550") # Resetear tamaño de ventana
        
    def toggle_camera(self):
        if not self.cam_running:
            self.cam_running = True
            if self.img_cam_on:
                self.btn_cam.configure(text="", image=self.img_cam_on, fg_color="#2b2b30", hover_color="#3a3a40")
            else:
                self.btn_cam.configure(text="📹", fg_color="#2b2b30", hover_color="#3a3a40")
            
            # Avisar que encendí la cámara y guardar mi propio estado
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': True})
            self.users_cam_state[self.user_session['id']] = True
            
            threading.Thread(target=self._camera_capture_loop, daemon=True).start()
        else:
            self.cam_running = False
            if self.img_cam_off:
                self.btn_cam.configure(text="", image=self.img_cam_off, fg_color="#e74c3c", hover_color="#c0392b")
            else:
                self.btn_cam.configure(text="❌\n📹", fg_color="#e74c3c", hover_color="#c0392b")
            
            # Avisar que apagué, guardar el estado y limpiar mi recuadro
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': False})
            self.users_cam_state[self.user_session['id']] = False
            self.update_camera_frame(self.user_session['id'], 'Tú', is_off=True)

    def _camera_capture_loop(self):
        cap = cv2.VideoCapture(0)
        
        while self.cam_running and self.client and self.client.connected:
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (320, 240))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                result, buffer = cv2.imencode('.jpg', frame_rgb, encode_param)
                
                if result and self.cam_running: 
                    binary_data = buffer.tobytes()
                    
                    self.client.send_message({
                        'type': 'CAMERA_FRAME',
                        'userId': self.user_session['id'],
                        'userName': self.user_session['nombres']
                    }, binary_data)
                    
                    self.gui_queue.put(({'type': 'LOCAL_CAMERA_FRAME', 'userId': self.user_session['id'], 'userName': 'Tú'}, binary_data))
            
            time.sleep(0.1) 
            
        cap.release()

    def refresh_popup_list(self):
        # Update waiting room badge count
        pending = getattr(self, 'pending_users', [])
        if hasattr(self, 'waiting_lbl') and self.waiting_lbl.winfo_exists():
            self.waiting_lbl.configure(text=f"Sala de Espera ({len(pending)} pendientes)")
            
        if not hasattr(self, 'waiting_list_frame') or not self.waiting_list_frame.winfo_exists():
            return
            
        for w in self.waiting_list_frame.winfo_children():
            w.destroy()
            
        # Unpack everything to control layout order
        self.waiting_section_frame.pack_forget()
        self.waiting_list_frame.pack_forget()
        self.active_section_lbl.pack_forget()
        self.active_list_frame.pack_forget()
        
        if pending:
            self.waiting_section_frame.pack(fill="x", pady=(0, 10), padx=5)
            self.waiting_list_frame.pack(fill="x", padx=5, pady=5)
            
        self.active_section_lbl.pack(pady=(10, 5))
        self.active_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        for user in pending:
            frame = ctk.CTkFrame(self.waiting_list_frame, fg_color="gray25")
            frame.pack(fill="x", pady=2, padx=2)
            
            ctk.CTkLabel(frame, text=user['nombre'], font=("Inter", 11)).pack(side="left", padx=5)
            
            btn_rej = ctk.CTkButton(frame, text="Rechazar", width=55, height=22, font=("Inter", 10), fg_color="#e74c3c", hover_color="#c0392b",
                                     command=lambda u=user['id']: self.on_admit_user(u, False))
            btn_rej.pack(side="right", padx=2)
            
            btn_acc = ctk.CTkButton(frame, text="Admitir", width=50, height=22, font=("Inter", 10), fg_color="#2ecc71", hover_color="#27ae60",
                                     command=lambda u=user['id']: self.on_admit_user(u, True))
            btn_acc.pack(side="right", padx=2)

    def on_admit_user(self, user_id, accept):
        self.client.send_message({
            'type': 'ADMIT_USER',
            'codigoSala': self.current_room_code,
            'userIdToAdmit': user_id,
            'accept': accept
        })
        if hasattr(self, 'pending_users'):
            self.pending_users = [u for u in self.pending_users if u['id'] != user_id]
            self.refresh_popup_list()

    def toggle_participants_sidebar(self):
        self.show_participants = not self.show_participants
        if self.show_participants:
            self.show_chat = False
            self.show_files = False
        self.update_sidebar_layout()

    def toggle_chat_sidebar(self):
        self.show_chat = not self.show_chat
        if self.show_chat:
            self.show_participants = False
            self.show_files = False
        self.update_sidebar_layout()

    def toggle_files_sidebar(self):
        self.show_files = not self.show_files
        if self.show_files:
            self.show_participants = False
            self.show_chat = False
        self.update_sidebar_layout()

    def update_sidebar_layout(self):
        if not hasattr(self, 'sidebar_frame') or not self.sidebar_frame.winfo_exists():
            return
            
        self.sidebar_frame.pack_forget()
        self.sidebar_participants.pack_forget()
        self.sidebar_chat.pack_forget()
        self.sidebar_files.pack_forget()
        
        if self.show_participants:
            self.btn_participants.configure(fg_color="#3a3a40", hover_color="#4f4f55")
        else:
            self.btn_participants.configure(fg_color="transparent", hover_color="#2b2b30")
            
        if self.show_chat:
            self.btn_chat.configure(fg_color="#3a3a40", hover_color="#4f4f55")
        else:
            self.btn_chat.configure(fg_color="transparent", hover_color="#2b2b30")

        if self.show_files:
            self.btn_files.configure(fg_color="#3a3a40", hover_color="#4f4f55")
        else:
            self.btn_files.configure(fg_color="transparent", hover_color="#2b2b30")
            
        if not self.show_participants and not self.show_chat and not self.show_files:
            return
            
        self.sidebar_frame.pack(side="right", fill="both", padx=(5, 0))
        
        if self.show_participants:
            self.sidebar_participants.pack(side="top", fill="both", expand=True, pady=5)
        if self.show_chat:
            self.sidebar_chat.pack(side="top", fill="both", expand=True, pady=5)
        if self.show_files:
            self.sidebar_files.pack(side="top", fill="both", expand=True, pady=5)

    def refresh_participants_popup_list(self):
        if not hasattr(self, 'active_list_frame') or not self.active_list_frame.winfo_exists():
            return
            
        for w in self.active_list_frame.winfo_children():
            w.destroy()
            
        participants = getattr(self, 'active_participants', [])
        
        for user in participants:
            frame = ctk.CTkFrame(self.active_list_frame, fg_color="gray20")
            frame.pack(fill="x", pady=2, padx=5)
            
            name_text = user['nombre']
            if user.get('isHost'):
                name_text += " (Anfitrión)"
            elif user['id'] == self.user_session['id']:
                name_text += " (Tú)"
                
            ctk.CTkLabel(frame, text=name_text, font=("Inter", 11)).pack(side="left", padx=10, pady=4)
            
            if self.is_host and not user.get('isHost') and user['id'] != self.user_session['id']:
                btn_kick = ctk.CTkButton(frame, text="Expulsar", width=60, height=20, font=("Inter", 9), fg_color="#e74c3c", hover_color="#c0392b",
                                         command=lambda u=user['id']: self.on_kick_user(u))
                btn_kick.pack(side="right", padx=5, pady=4)

    def on_kick_user(self, user_id):
        if messagebox.askyesno("Confirmar", "¿Estás seguro que deseas expulsar a este participante?"):
            self.client.send_message({
                'type': 'KICK_USER',
                'userIdToKick': user_id
            })

    def toggle_mic(self):
        if not self.mic_muted:
            self.mic_muted = True
            if self.img_mic_off:
                self.btn_mic.configure(text="", image=self.img_mic_off, fg_color="#e74c3c", hover_color="#c0392b")
            else:
                self.btn_mic.configure(text="❌\n🎙️", fg_color="#e74c3c", hover_color="#c0392b")
        else:
            self.mic_muted = False
            if self.img_mic_on:
                self.btn_mic.configure(text="", image=self.img_mic_on, fg_color="#2b2b30", hover_color="#3a3a40")
            else:
                self.btn_mic.configure(text="🎙️", fg_color="#2b2b30", hover_color="#3a3a40")

    def toggle_participants_popup(self):
        self.toggle_participants_sidebar()
        
    def toggle_waiting_room_popup(self):
        self.toggle_participants_sidebar()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
