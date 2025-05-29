"""
Features package for Silence Cutter
Contains additional functionality that extends the core application.
"""

from .manual_cutting import ManualCuttingManager, ManualCuttingIntegration

try:
    from .batch_processing import BatchProcessingManager, BatchProcessingDialog, BatchProcessingIntegration
    BATCH_PROCESSING_AVAILABLE = True
except ImportError:
    BATCH_PROCESSING_AVAILABLE = False

try:
    from .speech_recognition import SpeechRecognitionManager, integrate_speech_recognition
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

if BATCH_PROCESSING_AVAILABLE and SPEECH_RECOGNITION_AVAILABLE:
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration', 'BatchProcessingManager', 
               'BatchProcessingDialog', 'BatchProcessingIntegration', 'SpeechRecognitionManager', 
               'integrate_speech_recognition']
elif BATCH_PROCESSING_AVAILABLE:
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration', 'BatchProcessingManager', 
               'BatchProcessingDialog', 'BatchProcessingIntegration']
elif SPEECH_RECOGNITION_AVAILABLE:
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration', 'SpeechRecognitionManager', 
               'integrate_speech_recognition']
else:
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration']