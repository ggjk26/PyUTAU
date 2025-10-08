# embedded_utau/gui_component.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import zipfile
import tempfile
import os
from pathlib import Path
import numpy as np

# 灵活的导入方式
try:
    # 优先尝试绝对导入
    from embedded_utau.synthesis_engine import SynthesisEngine
    from embedded_utau.voice_library import VoiceLibrary
    from embedded_utau.note import Note, Track
    from embedded_utau.project import Project, ProjectSettings
    from embedded_utau.ust_parser import USTParser
except ImportError:
    # 后备：相对导入
    try:
        from .synthesis_engine import SynthesisEngine
        from .voice_library import VoiceLibrary
        from .note import Note, Track
        from .project import Project, ProjectSettings
        from .ust_parser import USTParser
    except ImportError as e:
        print(f"导入失败: {e}")
        raise

class PyUTAUComponent(ttk.Frame):
    """UTAU 组件"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.engine = SynthesisEngine()
        self.project = Project("未命名项目", ProjectSettings(total_duration=120.0))
        
        # 编辑状态
        self.edit_mode = "write"
        self.selected_note_indices = {}  # 音轨索引 -> 音符索引
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_type = None
        self.current_zoom = 1.0  # 缩放级别
        
        # 临时文件管理
        self.temp_dirs = {}  # 音源库路径 -> 临时目录
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置扩展的用户界面"""
        # 创建主面板
        main_panel = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 顶部控制面板
        top_frame = ttk.Frame(main_panel)
        main_panel.add(top_frame, weight=0)
        
        self.setup_top_controls(top_frame)
        
        # 中间音轨和钢琴卷帘面板
        middle_panel = ttk.PanedWindow(main_panel, orient=tk.HORIZONTAL)
        main_panel.add(middle_panel, weight=1)
        
        # 音轨列表面板
        tracks_frame = ttk.Frame(middle_panel, width=200)
        middle_panel.add(tracks_frame, weight=0)
        
        self.setup_tracks_panel(tracks_frame)
        
        # 钢琴卷帘面板
        piano_frame = ttk.Frame(middle_panel)
        middle_panel.add(piano_frame, weight=1)
        
        self.setup_piano_roll(piano_frame)
        
        # 底部状态栏
        bottom_frame = ttk.Frame(main_panel)
        main_panel.add(bottom_frame, weight=0)
        
        self.setup_bottom_controls(bottom_frame)
    
    def setup_top_controls(self, parent):
        """设置顶部控制面板"""
        # 项目控制
        project_frame = ttk.LabelFrame(parent, text="项目", padding=5)
        project_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(project_frame, text="新建项目", command=self.new_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(project_frame, text="打开项目", command=self.open_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(project_frame, text="保存项目", command=self.save_project).pack(side=tk.LEFT, padx=2)
        
        # 添加 UST 导入导出按钮
        ttk.Button(project_frame, text="导入UST", command=self.import_ust).pack(side=tk.LEFT, padx=2)
        ttk.Button(project_frame, text="导出UST", command=self.export_ust).pack(side=tk.LEFT, padx=2)
        
        # 项目信息
        self.project_name_var = tk.StringVar(value="未命名项目")
        ttk.Label(project_frame, textvariable=self.project_name_var).pack(side=tk.LEFT, padx=10)
        
        # 编辑模式控制
        mode_frame = ttk.Frame(parent)
        mode_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT, padx=2)
        
        self.mode_var = tk.StringVar(value="write")
        ttk.Radiobutton(mode_frame, text="编写", variable=self.mode_var, 
                       value="write", command=self.on_mode_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="编辑", variable=self.mode_var, 
                       value="edit", command=self.on_mode_change).pack(side=tk.LEFT, padx=2)
        
        # 缩放控制
        zoom_frame = ttk.Frame(mode_frame)
        zoom_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Button(zoom_frame, text="缩小", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="重置", command=self.zoom_reset).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="放大", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
    
    def setup_tracks_panel(self, parent):
        """设置音轨列表面板"""
        # 音轨控制
        track_controls = ttk.Frame(parent)
        track_controls.pack(fill=tk.X, pady=2)
        
        ttk.Button(track_controls, text="添加音轨", command=self.add_track).pack(side=tk.LEFT, padx=2)
        ttk.Button(track_controls, text="删除音轨", command=self.remove_track).pack(side=tk.LEFT, padx=2)
        
        # 音轨列表
        tracks_list_frame = ttk.LabelFrame(parent, text="音轨列表")
        tracks_list_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # 创建树形视图显示音轨
        columns = ("name", "library", "mute", "solo")
        self.tracks_tree = ttk.Treeview(tracks_list_frame, columns=columns, show="headings", height=10)
        
        self.tracks_tree.heading("name", text="音轨名称")
        self.tracks_tree.heading("library", text="音源库")
        self.tracks_tree.heading("mute", text="静音")
        self.tracks_tree.heading("solo", text="独奏")
        
        self.tracks_tree.column("name", width=80)
        self.tracks_tree.column("library", width=80)
        self.tracks_tree.column("mute", width=40)
        self.tracks_tree.column("solo", width=40)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(tracks_list_frame, orient=tk.VERTICAL, command=self.tracks_tree.yview)
        self.tracks_tree.configure(yscrollcommand=scrollbar.set)
        
        self.tracks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定事件
        self.tracks_tree.bind("<<TreeviewSelect>>", self.on_track_select)
        self.tracks_tree.bind("<Double-1>", self.on_track_double_click)
    
    def setup_piano_roll(self, parent):
        """设置钢琴卷帘面板"""
        # 钢琴卷帘控制
        piano_controls = ttk.Frame(parent)
        piano_controls.pack(fill=tk.X, pady=2)
        
        ttk.Button(piano_controls, text="播放", command=self.play).pack(side=tk.LEFT, padx=2)
        ttk.Button(piano_controls, text="停止", command=self.stop).pack(side=tk.LEFT, padx=2)
        ttk.Button(piano_controls, text="导出", command=self.export_audio).pack(side=tk.LEFT, padx=2)
        ttk.Button(piano_controls, text="清除", command=self.clear_notes).pack(side=tk.LEFT, padx=2)
        
        # 钢琴卷帘画布区域
        piano_canvas_frame = ttk.Frame(parent)
        piano_canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建带滚动条的画布
        self.setup_piano_canvas(piano_canvas_frame)
    
    def setup_piano_canvas(self, parent):
        """设置钢琴卷帘画布和滚动条"""
        # 垂直滚动条（钢琴键盘）
        v_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 水平滚动条（时间轴）
        h_scrollbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 画布
        self.canvas = tk.Canvas(
            parent, 
            bg='white', 
            width=800, 
            height=400,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set,
            scrollregion=(0, 0, 6000, 2000)  # 更宽的滚动区域
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.canvas.yview)
        h_scrollbar.config(command=self.canvas.xview)
        
        # 绑定事件
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<MouseWheel>", self.on_canvas_scroll)
    
    def setup_bottom_controls(self, parent):
        """设置底部状态栏"""
        self.status_var = tk.StringVar(value="就绪 - 编写模式")
        status_label = ttk.Label(parent, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 时间显示
        self.time_var = tk.StringVar(value="00:00 / 02:00")
        time_label = ttk.Label(parent, textvariable=self.time_var)
        time_label.pack(side=tk.RIGHT, padx=10)
    
    def on_mode_change(self):
        """模式改变"""
        self.edit_mode = self.mode_var.get()
        self.status_var.set(f"就绪 - {'编写' if self.edit_mode == 'write' else '编辑'}模式")
        self.redraw_all()
    
    def add_track(self):
        """添加音轨"""
        track_name = f"音轨 {len(self.project.tracks) + 1}"
        track = self.project.add_track(track_name)
        
        # 添加到树形视图
        self.tracks_tree.insert("", "end", values=(
            track.name, 
            Path(track.voice_library_path).name if track.voice_library_path else "无",
            "✓" if track.muted else "",
            "✓" if track.solo else ""
        ))
        
        self.status_var.set(f"已添加音轨: {track_name}")
    
    def remove_track(self):
        """删除选中音轨"""
        selection = self.tracks_tree.selection()
        if selection:
            for item in selection:
                index = self.tracks_tree.index(item)
                self.project.remove_track(index)
                self.tracks_tree.delete(item)
            self.redraw_all()
            self.status_var.set("已删除选中音轨")
        else:
            messagebox.showwarning("警告", "请先选择一个音轨")
    
    def on_track_select(self, event):
        """音轨选择事件"""
        selection = self.tracks_tree.selection()
        if selection:
            item = selection[0]
            index = self.tracks_tree.index(item)
            self.project.set_current_track(index)
            self.redraw_all()
    
    def on_track_double_click(self, event):
        """音轨双击事件 - 设置音源库"""
        selection = self.tracks_tree.selection()
        if selection:
            item = selection[0]
            index = self.tracks_tree.index(item)
            track = self.project.tracks[index]
            self.set_track_voice_library(track, item)
    
    def set_track_voice_library(self, track, tree_item):
        """为音轨设置音源库"""
        zip_path = filedialog.askopenfilename(
            title=f"为音轨 '{track.name}' 选择音源库",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        
        if zip_path:
            try:
                # 创建临时目录解压ZIP
                temp_dir = tempfile.mkdtemp(prefix="pyutau_")
                self.temp_dirs[zip_path] = temp_dir
                
                # 解压ZIP文件
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # 设置音轨的音源库路径
                track.voice_library_path = temp_dir
                
                # 更新树形视图
                voice_lib = VoiceLibrary(Path(temp_dir))
                lib_name = voice_lib.get_library_name()
                self.tracks_tree.set(tree_item, "library", lib_name)
                
                self.status_var.set(f"音轨 '{track.name}' 已加载音源库: {lib_name}")
                
            except Exception as e:
                messagebox.showerror("错误", f"加载音源库失败: {e}")
    
    def zoom_in(self):
        """放大"""
        self.current_zoom = min(4.0, self.current_zoom * 1.2)
        self.redraw_all()
    
    def zoom_out(self):
        """缩小"""
        self.current_zoom = max(0.25, self.current_zoom / 1.2)
        self.redraw_all()
    
    def zoom_reset(self):
        """重置缩放"""
        self.current_zoom = 1.0
        self.redraw_all()
    
    def on_canvas_scroll(self, event):
        """画布滚动事件"""
        if event.delta:
            scroll = -1 if event.delta < 0 else 1
        else:
            scroll = -1 if event.num == 5 else 1
        
        self.canvas.yview_scroll(scroll, "units")
        return "break"
    
    def new_project(self):
        """新建项目"""
        self.project = Project("新项目", ProjectSettings(total_duration=120.0))
        self.tracks_tree.delete(*self.tracks_tree.get_children())
        self.project_name_var.set("新项目")
        self.redraw_all()
        self.status_var.set("已创建新项目")
    
    def open_project(self):
        """打开项目"""
        file_path = filedialog.askopenfilename(
            title="打开项目",
            filetypes=[("PyUTAU Project", "*.putau"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.project.load_project(Path(file_path))
                self.project_name_var.set(self.project.name)
                
                # 更新音轨列表
                self.tracks_tree.delete(*self.tracks_tree.get_children())
                for track in self.project.tracks:
                    self.tracks_tree.insert("", "end", values=(
                        track.name,
                        Path(track.voice_library_path).name if track.voice_library_path else "无",
                        "✓" if track.muted else "",
                        "✓" if track.solo else ""
                    ))
                
                self.redraw_all()
                self.status_var.set(f"已打开项目: {self.project.name}")
                
            except Exception as e:
                messagebox.showerror("错误", f"打开项目失败: {e}")
    
    def save_project(self):
        """保存项目"""
        file_path = filedialog.asksaveasfilename(
            title="保存项目",
            defaultextension=".putau",
            filetypes=[("PyUTAU Project", "*.putau"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.project.save_project(Path(file_path))
                self.status_var.set(f"项目已保存: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存项目失败: {e}")
    
    def import_ust(self):
        """导入 UST 文件"""
        file_path = filedialog.askopenfilename(
            title="导入 UST 文件",
            filetypes=[
                ("UST files", "*.ust"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.status_var.set("正在导入 UST 文件...")
                self.update()
                
                # 创建 UST 解析器
                parser = USTParser()
                
                # 解析 UST 文件
                imported_project = parser.parse_ust_file(Path(file_path))
                
                # 合并到当前项目或替换
                if messagebox.askyesno("导入 UST", "是否替换当前项目？\n选择'否'将添加到新音轨"):
                    self.project = imported_project
                    self.project_name_var.set(imported_project.name)
                    
                    # 更新音轨列表
                    self.tracks_tree.delete(*self.tracks_tree.get_children())
                    for track in imported_project.tracks:
                        self.tracks_tree.insert("", "end", values=(
                            track.name,
                            Path(track.voice_library_path).name if track.voice_library_path else "无",
                            "✓" if track.muted else "",
                            "✓" if track.solo else ""
                        ))
                else:
                    # 添加到新音轨
                    for track in imported_project.tracks:
                        new_track = self.project.add_track(f"导入_{track.name}")
                        new_track.voice_library_path = track.voice_library_path
                        for note in track.notes:
                            new_track.add_note(note)
                        
                        # 添加到树形视图
                        self.tracks_tree.insert("", "end", values=(
                            new_track.name,
                            Path(new_track.voice_library_path).name if new_track.voice_library_path else "无",
                            "✓" if new_track.muted else "",
                            "✓" if new_track.solo else ""
                        ))
                
                self.redraw_all()
                self.status_var.set(f"成功导入 UST 文件: {Path(file_path).name}")
                
            except Exception as e:
                messagebox.showerror("导入错误", f"导入 UST 文件失败: {e}")
                self.status_var.set("UST 导入失败")
    
    def export_ust(self):
        """导出为 UST 文件"""
        if not self.project.tracks:
            messagebox.showwarning("警告", "没有可导出的音轨")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="导出 UST 文件",
            defaultextension=".ust",
            filetypes=[
                ("UST files", "*.ust"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.status_var.set("正在导出 UST 文件...")
                self.update()
                
                # 创建 UST 解析器
                parser = USTParser()
                
                # 导出 UST 文件
                success = parser.export_to_ust(self.project, Path(file_path))
                
                if success:
                    self.status_var.set(f"成功导出 UST 文件: {Path(file_path).name}")
                    messagebox.showinfo("导出成功", f"UST 文件已导出到:\n{file_path}")
                else:
                    messagebox.showerror("导出错误", "UST 文件导出失败")
                    self.status_var.set("UST 导出失败")
                
            except Exception as e:
                messagebox.showerror("导出错误", f"导出 UST 文件失败: {e}")
                self.status_var.set("UST 导出失败")
    
    def play(self):
        """播放项目"""
        if not self.project.tracks:
            messagebox.showwarning("警告", "没有可播放的音轨")
            return
        
        try:
            self.status_var.set("正在合成...")
            self.update()
            
            # 合成整个项目
            audio_data = self.engine.synthesize_project(self.project)
            
            # 播放音频
            self.try_play_audio(audio_data)
            
            self.status_var.set("播放完成")
            
        except Exception as e:
            messagebox.showerror("错误", f"播放失败: {e}")
            self.status_var.set("播放失败")
    
    def export_audio(self):
        """导出音频"""
        if not self.project.tracks:
            messagebox.showwarning("警告", "没有可导出的音轨")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.status_var.set("正在导出...")
                self.update()
                
                # 合成整个项目
                audio_data = self.engine.synthesize_project(self.project)
                self.engine.export_audio(audio_data, file_path)
                
                self.status_var.set(f"已导出: {Path(file_path).name}")
                messagebox.showinfo("成功", f"音频已导出到: {file_path}")
                
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
                self.status_var.set("导出失败")
    
    def on_canvas_click(self, event):
        """画布点击事件 - 需要重写为多音轨版本"""
        # 获取画布坐标
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 计算时间和音高
        pixels_per_second = 50 * self.current_zoom
        time = (x - 50) / pixels_per_second if x > 50 else 0
        pitch = 127 - int(y / 15)  # 假设每个音符高度为15像素
        
        if self.edit_mode == "write":
            # 编写模式：添加新音符
            current_track = self.project.get_current_track()
            if current_track:
                # 创建新音符
                note = Note(
                    lyric="a",  # 默认歌词
                    pitch=pitch,
                    start_time=time,
                    duration=1.0  # 默认1秒
                )
                current_track.add_note(note)
                self.redraw_all()
                self.status_var.set(f"添加音符: 音高{pitch}, 时间{time:.2f}s")
        else:
            # 编辑模式：选择音符
            current_track_idx = self.project.current_track_index
            current_track = self.project.get_current_track()
            if current_track:
                note_idx = current_track.get_note_at_position(time, pitch)
                if note_idx is not None:
                    self.selected_note_indices = {current_track_idx: note_idx}
                    self.redraw_all()
                    self.status_var.set(f"选择音符: 音轨{current_track_idx+1}, 音符{note_idx+1}")
    
    def on_canvas_drag(self, event):
        """画布拖拽事件 - 需要重写为多音轨版本"""
        if not self.selected_note_indices:
            return
        
        # 获取画布坐标
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 计算时间和音高
        pixels_per_second = 50 * self.current_zoom
        time = (x - 50) / pixels_per_second if x > 50 else 0
        pitch = 127 - int(y / 15)  # 假设每个音符高度为15像素
        
        # 更新选中的音符
        for track_idx, note_idx in self.selected_note_indices.items():
            if track_idx < len(self.project.tracks):
                track = self.project.tracks[track_idx]
                if note_idx < len(track.notes):
                    note = track.notes[note_idx]
                    note.start_time = time
                    note.pitch = pitch
                    self.redraw_all()
    
    def on_canvas_release(self, event):
        """画布释放事件"""
        self.drag_type = None
    
    def on_canvas_right_click(self, event):
        """画布右键点击 - 需要重写为多音轨版本"""
        # 获取画布坐标
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 计算时间和音高
        pixels_per_second = 50 * self.current_zoom
        time = (x - 50) / pixels_per_second if x > 50 else 0
        pitch = 127 - int(y / 15)  # 假设每个音符高度为15像素
        
        # 删除音符
        current_track_idx = self.project.current_track_index
        current_track = self.project.get_current_track()
        if current_track:
            note_idx = current_track.get_note_at_position(time, pitch)
            if note_idx is not None:
                current_track.remove_note(note_idx)
                self.redraw_all()
                self.status_var.set(f"删除音符: 音轨{current_track_idx+1}, 音符{note_idx+1}")
    
    def on_canvas_double_click(self, event):
        """画布双击事件 - 需要重写为多音轨版本"""
        # 获取画布坐标
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 计算时间和音高
        pixels_per_second = 50 * self.current_zoom
        time = (x - 50) / pixels_per_second if x > 50 else 0
        pitch = 127 - int(y / 15)  # 假设每个音符高度为15像素
        
        # 编辑音符属性
        current_track_idx = self.project.current_track_index
        current_track = self.project.get_current_track()
        if current_track:
            note_idx = current_track.get_note_at_position(time, pitch)
            if note_idx is not None:
                note = current_track.notes[note_idx]
                self.edit_note_properties(note)
    
    def edit_note_properties(self, note):
        """编辑音符属性"""
        # 创建编辑对话框
        dialog = tk.Toplevel(self)
        dialog.title("编辑音符属性")
        dialog.geometry("300x200")
        dialog.transient(self)
        dialog.grab_set()
        
        # 歌词输入
        ttk.Label(dialog, text="歌词:").pack(pady=5)
        lyric_var = tk.StringVar(value=note.lyric)
        lyric_entry = ttk.Entry(dialog, textvariable=lyric_var)
        lyric_entry.pack(pady=5, fill=tk.X, padx=20)
        
        # 音高输入
        ttk.Label(dialog, text="音高 (MIDI):").pack(pady=5)
        pitch_var = tk.IntVar(value=note.pitch)
        pitch_spinbox = ttk.Spinbox(dialog, from_=0, to=127, textvariable=pitch_var)
        pitch_spinbox.pack(pady=5, fill=tk.X, padx=20)
        
        # 持续时间输入
        ttk.Label(dialog, text="持续时间 (秒):").pack(pady=5)
        duration_var = tk.DoubleVar(value=note.duration)
        duration_spinbox = ttk.Spinbox(dialog, from_=0.1, to=10.0, increment=0.1, textvariable=duration_var)
        duration_spinbox.pack(pady=5, fill=tk.X, padx=20)
        
        def save_changes():
            note.lyric = lyric_var.get()
            note.pitch = pitch_var.get()
            note.duration = duration_var.get()
            self.redraw_all()
            dialog.destroy()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="保存", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def redraw_all(self):
        """重绘所有内容"""
        self.canvas.delete("all")
        self.draw_piano_roll_background()
        self.draw_tracks()
        self.draw_notes()
    
    def draw_piano_roll_background(self):
        """绘制钢琴卷帘背景 - 需要适应长时长"""
        # 绘制钢琴键盘（左侧）
        for i in range(128):
            y = (127 - i) * 15
            is_white_key = i % 12 in [0, 2, 4, 5, 7, 9, 11]
            color = 'white' if is_white_key else 'lightgray'
            outline = 'black' if is_white_key else 'darkgray'
            
            self.canvas.create_rectangle(
                0, y, 50, y + 15, 
                fill=color, outline=outline, tags="background"
            )
        
        # 绘制时间线（适应长时长）
        total_seconds = int(self.project.settings.total_duration)
        pixels_per_second = 50 * self.current_zoom
        
        for second in range(0, total_seconds + 1, 5):  # 每5秒一条线
            x = second * pixels_per_second
            self.canvas.create_line(x, 0, x, 2000, fill='lightgray', tags="background")
            if second % 10 == 0:  # 每10秒一个标签
                self.canvas.create_text(x, 10, text=f"{second}s", tags="background", font=("Arial", 8))
    
    def draw_tracks(self):
        """绘制音轨"""
        track_height = 30
        for i, track in enumerate(self.project.tracks):
            y = 50 + i * track_height
            color = 'lightyellow' if i == self.project.current_track_index else 'white'
            
            # 绘制音轨背景
            self.canvas.create_rectangle(
                50, y, 6000, y + track_height,
                fill=color, outline='gray', tags="tracks"
            )
            
            # 绘制音轨名称
            self.canvas.create_text(
                55, y + track_height/2,
                text=track.name, anchor=tk.W, tags="tracks", font=("Arial", 9)
            )
    
    def draw_notes(self):
        """绘制所有音轨的音符"""
        track_height = 30
        pixels_per_second = 50 * self.current_zoom
        
        for track_idx, track in enumerate(self.project.tracks):
            y_offset = 50 + track_idx * track_height
            
            for note_idx, note in enumerate(track.notes):
                y = y_offset + (127 - note.pitch) * (track_height / 128)
                x_start = 50 + note.start_time * pixels_per_second
                x_end = x_start + note.duration * pixels_per_second
                
                # 确定颜色
                is_selected = (self.selected_note_indices.get(track_idx) == note_idx)
                fill_color = 'orange' if is_selected else 'lightblue'
                outline_color = 'red' if is_selected else 'blue'
                
                # 绘制音符
                self.canvas.create_rectangle(
                    x_start, y, x_end, y + 5,
                    fill=fill_color, outline=outline_color, tags="notes", width=1
                )
                
                # 显示歌词
                self.canvas.create_text(
                    x_start + 2, y + 2,
                    text=note.lyric, anchor=tk.W, tags="notes", font=("Arial", 6)
                )
    
    def clear_notes(self):
        """清除当前音轨的音符"""
        current_track = self.project.get_current_track()
        if current_track:
            current_track.clear_notes()
            self.redraw_all()
            self.status_var.set(f"已清除音轨 '{current_track.name}' 的音符")
    
    def try_play_audio(self, audio_data):
        """尝试播放音频 - 使用 sounddevice 替代 simpleaudio"""
        try:
            import sounddevice as sd
            # 使用 sounddevice 播放音频
            sd.play(audio_data, self.engine.sample_rate)
            sd.wait()  # 等待播放完成
        except ImportError:
            # 如果 sounddevice 不可用，尝试其他方法
            self.fallback_audio_playback(audio_data)

    def fallback_audio_playback(self, audio_data):
        """后备音频播放方案"""
        try:
            # 方案2：使用 pydub 播放（需要安装 pydub 和 simpleaudio）
            from pydub import AudioSegment
            from pydub.playback import play
            
            # 将 numpy 数组转换为 AudioSegment
            audio_segment = AudioSegment(
                audio_data.tobytes(),
                frame_rate=self.engine.sample_rate,
                sample_width=audio_data.dtype.itemsize,
                channels=1
            )
            play(audio_segment)
        except ImportError:
            # 方案3：保存为临时文件并用系统默认播放器播放
            try:
                import tempfile
                import os
                from scipy.io import wavfile
                
                # 创建临时 WAV 文件
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # 保存为 WAV 文件
                wavfile.write(temp_path, self.engine.sample_rate, audio_data)
                
                # 使用系统默认播放器播放
                if os.name == 'nt':  # Windows
                    os.system(f'start {temp_path}')
                elif os.name == 'posix':  # macOS 或 Linux
                    if os.uname().sysname == 'Darwin':  # macOS
                        os.system(f'afplay {temp_path}')
                    else:  # Linux
                        os.system(f'aplay {temp_path}')
                
                # 提示用户文件位置
                self.status_var.set(f"音频已保存到临时文件: {temp_path}")
                
            except Exception as e:
                # 最终方案：显示信息让用户手动播放
                messagebox.showinfo("音频播放", 
                    f"无法自动播放音频。\n"
                    f"请安装以下任一库来启用音频播放：\n"
                    f"• pip install sounddevice (推荐)\n"
                    f"• pip install pydub simpleaudio\n\n"
                    f"错误详情: {e}")    
    def stop(self):
        """停止播放"""
        try:
            # 尝试停止 sounddevice 播放
            import sounddevice as sd
            sd.stop()
        except ImportError:
            pass
        except Exception:
            pass
        
        # 更新状态
        self.status_var.set("播放停止")
        
    def destroy(self):
        """销毁组件时清理资源"""
        # 清理所有临时目录
        for temp_dir in self.temp_dirs.values():
            if os.path.exists(temp_dir):
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        super().destroy()

