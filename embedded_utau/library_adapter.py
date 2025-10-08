# embedded_utau/library_adapter.py
import os
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import shutil

from .voice_library import VoiceLibrary, VoiceSample
from .library_detector import LibraryDetector

class LibraryAdapter:
    """通用声库适配器 - 支持多种声库格式"""
    
    def __init__(self):
        self.supported_formats = ["utau", "vocaloid", "cevio", "generic_audio"]
        self.temp_dirs = {}
    
    def load_library(self, library_path: Path, target_dir: Optional[Path] = None) -> Tuple[Optional[VoiceLibrary], str]:
        """加载任意格式的声库"""
        library_path = Path(library_path)
        
        # 检测声库类型
        library_type = LibraryDetector.detect_library_type(library_path)
        print(f"检测到声库类型: {library_type}")
        
        if library_type not in self.supported_formats:
            return None, f"不支持的声库格式: {library_type}"
        
        # 处理 ZIP 文件
        if library_path.suffix.lower() == '.zip':
            return self._handle_zip_library(library_path, library_type, target_dir)
        
        # 处理目录
        if library_path.is_dir():
            return self._handle_directory_library(library_path, library_type, target_dir)
        
        return None, "无法处理的声库格式"
    
    def _handle_zip_library(self, zip_path: Path, library_type: str, target_dir: Optional[Path]) -> Tuple[Optional[VoiceLibrary], str]:
        """处理 ZIP 格式声库"""
        try:
            # 创建临时目录
            if target_dir is None:
                temp_dir = tempfile.mkdtemp(prefix="pyutau_")
                self.temp_dirs[str(zip_path)] = temp_dir
            else:
                temp_dir = str(target_dir)
                os.makedirs(temp_dir, exist_ok=True)
            
            # 解压 ZIP 文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            print(f"ZIP 文件解压到: {temp_dir}")
            
            # 加载解压后的声库
            return self._handle_directory_library(Path(temp_dir), library_type, None)
            
        except Exception as e:
            return None, f"处理 ZIP 声库失败: {e}"
    
    def _handle_directory_library(self, dir_path: Path, library_type: str, target_dir: Optional[Path]) -> Tuple[Optional[VoiceLibrary], str]:
        """处理目录格式声库"""
        try:
            if library_type == "utau":
                return self._load_utau_library(dir_path), "成功加载 UTAU 声库"
            elif library_type == "vocaloid":
                return self._load_vocaloid_library(dir_path), "成功加载 Vocaloid 声库"
            elif library_type == "cevio":
                return self._load_cevio_library(dir_path), "成功加载 CeVIO 声库"
            elif library_type == "generic_audio":
                return self._load_generic_audio_library(dir_path), "成功加载通用音频库"
            else:
                return None, f"未实现的声库类型: {library_type}"
        except Exception as e:
            return None, f"加载 {library_type} 声库失败: {e}"
    
    def _load_utau_library(self, dir_path: Path) -> VoiceLibrary:
        """加载 UTAU 声库 - 使用现有的 VoiceLibrary"""
        return VoiceLibrary(dir_path)
    
    def _load_vocaloid_library(self, dir_path: Path) -> VoiceLibrary:
        """加载 Vocaloid 声库"""
        # 创建临时的 UTAU 兼容结构
        temp_utau_dir = tempfile.mkdtemp(prefix="vocaloid_to_utau_")
        self.temp_dirs[str(dir_path)] = temp_utau_dir
        
        print(f"转换 Vocaloid 声库到 UTAU 格式: {temp_utau_dir}")
        
        # 复制所有音频文件
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg']
        for ext in audio_extensions:
            for audio_file in dir_path.rglob(f"*{ext}"):
                # 复制到临时目录
                target_file = Path(temp_utau_dir) / audio_file.name
                shutil.copy2(audio_file, target_file)
        
        # 创建基本的 oto.ini
        self._create_vocaloid_oto_ini(dir_path, temp_utau_dir)
        
        # 复制角色信息
        self._copy_character_info(dir_path, temp_utau_dir)
        
        # 使用标准的 VoiceLibrary 加载
        return VoiceLibrary(Path(temp_utau_dir))
    
    def _load_cevio_library(self, dir_path: Path) -> VoiceLibrary:
        """加载 CeVIO 声库"""
        # 创建临时的 UTAU 兼容结构
        temp_utau_dir = tempfile.mkdtemp(prefix="cevio_to_utau_")
        self.temp_dirs[str(dir_path)] = temp_utau_dir
        
        print(f"转换 CeVIO 声库到 UTAU 格式: {temp_utau_dir}")
        
        # 复制所有音频文件
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg']
        for ext in audio_extensions:
            for audio_file in dir_path.rglob(f"*{ext}"):
                # 复制到临时目录
                target_file = Path(temp_utau_dir) / audio_file.name
                shutil.copy2(audio_file, target_file)
        
        # 创建基本的 oto.ini
        self._create_cevio_oto_ini(dir_path, temp_utau_dir)
        
        # 复制角色信息
        self._copy_character_info(dir_path, temp_utau_dir)
        
        # 使用标准的 VoiceLibrary 加载
        return VoiceLibrary(Path(temp_utau_dir))
    
    def _load_generic_audio_library(self, dir_path: Path) -> VoiceLibrary:
        """加载通用音频库"""
        # 创建临时的 UTAU 兼容结构
        temp_utau_dir = tempfile.mkdtemp(prefix="generic_to_utau_")
        self.temp_dirs[str(dir_path)] = temp_utau_dir
        
        print(f"转换通用音频库到 UTAU 格式: {temp_utau_dir}")
        
        # 复制所有音频文件
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg']
        for ext in audio_extensions:
            for audio_file in dir_path.rglob(f"*{ext}"):
                # 复制到临时目录
                target_file = Path(temp_utau_dir) / audio_file.name
                shutil.copy2(audio_file, target_file)
        
        # 创建基本的 oto.ini
        self._create_generic_oto_ini(dir_path, temp_utau_dir)
        
        # 创建基本的角色信息
        self._create_generic_character_info(dir_path, temp_utau_dir)
        
        # 使用标准的 VoiceLibrary 加载
        return VoiceLibrary(Path(temp_utau_dir))
    
    def _create_vocaloid_oto_ini(self, source_dir: Path, target_dir: str):
        """为 Vocaloid 声库创建 oto.ini"""
        oto_path = Path(target_dir) / "oto.ini"
        
        audio_files = list(Path(target_dir).glob("*.wav")) + list(Path(target_dir).glob("*.mp3"))
        
        with open(oto_path, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                # 从文件名推断参数
                filename = audio_file.stem
                lyric = self._extract_lyric_from_filename(filename)
                
                # 简单的 oto.ini 条目
                f.write(f"{audio_file.name}={lyric}\n")
    
    def _create_cevio_oto_ini(self, source_dir: Path, target_dir: str):
        """为 CeVIO 声库创建 oto.ini"""
        oto_path = Path(target_dir) / "oto.ini"
        
        audio_files = list(Path(target_dir).glob("*.wav")) + list(Path(target_dir).glob("*.mp3"))
        
        with open(oto_path, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                filename = audio_file.stem
                lyric = self._extract_lyric_from_filename(filename)
                
                f.write(f"{audio_file.name}={lyric}\n")
    
    def _create_generic_oto_ini(self, source_dir: Path, target_dir: str):
        """为通用音频库创建 oto.ini"""
        oto_path = Path(target_dir) / "oto.ini"
        
        audio_files = list(Path(target_dir).glob("*.wav")) + list(Path(target_dir).glob("*.mp3"))
        
        with open(oto_path, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                filename = audio_file.stem
                lyric = self._extract_lyric_from_filename(filename)
                
                f.write(f"{audio_file.name}={lyric}\n")
    
    def _extract_lyric_from_filename(self, filename: str) -> str:
        """从文件名提取歌词"""
        import re
        
        # 移除数字和常见符号
        cleaned = re.sub(r'[\d_\-\.]', '', filename)
        
        # 如果是日文，提取第一个假名
        japanese_pattern = r'[ぁ-んァ-ンー]'
        japanese_chars = re.findall(japanese_pattern, cleaned)
        if japanese_chars:
            return japanese_chars[0]
        
        # 如果是中文，提取第一个汉字
        chinese_pattern = r'[\u4e00-\u9fff]'
        chinese_chars = re.findall(chinese_pattern, cleaned)
        if chinese_chars:
            return chinese_chars[0]
        
        # 否则返回前2个字母
        return cleaned[:2] if len(cleaned) >= 2 else cleaned
    
    def _copy_character_info(self, source_dir: Path, target_dir: str):
        """复制角色信息文件"""
        char_files = list(source_dir.rglob("character.txt")) + \
                    list(source_dir.rglob("character.yaml")) + \
                    list(source_dir.rglob("character.yml")) + \
                    list(source_dir.rglob("readme.txt"))
        
        for char_file in char_files:
            try:
                target_file = Path(target_dir) / char_file.name
                shutil.copy2(char_file, target_file)
                break
            except:
                pass
    
    def _create_generic_character_info(self, source_dir: Path, target_dir: str):
        """为通用音频库创建角色信息"""
        char_path = Path(target_dir) / "character.txt"
        
        with open(char_path, 'w', encoding='utf-8') as f:
            f.write(f"name={source_dir.name}\n")
            f.write("author=Unknown\n")
            f.write("image=\n")
            f.write("description=Converted from generic audio library\n")
    
    def cleanup_temp_dirs(self):
        """清理临时目录"""
        for temp_dir in self.temp_dirs.values():
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        self.temp_dirs.clear()
