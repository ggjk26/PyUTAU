# embedded_utau/__init__.py
"""
PyUTAU - 基于Python的UTAU-like语音合成库
"""

from .gui_component import PyUTAUComponent
from .synthesis_engine import SynthesisEngine
from .voice_library import VoiceLibrary
from .note import Note, Track
from .project import Project, ProjectSettings
from .ust_parser import USTParser
from .library_adapter import LibraryAdapter  # 新增
from .library_detector import LibraryDetector  # 新增

__version__ = "0.0.4"  # 更新版本号
__all__ = [
    'PyUTAUComponent', 
    'SynthesisEngine', 
    'VoiceLibrary', 
    'Note', 
    'Track', 
    'Project',
    'ProjectSettings',
    'USTParser',
    'LibraryAdapter',  # 新增
    'LibraryDetector'  # 新增
]
