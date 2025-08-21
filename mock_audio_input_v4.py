# mock_audio_input_v5.py

import shutil
import time
from PySide6.QtCore import QThread, Signal

class MockAudioRecorder(QThread):
    """
    A mock recorder that simulates audio recording by copying a pre-existing file.
    It inherits from QThread to seamlessly replace RecordingWorker.
    """
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, mock_file_path: str, output_path: str):
        """
        Initializes the mock recorder.

        Args:
            mock_file_path: The path to the audio file to be used as a mock.
            output_path: The destination path where the mock file will be copied.
        """
        super().__init__()
        if not mock_file_path:
            raise ValueError("A mock file path must be provided.")
        self.mock_file_path = mock_file_path
        self.output_path = output_path
        self.is_running = False

    def run(self):
        """
        Starts the mock recording process.
        It simulates a short delay, then copies the file.
        """
        self.is_running = True
        try:
            # Simulate a short recording time
            time.sleep(2)
            
            # Copy the selected mock file to the target output path
            shutil.copy(self.mock_file_path, self.output_path)
            
            # Emit the finished signal with the path of the "new" file
            if self.is_running:
                self.finished.emit(self.output_path)

        except FileNotFoundError:
            self.error.emit(f"Mock file not found: {self.mock_file_path}")
        except Exception as e:
            self.error.emit(f"Failed to copy mock file: {str(e)}")

    def stop(self):
        """Stops the mock process."""
        self.is_running = False