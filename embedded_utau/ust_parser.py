# embedded_utau/ust_parser.py
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import chardet
from .note import Note, Track
from .project import Project, ProjectSettings

class USTParser:
    """UST 文件解析器 - 支持 UTAU 项目文件导入导出"""
    
    def __init__(self):
        self.supported_encodings = ['shift_jis', 'utf-8', 'cp932', 'utf-16']
    
    def detect_encoding(self, file_path: Path) -> str:
        """检测文件编码"""
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            
            # 处理常见的编码映射
            encoding_map = {
                'SHIFT_JIS': 'shift_jis',
                'UTF-8': 'utf-8',
                'UTF-16': 'utf-16',
                'GB2312': 'gbk',
                'ISO-8859-1': 'cp932'
            }
            
            detected = encoding_map.get(encoding.upper() if encoding else '', 'shift_jis')
            print(f"检测到文件编码: {detected} (原始: {encoding})")
            return detected
    
    def parse_ust_file(self, file_path: Path) -> Project:
        """解析 UST 文件并转换为 Project 对象"""
        encoding = self.detect_encoding(file_path)
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        print(f"开始解析 UST 文件: {file_path.name}")
        
        # 解析全局设置
        settings = self.parse_settings(content)
        project_name = file_path.stem
        project = Project(project_name, settings)
        
        # 解析音轨和音符
        tracks = self.parse_tracks(content, file_path.parent)
        
        for track in tracks:
            project.tracks.append(track)
        
        print(f"UST 解析完成: {len(tracks)} 个音轨, {sum(len(t.notes) for t in tracks)} 个音符")
        return project
    
    def parse_settings(self, content: str) -> ProjectSettings:
        """解析 UST 设置"""
        settings = ProjectSettings()
        
        # 解析曲速
        tempo_match = re.search(r'Tempo=([\d.]+)', content)
        if tempo_match:
            settings.tempo = float(tempo_match.group(1))
            print(f"解析曲速: {settings.tempo}")
        
        # 解析工程长度（通过音符计算）
        # UST 不直接指定总时长，我们需要计算
        
        # 解析采样率（UST 通常使用44100）
        settings.sample_rate = 44100
        
        return settings
    
    def parse_tracks(self, content: str, base_dir: Path) -> List[Track]:
        """解析音轨和音符"""
        tracks = []
        
        # UST 通常是单音轨的，但我们支持多音轨 UST
        track_sections = self.split_track_sections(content)
        
        for i, section in enumerate(track_sections):
            track_name = f"音轨 {i+1}"
            voice_library_path = self.parse_voice_library(section, base_dir)
            
            track = Track(track_name, str(voice_library_path) if voice_library_path else "")
            notes = self.parse_notes(section)
            
            for note in notes:
                track.add_note(note)
            
            tracks.append(track)
            print(f"解析音轨 {i+1}: {len(notes)} 个音符, 音源库: {voice_library_path}")
        
        return tracks
    
    def split_track_sections(self, content: str) -> List[str]:
        """分割音轨部分"""
        # 简单的实现：整个 UST 作为一个音轨
        return [content]
    
    def parse_voice_library(self, section: str, base_dir: Path) -> Optional[Path]:
        """解析音源库路径"""
        # 查找 VoiceDir 或 Project 设置
        voice_dir_match = re.search(r'VoiceDir=([^\r\n]+)', section)
        if voice_dir_match:
            voice_dir = voice_dir_match.group(1).strip()
            # 处理 UTAU 的相对路径
            if voice_dir.startswith('?'):
                voice_dir = voice_dir[1:]
            voice_path = base_dir / voice_dir
            if voice_path.exists():
                return voice_path
        
        # 尝试在工程目录下查找音源库
        possible_dirs = ['voice', 'Voice', '音源', '歌声']
        for dir_name in possible_dirs:
            voice_path = base_dir / dir_name
            if voice_path.exists():
                return voice_path
        
        return None
    
    def parse_notes(self, section: str) -> List[Note]:
        """解析音符数据"""
        notes = []
        
        # 分割为单个音符部分
        note_sections = re.findall(r'\[#\d+\][^[]+', section, re.DOTALL)
        
        for note_section in note_sections:
            note = self.parse_single_note(note_section)
            if note:
                notes.append(note)
        
        # 按开始时间排序
        notes.sort(key=lambda x: x.start_time)
        
        return notes
    
    def parse_single_note(self, note_section: str) -> Optional[Note]:
        """解析单个音符"""
        try:
            # 提取基本属性
            lyric = self.extract_value(note_section, 'Lyric')
            if not lyric or lyric == 'R' or lyric == 'r':  # 休止符
                return None
            
            note_num = self.extract_value(note_section, 'NoteNum')
            length = self.extract_value(note_section, 'Length')
            
            if not note_num or not length:
                return None
            
            # 计算开始时间（基于位置和前面的音符）
            position = self.extract_value(note_section, 'Position') or "0"
            
            # 转换数据
            pitch = int(note_num)
            duration_ticks = int(length)
            start_ticks = int(position)
            
            # 将 ticks 转换为秒（假设 480 ticks 为一拍，120 BPM）
            # 更准确的转换需要知道曲速
            ticks_per_beat = 480
            seconds_per_tick = 60.0 / (120 * ticks_per_beat)  # 默认 120 BPM
            
            start_time = start_ticks * seconds_per_tick
            duration = duration_ticks * seconds_per_tick
            
            # 处理特殊歌词
            if lyric.startswith('?'):
                lyric = lyric[1:]
            
            # 创建音符
            note = Note(
                lyric=lyric,
                pitch=pitch,
                start_time=start_time,
                duration=duration,
                velocity=64
            )
            
            return note
            
        except Exception as e:
            print(f"解析音符失败: {e}")
            return None
    
    def extract_value(self, text: str, key: str) -> Optional[str]:
        """从文本中提取键值"""
        pattern = rf'{key}=([^\r\n]+)'
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None
    
    def export_to_ust(self, project: Project, file_path: Path) -> bool:
        """将项目导出为 UST 文件"""
        try:
            print(f"开始导出 UST 文件: {file_path}")
            
            # UST 文件头
            lines = [
                "[#SETTING]",
                f"Tempo={project.settings.tempo}",
                "Tracks=1",
                "VoiceDir=%VOICE%",
                "CacheDir=%CACHE%",
                "OutFile=%OUTPUT%",
                "Mode2=True",
                ""
            ]
            
            # 处理每个音轨（UST 通常只支持单音轨，我们导出第一个音轨）
            if project.tracks:
                track = project.tracks[0]
                notes = sorted(track.notes, key=lambda x: x.start_time)
                
                # 计算 ticks（基于曲速）
                ticks_per_beat = 480
                seconds_per_tick = 60.0 / (project.settings.tempo * ticks_per_beat)
                
                current_position = 0
                
                for i, note in enumerate(notes):
                    # 计算位置和长度（ticks）
                    position_ticks = int(note.start_time / seconds_per_tick)
                    length_ticks = int(note.duration / seconds_per_tick)
                    
                    # 确保位置不重叠
                    position_ticks = max(position_ticks, current_position)
                    current_position = position_ticks + length_ticks
                    
                    # 音符块
                    lines.extend([
                        f"[#{i:04d}]",
                        f"Length={length_ticks}",
                        f"Lyric={note.lyric}",
                        f"NoteNum={note.pitch}",
                        f"Position={position_ticks}",
                        ""
                    ])
            
            # 文件尾
            lines.append("[#TRACKEND]")
            
            # 写入文件（使用 Shift-JIS 编码，这是 UST 的标准编码）
            with open(file_path, 'w', encoding='shift_jis') as f:
                f.write('\n'.join(lines))
            
            print(f"UST 文件导出成功: {file_path}")
            return True
            
        except Exception as e:
            print(f"导出 UST 文件失败: {e}")
            return False
    
    def estimate_project_duration(self, notes: List[Note]) -> float:
        """估算项目总时长"""
        if not notes:
            return 10.0  # 默认10秒
        
        last_note_end = max(note.start_time + note.duration for note in notes)
        return last_note_end + 2.0  # 额外2秒余量
