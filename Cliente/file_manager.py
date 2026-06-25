import os
import time
import threading
from tkinter import filedialog
import customtkinter as ctk

class FileManagerMixin:
    def on_share_file_click(self):
        file_path = filedialog.askopenfilename(title="Seleccionar archivo para compartir")
        if not file_path: return
        threading.Thread(target=self.bg_upload_file, args=(file_path, os.path.basename(file_path), os.path.getsize(file_path)), daemon=True).start()

    def bg_upload_file(self, file_path, file_name, file_size):
        try:
            self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': 0}, None))
            chunk_size = 4 * 1024 
            total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
            with open(file_path, 'rb') as f:
                for chunk_idx in range(total_chunks):
                    if not self.client or not getattr(self.client, 'connected', False): break
                    data = f.read(chunk_size)
                    self.client.send_message({
                        'type': 'FILE_CHUNK', 'fileName': file_name, 'chunkIndex': chunk_idx, 'totalChunks': total_chunks, 'isLast': chunk_idx == total_chunks - 1
                    }, binary_data=data)
                    self.gui_queue.put(({'type': 'UPLOAD_PROGRESS', 'fileName': file_name, 'progress': int(((chunk_idx + 1) / total_chunks) * 100)}, None))
                    time.sleep(0.01)
        except Exception as e:
            self.gui_queue.put(({'type': 'UPLOAD_ERROR', 'fileName': file_name, 'error': str(e)}, None))

    def add_file_to_list(self, file_id, file_name, sender_name):
        if not hasattr(self, 'files_frame') or not self.files_frame.winfo_exists(): return
        row = ctk.CTkFrame(self.files_frame, fg_color="#222222")
        row.pack(fill="x", pady=2, padx=5)
        ctk.CTkButton(row, text="Descargar", width=70, height=22, font=("Inter", 10), command=lambda f_id=file_id, f_name=file_name: self.on_download_file_click(f_id, f_name)).pack(side="left", padx=5, pady=4)
        ctk.CTkLabel(row, text=f"{file_name} ( {sender_name} )", font=("Inter", 11), anchor="w").pack(side="left", padx=8, pady=4)

    def on_download_file_click(self, file_id, file_name):
        file_path = filedialog.asksaveasfilename(title="Guardar archivo", initialfile=file_name, defaultextension=os.path.splitext(file_name)[1])
        if not file_path: return
        if not hasattr(self, 'active_downloads'): self.active_downloads = {}
        file_id_key = int(file_id)
        self.active_downloads[file_id_key] = {'filePath': file_path, 'fileName': file_name, 'expectedChunk': 0, 'fileObj': open(file_path, 'wb')}
        self.client.send_message({'type': 'FILE_DOWNLOAD_REQUEST', 'fileId': file_id_key})