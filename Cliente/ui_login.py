import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
from network_client import SocketsZoomClient

DEFAULT_HOST, DEFAULT_PORT = 'localhost', 8080
BG_WINDOW, BG_CARD, BORDER_CARD = "#0c0d0f", "#16181c", "#23272d"
COLOR_ACCENT, COLOR_ACCENT_HOVER, BG_ENTRY, COLOR_TEXT = "#7d5fff", "#575fcf", "#1e2124", "#ffffff"

class UILogin:
    def show_login_screen(self):
        self._clear_container()
        self.geometry("600x550")
        self.configure(fg_color=BG_WINDOW)
        card = ctk.CTkFrame(self.main_container, width=380, height=440, corner_radius=15, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        ctk.CTkFrame(card, height=4, fg_color=COLOR_ACCENT, corner_radius=0).place(relx=0, rely=0, relwidth=1)
        ctk.CTkLabel(card, text="Sockets Meet", font=("Inter", 24, "bold"), text_color=COLOR_TEXT).pack(pady=(40, 5))
        
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
        for attr in ['email_entry', 'pass_entry', 'ip_entry', 'btn_login', 'btn_reg_login']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.winfo_exists(): w.configure(state=state)

    def _set_register_state(self, state):
        for attr in ['reg_name', 'reg_email', 'reg_pass', 'reg_ip', 'btn_register', 'btn_back_reg']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.winfo_exists(): w.configure(state=state)

    def on_login_click(self):
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