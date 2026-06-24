import socket
import threading
import json
import struct
import queue
import time
import os
import winsound
import cv2
from PIL import Image
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

    def show_lobby_screen(self):
        self._clear_container()
        
        header = ctk.CTkFrame(self.main_container, height=60, corner_radius=8)
        header.pack(fill="x", pady=(0, 10))
        
        lbl_welcome = ctk.CTkLabel(header, text=f"Bienvenido, {self.user_session['nombres']}", font=("Inter", 16, "bold"))
        lbl_welcome.pack(side="left", padx=20, pady=15)
        
        btn_logout = ctk.CTkButton(header, text="Cerrar Sesión", width=100, height=30, fg_color="#e74c3c", hover_color="#c0392b", command=self.on_logout_click)
        btn_logout.pack(side="right", padx=20, pady=15)
        
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        
        lbl_info = ctk.CTkLabel(content, text="¡Inicio de Sesión Exitoso!", font=("Inter", 20, "bold"), text_color="#2ecc71")
        lbl_info.pack(pady=(60, 10))
        
        lbl_details = ctk.CTkLabel(content, text=f"ID: {self.user_session['id']}\nCorreo: {self.user_session['correo']}", font=("Inter", 14), justify="left")
        lbl_details.pack(pady=20)

        lbl_step_info = ctk.CTkLabel(content, text="Paso 4 Completado.\nEl host ahora puede ver su sesión de red TCP.\nProcederemos con la creación de salas en el siguiente paso.", font=("Inter", 12, "italic"), text_color="#7f8c8d")
        lbl_step_info.pack(pady=40)

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
                    self.add_file_to_list(f['IdArchivo'], f['NombreArchivo'], f['userName'])
                    
            else:
                messagebox.showerror("Error", json_msg.get('message', 'Error al crear sala.'))
                
        elif msg_type == 'JOIN_ROOM_RESPONSE':
            if json_msg['success']:
                self.show_waiting_room_guest()
            else:
                messagebox.showerror("Error", json_msg.get('message', 'No se pudo ingresar.'))
                
        elif msg_type == 'WAITING_ROOM_UPDATE':
            self.pending_users = json_msg.get('usuariosPendientes', [])
            if hasattr(self, 'btn_waiting') and self.btn_waiting.winfo_exists():
                self.btn_waiting.configure(text=f"Sala de Espera ({len(self.pending_users)})")
                if len(self.pending_users) > 0:
                    self.btn_waiting.configure(fg_color="#e74c3c", hover_color="#c0392b")
                else:
                    self.btn_waiting.configure(fg_color="#16a085", hover_color="#117a65")
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
                    self.add_file_to_list(f['IdArchivo'], f['NombreArchivo'], f['userName'])
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
            self.add_file_to_list(json_msg['fileId'], json_msg['fileName'], json_msg['senderName'])
            
        elif msg_type == 'FILE_DOWNLOAD_START':
            file_name = json_msg['fileName']
            file_size = json_msg['fileSize']
            print(f"Iniciando descarga de {file_name} ({file_size} bytes)")
            
        elif msg_type == 'FILE_DOWNLOAD_CHUNK':
            file_id = json_msg['fileId']
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
            file_id = json_msg.get('fileId')
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
            if hasattr(self, 'lbl_participants') and self.lbl_participants.winfo_exists():
                self.lbl_participants.configure(text=f"Participantes en sala: {len(self.active_participants)}")
            self.refresh_participants_popup_list()

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
            # Crear un nuevo marco para este usuario
            frame = ctk.CTkFrame(self.cameras_frame, fg_color="black", corner_radius=8)
            frame.pack(side="top", pady=5, padx=5, fill="x") 
            
            lbl_name = ctk.CTkLabel(frame, text=user_name, font=("Inter", 12, "bold"), fg_color="#333333", corner_radius=4)
            lbl_name.pack(anchor="nw", padx=5, pady=5)
            
            lbl_vid = ctk.CTkLabel(frame, text="Cámara apagada", width=320, height=240, fg_color="black")
            lbl_vid.pack(pady=5)
            
            self.camera_widgets[user_id] = {'frame': frame, 'label': lbl_vid}
        
        vid_label = self.camera_widgets[user_id]['label']
        
        if is_off:
            vid_label.configure(image="", text="Cámara apagada")
        elif ctk_image:
            vid_label.configure(image=ctk_image, text="")

    def show_meeting_room(self, room_code):
        self._clear_container()
        self.geometry("900x600") # Aumentar tamaño para el chat
        
        self.active_participants = []
        self.mic_muted = False
        
        # Header
        header = ctk.CTkFrame(self.main_container, height=50, corner_radius=6)
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header, text=f"Reunión: {room_code}", font=("Inter", 16, "bold")).pack(side="left", padx=15, pady=10)
        
        btn_leave = ctk.CTkButton(header, text="Salir", width=80, fg_color="#e74c3c", hover_color="#c0392b", command=self.on_leave_meeting)
        btn_leave.pack(side="right", padx=15, pady=10)
        
        btn_participants = ctk.CTkButton(header, text="Participantes", width=110, fg_color="#16a085", hover_color="#117a65", command=self.toggle_participants_popup)
        btn_participants.pack(side="right", padx=15, pady=10)
        
        if self.is_host:
            self.btn_waiting = ctk.CTkButton(header, text="Sala de Espera (0)", width=130, fg_color="#16a085", hover_color="#117a65", command=self.toggle_waiting_room_popup)
            self.btn_waiting.pack(side="right", padx=15, pady=10)
            self.pending_users = []
            
        # Main Layout (Video Placeholder + Chat)
        layout = ctk.CTkFrame(self.main_container, fg_color="transparent")
        layout.pack(fill="both", expand=True)
        
        # Panel izquierdo (Participantes / Cámara)
        self.video_panel = ctk.CTkFrame(layout, corner_radius=10, fg_color="#1e1e1e")
        self.video_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Etiqueta para contar participantes
        self.lbl_participants = ctk.CTkLabel(self.video_panel, text="Participantes en sala: 1", font=("Inter", 14, "bold"))
        self.lbl_participants.pack(pady=(10, 5))
        
        # Un ScrollableFrame para albergar MÚLTIPLES cámaras dinámicamente
        self.cameras_frame = ctk.CTkScrollableFrame(self.video_panel, fg_color="transparent")
        self.cameras_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.camera_widgets = {} 
        self.cam_running = False
        self.users_cam_state = {} # NUEVO: Filtro para frames fantasmas
        
        # Controls Bar at the bottom of video panel
        controls_frame = ctk.CTkFrame(self.video_panel, fg_color="transparent")
        controls_frame.pack(side="bottom", fill="x", pady=10)
        
        self.btn_mic = ctk.CTkButton(controls_frame, text="Silenciar Micrófono", command=self.toggle_mic, fg_color="#1f538d", hover_color="#14375e")
        self.btn_mic.pack(side="left", expand=True, padx=5)
        
        self.btn_cam = ctk.CTkButton(controls_frame, text="Activar Cámara", command=self.toggle_camera, fg_color="#1f538d", hover_color="#14375e")
        self.btn_cam.pack(side="right", expand=True, padx=5)
        
        # Panel derecho (Chat y Archivos)
        chat_panel = ctk.CTkFrame(layout, width=300, corner_radius=10)
        chat_panel.pack(side="right", fill="both", padx=(5, 0))
        
        ctk.CTkLabel(chat_panel, text="Chat de la Reunión", font=("Inter", 14, "bold")).pack(pady=(10, 5))
        
        self.chat_display = ctk.CTkTextbox(chat_panel, state="disabled", wrap="word", fg_color="#181818")
        self.chat_display.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        input_frame = ctk.CTkFrame(chat_panel, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Escribe un mensaje...")
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self.on_send_chat())
        self.chat_entry.focus()
        
        btn_send = ctk.CTkButton(input_frame, text="Enviar", width=60, command=self.on_send_chat)
        btn_send.pack(side="right")
        
        # Sección de Archivos
        ctk.CTkLabel(chat_panel, text="Archivos Compartidos", font=("Inter", 13, "bold")).pack(pady=(10, 5))
        
        self.files_frame = ctk.CTkScrollableFrame(chat_panel, height=120, fg_color="#181818")
        self.files_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        file_actions_frame = ctk.CTkFrame(chat_panel, fg_color="transparent")
        file_actions_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.lbl_upload_status = ctk.CTkLabel(file_actions_frame, text="", font=("Inter", 11, "italic"), text_color="#1abc9c")
        self.lbl_upload_status.pack(pady=(0, 5))
        
        btn_share_file = ctk.CTkButton(file_actions_frame, text="Compartir Archivo", fg_color="#16a085", hover_color="#117a65", command=self.on_share_file_click)
        btn_share_file.pack(fill="x")
 
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
        
        lbl = ctk.CTkLabel(row, text=f"{file_name} (por {sender_name})", font=("Inter", 11), anchor="w")
        lbl.pack(side="left", fill="x", expand=True, padx=8, pady=4)
        
        btn_dl = ctk.CTkButton(row, text="Descargar", width=70, height=22, font=("Inter", 10),
                               command=lambda f_id=file_id, f_name=file_name: self.on_download_file_click(f_id, f_name))
        btn_dl.pack(side="right", padx=5, pady=4)

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
            
        self.active_downloads[file_id] = {
            'filePath': file_path,
            'fileName': file_name,
            'expectedChunk': 0,
            'fileObj': open(file_path, 'wb')
        }
        
        self.client.send_message({
            'type': 'FILE_DOWNLOAD_REQUEST',
            'fileId': file_id
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
            self.btn_cam.configure(text="Detener Cámara", fg_color="#e74c3c", hover_color="#c0392b")
            
            # Avisar que encendí la cámara y guardar mi propio estado
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': True})
            self.users_cam_state[self.user_session['id']] = True
            
            threading.Thread(target=self._camera_capture_loop, daemon=True).start()
        else:
            self.cam_running = False
            self.btn_cam.configure(text="Activar Cámara", fg_color="#1f538d", hover_color="#14375e")
            
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

    def toggle_waiting_room_popup(self):
        if hasattr(self, 'popup_window') and self.popup_window.winfo_exists():
            self.popup_window.lift()
            return
            
        self.popup_window = ctk.CTkToplevel(self)
        self.popup_window.title("Sala de Espera (Pendientes)")
        self.popup_window.geometry("400x300")
        self.popup_window.transient(self)
        
        lbl = ctk.CTkLabel(self.popup_window, text="Usuarios en Sala de Espera", font=("Inter", 16, "bold"))
        lbl.pack(pady=10)
        
        self.popup_scroll = ctk.CTkScrollableFrame(self.popup_window)
        self.popup_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_popup_list()

    def refresh_popup_list(self):
        if not hasattr(self, 'popup_scroll') or not self.popup_scroll.winfo_exists():
            return
            
        for w in self.popup_scroll.winfo_children():
            w.destroy()
            
        pending = getattr(self, 'pending_users', [])
        if not pending:
            ctk.CTkLabel(self.popup_scroll, text="No hay usuarios en espera.").pack(pady=20)
            return
            
        for user in pending:
            frame = ctk.CTkFrame(self.popup_scroll)
            frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(frame, text=user['nombre']).pack(side="left", padx=10)
            
            btn_acc = ctk.CTkButton(frame, text="Admitir", width=70, fg_color="#2ecc71", hover_color="#27ae60",
                                     command=lambda u=user['id']: self.on_admit_user(u, True))
            btn_acc.pack(side="right", padx=5)
            
            btn_rej = ctk.CTkButton(frame, text="Rechazar", width=70, fg_color="#e74c3c", hover_color="#c0392b",
                                     command=lambda u=user['id']: self.on_admit_user(u, False))
            btn_rej.pack(side="right", padx=5)

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
            if hasattr(self, 'btn_waiting') and self.btn_waiting.winfo_exists():
                self.btn_waiting.configure(text=f"Sala de Espera ({len(self.pending_users)})")    

    def toggle_participants_popup(self):
        if hasattr(self, 'participants_popup') and self.participants_popup.winfo_exists():
            self.participants_popup.lift()
            return
            
        self.participants_popup = ctk.CTkToplevel(self)
        self.participants_popup.title("Participantes")
        self.participants_popup.geometry("400x300")
        self.participants_popup.transient(self)
        
        lbl = ctk.CTkLabel(self.participants_popup, text="Participantes de la Reunión", font=("Inter", 16, "bold"))
        lbl.pack(pady=10)
        
        self.participants_scroll = ctk.CTkScrollableFrame(self.participants_popup)
        self.participants_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_participants_popup_list()

    def refresh_participants_popup_list(self):
        if not hasattr(self, 'participants_scroll') or not self.participants_scroll.winfo_exists():
            return
            
        for w in self.participants_scroll.winfo_children():
            w.destroy()
            
        participants = getattr(self, 'active_participants', [])
        if not participants:
            ctk.CTkLabel(self.participants_scroll, text="No hay participantes en la sala.").pack(pady=20)
            return
            
        for user in participants:
            frame = ctk.CTkFrame(self.participants_scroll)
            frame.pack(fill="x", pady=5)
            
            name_text = user['nombre']
            if user.get('isHost'):
                name_text += " (Anfitrión)"
            elif user['id'] == self.user_session['id']:
                name_text += " (Tú)"
                
            ctk.CTkLabel(frame, text=name_text).pack(side="left", padx=10)
            
            # Si soy el anfitrión y el participante no es el anfitrión ni yo mismo
            if self.is_host and not user.get('isHost') and user['id'] != self.user_session['id']:
                btn_kick = ctk.CTkButton(frame, text="Expulsar", width=70, fg_color="#e74c3c", hover_color="#c0392b",
                                         command=lambda u=user['id']: self.on_kick_user(u))
                btn_kick.pack(side="right", padx=5)

    def on_kick_user(self, user_id):
        if messagebox.askyesno("Confirmar", "¿Estás seguro que deseas expulsar a este participante?"):
            self.client.send_message({
                'type': 'KICK_USER',
                'userIdToKick': user_id
            })

    def toggle_mic(self):
        if not self.mic_muted:
            self.mic_muted = True
            self.btn_mic.configure(text="Activar Micrófono", fg_color="#e74c3c", hover_color="#c0392b")
        else:
            self.mic_muted = False
            self.btn_mic.configure(text="Silenciar Micrófono", fg_color="#1f538d", hover_color="#14375e")

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
