import sys
import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, 
    QFormLayout, QDialogButtonBox, QFileDialog, QListWidget, QListWidgetItem, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

class ProjectDialog(QDialog):
    def __init__(self, parent=None, title="Create Project", prompt="Project Name:"):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        form_layout.addRow(QLabel(prompt), self.name_input)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_name(self):
        return self.name_input.text().strip()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Inference Mode
        self.inference_mode = QComboBox()
        self.inference_mode.addItems(["local", "cloud"])
        form_layout.addRow(QLabel("Inference Mode:"), self.inference_mode)

        # Cloud Settings
        self.cloud_api_base = QLineEdit("https://api.agicto.cn/v1")
        self.cloud_api_key = QLineEdit("sk-updTLk3DtUk5N2UrIIzD6yGgnE1WzmtXDlJGeTpaq6lucrSo")
        self.cloud_api_key.setEchoMode(QLineEdit.Password)
        self.cloud_model = QLineEdit("deepseek-chat")
        form_layout.addRow(QLabel("Cloud API Base:"), self.cloud_api_base)
        form_layout.addRow(QLabel("Cloud API Key:"), self.cloud_api_key)
        form_layout.addRow(QLabel("Cloud Model:"), self.cloud_model)

        # Local Settings
        self.local_api_base = QLineEdit("http://localhost:11434/v1/")
        self.local_model = QLineEdit("qwen3:4b")
        form_layout.addRow(QLabel("Local API Base:"), self.local_api_base)
        form_layout.addRow(QLabel("Local Model:"), self.local_model)

        # Embedding Settings
        self.embedding_model = QLineEdit("nomic-embed-text")
        self.embedding_api_base = QLineEdit("http://localhost:11500/api")
        form_layout.addRow(QLabel("Embedding Model:"), self.embedding_model)
        form_layout.addRow(QLabel("Embedding API Base:"), self.embedding_api_base)

        layout.addLayout(form_layout)

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.inference_mode.currentTextChanged.connect(self.toggle_fields)
        self.toggle_fields("local")

    def toggle_fields(self, mode):
        is_cloud = mode == "cloud"
        self.cloud_api_base.setEnabled(is_cloud)
        self.cloud_api_key.setEnabled(is_cloud)
        self.cloud_model.setEnabled(is_cloud)
        
        is_local = mode == "local"
        self.local_api_base.setEnabled(is_local)
        self.local_model.setEnabled(is_local)


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
        self.setWindowTitle("Add Files to Project")
        self.setMinimumWidth(600)

        self.text_files = []
        self.dialogue_file = None
        self.speaker_files = {} # name -> path

        layout = QVBoxLayout(self)

        # --- Icon Paths ---
        icon_path = "picture/"
        self.icons = {
            "text": QIcon(f"{icon_path}add-file.png"),
            "audio": QIcon(f"{icon_path}add-file.png"), # You might want a different icon
            "speaker": QIcon(f"{icon_path}add-file.png") # You might want a different icon
        }

        # Main sections
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # Left side: File selection
        add_text_btn = QPushButton(" Add Text Files")
        add_text_btn.setIcon(self.icons["text"])
        add_text_btn.clicked.connect(self.add_text_files)
        
        add_dialogue_btn = QPushButton(" Add Main Dialogue Audio")
        add_dialogue_btn.setIcon(self.icons["audio"])
        add_dialogue_btn.clicked.connect(self.add_dialogue_audio)

        left_layout.addWidget(add_text_btn)
        left_layout.addWidget(add_dialogue_btn)
        left_layout.addSpacing(20)

        # Character Registration
        char_reg_group = QGroupBox("Character Registration")
        char_reg_layout = QFormLayout(char_reg_group)
        
        self.speaker_name_input = QLineEdit()
        char_reg_layout.addRow(QLabel("Speaker Name:"), self.speaker_name_input)
        
        add_speaker_audio_btn = QPushButton(" Add Speaker Sample")
        add_speaker_audio_btn.setIcon(self.icons["speaker"])
        add_speaker_audio_btn.clicked.connect(self.add_speaker_sample)
        char_reg_layout.addRow(add_speaker_audio_btn)
        
        left_layout.addWidget(char_reg_group)
        left_layout.addStretch()

        # Right side: File lists
        self.file_list_widget = QListWidget()
        right_layout.addWidget(QLabel("Files to be included in build:"))
        right_layout.addWidget(self.file_list_widget)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)
        layout.addLayout(main_layout)

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def add_text_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Text Files", "", "Text files (*.txt)")
        if files:
            self.text_files.extend(files)
            self.update_file_list()

    def add_dialogue_audio(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Main Dialogue Audio", "", "Audio files (*.wav *.mp3)")
        if file:
            self.dialogue_file = file
            self.update_file_list()

    def add_speaker_sample(self):
        name = self.speaker_name_input.text()
        if not name.strip():
            # You might want to show a message box here
            print("Please enter a speaker name.")
            return
            
        file, _ = QFileDialog.getOpenFileName(self, f"Select Audio Sample for {name}", "", "Audio files (*.wav *.mp3)")
        if file:
            self.speaker_files[name] = file
            self.speaker_name_input.clear()
            self.update_file_list()

    def update_file_list(self):
        self.file_list_widget.clear()
        if self.dialogue_file:
            self.file_list_widget.addItem(f"Dialogue: {self.dialogue_file}")
        
        if self.speaker_files:
            self.file_list_widget.addItem("\n--- Speaker Samples ---")
            for name, path in self.speaker_files.items():
                self.file_list_widget.addItem(f"{name}: {path}")

        if self.text_files:
            self.file_list_widget.addItem("\n--- Text Files ---")
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
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Build Configuration")

        # Keep a reference to the main settings to pre-populate
        self.current_settings = current_settings if current_settings else {}
        self.custom_models = self._load_custom_models()

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Reasoning mode (local/cloud)
        self.reasoning_mode = QComboBox()
        self.reasoning_mode.addItems(["local", "cloud"])
        # Pre-select based on current settings if available
        if "inference_mode" in self.current_settings:
            self.reasoning_mode.setCurrentText(self.current_settings["inference_mode"])
        form_layout.addRow(QLabel("Reasoning:"), self.reasoning_mode)

        # Model selection
        self.model_selection = QComboBox()
        form_layout.addRow(QLabel("Model:"), self.model_selection)
        
        # --- Custom Group ---
        self.custom_group = QGroupBox("Custom Model Details")
        self.custom_group.setVisible(False)
        custom_layout = QFormLayout(self.custom_group)
        
        self.custom_model_name = QLineEdit()
        custom_layout.addRow(QLabel("Model Name:"), self.custom_model_name)
        
        self.custom_api_base_label = QLabel("API Base:")
        self.custom_api_base = QLineEdit()
        custom_layout.addRow(self.custom_api_base_label, self.custom_api_base)
        
        self.custom_api_key_label = QLabel("API Key:")
        self.custom_api_key = QLineEdit()
        self.custom_api_key.setEchoMode(QLineEdit.Password)
        custom_layout.addRow(self.custom_api_key_label, self.custom_api_key)

        form_layout.addWidget(self.custom_group)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # --- Connections ---
        self.reasoning_mode.currentTextChanged.connect(self._update_model_options)
        self.model_selection.currentTextChanged.connect(self._toggle_custom_fields)

        # Initialize
        self._update_model_options(self.reasoning_mode.currentText())

    def _load_custom_models(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {"local": [], "cloud": []}

    def _save_custom_models(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.custom_models, f, indent=4)

    def _update_model_options(self, mode):
        self.model_selection.clear()
        
        if mode == "local":
            predefined = ["qwen3:0.6b", "qwen3:1.7b", "qwen3:4b", "qwen3:8b", "deepseek", "llama3.2", "llama3.2:1b", "llama3.2:3b", "llama3.1:8b"]
            self.model_selection.addItems(predefined)
            self.model_selection.addItems(self.custom_models.get("local", []))
        
        elif mode == "cloud":
            for model_data in self.custom_models.get("cloud", []):
                self.model_selection.addItem(model_data["name"], userData=model_data)

        self.model_selection.addItem("custom")
        self._toggle_custom_fields(self.model_selection.currentText())

    def _toggle_custom_fields(self, model_text):
        is_custom = model_text == "custom"
        self.custom_group.setVisible(is_custom)

        if is_custom:
            is_cloud = self.reasoning_mode.currentText() == "cloud"
            self.custom_api_base.setVisible(is_cloud)
            self.custom_api_base_label.setVisible(is_cloud)
            self.custom_api_key.setVisible(is_cloud)
            self.custom_api_key_label.setVisible(is_cloud)

    def accept(self):
        """Handle saving custom models before closing."""
        if self.model_selection.currentText() == "custom":
            mode = self.reasoning_mode.currentText()
            name = self.custom_model_name.text().strip()
            if not name:
                # Ideally, show a QMessageBox here
                print("Error: Custom model name cannot be empty.")
                return

            if mode == "local":
                local_models = self.custom_models.setdefault("local", [])
                if name not in local_models:
                    local_models.append(name)

            elif mode == "cloud":
                api_base = self.custom_api_base.text().strip()
                api_key = self.custom_api_key.text().strip()
                if not api_base or not api_key:
                    print("Error: API Base and Key are required for cloud models.")
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
        if model_text == "custom":
            config["model"] = self.custom_model_name.text().strip()
            if mode == "cloud":
                config["api_base"] = self.custom_api_base.text().strip()
                config["api_key"] = self.custom_api_key.text().strip()
        else:
            config["model"] = model_text
            if mode == "cloud":
                # For pre-saved cloud models, get data from the item
                user_data = self.model_selection.currentData()
                if user_data:
                    config.update(user_data)
        return config 