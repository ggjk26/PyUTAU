# embedded_utau/voice_library.py
import os
import numpy as np
import librosa
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import tempfile
import re
import json
from PIL import Image, ImageTk
import io
try:
    from embedded_utau.note import Note, Track
except ImportError:
    from .note import Note, Track

@dataclass
class VoiceSample:
    """语音样本类"""
    file_path: Path
    pitch: int
    lyric: str
    sample_data: Optional[np.ndarray] = None
    sample_rate: int = 44100
    original_length: int = 0
    
    def load_sample(self):
        """加载音频样本"""
        if self.sample_data is None:
            try:
                self.sample_data, self.sample_rate = librosa.load(
                    str(self.file_path), sr=self.sample_rate, mono=True
                )
                self.original_length = len(self.sample_data)
            except Exception as e:
                print(f"加载样本失败 {self.file_path}: {e}")
                # 创建一个静音样本作为后备
                self.sample_data = np.zeros(self.sample_rate)
                self.original_length = self.sample_rate
    
    def get_pitch_shifted(self, target_pitch: int) -> np.ndarray:
        """获取移调后的样本 - 改进版本"""
        self.load_sample()
        semitones = target_pitch - self.pitch
        
        if semitones == 0:
            return self.sample_data.copy()
        
        try:
            # 使用更高质量的音高移动参数
            return librosa.effects.pitch_shift(
                self.sample_data, 
                sr=self.sample_rate, 
                n_steps=semitones,
                n_fft=2048,  # 增加FFT大小以提高质量
                hop_length=512  # 优化hop长度
            )
        except Exception as e:
            print(f"音高移动失败: {e}")
            return self.sample_data.copy()

