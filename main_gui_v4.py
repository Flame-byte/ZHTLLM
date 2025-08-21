import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSplitter, QListWidget, QTextEdit, QLineEdit, QGroupBox, QMessageBox,
    QComboBox, QDialogButtonBox, QFileDialog, QListWidgetItem, QDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QTextCursor, QMovie

# 独立的语言模块
from language import lang  # 从独立模块导入语言实例

# 导入对话框
from gui_dialogs_v4 import (
    SettingsDialog, AddFilesDialog, BuildSettingsDialog, ProjectManagerDialog, QuerySettingsDialog, LogViewDialog, MeetingModeDialog
)
from gui_dialogs_v4 import LogManager  # 导入日志管理器

# 确保依赖项
try:
    # 假设脚本从项目根目录运行，'test'是子文件夹
    # 调整路径以正确找到模块
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from graphrag_online.ZHTLLM_reasoning import run_build, run_search, run_init
except ImportError:
    print("Error: Could not import from graphrag_online.ZHTLLM_reasoning.")
    print("Please ensure the file exists and the path is correct.")
    sys.exit(1)


class Worker(QThread):
    """用于运行长时间任务（构建、搜索）而不冻结GUI的工作线程。"""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")


class ZHTLLM_GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(lang.get('title'))
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化日志管理器
        self.log_manager = LogManager()
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Application state
        self.settings = SettingsDialog(self).get_settings()  # 从默认设置开始

        # --- MODIFICATION: Separate build and query settings ---
        # 为构建和查询分别创建独立的模型配置字典，并从通用设置初始化
        self.build_settings = {
            'inference_mode': self.settings.get('inference_mode'),
            'cloud_api_base': self.settings.get('cloud_api_base'),
            'cloud_api_key': self.settings.get('cloud_api_key'),
            'cloud_model': self.settings.get('cloud_model'),
            'local_api_base': self.settings.get('local_api_base'),
            'local_model': self.settings.get('local_model'),
        }
        self.query_settings = self.build_settings.copy()
        self.query_settings['method'] = 'local'

        self.build_params = {}
        self.worker = None
        self.current_project = None
        self.meeting_dialog = None 
        # 使历史根路径更健壮
        self.history_root = os.path.join(os.path.dirname(__file__), 'graphrag_online', 'history')

        # --- Icon Paths ---
        icon_path = "picture/"
        self.icons = {
            "create": QIcon(f"{icon_path}create-new-project.png"),
            "search": QIcon(f"{icon_path}search-history.png"),
            "log": QIcon(f"{icon_path}logview.png"),
            "meeting": QIcon(f"{icon_path}add-file.png"), # Placeholder icon for meeting mode
            "add_file": QIcon(f"{icon_path}add-file.png"),
            "configure": QIcon(f"{icon_path}config.png"),
        }

        # 创建一个分割器以允许调整侧边栏和主内容的大小
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left Sidebar
        left_sidebar = QFrame()
        left_sidebar.setObjectName("left_sidebar")
        left_sidebar.setFrameShape(QFrame.StyledPanel)
        left_sidebar_layout = QVBoxLayout(left_sidebar)
        left_sidebar_layout.setAlignment(Qt.AlignTop)

        # --- Sidebar Widgets ---
        self.search_projects_btn = QPushButton(lang.get('search_projects'))
        self.search_projects_btn.setIcon(self.icons["search"])
        
        self.project_manager_btn = QPushButton(lang.get('create_or_delete_project'))
        self.project_manager_btn.setIcon(self.icons["create"])
        
        self.log_view_btn = QPushButton(lang.get('log_view'))
        self.log_view_btn.setIcon(self.icons["log"])
        
        self.meeting_mode_btn = QPushButton(lang.get('meeting_mode'))
        self.meeting_mode_btn.setIcon(self.icons["meeting"]) # Use a specific icon

        self.history_label = QLabel(lang.get('history_list'))
        self.history_list = QListWidget()

        left_sidebar_layout.addWidget(self.search_projects_btn)
        left_sidebar_layout.addWidget(self.project_manager_btn)
        left_sidebar_layout.addWidget(self.log_view_btn)
        left_sidebar_layout.addWidget(self.meeting_mode_btn)
        left_sidebar_layout.addSpacing(20)
        left_sidebar_layout.addWidget(self.history_label)
        left_sidebar_layout.addWidget(self.history_list)
        
        # --- 添加Logo ---
        logo_version_layout = QHBoxLayout()
        
        self.logo_label = QLabel()
        try:
            logo_pixmap = QPixmap("picture/logo.png")
            if not logo_pixmap.isNull():
                scaled_logo = logo_pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(scaled_logo)
                self.logo_label.setAlignment(Qt.AlignCenter)
            else:
                self.logo_label.setText("Logo")
                self.log_manager.log("警告: 无法加载Logo图片")
        except Exception as e:
            self.logo_label.setText("Logo")
            self.log_manager.log(f"错误: 加载Logo时出错 - {str(e)}")
        
        self.version_label = QLabel("UI 20250725 v4")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setStyleSheet("font-size: 12px; color: #666;")
        
        logo_version_layout.addWidget(self.logo_label)
        logo_version_layout.addWidget(self.version_label)
        left_sidebar_layout.addLayout(logo_version_layout)

        # Center Content
        center_content = QFrame()
        center_content.setObjectName("center_content")
        center_content.setFrameShape(QFrame.StyledPanel)
        center_content_layout = QVBoxLayout(center_content)

        # --- Build RAG Section ---
        self.build_rag_group = QGroupBox(lang.get('build_rag'))
        build_rag_layout = QVBoxLayout()
        self.build_rag_group.setLayout(build_rag_layout)

        top_bar_layout = QHBoxLayout()
        
        self.project_desc_label = QLabel(lang.get('project_desc'))
        top_bar_layout.addWidget(self.project_desc_label)
        top_bar_layout.addStretch()
        
        self.language_selector = QComboBox()
        self.language_selector.addItems(lang.get_language_list())
        self.language_selector.currentTextChanged.connect(self.change_language)
        
        self.settings_btn = QPushButton(lang.get('settings'))
        self.settings_btn.setIcon(QIcon("picture/config.png"))
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        
        top_bar_layout.addWidget(self.language_selector)
        top_bar_layout.addWidget(self.settings_btn)
        
        build_rag_layout.addLayout(top_bar_layout)

        build_buttons_layout = QHBoxLayout()
        self.add_files_btn = QPushButton(lang.get('add_files'))
        self.add_files_btn.setIcon(self.icons["add_file"])
        self.configure_build_btn = QPushButton(lang.get('configure_build'))
        self.configure_build_btn.setIcon(self.icons["configure"])
        self.run_build_btn = QPushButton(lang.get('run_build'))
        build_buttons_layout.addWidget(self.add_files_btn)
        build_buttons_layout.addWidget(self.configure_build_btn)
        build_buttons_layout.addWidget(self.run_build_btn)
        build_buttons_layout.addStretch()

        build_rag_layout.addLayout(build_buttons_layout)

        # --- Query Section ---
        self.query_group = QGroupBox(lang.get('query'))
        query_layout = QVBoxLayout()
        self.query_group.setLayout(query_layout)

        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText(lang.get('query_input'))

        query_buttons_layout = QHBoxLayout()
        self.configure_query_btn = QPushButton(lang.get('configure_query'))
        self.configure_query_btn.setIcon(self.icons["configure"])
        self.run_query_btn = QPushButton(lang.get('run_query'))
        query_buttons_layout.addWidget(self.configure_query_btn)
        query_buttons_layout.addWidget(self.run_query_btn)
        query_buttons_layout.addStretch()

        query_layout.addWidget(self.query_input)
        query_layout.addLayout(query_buttons_layout)

        # --- Output/Log Section ---
        self.output_group = QGroupBox(lang.get('output'))
        output_layout = QVBoxLayout()
        self.output_group.setLayout(output_layout)
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        output_layout.addWidget(self.output_console)

        center_content_layout.addWidget(self.build_rag_group)
        center_content_layout.addWidget(self.query_group)
        center_content_layout.addWidget(self.output_group)

        splitter.addWidget(left_sidebar)
        splitter.addWidget(center_content)
        splitter.setSizes([200, 800])

        self.connect_signals()
        self.refresh_project_list()
        
        self.log_manager.log(lang.get('application_started'))
    
    
    def connect_signals(self):
        self.add_files_btn.clicked.connect(self.open_add_files_dialog)
        self.configure_build_btn.clicked.connect(self.open_build_config_dialog)
        self.configure_query_btn.clicked.connect(self.open_query_config_dialog)
        self.run_build_btn.clicked.connect(self.execute_build)
        self.run_query_btn.clicked.connect(self.execute_search)
        self.project_manager_btn.clicked.connect(self.open_project_manager)
        self.search_projects_btn.clicked.connect(self.search_external_project)
        self.history_list.itemClicked.connect(self.set_active_project)
        self.log_view_btn.clicked.connect(self.open_log_view)
        self.meeting_mode_btn.clicked.connect(self.open_meeting_mode_dialog)

    def refresh_project_list(self):
        self.history_list.clear()
        if not os.path.exists(self.history_root):
            os.makedirs(self.history_root)
        
        try:
            projects = [d for d in os.listdir(self.history_root) if os.path.isdir(os.path.join(self.history_root, d))]
            self.history_list.addItems(projects)
        except FileNotFoundError:
            self.output_console.append(f"Warning: History directory not found at {self.history_root}")
            self.log_manager.log(f"警告: 历史目录不存在 - {self.history_root}")
    
    def open_project_manager(self):
        dialog = ProjectManagerDialog(self, self.history_root)
        dialog.exec()
        self.refresh_project_list()
    
    def search_external_project(self):
        project_dir = QFileDialog.getExistingDirectory(
            self, 
            lang.get('search_projects'), 
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not project_dir:
            return
        
        project_name = os.path.basename(project_dir)
        target_dir = os.path.join(self.history_root, project_name)
        
        try:
            import shutil
            if os.path.exists(target_dir):
                reply = QMessageBox.question(
                    self, 
                    "确认覆盖", 
                    f"项目 '{project_name}' 已存在，是否覆盖？", 
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            for item in os.listdir(project_dir):
                s = os.path.join(project_dir, item)
                d = os.path.join(target_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            
            self.refresh_project_list()
            items = self.history_list.findItems(project_name, Qt.MatchExactly)
            if items:
                self.history_list.setCurrentItem(items[0])
                self.set_active_project(items[0])
                QMessageBox.information(self, "成功", f"项目 '{project_name}' 已添加到历史记录")
                self.log_manager.log(f"项目 '{project_name}' 已从外部添加")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法添加项目: {str(e)}")
            self.log_manager.log(f"错误: 添加外部项目失败 - {str(e)}")
    
    def set_active_project(self, item):
        self.current_project = item.text()
        self.project_desc_label.setText(lang.get('active_project').format(self.current_project))
        self.log_manager.log(lang.get('active_project').format(self.current_project))
    
    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.log_manager.log(lang.get('settings_updated'))
    
    def open_add_files_dialog(self):
        dialog = AddFilesDialog(self)
        if dialog.exec():
            self.build_params = dialog.get_build_params()
            self.log_manager.log(lang.get('files_selected'))
    
    def open_build_config_dialog(self):
        """MODIFIED: Opens build config and updates the dedicated build_settings dict."""
        dialog = BuildSettingsDialog(self, self.build_settings)
        if dialog.exec():
            config = dialog.get_build_config()
            # 更新独立的构建配置字典
            self.build_settings['inference_mode'] = config['inference_mode']
            if config['inference_mode'] == 'local':
                self.build_settings['local_model'] = config['model']
            elif config['inference_mode'] == 'cloud':
                self.build_settings['cloud_model'] = config['model']
                if 'api_base' in config: self.build_settings['cloud_api_base'] = config['api_base']
                if 'api_key' in config: self.build_settings['cloud_api_key'] = config['api_key']
            
            self.log_manager.log(lang.get('build_config_updated').format(config['inference_mode'], config['model']))
    
    def open_query_config_dialog(self):
        """MODIFIED: Opens query config and updates the dedicated query_settings dict."""
        dialog = QuerySettingsDialog(self, self.query_settings)
        if dialog.exec():
            config = dialog.get_query_config()
            # 更新独立的查询配置字典
            self.query_settings['inference_mode'] = config['inference_mode']
            self.query_settings['method'] = config.get('method', 'local')
            if config['inference_mode'] == 'local':
                self.query_settings['local_model'] = config['model']
            elif config['inference_mode'] == 'cloud':
                self.query_settings['cloud_model'] = config['model']
                if 'api_base' in config: self.query_settings['cloud_api_base'] = config['api_base']
                if 'api_key' in config: self.query_settings['cloud_api_key'] = config['api_key']
            
            self.log_manager.log(lang.get('query_config_updated').format(config['inference_mode'], config['model']))

    def open_meeting_mode_dialog(self):
        """
        MODIFIED: Passes the build_settings to the meeting mode dialog.
        """
        if not self.current_project:
            QMessageBox.warning(self, lang.get('warning'), lang.get('query_error_no_project'))
            return

        if self.meeting_dialog and self.meeting_dialog.isVisible():
            self.meeting_dialog.activateWindow() 
            return
            
        # 创建新对话框实例，并传入独立的构建配置
        self.meeting_dialog = MeetingModeDialog(
            parent=self, 
            project_name=self.current_project, 
            history_root=self.history_root,
            settings=self.settings,
            build_settings=self.build_settings  # 传入构建配置
        )
        self.meeting_dialog.show() 


    def execute_build(self):
        if not self.build_params or (not self.build_params.get('dialogue') and not self.build_params.get('text_files')):
            QMessageBox.warning(self, "Build Error", lang.get('build_error_no_files'))
            self.log_manager.log(lang.get('build_error_no_files'))
            return
        
        if not self.current_project:
            QMessageBox.warning(self, "Build Error", lang.get('build_error_no_project'))
            self.log_manager.log(lang.get('build_error_no_project'))
            return

        self.output_console.append(f"\n--- {lang.get('build_started').format(self.current_project)} ---")
        self.log_manager.log(lang.get('build_started').format(self.current_project))
        self.run_build_btn.setEnabled(False)
        self.run_query_btn.setEnabled(False)

        # MODIFIED: Combine general, file, and build-specific settings.
        # build_settings会覆盖settings中的同名键。
        build_args = {**self.settings, **self.build_params, **self.build_settings, "name": self.current_project}

        self.worker = Worker(run_build, **build_args)
        self.worker.finished.connect(self.on_build_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.start()
    
    def execute_search(self):
        query = self.query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Query Error", lang.get('query_error_empty'))
            self.log_manager.log(lang.get('query_error_empty'))
            return

        if not self.current_project:
            QMessageBox.warning(self, "Query Error", lang.get('query_error_no_project'))
            self.log_manager.log(lang.get('query_error_no_project'))
            return

        # --- MODIFICATION: Add language-specific instruction to the query ---
        try:
            # Safely access current_language, defaulting to English if unavailable
            current_language = getattr(lang, 'current_language', 'English') 
            if current_language == '中文':
                query += "\n\n Answer in Chinese"
            else: # Default to English for any other case
                query += "\n\n Answer in English"
        except Exception as e:
            self.log_manager.log(f"Could not append language instruction to query: {e}")
        # --- END MODIFICATION ---

        self.output_console.append(f"\n--- {lang.get('query_started').format(self.current_project, query[:50])} ---")
        self.log_manager.log(lang.get('query_started').format(self.current_project, query[:50]))
        self.query_input.clear()
        self.run_build_btn.setEnabled(False)
        self.run_query_btn.setEnabled(False)

        # MODIFIED: Combine general and query-specific settings.
        # query_settings会覆盖settings中的同名键。
        search_args = {**self.settings, **self.query_settings, "query": query, "name": self.current_project}

        self.worker = Worker(run_search, **search_args)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.start()
    
    def on_build_finished(self, result):
        self.output_console.append(lang.get('build_finished'))
        self.output_console.append(str(result) if result else "Build process completed successfully.")
        self.log_manager.log(lang.get('build_complete'))
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def on_search_finished(self, result):
        self.output_console.append(lang.get('search_finished'))
        self.output_console.append(result if result else "Search completed with no result.")
        self.log_manager.log(lang.get('query_complete').format(result[:50] if result else "无结果"))
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def on_task_error(self, error_message):
        self.output_console.append(f"\n{lang.get('error_occurred')} \n{error_message}")
        self.log_manager.log(lang.get('task_error').format(error_message))
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def open_log_view(self):
        dialog = LogViewDialog(self, self.log_manager)
        dialog.exec()
    
    def change_language(self, language):
        lang.set_language(language)
        self.update_ui_text()
    
    def update_ui_text(self):
        self.settings_btn.setText(lang.get('settings'))
        self.setWindowTitle(lang.get('title'))
        self.search_projects_btn.setText(lang.get('search_projects'))
        self.project_manager_btn.setText(lang.get('create_or_delete_project'))
        self.log_view_btn.setText(lang.get('log_view'))
        self.meeting_mode_btn.setText(lang.get('meeting_mode'))
        self.history_label.setText(lang.get('history_list'))
        
        self.build_rag_group.setTitle(lang.get('build_rag'))
        self.add_files_btn.setText(lang.get('add_files'))
        self.configure_build_btn.setText(lang.get('configure_build'))
        self.run_build_btn.setText(lang.get('run_build'))
        
        self.query_group.setTitle(lang.get('query'))
        self.query_input.setPlaceholderText(lang.get('query_input'))
        self.configure_query_btn.setText(lang.get('configure_query'))
        self.run_query_btn.setText(lang.get('run_query'))
        
        self.output_group.setTitle(lang.get('output'))
        
        if not self.current_project:
            self.project_desc_label.setText(lang.get('project_desc'))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    STYLESHEET = """
        QWidget {
            background-color: #f7f7f8;
            color: #202123;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 14px;
        }
        QMainWindow {
            background-color: #f7f7f8;
        }
        QFrame#left_sidebar {
            background-color: #ffffff;
            border-right: 1px solid #e0e0e0;
            border-radius: 0px;
        }
        QFrame#center_content {
            background-color: transparent;
            border: none;
        }
        QGroupBox {
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            margin-top: 15px;
            background-color: #ffffff;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 15px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #dcdcdc;
            border-radius: 8px;
            padding: 8px 16px;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
        QFrame#left_sidebar QPushButton {
            background-color: transparent;
            border: none;
            border-radius: 8px;
            text-align: left;
            padding: 12px;
        }
        QFrame#left_sidebar QPushButton:hover {
            background-color: #ececf1;
        }
        QTextEdit, QListWidget, QLineEdit, QTextBrowser, QSpinBox {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 8px;
        }
        QComboBox {
            border: 1px solid #dcdcdc;
            border-radius: 8px;
            padding: 5px 10px;
            background-color: white;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 1px;
            border-left-color: #dcdcdc;
            border-left-style: solid;
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
        }
        QComboBox::down-arrow {
            image: url(picture/open_select2.jpg);
        }
        QComboBox QAbstractItemView {
            border: 1px solid #dcdcdc;
            background-color: white;
            selection-background-color: #f0f0f0;
            color: #202123;
        }
        QSplitter::handle:horizontal {
            background: #e0e0e0;
            width: 1px;
        }
        QLabel {
            background-color: transparent;
        }
    """
    app.setStyleSheet(STYLESHEET)
    
    window = ZHTLLM_GUI()
    window.show()
    
    window.log_manager.log(lang.get('application_started_complete'))
    
    sys.exit(app.exec())