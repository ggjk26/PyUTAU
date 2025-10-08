# embedded_utau/project.py
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from .note import Note, Track

@dataclass
class ProjectSettings:
    """项目设置"""
    tempo: float = 120.0
    time_signature: str = "4/4"
    sample_rate: int = 44100
    total_duration: float = 120.0  # 总时长（秒）
    max_tracks: int = 16

class Project:
    """扩展的项目类"""
    
    def __init__(self, name: str, settings: ProjectSettings = None):
        self.name = name
        self.settings = settings or ProjectSettings()
        self.tracks: List[Track] = []
        self.current_track_index = 0
        self.original_file_path: Optional[Path] = None  # 新增：原始文件路径
    
    def add_track(self, name: str, voice_library_path: str = ""):
        """添加音轨"""
        if len(self.tracks) >= self.settings.max_tracks:
            raise ValueError(f"已达到最大音轨数: {self.settings.max_tracks}")
        
        track = Track(name, voice_library_path)
        self.tracks.append(track)
        return track
    def import_ust(self, file_path: Path) -> bool:
        """从 UST 文件导入"""
        try:
            from .ust_parser import USTParser
            parser = USTParser()
            imported_project = parser.parse_ust_file(file_path)
            
            # 复制导入的项目数据
            self.name = imported_project.name
            self.settings = imported_project.settings
            self.tracks = imported_project.tracks
            self.original_file_path = file_path
            
            return True
        except Exception as e:
            print(f"导入 UST 失败: {e}")
            return False
    
    def export_ust(self, file_path: Path) -> bool:
        """导出为 UST 文件"""
        try:
            from .ust_parser import USTParser
            parser = USTParser()
            return parser.export_to_ust(self, file_path)
        except Exception as e:
            print(f"导出 UST 失败: {e}")
            return False
    
    def remove_track(self, index: int):
        """移除音轨"""
        if 0 <= index < len(self.tracks):
            del self.tracks[index]
            if self.current_track_index >= len(self.tracks):
                self.current_track_index = max(0, len(self.tracks) - 1)
    
    def get_current_track(self) -> Optional[Track]:
        """获取当前音轨"""
        if self.tracks and 0 <= self.current_track_index < len(self.tracks):
            return self.tracks[self.current_track_index]
        return None
    
    def set_current_track(self, index: int):
        """设置当前音轨"""
        if 0 <= index < len(self.tracks):
            self.current_track_index = index
    
    def get_track_by_name(self, name: str) -> Optional[Track]:
        """根据名称获取音轨"""
        for track in self.tracks:
            if track.name == name:
                return track
        return None
    
    def save_project(self, filepath: Path):
        """保存项目到文件"""
        project_data = {
            'name': self.name,
            'settings': asdict(self.settings),
            'tracks': [
                {
                    'name': track.name,
                    'voice_library_path': track.voice_library_path,
                    'notes': [
                        {
                            'lyric': note.lyric,
                            'pitch': note.pitch,
                            'start_time': note.start_time,
                            'duration': note.duration,
                            'velocity': note.velocity,
                            'flags': note.flags
                        }
                        for note in track.notes
                    ]
                }
                for track in self.tracks
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
    
    def load_project(self, filepath: Path):
        """从文件加载项目"""
        with open(filepath, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        
        self.name = project_data['name']
        self.settings = ProjectSettings(**project_data['settings'])
        self.tracks.clear()
        
        for track_data in project_data['tracks']:
            track = Track(track_data['name'], track_data['voice_library_path'])
            for note_data in track_data['notes']:
                note = Note(**note_data)
                track.notes.append(note)
            self.tracks.append(track)
    def create_from_template(cls, template_name: str) -> 'Project':
        """从模板创建项目"""
        templates = {
            "pop_vocal": {
                "tempo": 120,
                "tracks": ["主唱", "和声1", "和声2"]
            },
            "instrumental": {
                "tempo": 140,
                "tracks": ["旋律", "和弦", "贝斯", "鼓"]
            },
            "choir": {
                "tempo": 90,
                "tracks": ["女高音", "女低音", "男高音", "男低音"]
            }
        }
        
        if template_name in templates:
            template = templates[template_name]
            settings = ProjectSettings(tempo=template["tempo"])
            project = cls(f"{template_name}项目", settings)
            
            for track_name in template["tracks"]:
                project.add_track(track_name)
            
            return project
        else:
            raise ValueError(f"未知模板: {template_name}")

