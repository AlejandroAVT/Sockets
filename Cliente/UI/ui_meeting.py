import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import threading
import time
import os
import winsound
import cv2
from PIL import Image, ImageDraw
import io

class UIMeeting:
    def _create_control_icon(self, name, show_x=False):
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
            return None

    def rebuild_grid(self):
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

        # -- ARREGLO DE ESPACIOS FANTASMAS --
        for i in range(10): 
            self.cameras_frame.rowconfigure(i, weight=0)
            self.cameras_frame.columnconfigure(i, weight=0)

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
        
        self.sidebar_files = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        title_frame_files = ctk.CTkFrame(self.sidebar_files, fg_color="transparent")
        title_frame_files.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(title_frame_files, text="📂 Archivos Compartidos", font=("Inter", 14, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(title_frame_files, text="✕", width=28, height=28, fg_color="transparent", hover_color="#e74c3c", text_color="gray", font=("Inter", 12, "bold"), command=self.toggle_files_sidebar).pack(side="right", padx=10)
        self.files_frame = ctk.CTkScrollableFrame(self.sidebar_files, fg_color="#121214")
        self.files_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
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
        text = self.chat_entry.get().strip()
        if not text: return
        self.chat_entry.delete(0, tk.END)
        self.client.send_message({'type': 'CHAT_MESSAGE', 'message': text})

    def append_chat_message(self, sender, text, timestamp=""):
        self.chat_display.configure(state="normal")
        time_str = timestamp.split(' ')[1][:5] if timestamp and ' ' in timestamp else time.strftime('%H:%M')
        self.chat_display.insert(tk.END, f"[{time_str}] {sender}: {text}\n")
        self.chat_display.configure(state="disabled"); self.chat_display.see(tk.END)

    def on_leave_meeting(self):
        self.cam_running = False
        if self.client and self.client.connected: self.client.send_message({'type': 'LEAVE_ROOM'})
        self.show_lobby_screen(); self.geometry("600x550") 

    def toggle_mic(self):
        self.mic_muted = not self.mic_muted
        if self.mic_muted:
            self.btn_mic.configure(text="" if self.img_mic_off else "❌\n🎙️", image=self.img_mic_off, fg_color="#e74c3c", hover_color="#c0392b")
        else:
            self.btn_mic.configure(text="" if self.img_mic_on else "🎙️", image=self.img_mic_on, fg_color="#2b2b30", hover_color="#3a3a40")

    def refresh_popup_list(self):
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
        self.client.send_message({'type': 'ADMIT_USER', 'codigoSala': self.current_room_code, 'userIdToAdmit': user_id, 'accept': accept})
        if hasattr(self, 'pending_users'):
            self.pending_users = [u for u in self.pending_users if u['id'] != user_id]
            self.refresh_popup_list()

    def toggle_participants_sidebar(self):
        self.show_participants = not self.show_participants
        if self.show_participants: self.show_chat = self.show_files = False
        self.update_sidebar_layout()

    def toggle_chat_sidebar(self):
        self.show_chat = not self.show_chat
        if self.show_chat: self.show_participants = self.show_files = False
        self.update_sidebar_layout()

    def toggle_files_sidebar(self):
        self.show_files = not self.show_files
        if self.show_files: self.show_participants = self.show_chat = False
        self.update_sidebar_layout()

    def update_sidebar_layout(self):
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
        if messagebox.askyesno("Confirmar", "¿Estás seguro que deseas expulsar a este participante?"):
            self.client.send_message({'type': 'KICK_USER', 'userIdToKick': user_id})

    def toggle_participants_popup(self): self.toggle_participants_sidebar()
    def toggle_waiting_room_popup(self): self.toggle_participants_sidebar()