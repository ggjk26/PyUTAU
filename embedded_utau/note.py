# embedded_utau/note.py
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Note:
    """音符数据类"""
    lyric: str
    pitch: int  # MIDI 音高
    start_time: float
    duration: float
    velocity: int = 64
    flags: str = ""
    
    def __post_init__(self):
        """初始化后验证数据"""
        if self.duration <= 0:
            print(f"警告: 音符持续时间必须为正数，当前为 {self.duration}")
            self.duration = 0.1  # 设置最小持续时间

class Track:
    """音轨类 - 支持独立音源库"""
    
    def __init__(self, name: str, voice_library_path: str = ""):
        self.name = name
        self.voice_library_path = voice_library_path
        self.notes: List[Note] = []
        self.muted: bool = False
        self.solo: bool = False
        self.volume: float = 1.0  # 0.0 到 1.0
        self.pan: float = 0.0     # -1.0 (左) 到 1.0 (右)
    
    def add_note(self, note: Note):
        """添加音符"""
        self.notes.append(note)
    
    def remove_note(self, index: int):
        """移除音符"""
        if 0 <= index < len(self.notes):
            del self.notes[index]
    
    def clear_notes(self):
        """清空所有音符"""
        self.notes.clear()
    
    def get_note_at_position(self, time: float, pitch: int, tolerance: float = 0.1) -> Optional[int]:
        """获取指定位置和音高的音符索引"""
        for i, note in enumerate(self.notes):
            if (abs(note.pitch - pitch) <= 1 and
                note.start_time <= time <= note.start_time + note.duration + tolerance):
                return i
        return None
