"""
Features package for Silence Cutter
Contains additional functionality that extends the core application.
"""

from .manual_cutting import ManualCuttingManager, ManualCuttingIntegration

try:
    from .batch_processing import BatchProcessingManager, BatchProcessingDialog, BatchProcessingIntegration
    BATCH_PROCESSING_AVAILABLE = True
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration', 'BatchProcessingManager', 'BatchProcessingDialog', 'BatchProcessingIntegration']
except ImportError:
    BATCH_PROCESSING_AVAILABLE = False
    __all__ = ['ManualCuttingManager', 'ManualCuttingIntegration'] 