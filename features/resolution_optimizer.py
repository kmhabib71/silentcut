"""
Resolution Optimizer for Silence Cutter
Automatically detects video resolution and applies appropriate optimizations for 4K/8K processing
while maintaining current functionality for lower resolutions.
"""

import os
import subprocess
import threading
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal

# Try to import psutil, fallback to basic system info if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ResolutionOptimizer(QObject):
    """Optimizes processing settings based on video resolution"""
    
    optimization_applied = pyqtSignal(str, dict)  # resolution_category, settings
    
    # Resolution categories
    RESOLUTION_CATEGORIES = {
        'SD': {'max_width': 720, 'max_height': 576},      # Standard Definition
        'HD': {'max_width': 1280, 'max_height': 720},     # HD 720p
        'FHD': {'max_width': 1920, 'max_height': 1080},   # Full HD 1080p
        '4K': {'max_width': 3840, 'max_height': 2160},    # 4K UHD
        '8K': {'max_width': 7680, 'max_height': 4320},    # 8K UHD
        'ULTRA': {'max_width': 99999, 'max_height': 99999} # Beyond 8K
    }
    
    def __init__(self):
        super().__init__()
        self.current_optimizations = {}
        self.system_capabilities = self._analyze_system_capabilities()
        
    def _analyze_system_capabilities(self):
        """Analyze system capabilities for optimal settings"""
        if PSUTIL_AVAILABLE:
            capabilities = {
                'total_memory_gb': psutil.virtual_memory().total / (1024**3),
                'available_memory_gb': psutil.virtual_memory().available / (1024**3),
                'cpu_cores': psutil.cpu_count(),
                'cpu_threads': psutil.cpu_count(logical=True),
                'has_ssd': self._detect_ssd_storage(),
                'gpu_memory_estimate': self._estimate_gpu_memory()
            }
        else:
            # Fallback to basic estimates
            capabilities = {
                'total_memory_gb': 8.0,  # Conservative estimate
                'available_memory_gb': 4.0,  # Conservative estimate
                'cpu_cores': 4,  # Conservative estimate
                'cpu_threads': 8,  # Conservative estimate
                'has_ssd': True,  # Assume SSD for modern systems
                'gpu_memory_estimate': 2.0  # Conservative estimate
            }
        
        
        return capabilities
        
    def _detect_ssd_storage(self):
        """Detect if primary storage is SSD (simplified detection)"""
        if not PSUTIL_AVAILABLE:
            return True  # Assume SSD for modern systems
            
        try:
            # This is a simplified check - in production you might want more sophisticated detection
            disk_usage = psutil.disk_usage('/')
            return disk_usage.total > 100 * 1024**3  # Assume SSD if >100GB
        except:
            return True  # Default to SSD assumption
            
    def _estimate_gpu_memory(self):
        """Estimate GPU memory (simplified)"""
        try:
            # Try to detect NVIDIA GPU memory
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return int(result.stdout.strip()) / 1024  # Convert MB to GB
        except:
            pass
        
        # Fallback estimate based on system memory
        if hasattr(self, 'system_capabilities'):
            return min(self.system_capabilities.get('total_memory_gb', 8) / 4, 8)
        else:
            return 2.0  # Conservative fallback
        
    def get_video_resolution(self, video_path):
        """Get video resolution using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration,bit_rate',
                '-of', 'csv=p=0', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                if len(parts) >= 2:
                    width = int(parts[0])
                    height = int(parts[1])
                    duration = float(parts[2]) if len(parts) > 2 and parts[2] else 0
                    bitrate = int(parts[3]) if len(parts) > 3 and parts[3] else 0
                    
                    return {
                        'width': width,
                        'height': height,
                        'duration': duration,
                        'bitrate': bitrate,
                        'total_pixels': width * height,
                        'file_size': os.path.getsize(video_path)
                    }
        except Exception as e:
            pass
            
        return None
        
    def categorize_resolution(self, width, height):
        """Categorize video resolution"""
        total_pixels = width * height
        
        for category, limits in self.RESOLUTION_CATEGORIES.items():
            if width <= limits['max_width'] and height <= limits['max_height']:
                return category
                
        return 'ULTRA'
        
    def get_optimized_settings(self, video_path):
        """Get optimized settings based on video resolution and system capabilities"""
        video_info = self.get_video_resolution(video_path)
        if not video_info:
            return self._get_default_settings()
            
        width = video_info['width']
        height = video_info['height']
        category = self.categorize_resolution(width, height)
        
        
        # Get category-specific settings
        if category in ['4K', '8K', 'ULTRA']:
            settings = self._get_high_resolution_settings(category, video_info)
        else:
            settings = self._get_standard_settings(category, video_info)
            
        # Apply system-specific adjustments
        settings = self._apply_system_adjustments(settings, video_info)
        
        self.current_optimizations = settings
        self.optimization_applied.emit(category, settings)
        
        return settings
        
    def _get_standard_settings(self, category, video_info):
        """Get settings for SD/HD/FHD videos (maintains current functionality)"""
        return {
            'category': category,
            'buffer_settings': {
                'frame_buffer_size': 30,  # Current default
                'audio_buffer_duration': 10.0,  # Current default
                'waveform_cache_levels': 10,  # Current default
                'enable_prefetch': True
            },
            'preview_settings': {
                'target_width': 1280,  # Current 720p target
                'interpolation': 'INTER_LINEAR',  # Current default
                'quality_mode': 'balanced'
            },
            'processing_settings': {
                'use_hardware_acceleration': True,
                'preset': 'fast',  # Current default
                'crf_quality': 23,  # Current default
                'parallel_batch': False,  # Current behavior
                'memory_limit_mb': None  # No limit (current behavior)
            },
            'detection_settings': {
                'chunk_size_seconds': 30,  # Current default
                'use_fast_detection': True
            },
            'optimizations_applied': ['standard_processing']
        }
        
    def _get_high_resolution_settings(self, category, video_info):
        """Get optimized settings for 4K/8K videos"""
        width = video_info['width']
        height = video_info['height']
        duration = video_info['duration']
        file_size_gb = video_info['file_size'] / (1024**3)
        
        # Calculate memory requirements
        estimated_frame_memory_mb = (width * height * 3) / (1024**2)  # RGB frame in MB
        
        # Adaptive buffer sizing
        if category == '8K' or estimated_frame_memory_mb > 100:
            frame_buffer_size = 5  # Very small buffer for 8K
            preview_target = 1920  # 1080p preview for 8K
        elif category == '4K':
            frame_buffer_size = 10  # Smaller buffer for 4K
            preview_target = 1920  # 1080p preview for 4K
        else:  # ULTRA
            frame_buffer_size = 3
            preview_target = 1280
            
        # Quality settings based on resolution
        if category == '8K':
            crf_quality = 18  # Higher quality for 8K
            preset = 'slow'   # Better compression for 8K
            bitrate_target = '50M'
        elif category == '4K':
            crf_quality = 20  # Higher quality for 4K
            preset = 'medium' # Balanced for 4K
            bitrate_target = '25M'
        else:  # ULTRA
            crf_quality = 16
            preset = 'veryslow'
            bitrate_target = '100M'
            
        # Memory management
        memory_limit_mb = min(
            self.system_capabilities['available_memory_gb'] * 1024 * 0.6,  # 60% of available
            8192  # Max 8GB
        )
        
        settings = {
            'category': category,
            'buffer_settings': {
                'frame_buffer_size': frame_buffer_size,
                'audio_buffer_duration': 5.0,  # Smaller audio buffer
                'waveform_cache_levels': 5,    # Fewer cache levels
                'enable_prefetch': False       # Disable prefetch for high-res
            },
            'preview_settings': {
                'target_width': preview_target,
                'interpolation': 'INTER_AREA',  # Better for downscaling
                'quality_mode': 'performance'   # Prioritize performance
            },
            'processing_settings': {
                'use_hardware_acceleration': True,
                'preset': preset,
                'crf_quality': crf_quality,
                'bitrate_target': bitrate_target,
                'parallel_batch': self._should_enable_parallel_batch(video_info),
                'memory_limit_mb': int(memory_limit_mb),
                'use_two_pass': duration > 300,  # Two-pass for long videos
                'gpu_memory_fraction': 0.8 if category == '8K' else 0.6
            },
            'detection_settings': {
                'chunk_size_seconds': 60 if category == '8K' else 45,  # Larger chunks
                'use_fast_detection': True,
                'parallel_detection': True
            },
            'optimizations_applied': [
                f'{category.lower()}_optimized',
                'adaptive_buffering',
                'memory_management',
                'high_quality_encoding'
            ]
        }
        
        # Add system-specific optimizations
        if file_size_gb > 10:  # Large files
            settings['optimizations_applied'].append('large_file_handling')
            settings['processing_settings']['streaming_mode'] = True
            
        if not self.system_capabilities['has_ssd']:
            settings['optimizations_applied'].append('hdd_optimization')
            settings['buffer_settings']['frame_buffer_size'] = max(1, frame_buffer_size // 2)
            
        return settings
        
    def _should_enable_parallel_batch(self, video_info):
        """Determine if parallel batch processing should be enabled"""
        file_size_gb = video_info['file_size'] / (1024**3)
        available_memory_gb = self.system_capabilities['available_memory_gb']
        cpu_cores = self.system_capabilities['cpu_cores']
        
        # Enable parallel if we have enough resources
        return (
            cpu_cores >= 4 and 
            available_memory_gb >= 16 and 
            file_size_gb < available_memory_gb / 4
        )
        
    def _apply_system_adjustments(self, settings, video_info):
        """Apply system-specific adjustments to settings"""
        available_memory_gb = self.system_capabilities['available_memory_gb']
        cpu_cores = self.system_capabilities['cpu_cores']
        
        # Memory-constrained systems
        if available_memory_gb < 8:
            settings['buffer_settings']['frame_buffer_size'] = min(
                settings['buffer_settings']['frame_buffer_size'], 5
            )
            settings['buffer_settings']['audio_buffer_duration'] = 3.0
            settings['optimizations_applied'].append('low_memory_mode')
            
        # CPU-constrained systems
        if cpu_cores < 4:
            settings['processing_settings']['preset'] = 'ultrafast'
            settings['processing_settings']['parallel_batch'] = False
            settings['optimizations_applied'].append('low_cpu_mode')
            
        # High-end systems
        if available_memory_gb >= 32 and cpu_cores >= 8:
            if settings['category'] in ['4K', '8K', 'ULTRA']:
                settings['buffer_settings']['frame_buffer_size'] *= 2
                settings['processing_settings']['parallel_batch'] = True
                settings['optimizations_applied'].append('high_end_optimization')
                
        return settings
        
    def _get_default_settings(self):
        """Get default settings when video analysis fails"""
        return self._get_standard_settings('HD', {
            'width': 1280, 'height': 720, 'duration': 0, 
            'bitrate': 0, 'file_size': 0
        })
        
    def get_hardware_acceleration_settings(self, category):
        """Get hardware acceleration settings optimized for resolution category"""
        base_settings = {
            'SD': {'preset': 'fast', 'crf': 23, 'bitrate': '2M'},
            'HD': {'preset': 'fast', 'crf': 23, 'bitrate': '5M'},
            'FHD': {'preset': 'fast', 'crf': 23, 'bitrate': '8M'},
            '4K': {'preset': 'medium', 'crf': 20, 'bitrate': '25M'},
            '8K': {'preset': 'slow', 'crf': 18, 'bitrate': '50M'},
            'ULTRA': {'preset': 'veryslow', 'crf': 16, 'bitrate': '100M'}
        }
        
        return base_settings.get(category, base_settings['HD'])
        
    def apply_optimizations_to_thread(self, thread_instance, settings):
        """Apply optimizations to processing threads"""
        if hasattr(thread_instance, 'set_optimization_settings'):
            thread_instance.set_optimization_settings(settings)
            
        # Apply buffer settings
        if hasattr(thread_instance, 'frame_buffer'):
            thread_instance.frame_buffer.max_size = settings['buffer_settings']['frame_buffer_size']
            
        # Apply preview settings
        if hasattr(thread_instance, 'set_preview_target'):
            thread_instance.set_preview_target(settings['preview_settings']['target_width'])
            
        
    def get_memory_usage_estimate(self, video_info, settings):
        """Estimate memory usage for the given video and settings"""
        if not video_info:
            return {'estimated_mb': 500, 'warning': None}
            
        width = video_info['width']
        height = video_info['height']
        frame_buffer_size = settings['buffer_settings']['frame_buffer_size']
        
        # Calculate estimates
        frame_size_mb = (width * height * 3) / (1024**2)  # RGB frame
        buffer_memory_mb = frame_size_mb * frame_buffer_size
        processing_memory_mb = frame_size_mb * 2  # Working memory
        total_estimated_mb = buffer_memory_mb + processing_memory_mb + 200  # Base overhead
        
        available_mb = self.system_capabilities['available_memory_gb'] * 1024
        usage_percentage = (total_estimated_mb / available_mb) * 100
        
        warning = None
        if usage_percentage > 80:
            warning = f"High memory usage expected ({usage_percentage:.1f}% of available)"
        elif usage_percentage > 60:
            warning = f"Moderate memory usage expected ({usage_percentage:.1f}% of available)"
            
        return {
            'estimated_mb': int(total_estimated_mb),
            'frame_size_mb': frame_size_mb,
            'buffer_memory_mb': buffer_memory_mb,
            'usage_percentage': usage_percentage,
            'warning': warning
        }
        
    def print_optimization_summary(self, video_path, settings):
        """Print a summary of applied optimizations"""
        video_info = self.get_video_resolution(video_path)
        memory_info = self.get_memory_usage_estimate(video_info, settings)
        
        
        if memory_info['warning']:
            pass
            


class ResolutionAwareProcessingMixin:
    """Mixin class to add resolution-aware processing to existing threads"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resolution_optimizer = ResolutionOptimizer()
        self.optimization_settings = None
        
    def set_optimization_settings(self, settings):
        """Set optimization settings for this thread"""
        self.optimization_settings = settings
        
        # Apply settings to thread behavior
        if hasattr(self, 'frame_buffer') and 'buffer_settings' in settings:
            self.frame_buffer.max_size = settings['buffer_settings']['frame_buffer_size']
            
        
    def get_optimized_ffmpeg_params(self, video_codec):
        """Get FFmpeg parameters optimized for the current resolution"""
        if not self.optimization_settings:
            return []
            
        category = self.optimization_settings['category']
        processing_settings = self.optimization_settings['processing_settings']
        
        params = ["-pix_fmt", "yuv420p"]
        
        if video_codec == 'h264_nvenc':
            params.extend([
                "-preset", processing_settings.get('preset', 'fast'),
                "-rc", "vbr",
                "-cq", str(processing_settings.get('crf_quality', 23)),
                "-b:v", processing_settings.get('bitrate_target', '5M'),
                "-maxrate", processing_settings.get('bitrate_target', '5M').replace('M', '0M'),
                "-bufsize", processing_settings.get('bitrate_target', '5M').replace('M', '0M')
            ])
            
            # 4K/8K specific optimizations
            if category in ['4K', '8K', 'ULTRA']:
                params.extend([
                    "-spatial_aq", "1",
                    "-temporal_aq", "1",
                    "-rc-lookahead", "32"
                ])
                
        elif video_codec == 'h264_qsv':
            params.extend([
                "-preset", processing_settings.get('preset', 'fast'),
                "-global_quality", str(processing_settings.get('crf_quality', 23)),
                "-look_ahead", "1"
            ])
            
        elif video_codec == 'h264_amf':
            params.extend([
                "-quality", "speed" if category in ['4K', '8K'] else "balanced",
                "-rc", "vbr_peak",
                "-qp_i", str(max(16, processing_settings.get('crf_quality', 23) - 2)),
                "-qp_p", str(processing_settings.get('crf_quality', 23)),
                "-qp_b", str(processing_settings.get('crf_quality', 23) + 2)
            ])
            
        else:  # libx264
            params.extend([
                "-preset", processing_settings.get('preset', 'fast'),
                "-crf", str(processing_settings.get('crf_quality', 23))
            ])
            
            # High resolution optimizations
            if category in ['4K', '8K', 'ULTRA']:
                params.extend([
                    "-tune", "film",
                    "-x264-params", "aq-mode=3:aq-strength=0.8"
                ])
                
        return params
        
    def should_use_streaming_mode(self):
        """Determine if streaming mode should be used"""
        if not self.optimization_settings:
            return False
            
        return self.optimization_settings['processing_settings'].get('streaming_mode', False)
        
    def get_chunk_size(self):
        """Get optimal chunk size for processing"""
        if not self.optimization_settings:
            return 30  # Default
            
        return self.optimization_settings['detection_settings'].get('chunk_size_seconds', 30) 