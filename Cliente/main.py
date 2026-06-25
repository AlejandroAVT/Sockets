import queue
import time
import os
import io
from PIL import Image
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Importación de las Vistas (Carpeta Interfaz)
from UI.ui_login import UILogin
from UI.ui_lobby import UILobby
from UI.ui_meeting import UIMeeting

# Importación de la Red y Controladores (Carpeta Logica)
from Logic.network_client import SocketsZoomClient
from Logic.video_controller import VideoControllerMixin
from Logic.file_manager import FileManagerMixin

DEFAULT_PORT = 8080
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Herencia Múltiple: App absorbe todas las funciones de UI sin modificarlas
class App(ctk.CTk, UILogin, UILobby, UIMeeting,VideoControllerMixin, FileManagerMixin):
    def __init__(self):
        super().__init__()
        self.title("Prototipo Videoconferencia")
        self.geometry("600x550")
        self.minsize(500, 450)
        self.client, self.user_session = None, None
        self.gui_queue = queue.Queue()
        self.after(50, self._process_queue)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        self.show_login_screen()

    def on_logout_click(self):
        if self.client: self.client.disconnect()
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
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def _handle_ui_message(self, json_msg, bin_data):
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
                    # -- ARREGLO DE TAMAÑO DE RENDERIZADO --
                    ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=(480, 360))
                    self.update_camera_frame(u_id, json_msg.get('userName', 'Desconocido'), ctk_image=ctk_img)
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
        for widget in self.main_container.winfo_children(): widget.destroy()

    def on_closing(self):
        if self.client: self.client.disconnect()
        self.destroy()       

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()