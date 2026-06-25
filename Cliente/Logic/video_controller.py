import tkinter as tk
import threading
import time
import cv2

class VideoControllerMixin:
    def toggle_camera(self):
        self.cam_running = not getattr(self, 'cam_running', False)
        if self.cam_running:
            self.btn_cam.configure(text="" if self.img_cam_on else "📹", image=self.img_cam_on, fg_color="#2b2b30", hover_color="#3a3a40")
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': True})
            self.users_cam_state[self.user_session['id']] = True
            threading.Thread(target=self._camera_capture_loop, daemon=True).start()
        else:
            self.btn_cam.configure(text="" if getattr(self, 'img_cam_off', None) else "❌\n📹", image=getattr(self, 'img_cam_off', None), fg_color="#e74c3c", hover_color="#c0392b")
            self.client.send_message({'type': 'CAMERA_TOGGLE', 'state': False})
            self.users_cam_state[self.user_session['id']] = False
            self.update_camera_frame(self.user_session['id'], 'Tú', is_off=True)

    def _camera_capture_loop(self):
        cap = cv2.VideoCapture(0)
        while self.cam_running and self.client and self.client.connected:
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (640, 480))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result, buffer = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if result and self.cam_running:
                    binary_data = buffer.tobytes()
                    self.client.send_message({'type': 'CAMERA_FRAME', 'userId': self.user_session['id'], 'userName': self.user_session['nombres']}, binary_data)
                    self.gui_queue.put(({'type': 'LOCAL_CAMERA_FRAME', 'userId': self.user_session['id'], 'userName': 'Tú'}, binary_data))
            time.sleep(0.1)
        cap.release()
        
    def update_camera_frame(self, user_id, user_name, ctk_image=None, is_off=False):
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