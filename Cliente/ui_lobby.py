import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

BG_WINDOW, BG_CARD, BORDER_CARD = "#0c0d0f", "#16181c", "#23272d"
COLOR_ACCENT, COLOR_ACCENT_HOVER, BG_ENTRY, COLOR_TEXT = "#7d5fff", "#575fcf", "#1e2124", "#ffffff"

class UILobby:
    def show_lobby_screen(self):
        self._clear_container()
        self.geometry("750x550")
        self.configure(fg_color=BG_WINDOW)
        header = ctk.CTkFrame(self.main_container, height=60, corner_radius=8, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1)
        header.pack(fill="x", pady=(0, 10))
        
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

        card_create = ctk.CTkFrame(left_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_create.pack(pady=(0, 15), fill="x", ipady=10)
        ctk.CTkLabel(card_create, text="➕ Crear una Nueva Sala", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=15, pady=(12, 5))
        self.entry_room_code = ctk.CTkEntry(card_create, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Código de Sala Único")
        self.entry_room_code.pack(fill="x", pady=5, padx=15)
        self.entry_room_name = ctk.CTkEntry(card_create, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Nombre de la Sala")
        self.entry_room_name.pack(fill="x", pady=5, padx=15)
        ctk.CTkButton(card_create, text="Crear Sala", height=32, corner_radius=8, font=("Inter", 12, "bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.on_create_room).pack(pady=(8, 5), padx=15, anchor="e")

        card_join = ctk.CTkFrame(left_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_join.pack(pady=5, fill="x", ipady=10)
        ctk.CTkLabel(card_join, text="🚪 Unirse a una Sala", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=15, pady=(12, 5))
        self.entry_join_code = ctk.CTkEntry(card_join, height=38, corner_radius=8, fg_color=BG_ENTRY, border_color=BORDER_CARD, placeholder_text="Ingrese el Código de la Sala")
        self.entry_join_code.pack(fill="x", pady=5, padx=15)
        ctk.CTkButton(card_join, text="Solicitar Ingreso", height=32, corner_radius=8, font=("Inter", 12, "bold"), fg_color="#2ecc71", hover_color="#27ae60", command=self.on_join_room).pack(pady=(8, 5), padx=15, anchor="e")

        card_rooms = ctk.CTkFrame(right_col, fg_color=BG_CARD, border_color=BORDER_CARD, border_width=1, corner_radius=12)
        card_rooms.pack(fill="both", expand=True)
        title_frame = ctk.CTkFrame(card_rooms, fg_color="transparent")
        title_frame.pack(fill="x", pady=(12, 5), padx=15)
        ctk.CTkLabel(title_frame, text="📁 Mis Salas Registradas", font=("Inter", 15, "bold"), text_color=COLOR_TEXT).pack(side="left")

        self.my_rooms_scroll = ctk.CTkScrollableFrame(card_rooms, fg_color="transparent")
        self.my_rooms_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_my_rooms()

    def refresh_my_rooms(self):
        if self.client and self.client.connected: self.client.send_message({'type': 'GET_MY_ROOMS'})

    def on_start_existing_room(self, code, name):
        if self.client and self.client.connected:
            self.is_host = True
            self.client.send_message({'type': 'CREATE_ROOM', 'codigoSala': code, 'nombre': name})

    def populate_my_rooms_list(self, salas):
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
            
            ctk.CTkButton(frame, text="🗑", width=32, height=32, corner_radius=6, fg_color="#e74c3c", hover_color="#c0392b", font=("Segoe UI Symbol", 12), anchor="center", command=lambda code=sala['CodigoSala']: self.on_delete_room_click(code)).pack(side="right", padx=(0, 8), pady=8)
            ctk.CTkButton(frame, text="▶", width=32, height=32, corner_radius=6, fg_color="#2ecc71", hover_color="#27ae60", font=("Segoe UI Symbol", 12), anchor="center", command=lambda code=sala['CodigoSala'], name=sala['Nombre']: self.on_start_existing_room(code, name)).pack(side="right", padx=8, pady=8)

    def on_create_room(self):
        code, name = self.entry_room_code.get().strip(), self.entry_room_name.get().strip()
        if not code or not name:
            messagebox.showerror("Error", "Debe proporcionar un código y un nombre para la sala.")
            return
        self.client.send_message({'type': 'CREATE_ROOM', 'codigoSala': code, 'nombre': name})

    def on_delete_room_click(self, code):
        if messagebox.askyesno("Confirmar", f"¿Deseas eliminar permanentemente la sala {code}?"):
            if self.client and self.client.connected: self.client.send_message({'type': 'DELETE_ROOM', 'codigoSala': code})

    def on_join_room(self):
        code = self.entry_join_code.get().strip()
        if not code:
            messagebox.showerror("Error", "Debe proporcionar el código de la sala.")
            return
        self.client.send_message({'type': 'JOIN_ROOM_REQUEST', 'codigoSala': code})

    def show_waiting_room_guest(self):
        self._clear_container()
        content = ctk.CTkFrame(self.main_container, corner_radius=12)
        content.pack(fill="both", expand=True, pady=10)
        ctk.CTkLabel(content, text="Sala de Espera", font=("Inter", 24, "bold")).pack(pady=(80, 20))
        ctk.CTkLabel(content, text="Por favor, espere a que el anfitrión le permita el ingreso...", font=("Inter", 14)).pack()
        ctk.CTkButton(content, text="Cancelar Espera", fg_color="#e74c3c", hover_color="#c0392b", command=self.on_cancel_join).pack(pady=20)

    def on_cancel_join(self):
        if self.client and self.client.connected: self.client.send_message({'type': 'CANCEL_JOIN_REQUEST'})
        self.show_lobby_screen()