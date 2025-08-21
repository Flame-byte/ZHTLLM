from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, QInputDialog,QWidget,
    QFormLayout, QDialogButtonBox, QFileDialog, QListWidget, QListWidgetItem, QGroupBox, QMessageBox, QSplitter, QTextBrowser, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QTextCursor, QMovie
import os
import json
import shutil
from datetime import datetime
import pyaudio
import wave
import subprocess
import sys

# 导入语言模块
from language import lang

# --- Recording Worker ---
class RecordingWorker(QThread):
    """Worker thread for recording audio to prevent freezing the GUI."""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, output_path):
        super().__init__()
        self.output_path = output_path
        self.is_recording = False
        self.p = None
        self.stream = None

    def run(self):
        self.is_recording = True
        frames = []
        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt16,
                                     channels=1,
                                     rate=44100,
                                     input=True,
                                     frames_per_buffer=1024)
            while self.is_recording:
                data = self.stream.read(1024)
                frames.append(data)
            
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

            wf = wave.open(self.output_path, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(frames))
            wf.close()
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_recording = False

class MeetingModeDialog(QDialog):
    """Dialog for the new Meeting Mode functionality."""
    def __init__(self, parent=None, project_name=None, history_root=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle(lang.get('meeting_mode_title'))
        self.setMinimumSize(700, 500)

        self.project_name = project_name
        self.history_root = history_root
        self.settings = settings
        self.speaker_name = None
        self.speaker_file = None
        self.recording_worker = None
        self.auto_build_timer = QTimer(self)
        self.log_manager = parent.log_manager if hasattr(parent, 'log_manager') else LogManager()


        # --- Layouts ---
        layout = QVBoxLayout(self)
        main_splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # --- Left Panel: Speaker and Recording ---
        speaker_group = QGroupBox(lang.get('character_registration'))
        speaker_layout = QFormLayout(speaker_group)
        
        self.speaker_name_input = QLineEdit()
        self.add_speaker_file_btn = QPushButton(lang.get('add_speaker_sample_btn'))
        self.speaker_file_label = QLabel(lang.get('no_file_selected'))
        
        speaker_layout.addRow(lang.get('speaker_name_label'), self.speaker_name_input)
        speaker_layout.addRow(self.add_speaker_file_btn, self.speaker_file_label)
        
        recording_group = QGroupBox(lang.get('recording_status_label'))
        recording_layout = QVBoxLayout(recording_group)
        
        self.recording_icon_label = QLabel()
        self.recording_icon_label.setAlignment(Qt.AlignCenter)
        self.static_icon = QMovie("picture/sound_input_static.jpg")
        self.animated_icon = QMovie("picture/sound_input.gif")
        self.recording_icon_label.setMovie(self.static_icon)
        self.static_icon.start()

        self.recording_status_label = QLabel(lang.get('not_recording'))
        self.recording_status_label.setAlignment(Qt.AlignCenter)

        self.start_record_btn = QPushButton(lang.get('start_recording_button'))
        self.stop_record_btn = QPushButton(lang.get('stop_recording_button'))
        self.stop_record_btn.setEnabled(False)

        recording_layout.addWidget(self.recording_icon_label)
        recording_layout.addWidget(self.recording_status_label)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_record_btn)
        btn_layout.addWidget(self.stop_record_btn)
        recording_layout.addLayout(btn_layout)

        left_layout.addWidget(speaker_group)
        left_layout.addWidget(recording_group)
        left_layout.addStretch()

        # --- Right Panel: Auto Build ---
        build_group = QGroupBox(lang.get('build_configuration'))
        build_layout = QFormLayout(build_group)
        
        self.build_interval_input = QSpinBox()
        self.build_interval_input.setRange(1, 1440) # 1 min to 24 hours
        self.build_interval_input.setValue(10)
        
        self.start_build_btn = QPushButton(lang.get('start_auto_build_button'))
        self.stop_build_btn = QPushButton(lang.get('stop_auto_build_button'))
        self.stop_build_btn.setEnabled(False)
        
        build_layout.addRow(lang.get('build_interval_label'), self.build_interval_input)
        build_btn_layout = QHBoxLayout()
        build_btn_layout.addWidget(self.start_build_btn)
        build_btn_layout.addWidget(self.stop_build_btn)
        build_layout.addRow(build_btn_layout)

        self.log_output = QTextBrowser()
        self.log_output.setReadOnly(True)

        right_layout.addWidget(build_group)
        right_layout.addWidget(self.log_output)

        # --- Splitter and Main Layout ---
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([300, 400])
        
        self.close_btn = QPushButton(lang.get('close'))
        layout.addWidget(main_splitter)
        layout.addWidget(self.close_btn, alignment=Qt.AlignRight)

        # --- Connections ---
        self.add_speaker_file_btn.clicked.connect(self.select_speaker_file)
        self.start_record_btn.clicked.connect(self.start_recording)
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.start_build_btn.clicked.connect(self.start_auto_build)
        self.stop_build_btn.clicked.connect(self.stop_auto_build)
        self.auto_build_timer.timeout.connect(self.run_periodic_build)
        self.close_btn.clicked.connect(self.close)
        
    def select_speaker_file(self):
        """Opens a file dialog to select the speaker's sample audio file."""
        file, _ = QFileDialog.getOpenFileName(self, lang.get('select_speaker_sample_title').format(self.speaker_name_input.text()), "", "Audio files (*.wav *.mp3)")
        if file:
            self.speaker_file = file
            self.speaker_file_label.setText(os.path.basename(file))
            self.log_message(f"Speaker file selected: {self.speaker_file}")

    def start_recording(self):
        self.speaker_name = self.speaker_name_input.text().strip()
        if not self.speaker_name or not self.speaker_file:
            QMessageBox.warning(self, lang.get('input_error'), lang.get('speaker_and_file_required'))
            return
            
        project_path = os.path.join(self.history_root, self.project_name)
        meeting_data_path = os.path.join(project_path, 'meeting_data')
        os.makedirs(meeting_data_path, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(meeting_data_path, f"rec_{self.speaker_name}_{timestamp}.wav")
        
        self.recording_worker = RecordingWorker(output_filename)
        self.recording_worker.finished.connect(self.on_recording_finished)
        self.recording_worker.error.connect(self.on_recording_error)
        
        self.recording_worker.start()

        self.recording_icon_label.setMovie(self.animated_icon)
        self.animated_icon.start()
        self.recording_status_label.setText(lang.get('recording_in_progress'))
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.log_message(f"Recording started for speaker {self.speaker_name}...")

    def stop_recording(self):
        if self.recording_worker:
            self.recording_worker.stop()
            self.recording_icon_label.setMovie(self.static_icon)
            self.static_icon.start()
            self.recording_status_label.setText(lang.get('not_recording'))
            self.start_record_btn.setEnabled(True)
            self.stop_record_btn.setEnabled(False)
    
    def on_recording_finished(self, output_path):
        self.log_message(lang.get('recording_saved_to').format(output_path))
        self.recording_worker = None

    def on_recording_error(self, error_message):
        QMessageBox.critical(self, lang.get('error'), error_message)
        self.log_message(f"Recording error: {error_message}", 'error')
        self.stop_recording()

    def start_auto_build(self):
        interval_minutes = self.build_interval_input.value()
        if interval_minutes <= 0:
            QMessageBox.warning(self, lang.get('input_error'), lang.get('invalid_build_interval'))
            return
            
        interval_ms = interval_minutes * 60 * 1000
        self.auto_build_timer.start(interval_ms)

        self.start_build_btn.setEnabled(False)
        self.stop_build_btn.setEnabled(True)
        self.build_interval_input.setEnabled(False)
        self.log_message(lang.get('auto_build_started').format(self.project_name, interval_minutes))
        self.log_manager.log(lang.get('auto_build_started').format(self.project_name, interval_minutes))


    def stop_auto_build(self):
        self.auto_build_timer.stop()
        self.start_build_btn.setEnabled(True)
        self.stop_build_btn.setEnabled(False)
        self.build_interval_input.setEnabled(True)
        self.log_message(lang.get('auto_build_stopped').format(self.project_name))
        self.log_manager.log(lang.get('auto_build_stopped').format(self.project_name))


    def run_periodic_build(self):
        """Runs the build process in a new terminal."""
        self.log_message(f"Triggering auto-build for project '{self.project_name}'...")
        
        # Prepare arguments for run_build
        # Note: We need a way to get the latest files from meeting_data
        project_path = os.path.join(self.history_root, self.project_name)
        meeting_data_path = os.path.join(project_path, 'meeting_data')
        
        # This assumes run_build can handle a directory of audio files.
        # This part may need adjustment based on `run_build`'s actual signature.
        build_args = {
            **self.settings,
            "name": self.project_name,
            "dialogue": meeting_data_path, # Assuming run_build can take a directory
            "speakers": {self.speaker_name: self.speaker_file} if self.speaker_name and self.speaker_file else None,
        }

        # Create a command to run a script that calls run_build
        # This avoids complex argument passing on the command line
        cmd = [
            sys.executable,  # Path to the current python interpreter
            "-c",
            f"from graphrag_online.ZHTLLM_reasoning import run_build; run_build(**{json.dumps(build_args)})"
        ]

        try:
            # Use Popen to run in a new process without blocking
            # On Windows, use CREATE_NEW_CONSOLE to open a new terminal window
            creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            subprocess.Popen(cmd, creationflags=creation_flags)
            self.log_message("Build process started in a new terminal.")
        except Exception as e:
            error_msg = f"Failed to start build process: {e}"
            self.log_message(error_msg, 'error')
            QMessageBox.critical(self, lang.get('error'), error_msg)

    def log_message(self, message, level='info'):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = 'green' if level == 'info' else 'red'
        self.log_output.append(f'<font color="{color}">[{timestamp}] {message}</font>')
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def closeEvent(self, event):
        """Ensure background tasks are stopped when the dialog is closed."""
        self.stop_recording()
        self.stop_auto_build()
        super().closeEvent(event)

# Keep the original dialogs untouched
class LogManager:
    """日志管理器，处理应用程序日志"""
    def __init__(self):
        self.logs = []
        self.max_logs = 1000
        
    def log(self, message):
        """添加日志条目"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        
        # 限制日志数量
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
            
    def get_logs(self):
        """获取所有日志条目"""
        return self.logs
    
    def clear_logs(self):
        """清除所有日志条目"""
        self.logs = []


class ProjectManagerDialog(QDialog):
    """对话框用于创建或删除项目"""
    def __init__(self, parent=None, history_root=None, title=None, prompt=None):
        super().__init__(parent)
        self.setWindowTitle(title or lang.get('project_manager_title'))
        self.setMinimumWidth(600)
        self.history_root = history_root or os.path.join(os.path.dirname(__file__), 'graphrag_online', 'history')
        
        self.log_manager = LogManager()

        # 确保历史目录存在
        if not os.path.exists(self.history_root):
            os.makedirs(self.history_root)
        
        layout = QVBoxLayout(self)
        
        # 项目列表
        self.project_list = QListWidget()
        self.refresh_project_list()
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.create_btn = QPushButton(lang.get('create_project'))
        self.delete_btn = QPushButton(lang.get('delete_project'))
        # 修改关闭按钮
        self.close_btn = QPushButton(lang.get('close'))  # 原为 "关闭"
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.close_btn)
        
        layout.addWidget(QLabel(lang.get('history_list')))
        layout.addWidget(self.project_list)
        layout.addLayout(button_layout)
        
        # 连接信号
        self.create_btn.clicked.connect(self.create_project)
        self.delete_btn.clicked.connect(self.delete_project)
        self.close_btn.clicked.connect(self.accept)
        self.project_list.itemClicked.connect(self.on_project_selected)
        
        # 默认禁用删除按钮
        self.delete_btn.setEnabled(False)
    
    def delete_project(self):
        if not hasattr(self, 'selected_project') or not self.selected_project:
            QMessageBox.warning(self, lang.get('warning'), lang.get('select_project_first'))
            return
            
        reply = QMessageBox.question(
            self, 
            lang.get('confirm_delete'), 
            lang.get('delete_project_confirm').format(self.selected_project), 
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            project_path = os.path.join(self.history_root, self.selected_project)
            try:
                # 使用 shutil.rmtree 安全删除目录
                import shutil
                shutil.rmtree(project_path)
                self.refresh_project_list()
                self.delete_btn.setEnabled(False)
                QMessageBox.information(self, lang.get('success'), lang.get('delete_project_success'))
                self.log_manager.log(f"项目 '{self.selected_project}' 已删除")  # 记录日志
            except Exception as e:
                QMessageBox.critical(self, lang.get('error'), lang.get('delete_project_failure') + f": {str(e)}")
                self.log_manager.log(f"错误: 删除项目失败 - {str(e)}")

    def refresh_project_list(self):
        """刷新项目列表"""
        self.project_list.clear()
        projects = [d for d in os.listdir(self.history_root) if os.path.isdir(os.path.join(self.history_root, d))]
        self.project_list.addItems(projects)
    
    def on_project_selected(self, item):
        """项目被选中时的处理"""
        self.selected_project = item.text()
        self.delete_btn.setEnabled(True)
    
    def create_project(self):
        """创建新项目"""
        project_name, ok = QInputDialog.getText(
            self, 
            lang.get('project_manager_title'), 
            lang.get('enter_project_name')
        )
        
        if ok and project_name:
            try:
                # 直接调用初始化函数，让它处理目录创建
                from graphrag_online.ZHTLLM_reasoning import run_init
                run_init(project_name)
                
                # 刷新项目列表
                self.refresh_project_list()
                QMessageBox.information(self, lang.get('success'), lang.get('create_project_success').format(project_name))
            except ValueError as e:
                QMessageBox.warning(self, lang.get('warning'), str(e))
            except Exception as e:
                QMessageBox.critical(self, lang.get('error'), lang.get('create_project_failure') + f": {str(e)}")
    
    def delete_project(self):
        """删除选中的项目"""
        if not hasattr(self, 'selected_project'):
            QMessageBox.warning(self, lang.get('warning'), lang.get('select_project_first'))
            return
        
        reply = QMessageBox.question(
            self, 
            lang.get('confirm_delete'), 
            lang.get('delete_project_confirm').format(self.selected_project), 
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            project_path = os.path.join(self.history_root, self.selected_project)
            try:
                shutil.rmtree(project_path)
                self.refresh_project_list()
                self.delete_btn.setEnabled(False)
                QMessageBox.information(self, lang.get('success'), lang.get('delete_project_success'))
            except Exception as e:
                QMessageBox.critical(self, lang.get('error'), lang.get('delete_project_failure') + f": {str(e)}")


class LogManager:
    """日志管理类，处理日志记录和查看"""
    def __init__(self, log_dir=None):
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), 'log')
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 日志文件按日期命名
        self.current_log_file = os.path.join(self.log_dir, f"{datetime.now().strftime('%Y%m%d')}.log")
    
    def log(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error writing to log file: {e}")
    
    def get_log_files(self):
        """获取所有日志文件"""
        if not os.path.exists(self.log_dir):
            return []
        
        return sorted(
            [f for f in os.listdir(self.log_dir) if os.path.isfile(os.path.join(self.log_dir, f))],
            reverse=True
        )
    
    def read_log(self, log_file):
        """读取指定日志文件内容"""
        log_path = os.path.join(self.log_dir, log_file)
        if not os.path.exists(log_path):
            return lang.get('log_file_not_found')
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return lang.get('error_reading_log').format(e)


class LogViewDialog(QDialog):
    """日志查看对话框"""
    
    def __init__(self, parent=None, log_manager=None):
        super().__init__(parent)
        self.setWindowTitle(lang.get('log_view_title'))
        self.setMinimumSize(800, 600)
        self.log_manager = log_manager or LogManager()
        
        layout = QVBoxLayout(self)
        
        # 日志文件列表
        self.log_files_list = QListWidget()
        self.refresh_log_files()
        
        # 日志内容显示
        self.log_content = QTextBrowser()
        self.log_content.setReadOnly(True)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.log_files_list)
        splitter.addWidget(self.log_content)
        splitter.setSizes([200, 600])
        
        # 关闭按钮
        close_btn = QPushButton(lang.get('close'))
        close_btn.clicked.connect(self.close)
        
        layout.addWidget(splitter)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        
        # 连接信号
        self.log_files_list.itemClicked.connect(self.on_log_file_selected)
    
    def refresh_log_files(self):
        self.log_files_list.clear()
        log_files = self.log_manager.get_log_files()
        for file in log_files:
            item = QListWidgetItem(file)
            # 显示友好的日期
            try:
                date_str = file.split('.')[0]
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                item.setToolTip(formatted_date)
            except:
                pass
            self.log_files_list.addItem(item)
    
    def on_log_file_selected(self, item):
        log_file = item.text()
        content = self.log_manager.read_log(log_file)
        self.log_content.setPlainText(content)
        # 滚动到底部
        cursor = self.log_content.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_content.setTextCursor(cursor)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(lang.get('settings'))
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Inference Mode
        self.inference_mode = QComboBox()
        self.inference_mode.addItems(["local", "cloud"])
        self.form_layout.addRow(QLabel(lang.get('inference_mode_label')), self.inference_mode)

        # Cloud Settings
        self.cloud_api_base = QLineEdit("https://api.agicto.cn/v1")
        self.cloud_api_key = QLineEdit("sk-updTLk3DtUk5N2UrIIzD6yGgnE1WzmtXDlJGeTpaq6lucrSo")
        self.cloud_api_key.setEchoMode(QLineEdit.Password)
        self.cloud_model = QLineEdit("deepseek-chat")
        
        # Local Settings
        self.local_api_base = QLineEdit("http://localhost:11434/v1/")
        self.local_model = QLineEdit("qwen3:4b")

        # Use tuples to group widgets with their labels for easy toggling
        self.cloud_widgets = [
            (QLabel(lang.get('cloud_api_base_label')), self.cloud_api_base),
            (QLabel(lang.get('cloud_api_key_label')), self.cloud_api_key),
            (QLabel(lang.get('cloud_model_label')), self.cloud_model)
        ]
        self.local_widgets = [
            (QLabel(lang.get('local_api_base_label')), self.local_api_base),
            (QLabel(lang.get('local_model_label')), self.local_model)
        ]

        for label, widget in self.cloud_widgets: self.form_layout.addRow(label, widget)
        for label, widget in self.local_widgets: self.form_layout.addRow(label, widget)

        # Embedding Settings
        self.embedding_model = QLineEdit("nomic-embed-text")
        self.embedding_api_base = QLineEdit("http://localhost:11500/api")
        self.form_layout.addRow(QLabel(lang.get('embedding_model_label')), self.embedding_model)
        self.form_layout.addRow(QLabel(lang.get('embedding_api_base_label')), self.embedding_api_base)

        layout.addLayout(self.form_layout)

        # Dialog Buttons
        # 修改按钮文本
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText(lang.get('ok'))  # 如果没有 'ok' 键，需要添加
        button_box.button(QDialogButtonBox.Cancel).setText(lang.get('cancel'))  # 如果没有 'cancel' 键，需要添加
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.inference_mode.currentTextChanged.connect(self.toggle_fields)
        self.toggle_fields(self.inference_mode.currentText())

    def toggle_fields(self, mode):
        is_cloud = mode == "cloud"
        for label, widget in self.cloud_widgets:
            label.setVisible(is_cloud)
            widget.setVisible(is_cloud)
        
        is_local = mode == "local"
        for label, widget in self.local_widgets:
            label.setVisible(is_local)
            widget.setVisible(is_local)

    def get_settings(self):
        return {
            "inference_mode": self.inference_mode.currentText(),
            "cloud_api_base": self.cloud_api_base.text(),
            "cloud_api_key": self.cloud_api_key.text(),
            "cloud_model": self.cloud_model.text(),
            "local_api_base": self.local_api_base.text(),
            "local_model": self.local_model.text(),
            "embedding_model": self.embedding_model.text(),
            "embedding_api_base": self.embedding_api_base.text(),
        }

class AddFilesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(lang.get('add_files_to_project'))
        self.setMinimumWidth(600)

        self.text_files = []
        self.dialogue_file = None
        self.speaker_files = {} # name -> path

        layout = QVBoxLayout(self)

        icon_path = "picture/"
        self.icons = {
            "text": QIcon(f"{icon_path}add-file.png"),
            "audio": QIcon(f"{icon_path}add-file.png"),
            "speaker": QIcon(f"{icon_path}add-file.png")
        }

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        add_text_btn = QPushButton(lang.get('add_text_files_btn'))
        add_text_btn.setIcon(self.icons["text"])
        add_text_btn.clicked.connect(self.add_text_files)
        
        add_dialogue_btn = QPushButton(lang.get('add_dialogue_audio_btn'))
        add_dialogue_btn.setIcon(self.icons["audio"])
        add_dialogue_btn.clicked.connect(self.add_dialogue_audio)

        left_layout.addWidget(add_text_btn)
        left_layout.addWidget(add_dialogue_btn)
        left_layout.addSpacing(20)

        char_reg_group = QGroupBox(lang.get('character_registration'))
        char_reg_layout = QFormLayout(char_reg_group)
        
        self.speaker_name_input = QLineEdit()
        char_reg_layout.addRow(QLabel(lang.get('speaker_name_label')), self.speaker_name_input)
        
        add_speaker_audio_btn = QPushButton(lang.get('add_speaker_sample_btn'))
        add_speaker_audio_btn.setIcon(self.icons["speaker"])
        add_speaker_audio_btn.clicked.connect(self.add_speaker_sample)
        char_reg_layout.addRow(add_speaker_audio_btn)
        
        left_layout.addWidget(char_reg_group)
        left_layout.addStretch()

        self.file_list_widget = QListWidget()
        right_layout.addWidget(QLabel(lang.get('files_included_in_build')))
        right_layout.addWidget(self.file_list_widget)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)
        layout.addLayout(main_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def add_text_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 
                                               lang.get('select_text_files_title'), 
                                               "", 
                                               lang.get('text_files_filter'))
        if files:
            self.text_files.extend(files)
            self.update_file_list()

    def add_dialogue_audio(self):
        file, _ = QFileDialog.getOpenFileName(self, 
                                             lang.get('select_dialogue_audio_title'), 
                                             "", 
                                             "音频文件 (*.wav *.mp3)" if lang.current_language == '中文' else "Audio files (*.wav *.mp3)")
        if file:
            self.dialogue_file = file
            self.update_file_list()

    def add_speaker_sample(self):
        name = self.speaker_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 
                              lang.get('input_error'), 
                              lang.get('enter_speaker_name'))
            return
            
        file, _ = QFileDialog.getOpenFileName(self, 
                                             lang.get('select_speaker_sample_title').format(name), 
                                             "", 
                                             "音频文件 (*.wav *.mp3)" if lang.current_language == '中文' else "Audio files (*.wav *.mp3)")
        if file:
            self.speaker_files[name] = file
            self.speaker_name_input.clear()
            self.update_file_list()

    def update_file_list(self):
        self.file_list_widget.clear()
        if self.dialogue_file:
            self.file_list_widget.addItem(f"对话: {self.dialogue_file}")
        
        if self.speaker_files:
            self.file_list_widget.addItem("\n--- 说话者样本 ---" if lang.current_language == '中文' else "\n--- Speaker Samples ---")
            for name, path in self.speaker_files.items():
                self.file_list_widget.addItem(f"{name}: {path}")

        if self.text_files:
            self.file_list_widget.addItem("\n--- 文本文件 ---" if lang.current_language == '中文' else "\n--- Text Files ---")
            for file in self.text_files:
                self.file_list_widget.addItem(file)

    def get_build_params(self):
        return {
            "dialogue": self.dialogue_file,
            "speakers": self.speaker_files or None,
            "text_files": self.text_files or None
        }

CONFIG_FILE = "custom_models.json"

class BuildSettingsDialog(QDialog):
    """A dialog for configuring build-specific model settings."""
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle(lang.get('build_configuration'))

        self.current_settings = current_settings if current_settings else {}
        self.custom_models = self._load_custom_models()

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.reasoning_mode = QComboBox()
        self.reasoning_mode.addItems(["local", "cloud"])
        if "inference_mode" in self.current_settings:
            self.reasoning_mode.setCurrentText(self.current_settings["inference_mode"])
        form_layout.addRow(QLabel(lang.get('reasoning_label')), self.reasoning_mode)

        self.model_selection = QComboBox()
        form_layout.addRow(QLabel(lang.get('model_label')), self.model_selection)
        
        self.custom_group = QGroupBox(lang.get('custom_model_details'))
        self.custom_group.setVisible(False)
        custom_layout = QFormLayout(self.custom_group)
        
        self.custom_model_name = QLineEdit()
        custom_layout.addRow(QLabel(lang.get('model_name_label')), self.custom_model_name)
        
        self.custom_api_base_label = QLabel(lang.get('api_base_label'))
        self.custom_api_base = QLineEdit()
        custom_layout.addRow(self.custom_api_base_label, self.custom_api_base)
        
        self.custom_api_key_label = QLabel(lang.get('api_key_label'))
        self.custom_api_key = QLineEdit()
        self.custom_api_key.setEchoMode(QLineEdit.Password)
        custom_layout.addRow(self.custom_api_key_label, self.custom_api_key)

        form_layout.addWidget(self.custom_group)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.reasoning_mode.currentTextChanged.connect(self._update_model_options)
        self.model_selection.currentTextChanged.connect(self._toggle_custom_fields)

        self._update_model_options(self.reasoning_mode.currentText())

    def _load_custom_models(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError): pass
        return {"local": [], "cloud": []}

    def _save_custom_models(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.custom_models, f, indent=4)

    def _update_model_options(self, mode):
        self.model_selection.clear()
        
        if mode == "local":
            predefined = ["qwen3:0.6b", "qwen3:1.7b", "qwen3:4b", "qwen3:8b", "llama3.2", "llama3.2:1b", "llama3.2:3b", "llama3.1:8b"]
            self.model_selection.addItems(predefined)
            self.model_selection.addItems(self.custom_models.get("local", []))
        
        elif mode == "cloud":
            for model_data in self.custom_models.get("cloud", []):
                self.model_selection.addItem(model_data["name"], userData=model_data)

        self.model_selection.addItem(lang.get('custom'))
        self._toggle_custom_fields(self.model_selection.currentText())

    def _toggle_custom_fields(self, model_text):
        is_custom = model_text == lang.get('custom')
        self.custom_group.setVisible(is_custom)

        if is_custom:
            is_cloud = self.reasoning_mode.currentText() == "cloud"
            self.custom_api_base.setVisible(is_cloud)
            self.custom_api_base_label.setVisible(is_cloud)
            self.custom_api_key.setVisible(is_cloud)
            self.custom_api_key_label.setVisible(is_cloud)

    def accept(self):
        if self.model_selection.currentText() == lang.get('custom'):
            mode = self.reasoning_mode.currentText()
            name = self.custom_model_name.text().strip()
            if not name:
                QMessageBox.warning(self, 
                                  lang.get('input_error'), 
                                  lang.get('custom_model_name_empty'))
                return

            if mode == "local":
                local_models = self.custom_models.setdefault("local", [])
                if name not in local_models:
                    local_models.append(name)

            elif mode == "cloud":
                api_base = self.custom_api_base.text().strip()
                api_key = self.custom_api_key.text().strip()
                if not api_base or not api_key:
                    QMessageBox.warning(self, 
                                      lang.get('input_error'), 
                                      lang.get('custom_cloud_model_requirements'))
                    return
                
                cloud_models = self.custom_models.setdefault("cloud", [])
                if not any(m["name"] == name for m in cloud_models):
                    cloud_models.append({"name": name, "api_base": api_base, "api_key": api_key})
            
            self._save_custom_models()
        super().accept()

    def get_build_config(self):
        mode = self.reasoning_mode.currentText()
        config = {"inference_mode": mode}
        
        model_text = self.model_selection.currentText()
        if model_text == lang.get('custom'):
            config["model"] = self.custom_model_name.text().strip()
            if mode == "cloud":
                config["api_base"] = self.custom_api_base.text().strip()
                config["api_key"] = self.custom_api_key.text().strip()
        else:
            config["model"] = model_text
            if mode == "cloud":
                user_data = self.model_selection.currentData()
                if user_data:
                    config.update(user_data)
        return config

class QuerySettingsDialog(BuildSettingsDialog):
    """
    A dialog for configuring query-specific model settings.
    Inherits from BuildSettingsDialog to duplicate functionality.
    """
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent, current_settings)
        self.setWindowTitle(lang.get('query_configuration'))
    
    def get_query_config(self):
        # The parent method is named get_build_config, so we call that one.
        return super().get_build_config()