# embedded_utau/library_detector.py
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import zipfile
import tempfile

class LibraryDetector:
    """声库类型检测器"""
    
    @staticmethod
    def detect_library_type(library_path: Path) -> str:
        """检测声库类型"""
        library_path = Path(library_path)
        
        # 检查是否是 ZIP 文件
        if library_path.suffix.lower() == '.zip':
            return LibraryDetector.detect_zip_library_type(library_path)
        
        # 检查目录结构
        if library_path.is_dir():
            return LibraryDetector.detect_directory_library_type(library_path)
        
        return "unknown"
    
    @staticmethod
    def detect_zip_library_type(zip_path: Path) -> str:
        """检测 ZIP 文件中的声库类型"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                # 检查 UTAU 特征文件
                if any('oto.ini' in f.lower() for f in file_list):
                    return "utau"
                
                # 检查 Vocaloid 特征文件
                if any('.vpr' in f.lower() for f in file_list):
                    return "vocaloid"
                if any('character.txt' in f.lower() for f in file_list) and any('.wav' in f.lower() for f in file_list):
                    return "vocaloid"
                
                # 检查 CeVIO 特征文件
                if any('.voice' in f.lower() for f in file_list):
                    return "cevio"
                if any('.ccs' in f.lower() for f in file_list):
                    return "cevio"
                
        except Exception as e:
            print(f"检测 ZIP 声库类型失败: {e}")
        
        return "unknown"
    
    @staticmethod
    def detect_directory_library_type(dir_path: Path) -> str:
        """检测目录中的声库类型"""
        # 检查 UTAU 特征
        if (dir_path / "oto.ini").exists():
            return "utau"
        
        # 检查 Vocaloid 特征
        vpr_files = list(dir_path.rglob("*.vpr"))
        if vpr_files:
            return "vocaloid"
        
        # 检查是否有 Vocaloid 典型的目录结构
        if (dir_path / "character.txt").exists() and any(dir_path.rglob("*.wav")):
            return "vocaloid"
        
        # 检查 CeVIO 特征
        voice_files = list(dir_path.rglob("*.voice"))
        ccs_files = list(dir_path.rglob("*.ccs"))
        if voice_files or ccs_files:
            return "cevio"
        
        # 检查是否有音频文件但无明确格式标识
        audio_files = list(dir_path.rglob("*.wav")) + list(dir_path.rglob("*.mp3"))
        if audio_files:
            return "generic_audio"  # 通用音频库
        
        return "unknown"
    
    @staticmethod
    def extract_library_info(library_path: Path, library_type: str) -> Dict:
        """提取声库基本信息"""
        info = {
            "type": library_type,
            "name": library_path.name,
            "path": str(library_path),
            "format_version": "unknown"
        }
        
        if library_type == "vocaloid":
            info.update(LibraryDetector._extract_vocaloid_info(library_path))
        elif library_type == "cevio":
            info.update(LibraryDetector._extract_cevio_info(library_path))
        elif library_type == "utau":
            info.update(LibraryDetector._extract_utau_info(library_path))
        
        return info
    
    @staticmethod
    def _extract_vocaloid_info(library_path: Path) -> Dict:
        """提取 Vocaloid 声库信息"""
        info = {}
        
        # 查找 VPR 文件（Vocaloid 5 工程文件）
        vpr_files = list(library_path.rglob("*.vpr"))
        if vpr_files:
            info["format_version"] = "vocaloid5"
            # 可以添加更多 VPR 解析逻辑
            
        # 查找 character.txt
        char_files = list(library_path.rglob("character.txt"))
        if char_files:
            try:
                with open(char_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # 简单解析角色信息
                    for line in content.split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == 'name':
                                info["name"] = value
                            elif key == 'author':
                                info["author"] = value
            except:
                pass
        
        return info
    
    @staticmethod
    def _extract_cevio_info(library_path: Path) -> Dict:
        """提取 CeVIO 声库信息"""
        info = {}
        
        # 查找 VOICE 文件
        voice_files = list(library_path.rglob("*.voice"))
        if voice_files:
            info["format_version"] = "cevio_voice"
        
        # 查找 CCS 文件（CeVIO 工程文件）
        ccs_files = list(library_path.rglob("*.ccs"))
        if ccs_files:
            info["format_version"] = "cevio_ccs"
        
        return info
    
    @staticmethod
    def _extract_utau_info(library_path: Path) -> Dict:
        """提取 UTAU 声库信息"""
        info = {"format_version": "utau_standard"}
        
        # 这里可以添加更多 UTAU 特定信息的提取
        char_files = list(library_path.rglob("character.txt"))
        if char_files:
            try:
                with open(char_files[0], 'r', encoding='shift_jis', errors='ignore') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == 'name':
                                info["name"] = value
                            elif key in ['author', 'creator']:
                                info["author"] = value
            except:
                pass
        
        return info
