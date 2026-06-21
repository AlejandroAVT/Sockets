import socket
import threading
import json
import struct
import queue
import time
import os
import tkinter as tk
from tkinter import messagebox
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
        
        lbl_details = ctk.CTkLabel(content, text=f"ID: {self.user_session['id']}\nCorreo: {self.user_session['correo']}\nRol: {self.user_session['rol']}", font=("Inter", 14), justify="left")
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
                self.show_host_panel(json_msg['codigoSala'], json_msg['nombreSala'])
            else:
                messagebox.showerror("Error", json_msg.get('message', 'Error al crear sala.'))
                
        elif msg_type == 'JOIN_ROOM_RESPONSE':
            if json_msg['success']:
                self.show_waiting_room_guest()
            else:
                messagebox.showerror("Error", json_msg.get('message', 'No se pudo ingresar.'))
                
        elif msg_type == 'WAITING_ROOM_UPDATE':
            if hasattr(self, 'waiting_frame'):
                self.update_waiting_list(json_msg.get('usuariosPendientes', []))
                
        elif msg_type == 'ADMIT_RESULT':
            if json_msg['success']:
                self.show_meeting_room(json_msg['codigoSala'])
            else:
                messagebox.showwarning("Acceso Denegado", json_msg.get('message', 'Has sido rechazado.'))
                self.show_lobby_screen()

    def _clear_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def on_closing(self):
        if self.client:
            self.client.disconnect()
        self.destroy()
        
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

        frame_create = ctk.CTkFrame(content, fg_color="transparent")
        frame_create.pack(pady=20, padx=20, fill="x")
        
        ctk.CTkLabel(frame_create, text="Crear una Nueva Sala", font=("Inter", 16, "bold")).pack(anchor="w")
        
        self.entry_room_code = ctk.CTkEntry(frame_create, placeholder_text="Código de Sala Único (Ej: REUNION1)")
        self.entry_room_code.pack(fill="x", pady=(10, 5))
        
        self.entry_room_name = ctk.CTkEntry(frame_create, placeholder_text="Nombre de la Sala")
        self.entry_room_name.pack(fill="x", pady=5)
        
        btn_create = ctk.CTkButton(frame_create, text="Crear Sala", command=self.on_create_room)
        btn_create.pack(pady=5, anchor="e")

        ctk.CTkFrame(content, height=2, fg_color="gray30").pack(fill="x", padx=20) # Divisor

        frame_join = ctk.CTkFrame(content, fg_color="transparent")
        frame_join.pack(pady=20, padx=20, fill="x")
        
        ctk.CTkLabel(frame_join, text="Unirse a una Sala", font=("Inter", 16, "bold")).pack(anchor="w")
        
        self.entry_join_code = ctk.CTkEntry(frame_join, placeholder_text="Ingrese el Código de la Sala")
        self.entry_join_code.pack(fill="x", pady=(10, 5))
        
        btn_join = ctk.CTkButton(frame_join, text="Solicitar Ingreso", command=self.on_join_room)
        btn_join.pack(pady=5, anchor="e")

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

    def on_join_room(self):
        code = self.entry_join_code.get().strip()
        
        if not code:
            messagebox.showerror("Error", "Debe proporcionar el código de la sala.")
            return
            
        self.client.send_message({
            'type': 'JOIN_ROOM_REQUEST',
            'codigoSala': code
        })

    def show_host_panel(self, room_code, room_name):
        self._clear_container()
        
        header = ctk.CTkFrame(self.main_container, height=60, corner_radius=8)
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header, text=f"Panel de Anfitrión - {room_name} ({room_code})", font=("Inter", 16, "bold")).pack(side="left", padx=20, pady=15)
        
        self.waiting_frame = ctk.CTkScrollableFrame(self.main_container, label_text="Sala de Espera (Pendientes)")
        self.waiting_frame.pack(fill="both", expand=True, pady=10)
        
        self.current_room_code = room_code

    def update_waiting_list(self, pending_users):
        for widget in self.waiting_frame.winfo_children():
            widget.destroy()
            
        if not pending_users:
            ctk.CTkLabel(self.waiting_frame, text="No hay usuarios en espera.").pack(pady=10)
            return

        for user in pending_users:
            user_frame = ctk.CTkFrame(self.waiting_frame)
            user_frame.pack(fill="x", pady=5, padx=5)
            
            ctk.CTkLabel(user_frame, text=user['nombre']).pack(side="left", padx=10)
            
            btn_accept = ctk.CTkButton(user_frame, text="Admitir", width=80, fg_color="#2ecc71", hover_color="#27ae60", 
                                     command=lambda u=user['id']: self.on_admit_user(u, True))
            btn_accept.pack(side="right", padx=5, pady=5)
            
            btn_reject = ctk.CTkButton(user_frame, text="Rechazar", width=80, fg_color="#e74c3c", hover_color="#c0392b",
                                     command=lambda u=user['id']: self.on_admit_user(u, False))
            btn_reject.pack(side="right", padx=5, pady=5)

    def on_admit_user(self, user_id, accept):
        self.client.send_message({
            'type': 'ADMIT_USER',
            'codigoSala': self.current_room_code,
            'userIdToAdmit': user_id,
            'accept': accept
        })

    def show_waiting_room_guest(self):
        self._clear_container()
        
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(content, text="Sala de Espera", font=("Inter", 24, "bold")).pack(pady=(80, 20))
        ctk.CTkLabel(content, text="Por favor, espere a que el anfitrión le permita el ingreso...", font=("Inter", 14)).pack()

    def show_meeting_room(self, room_code):
        self._clear_container()
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(content, text=f"Reunión Activa: {room_code}", font=("Inter", 24, "bold"), text_color="#3498db").pack(pady=(80, 20))
        ctk.CTkLabel(content, text="¡Has sido admitido! (El chat y cámara se implementarán en la Fase 4)", font=("Inter", 14)).pack()    

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