class VoiceLibrary:
    """音源库管理器 - 修复版本"""
    
    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self.samples: Dict[str, List[VoiceSample]] = {}
        self.oto_ini_data: Dict[str, Dict] = {}
        self.character_info: Dict[str, str] = {}
        self.avatar_image: Optional[Image.Image] = None
        self.avatar_photo: Optional[ImageTk.PhotoImage] = None
        
        # 首先加载角色信息，确保名称正确
        self.load_character_info()
        self.load_avatar()
        self.load_library()
    
    def load_library(self):
        """加载音源库"""
        print(f"正在加载音源库: {self.library_path}")
        print(f"音源库名称: {self.get_library_name()}")
        
        # 首先尝试加载 oto.ini
        self.load_oto_ini()
        
        # 扫描音频文件
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg']
        audio_files = []
        
        for ext in audio_extensions:
            audio_files.extend(list(self.library_path.rglob(f"*{ext}")))
        
        print(f"找到 {len(audio_files)} 个音频文件")
        
        for audio_file in audio_files:
            self.add_sample(audio_file)
        
        print(f"音源库加载完成，共 {len(self.samples)} 种歌词")
    
    def load_character_info(self):
        """加载角色信息 - 修复版本，支持子目录搜索"""
        # 尝试不同的角色信息文件
        character_files = [
            "character.yaml", "character.yml",  # YAML格式优先
            "character.txt",
            "readme.txt", 
            "info.txt",
            "キャラクター.txt",
            "CHARACTER.TXT"
        ]
        
        found_character_file = False
        
        # 先在根目录搜索
        for char_file in character_files:
            char_path = self.library_path / char_file
            if char_path.exists():
                print(f"在根目录找到角色文件: {char_path}")
                found_character_file = True
                try:
                    # 根据文件类型使用不同的解析方法
                    if char_path.suffix.lower() in ['.yaml', '.yml']:
                        self.parse_yaml_character_info(char_path)
                    else:
                        self.parse_text_character_info(char_path)
                    
                    print(f"成功加载角色信息: {char_file}")
                    print(f"角色信息: {self.character_info}")
                    break
                except Exception as e:
                    print(f"解析角色信息文件失败 {char_file}: {e}")
        
        # 如果在根目录没找到，搜索子目录
        if not found_character_file:
            print("在根目录未找到角色文件，搜索子目录...")
            for subdir in self.library_path.iterdir():
                if subdir.is_dir():
                    print(f"搜索子目录: {subdir}")
                    for char_file in character_files:
                        char_path = subdir / char_file
                        if char_path.exists():
                            print(f"在子目录找到角色文件: {char_path}")
                            found_character_file = True
                            try:
                                if char_path.suffix.lower() in ['.yaml', '.yml']:
                                    self.parse_yaml_character_info(char_path)
                                else:
                                    self.parse_text_character_info(char_path)
                                
                                print(f"成功加载角色信息: {char_file}")
                                print(f"角色信息: {self.character_info}")
                                break
                            except Exception as e:
                                print(f"解析角色信息文件失败 {char_file}: {e}")
                    if found_character_file:
                        break
        
        # 如果没有找到角色文件，使用文件夹名作为音源库名
        if not found_character_file or not self.character_info.get('name'):
            # 尝试从子目录名获取名称
            subdirs = [d for d in self.library_path.iterdir() if d.is_dir()]
            if subdirs:
                # 使用第一个子目录的名称
                self.character_info['name'] = subdirs[0].name
                print(f"使用子目录名作为音源库名: {subdirs[0].name}")
            else:
                self.character_info['name'] = self.library_path.name
                print(f"使用文件夹名作为音源库名: {self.library_path.name}")
    
    def parse_yaml_character_info(self, yaml_path: Path):
        """解析YAML格式的角色信息"""
        try:
            # 尝试导入yaml模块
            import yaml
            
            # 尝试多种编码
            encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-16']
            for encoding in encodings:
                try:
                    with open(yaml_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    
                    print(f"YAML文件内容 (编码: {encoding}):")
                    print(content[:500])  # 打印前500个字符
                    
                    # 解析YAML
                    data = yaml.safe_load(content)
                    
                    if data:
                        print(f"解析的YAML数据: {data}")
                        # 提取角色信息
                        if 'name' in data:
                            self.character_info['name'] = data['name']
                        if 'author' in data:
                            self.character_info['author'] = data['author']
                        elif 'created_by' in data:
                            self.character_info['author'] = data['created_by']
                        if 'image' in data:
                            self.character_info['image'] = data['image']
                        if 'description' in data:
                            self.character_info['description'] = data['description']
                    
                    break
                except UnicodeDecodeError:
                    print(f"编码 {encoding} 解码失败")
                    continue
                except yaml.YAMLError as e:
                    print(f"YAML解析错误: {e}")
                    # 如果YAML解析失败，尝试简单文本解析
                    self.fallback_yaml_parsing(yaml_path)
                    break
                    
        except ImportError:
            print("未安装PyYAML，使用简单解析")
            self.fallback_yaml_parsing(yaml_path)
    
    def fallback_yaml_parsing(self, yaml_path: Path):
        """YAML解析失败时的后备方案 - 简单文本解析"""
        # 尝试多种编码
        encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-16']
        for encoding in encodings:
            try:
                with open(yaml_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                print(f"使用后备解析，文件内容 (编码: {encoding}):")
                print(content[:500])  # 打印前500个字符
                
                # 简单的键值对提取
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):  # 忽略注释
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"\'')  # 移除引号
                        
                        print(f"解析键值对: {key} = {value}")
                        
                        if key == 'name':
                            self.character_info['name'] = value
                        elif key in ['author', 'created_by']:
                            self.character_info['author'] = value
                        elif key == 'image':
                            self.character_info['image'] = value
                        elif key == 'description':
                            self.character_info['description'] = value
                
                break
            except UnicodeDecodeError:
                print(f"编码 {encoding} 解码失败")
                continue
    
    def parse_text_character_info(self, text_path: Path):
        """解析文本格式的角色信息"""
        # 尝试多种编码
        encodings = ['shift_jis', 'utf-8', 'cp932', 'gbk', 'utf-16']
        for encoding in encodings:
            try:
                with open(text_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                print(f"文本文件内容 (编码: {encoding}):")
                print(content[:500])  # 打印前500个字符
                
                # 解析角色信息
                self.parse_character_info(content)
                break
            except UnicodeDecodeError:
                print(f"编码 {encoding} 解码失败")
                continue
    
    def parse_character_info(self, content: str):
        """解析角色信息内容"""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ['name', 'character', 'voicebank']:
                    self.character_info['name'] = value
                elif key in ['author', 'creator', 'maker']:
                    self.character_info['author'] = value
                elif key in ['image', 'avatar', 'icon']:
                    self.character_info['image'] = value
                elif key in ['description', 'info', 'readme']:
                    self.character_info['description'] = value
            # 也支持冒号分隔
            elif ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ['name', 'character', 'voicebank']:
                    self.character_info['name'] = value
                elif key in ['author', 'creator', 'maker']:
                    self.character_info['author'] = value
                elif key in ['image', 'avatar', 'icon']:
                    self.character_info['image'] = value
                elif key in ['description', 'info', 'readme']:
                    self.character_info['description'] = value
    
    def load_avatar(self):
        """加载头像图片 - 简化版本，只检测子目录下的.bmp文件"""
        print("搜索子目录中的.bmp头像文件...")
        
        # 只在子目录中搜索.bmp文件
        for subdir in self.library_path.iterdir():
            if subdir.is_dir():
                print(f"搜索子目录: {subdir}")
                # 搜索所有.bmp文件
                bmp_files = list(subdir.glob("*.bmp"))
                for bmp_file in bmp_files:
                    try:
                        self.avatar_image = Image.open(bmp_file)
                        # 调整大小为适当尺寸
                        self.avatar_image = self.avatar_image.resize((64, 64), Image.Resampling.LANCZOS)
                        print(f"找到并加载头像: {bmp_file}")
                        return
                    except Exception as e:
                        print(f"加载头像失败 {bmp_file}: {e}")
        
        print("未找到任何.bmp头像文件")    
    def get_avatar_photo(self):
        """获取Tkinter可用的头像照片"""
        if self.avatar_image and self.avatar_photo is None:
            self.avatar_photo = ImageTk.PhotoImage(self.avatar_image)
        return self.avatar_photo
    
    def get_library_name(self) -> str:
        """获取音源库名称"""
        name = self.character_info.get('name', self.library_path.name)
        print(f"获取音源库名称: {name}")
        return name
    
    def get_author(self) -> str:
        """获取作者信息"""
        return self.character_info.get('author', '未知')
    
    def load_oto_ini(self):
        """加载 oto.ini 文件"""
        oto_path = self.library_path / "oto.ini"
        if not oto_path.exists():
            # 尝试在子目录中查找
            for subdir in self.library_path.iterdir():
                if subdir.is_dir():
                    oto_path = subdir / "oto.ini"
                    if oto_path.exists():
                        break
        
        if oto_path.exists():
            print(f"找到 oto.ini: {oto_path}")
            try:
                # 尝试多种编码
                encodings = ['shift_jis', 'utf-8', 'cp932', 'gbk']
                for encoding in encodings:
                    try:
                        with open(oto_path, 'r', encoding=encoding) as f:
                            current_file = None
                            for line in f:
                                line = line.strip()
                                if line.startswith('[') and line.endswith(']'):
                                    current_file = line[1:-1]
                                    self.oto_ini_data[current_file] = {}
                                elif '=' in line and current_file:
                                    key, value = line.split('=', 1)
                                    self.oto_ini_data[current_file][key.strip()] = value.strip()
                        print(f"成功解析 oto.ini，使用编码: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
            except Exception as e:
                print(f"解析 oto.ini 失败: {e}")
        else:
            print("未找到 oto.ini 文件")
    
    def add_sample(self, audio_file: Path):
        """添加音频样本"""
        try:
            # 从文件名推断音高和歌词
            filename = audio_file.stem
            pitch = self.extract_pitch_from_filename(filename)
            lyric = self.extract_lyric_from_filename(filename)
            
            sample = VoiceSample(
                file_path=audio_file,
                pitch=pitch,
                lyric=lyric
            )
            
            if lyric not in self.samples:
                self.samples[lyric] = []
            self.samples[lyric].append(sample)
            
        except Exception as e:
            print(f"添加样本失败 {audio_file}: {e}")
    
    def extract_pitch_from_filename(self, filename: str) -> int:
        """从文件名提取音高 - 改进版本"""
        # 更全面的音高模式匹配
        pitch_patterns = [
            # 低音区
            (['C1'], 24), (['C#1', 'Db1'], 25), (['D1'], 26), (['D#1', 'Eb1'], 27), 
            (['E1'], 28), (['F1'], 29), (['F#1', 'Gb1'], 30), (['G1'], 31), 
            (['G#1', 'Ab1'], 32), (['A1'], 33), (['A#1', 'Bb1'], 34), (['B1'], 35),
            # 中低音区
            (['C2'], 36), (['C#2', 'Db2'], 37), (['D2'], 38), (['D#2', 'Eb2'], 39), 
            (['E2'], 40), (['F2'], 41), (['F#2', 'Gb2'], 42), (['G2'], 43), 
            (['G#2', 'Ab2'], 44), (['A2'], 45), (['A#2', 'Bb2'], 46), (['B2'], 47),
            # 中音区
            (['C3'], 48), (['C#3', 'Db3'], 49), (['D3'], 50), (['D#3', 'Eb3'], 51), 
            (['E3'], 52), (['F3'], 53), (['F#3', 'Gb3'], 54), (['G3'], 55), 
            (['G#3', 'Ab3'], 56), (['A3'], 57), (['A#3', 'Bb3'], 58), (['B3'], 59),
            # 中央C区
            (['C4'], 60), (['C#4', 'Db4'], 61), (['D4'], 62), (['D#4', 'Eb4'], 63), 
            (['E4'], 64), (['F4'], 65), (['F#4', 'Gb4'], 66), (['G4'], 67), 
            (['G#4', 'Ab4'], 68), (['A4'], 69), (['A#4', 'Bb4'], 70), (['B4'], 71),
            # 高音区
            (['C5'], 72), (['C#5', 'Db5'], 73), (['D5'], 74), (['D#5', 'Eb5'], 75), 
            (['E5'], 76), (['F5'], 77), (['F#5', 'Gb5'], 78), (['G5'], 79), 
            (['G#5', 'Ab5'], 80), (['A5'], 81), (['A#5', 'Bb5'], 82), (['B5'], 83),
            # 超高音区
            (['C6'], 84), (['C#6', 'Db6'], 85), (['D6'], 86), (['D#6', 'Eb6'], 87), 
            (['E6'], 88), (['F6'], 89), (['F#6', 'Gb6'], 90), (['G6'], 91), 
            (['G#6', 'Ab6'], 92), (['A6'], 93), (['A#6', 'Bb6'], 94), (['B6'], 95),
        ]
        
        filename_upper = filename.upper()
        for note_names, midi_pitch in pitch_patterns:
            for note_name in note_names:
                if note_name in filename_upper:
                    return midi_pitch
        
        # 如果没有找到明确的音高标记，尝试从文件名中提取数字
        numbers = re.findall(r'\d+', filename)
        if numbers:
            number = int(numbers[0])
            # 扩展合理的MIDI音高范围
            if 24 <= number <= 95:
                return number
        
        # 默认返回中音C
        return 60
    
    def extract_lyric_from_filename(self, filename: str) -> str:
        """从文件名提取歌词 - 改进版本"""
        # 移除常见的音高标记和数字
        import re
        
        # 首先尝试从oto.ini中获取歌词映射
        if filename in self.oto_ini_data:
            oto_entry = self.oto_ini_data[filename]
            if 'alias' in oto_entry:
                return oto_entry['alias']
        
        # 移除音高标记
        pitch_pattern = r'[A-G][#b]?\d+'
        cleaned = re.sub(pitch_pattern, '', filename, flags=re.IGNORECASE)
        
        # 移除数字
        cleaned = re.sub(r'\d+', '', cleaned)
        
        # 移除常见分隔符和扩展名相关
        cleaned = re.sub(r'[._-]', '', cleaned)
        
        # 如果是日语音源，尝试提取平假名或片假名
        japanese_pattern = r'[ぁ-んァ-ンー]'
        japanese_chars = re.findall(japanese_pattern, cleaned)
        if japanese_chars:
            return japanese_chars[0]
        
        # 如果是中文音源，尝试提取中文字符
        chinese_pattern = r'[\u4e00-\u9fff]'
        chinese_chars = re.findall(chinese_pattern, cleaned)
        if chinese_chars:
            return chinese_chars[0]
        
        # 如果是韩语音源
        korean_pattern = r'[가-힣]'
        korean_chars = re.findall(korean_pattern, cleaned)
        if korean_chars:
            return korean_chars[0]
        
        # 如果是英文或其他，返回前2个字母（如果是辅音+元音组合）
        if len(cleaned) >= 2:
            # 检查是否是常见的音节组合
            common_syllables = ['la', 'le', 'li', 'lo', 'lu', 'ra', 're', 'ri', 'ro', 'ru',
                              'ma', 'me', 'mi', 'mo', 'mu', 'na', 'ne', 'ni', 'no', 'nu',
                              'pa', 'pe', 'pi', 'po', 'pu', 'ba', 'be', 'bi', 'bo', 'bu']
            first_two = cleaned[:2].lower()
            if first_two in common_syllables:
                return first_two
        
        # 返回第一个非空字符
        if cleaned:
            return cleaned[0]
        
        # 最后手段：使用文件名前2个字符
        return filename[:2] if len(filename) >= 2 else filename
    
    def get_best_sample(self, lyric: str, target_pitch: int) -> Optional[VoiceSample]:
        """获取最适合指定歌词和音高的样本 - 改进版本"""
        if lyric not in self.samples or not self.samples[lyric]:
            # 尝试找到相似的歌词
            similar_lyrics = self.find_similar_lyrics(lyric)
            if not similar_lyrics:
                print(f"没有找到歌词 '{lyric}' 的样本")
                return None
            # 使用第一个相似的歌词
            lyric = similar_lyrics[0]
        
        available_samples = self.samples[lyric]
        
        # 优先选择音高接近的样本（±3个半音内）
        close_samples = [s for s in available_samples if abs(s.pitch - target_pitch) <= 3]
        if close_samples:
            # 在接近样本中按音高接近程度排序
            close_samples.sort(key=lambda x: abs(x.pitch - target_pitch))
            return close_samples[0]
        else:
            # 如果没有接近样本，使用所有样本中最接近的
            available_samples.sort(key=lambda x: abs(x.pitch - target_pitch))
            return available_samples[0]
    
    def find_similar_lyrics(self, target_lyric: str) -> List[str]:
        """查找相似的歌词"""
        similar = []
        for lyric in self.samples.keys():
            if target_lyric == lyric:
                similar.insert(0, lyric)  # 完全匹配的优先级最高
            elif target_lyric in lyric or lyric in target_lyric:
                similar.append(lyric)
            elif self.is_similar_pronunciation(target_lyric, lyric):
                similar.append(lyric)
        
        return similar
    
    def is_similar_pronunciation(self, lyric1: str, lyric2: str) -> bool:
        """判断两个歌词是否发音相似"""
        if len(lyric1) == 0 or len(lyric2) == 0:
            return False
        
        # 发音相似性映射（简化的实现）
        pronunciation_groups = {
            'a': ['a', 'ah', 'aa'],
            'i': ['i', 'ee', 'ii'],
            'u': ['u', 'oo', 'uu'],
            'e': ['e', 'eh'],
            'o': ['o', 'oh'],
            'ka': ['ka', 'ca'],
            'ki': ['ki', 'key'],
            'ku': ['ku', 'coo'],
            'ke': ['ke', 'kay'],
            'ko': ['ko', 'co'],
        }
        
        lyric1_lower = lyric1.lower()
        lyric2_lower = lyric2.lower()
        
        for group in pronunciation_groups.values():
            if lyric1_lower in group and lyric2_lower in group:
                return True
        
        return False
    
    def is_japanese(self, text: str) -> bool:
        """判断文本是否为日文"""
        import re
        return bool(re.search(r'[ぁ-んァ-ン]', text))
    
    def get_available_lyrics(self) -> List[str]:
        """获取所有可用的歌词"""
        return list(self.samples.keys())
    
    def get_sample_count(self) -> int:
        """获取样本总数"""
        return sum(len(samples) for samples in self.samples.values())
    
    def get_pitch_range(self) -> Tuple[int, int]:
        """获取音源库的音高范围"""
        all_pitches = []
        for samples in self.samples.values():
            for sample in samples:
                all_pitches.append(sample.pitch)
        
        if all_pitches:
            return min(all_pitches), max(all_pitches)
        else:
            return 60, 60  # 默认范围
    def batch_preload_samples(self, max_workers=4):
        """批量预加载样本（多线程）"""
        try:
            from concurrent.futures import ThreadPoolExecutor
            
            all_samples = []
            for samples in self.samples.values():
                all_samples.extend(samples)
            
            def load_sample(sample):
                sample.load_sample()
                return sample
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(load_sample, all_samples))
                
            print(f"已预加载 {len(all_samples)} 个样本")
            
        except ImportError:
            # 如果没有concurrent.futures，顺序加载
            for samples in self.samples.values():
                for sample in samples:
                    sample.load_sample()
