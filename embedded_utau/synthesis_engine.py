# embedded_utau/synthesis_engine.py
import numpy as np
from pathlib import Path
import scipy.signal as signal
from scipy.io import wavfile
import librosa
import logging
from typing import Optional, Dict
try:
    from embedded_utau.voice_library import VoiceLibrary
    from embedded_utau.note import Track
    from embedded_utau.project import Project
    from embedded_utau.library_adapter import LibraryAdapter
except ImportError:
    from .voice_library import VoiceLibrary
    from .note import Track
    from .project import Project
    from .library_adapter import LibraryAdapter

class SynthesisEngine:
    """扩展的合成引擎 - 支持多音轨和不同音源库"""
    
    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate
        self.voice_libraries: Dict[str, VoiceLibrary] = {}  # 路径 -> 音源库映射
        self.logger = self.setup_logger()
        self.sample_cache: Dict[str, np.ndarray] = {}  # 样本缓存
        self.library_adapter = LibraryAdapter()
    
    def load_voice_library(self, library_path: str) -> bool:
        """加载音源库到引擎 - 支持多格式"""
        try:
            if library_path not in self.voice_libraries:
                # 使用通用适配器加载声库
                voice_lib, message = self.library_adapter.load_library(Path(library_path))
                
                if voice_lib:
                    self.voice_libraries[library_path] = voice_lib
                    print(f"成功加载音源库: {voice_lib.get_library_name()} - {message}")
                    return True
                else:
                    print(f"加载音源库失败 {library_path}: {message}")
                    return False
            return True
        except Exception as e:
            print(f"加载音源库失败 {library_path}: {e}")
            return False
    
    def unload_voice_library(self, library_path: str):
        """卸载音源库"""
        if library_path in self.voice_libraries:
            del self.voice_libraries[library_path]
    
    def get_voice_library(self, library_path: str) -> Optional[VoiceLibrary]:
        """获取音源库"""
        return self.voice_libraries.get(library_path)
    
    def synthesize_project(self, project: Project) -> np.ndarray:
        """合成整个项目 - 多音轨混合"""
        print(f"开始合成项目 '{project.name}'，包含 {len(project.tracks)} 个音轨")
        
        # 计算项目总时长
        total_duration = project.settings.total_duration
        total_samples = int(total_duration * self.sample_rate)
        master_output = np.zeros(total_samples)
        
        # 处理每个音轨
        for i, track in enumerate(project.tracks):
            if track.muted:
                print(f"跳过静音音轨: {track.name}")
                continue
            
            if track.solo and not any(t.solo for t in project.tracks if not t.muted):
                # 如果有solo音轨，只处理solo音轨
                continue
            
            print(f"合成音轨 {i+1}/{len(project.tracks)}: {track.name}")
            
            # 加载音轨的音源库
            if track.voice_library_path:
                if not self.load_voice_library(track.voice_library_path):
                    print(f"警告: 无法加载音轨 {track.name} 的音源库")
                    continue
                
                voice_lib = self.get_voice_library(track.voice_library_path)
                if not voice_lib:
                    print(f"警告: 音轨 {track.name} 的音源库未找到")
                    continue
            else:
                print(f"警告: 音轨 {track.name} 没有设置音源库")
                continue
            
            # 合成音轨
            track_audio = self.synthesize_track(track, voice_lib)
            
            # 应用音轨音量和平移
            track_audio = self.apply_track_mix(track_audio, track.volume, track.pan)
            
            # 混合到主输出
            min_len = min(len(track_audio), len(master_output))
            master_output[:min_len] += track_audio[:min_len]
        
        # 主输出处理
        master_output = self.master_processing(master_output)
        
        print("项目合成完成")
        return master_output
    
    def synthesize_track(self, track: Track, voice_library: VoiceLibrary) -> np.ndarray:
        """合成单个音轨"""
        if not track.notes:
            print(f"音轨 {track.name} 没有音符")
            return np.zeros(int(self.sample_rate * 10))  # 返回10秒静音
        
        # 计算音轨时长
        track_duration = max((note.start_time + note.duration for note in track.notes), default=10)
        track_samples = int(track_duration * self.sample_rate)
        track_output = np.zeros(track_samples)
        
        for i, note in enumerate(track.notes):
            print(f"  合成音符 {i+1}/{len(track.notes)}: {note.lyric} 音高{note.pitch}")
            
            # 获取合适的样本
            sample = voice_library.get_best_sample(note.lyric, note.pitch)
            if sample:
                # 合成音符
                note_audio = self.synthesize_note_safe(note, sample)
                
                # 混合到音轨输出
                start_sample = int(note.start_time * self.sample_rate)
                end_sample = start_sample + len(note_audio)
                
                if end_sample <= len(track_output):
                    track_output[start_sample:end_sample] += note_audio
                else:
                    # 如果超出范围，扩展输出数组
                    extension = end_sample - len(track_output)
                    track_output = np.pad(track_output, (0, extension), mode='constant')
                    track_output[start_sample:end_sample] += note_audio
        
        return track_output
    
    def apply_track_mix(self, audio_data: np.ndarray, volume: float, pan: float) -> np.ndarray:
        """应用音轨混音设置（音量和声像）"""
        # 应用音量
        audio_data = audio_data * volume
        
        # 应用声像（简单的立体声平衡）
        if len(audio_data) > 0:
            # 创建立体声（目前还是单声道，但为未来扩展准备）
            left_gain = 1.0 if pan <= 0 else 1.0 - pan
            right_gain = 1.0 if pan >= 0 else 1.0 + pan
            
            # 目前还是返回单声道，但应用平衡
            balanced_mono = audio_data * (left_gain + right_gain) / 2
            return balanced_mono
        
        return audio_data
    
    def master_processing(self, audio_data: np.ndarray) -> np.ndarray:
        """主输出处理"""
        if len(audio_data) == 0:
            return audio_data
        
        print("应用主输出处理...")
        
        try:
            # 1. 移除DC偏移
            audio_data = audio_data - np.mean(audio_data)
            
            # 2. 多段均衡器
            audio_data = self.multiband_eq(audio_data)
            
            # 3. 压缩器
            audio_data = self.advanced_compression(audio_data)
            
            # 4. 限制器
            audio_data = self.limiter(audio_data)
            
            # 5. 最终归一化
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                target_level = 0.9  # 留出余量
                audio_data = audio_data / max_val * target_level
            
            print("主输出处理完成")
            return audio_data
            
        except Exception as e:
            print(f"主输出处理失败: {e}")
            return audio_data
    
    def synthesize_note_safe(self, note, sample):
        """安全的音符合成-带缓存"""
        cache_key = f"{sample.file_path}_{note.pitch}_{note.duration}"
        
        if cache_key in self.sample_cache:
            return self.sample_cache[cache_key].copy()
        try:
            # 加载样本
            sample.load_sample()
            
            # 检查样本数据
            if sample.sample_data is None or len(sample.sample_data) == 0:
                print(f"警告: 样本数据为空，使用静音")
                return np.zeros(int(note.duration * self.sample_rate))
            
            # 预处理样本
            audio_data = self.preprocess_sample(sample.sample_data)
            
            # 应用音高移动
            semitones = note.pitch - sample.pitch
            if abs(semitones) > 0.5:  # 只在实际需要时移动音高
                print(f"  音高移动: {semitones} 半音")
                audio_data = self.safe_pitch_shift(audio_data, semitones)
            
            # 调整持续时间
            target_samples = int(note.duration * self.sample_rate)
            audio_data = self.time_stretch_safe(audio_data, target_samples)
            
            # 应用包络
            audio_data = self.apply_note_envelope(audio_data)
            
            # 最终安全检查
            audio_data = self.final_safety_check(audio_data)
            
            # 缓存结果（限制缓存大小）
            if len(self.sample_cache) > 100:
                self.sample_cache.pop(next(iter(self.sample_cache)))
            self.sample_cache[cache_key] = audio_data.copy()
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"合成音符失败: {e}")
            return np.zeros(int(note.duration * self.sample_rate))
    
    def preprocess_sample(self, audio_data):
        """预处理样本数据"""
        # 移除DC偏移
        audio_data = audio_data - np.mean(audio_data)
        
        # 应用轻微的淡入淡出避免咔嗒声
        fade_samples = min(100, len(audio_data) // 10)
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            audio_data[:fade_samples] *= fade_in
            audio_data[-fade_samples:] *= fade_out
        
        # 轻微压缩避免过载
        threshold = 0.8
        compression_ratio = 1.5
        compressed = np.tanh(audio_data * compression_ratio) / compression_ratio
        
        return compressed
    
    def safe_pitch_shift(self, audio_data, semitones):
        """安全的音高移动"""
        try:
            # 限制音高移动范围
            semitones = max(-24, min(24, semitones))
            
            # 对于小范围移动，使用更高质量设置
            if abs(semitones) <= 6:
                n_fft = 2048
                hop_length = 512
            else:
                n_fft = 4096  # 更大的FFT窗口用于大范围移动
                hop_length = 1024
            
            # 确保参数有效
            if len(audio_data) < n_fft:
                n_fft = 1024
                hop_length = 256
            
            if len(audio_data) < n_fft:
                print(f"  音频过短 ({len(audio_data)} 样本)，跳过音高移动")
                return audio_data
            
            # 使用librosa进行音高移动
            shifted = librosa.effects.pitch_shift(
                y=audio_data,
                sr=self.sample_rate,
                n_steps=semitones,
                n_fft=n_fft,
                hop_length=hop_length,
                bins_per_octave=12
            )
            
            return shifted
            
        except Exception as e:
            print(f"音高移动失败: {e}")
            return audio_data
    
    def time_stretch_safe(self, audio_data, target_samples):
        """安全的时间拉伸"""
        current_samples = len(audio_data)
        
        if current_samples == target_samples:
            return audio_data
        
        ratio = target_samples / current_samples
        
        # 对于小范围拉伸，使用高质量设置
        if 0.5 <= ratio <= 2.0:
            # 使用相位声码器进行高质量时间拉伸
            try:
                stretched = librosa.effects.time_stretch(
                    y=audio_data,
                    rate=1/ratio
                )
                
                # 确保长度正确
                if len(stretched) > target_samples:
                    return stretched[:target_samples]
                elif len(stretched) < target_samples:
                    return np.pad(stretched, (0, target_samples - len(stretched)), mode='constant')
                else:
                    return stretched
                    
            except Exception as e:
                print(f"时间拉伸失败: {e}, 使用简单方法")
        
        # 后备方法：交叉淡化重复
        return self.crossfade_repeat(audio_data, target_samples)
    
    def crossfade_repeat(self, audio_data, target_samples):
        """交叉淡化重复"""
        current_samples = len(audio_data)
        
        if current_samples >= target_samples:
            # 缩短 - 应用淡出
            fade_out_len = min(current_samples - target_samples, 512)
            shortened = audio_data[:target_samples].copy()
            if fade_out_len > 0:
                fade_out = np.linspace(1, 0, fade_out_len)
                shortened[-fade_out_len:] *= fade_out
            return shortened
        
        # 延长 - 使用重叠相加
        result = np.zeros(target_samples)
        pos = 0
        
        while pos < target_samples:
            # 计算这次复制的长度
            copy_len = min(current_samples, target_samples - pos)
            
            if pos == 0:
                # 第一次复制，不需要交叉淡化
                result[:copy_len] = audio_data[:copy_len]
            else:
                # 后续复制，应用交叉淡化
                overlap_len = min(256, current_samples // 4, pos, copy_len)
                
                if overlap_len > 0:
                    # 交叉淡化区域
                    fade_out = np.linspace(1, 0, overlap_len)
                    fade_in = 1 - fade_out
                    
                    # 应用交叉淡化
                    result[pos:pos+overlap_len] = (
                        result[pos:pos+overlap_len] * fade_out + 
                        audio_data[:overlap_len] * fade_in
                    )
                    
                    # 复制剩余部分
                    if copy_len > overlap_len:
                        result[pos+overlap_len:pos+copy_len] = audio_data[overlap_len:copy_len]
                else:
                    # 没有重叠，直接复制
                    result[pos:pos+copy_len] = audio_data[:copy_len]
            
            pos += copy_len
        
        return result
    
    def apply_note_envelope(self, audio_data):
        """应用音符包络"""
        length = len(audio_data)
        if length < 10:
            return audio_data
        
        envelope = np.ones(length)
        
        # 使用更长的淡入淡出时间
        attack_len = min(int(0.15 * length), 1500)   # 15% 或最多1500样本
        release_len = min(int(0.35 * length), 3500)  # 35% 或最多3500样本
        
        # 使用更平滑的曲线
        if attack_len > 0:
            t = np.linspace(0, 1, attack_len)
            # 使用正弦曲线获得更自然的淡入
            envelope[:attack_len] = 0.5 - 0.5 * np.cos(np.pi * t)
        
        if release_len > 0:
            t = np.linspace(0, 1, release_len)
            # 使用正弦曲线获得更自然的淡出
            envelope[-release_len:] = 0.5 + 0.5 * np.cos(np.pi * t)
        
        return audio_data * envelope
    
    def final_safety_check(self, audio_data):
        """最终安全检查"""
        # 移除任何NaN或无穷大
        audio_data = np.nan_to_num(audio_data)
        
        # 限制幅度
        audio_data = np.clip(audio_data, -0.95, 0.95)
        
        # 应用轻微的平滑
        if len(audio_data) > 3:
            audio_data[1:-1] = 0.25 * audio_data[:-2] + 0.5 * audio_data[1:-1] + 0.25 * audio_data[2:]
        
        return audio_data
    
    def multiband_eq(self, audio_data):
        """多段均衡器"""
        try:
            # 设计多个频段的滤波器
            nyquist = self.sample_rate / 2
            
            # 低频增强 (80-300Hz)
            b_low, a_low = signal.butter(2, [80/nyquist, 300/nyquist], btype='band')
            low_band = signal.filtfilt(b_low, a_low, audio_data)
            
            # 中频控制 (300-3000Hz)
            b_mid, a_mid = signal.butter(2, [300/nyquist, 3000/nyquist], btype='band')
            mid_band = signal.filtfilt(b_mid, a_mid, audio_data)
            
            # 高频衰减 (3000Hz以上)
            b_high, a_high = signal.butter(2, 3000/nyquist, btype='high')
            high_band = signal.filtfilt(b_high, a_high, audio_data)
            
            # 混合各频段
            result = (
                1.2 * low_band +    # 低频增强20%
                1.0 * mid_band +    # 中频保持
                0.7 * high_band     # 高频衰减30%
            )
            
            return result
            
        except Exception as e:
            print(f"均衡器失败: {e}")
            return audio_data
    
    def advanced_compression(self, audio_data):
        """高级压缩器"""
        # 简单的软膝压缩器
        threshold = 0.3
        ratio = 2.0
        knee_width = 0.1
        
        compressed = audio_data.copy()
        
        # 计算每个样本的增益减少
        above_threshold = np.abs(audio_data) > threshold - knee_width/2
        
        if np.any(above_threshold):
            # 软膝压缩
            excess = np.abs(audio_data[above_threshold]) - (threshold - knee_width/2)
            excess = np.maximum(0, excess)
            
            # 在膝部区域内线性过渡
            in_knee = excess < knee_width
            if np.any(in_knee):
                # 膝部区域：从1:1过渡到设定的压缩比
                knee_ratio = 1 + (ratio - 1) * excess[in_knee] / knee_width
                gain_reduction = excess[in_knee] * (1 - 1/knee_ratio)
                compressed[above_threshold][in_knee] = (
                    np.sign(audio_data[above_threshold][in_knee]) * 
                    (threshold - knee_width/2 + excess[in_knee] - gain_reduction)
                )
            
            # 膝部以上：完全压缩
            above_knee = ~in_knee
            if np.any(above_knee):
                gain_reduction = excess[above_knee] * (1 - 1/ratio)
                compressed[above_threshold][above_knee] = (
                    np.sign(audio_data[above_threshold][above_knee]) * 
                    (threshold - knee_width/2 + excess[above_knee] - gain_reduction)
                )
        
        return compressed
    
    def limiter(self, audio_data):
        """限制器 - 防止过载"""
        threshold = 0.9
        
        # 简单的峰值限制
        peaks = np.abs(audio_data)
        over_threshold = peaks > threshold
        
        if np.any(over_threshold):
            # 计算需要的增益减少
            reduction = peaks[over_threshold] / threshold
            audio_data[over_threshold] = audio_data[over_threshold] / reduction
        
        return audio_data
    
    def export_audio(self, audio_data, filepath):
        """导出音频文件"""
        try:
            # 最终安全检查
            audio_data = np.nan_to_num(audio_data)
            audio_data = np.clip(audio_data, -1.0, 1.0)
            
            # 转换为16位PCM
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # 保存为WAV
            wavfile.write(filepath, self.sample_rate, audio_int16)
            print(f"音频已成功导出: {filepath}")
            return True
            
        except Exception as e:
            print(f"导出音频失败: {e}")
            return False
    def setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger('SynthesisEngine')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
