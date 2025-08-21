import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSplitter, QListWidget, QTextEdit, QLineEdit, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap
from gui_dialogs_v2 import (
    SettingsDialog, AddFilesDialog, BuildSettingsDialog, ProjectManagerDialog, QuerySettingsDialog, LogViewDialog
)
from gui_dialogs_v2 import LogManager # 导入日志管理器

# It's good practice to check for dependencies.
try:
    # Assuming the script is run from the project root, and 'test' is a subfolder.
    # Adjusting path to correctly find the module.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from graphrag_online.ZHTLLM_reasoning import run_build, run_search, run_init
except ImportError:
    print("Error: Could not import from graphrag_online.ZHTLLM_reasoning.")
    print("Please ensure the file exists and the path is correct.")
    sys.exit(1)


class Worker(QThread):
    """A worker thread for running long tasks (build, search) without freezing the GUI."""
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
        self.setWindowTitle("ZHTLLM RAG Project Interface")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化日志管理器
        self.log_manager = LogManager()
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)  # 改为垂直布局，以便添加顶部Logo
        
        # Application state
        self.settings = SettingsDialog(self).get_settings()  # Start with default settings
        self.build_params = {}
        self.worker = None
        self.current_project = None
        # Make history root path more robust
        self.history_root = os.path.join(os.path.dirname(__file__), 'graphrag_online', 'history')
        #print(f"History root: {self.history_root}")

        # --- Icon Paths ---
        icon_path = "picture/"
        self.icons = {
            "create": QIcon(f"{icon_path}create-new-project.png"),
            "search": QIcon(f"{icon_path}search-history.png"),
            "log": QIcon(f"{icon_path}logview.png"),
            "add_file": QIcon(f"{icon_path}add-file.png"),
            "configure": QIcon(f"{icon_path}config.png"),
        }
        
        # --- 添加Logo ---
        logo_layout = QHBoxLayout()
        logo_label = QLabel()
        try:
            logo_pixmap = QPixmap("picture/logo.png")
            if not logo_pixmap.isNull():
                # 调整Logo大小
                scaled_logo = logo_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_logo)
                logo_label.setAlignment(Qt.AlignCenter)
                logo_layout.addWidget(logo_label, alignment=Qt.AlignCenter)
            else:
                logo_label.setText("Logo")
                logo_layout.addWidget(logo_label, alignment=Qt.AlignCenter)
                self.log_manager.log("警告: 无法加载Logo图片")
        except Exception as e:
            logo_label.setText("Logo")
            logo_layout.addWidget(logo_label, alignment=Qt.AlignCenter)
            self.log_manager.log(f"错误: 加载Logo时出错 - {str(e)}")
        
        # 添加分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        
        main_layout.addLayout(logo_layout)
        main_layout.addWidget(line)

        # Create a splitter to allow resizing of sidebar and main content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left Sidebar
        left_sidebar = QFrame()
        left_sidebar.setObjectName("left_sidebar")
        left_sidebar.setFrameShape(QFrame.StyledPanel)
        left_sidebar_layout = QVBoxLayout(left_sidebar)
        left_sidebar_layout.setAlignment(Qt.AlignTop)
        # --- Sidebar Widgets ---
        self.create_project_btn = QPushButton(" Create a project")
        self.create_project_btn.setIcon(self.icons["create"])
        self.search_projects_btn = QPushButton(" Search for projects")
        self.search_projects_btn.setIcon(self.icons["search"])
        self.log_view_btn = QPushButton(" Log View")
        self.log_view_btn.setIcon(self.icons["log"])
        self.meeting_mode_btn = QPushButton(" Meeting mode")

        history_label = QLabel("History list")
        self.history_list = QListWidget()

        left_sidebar_layout.addWidget(self.create_project_btn)
        left_sidebar_layout.addWidget(self.search_projects_btn)
        left_sidebar_layout.addWidget(self.log_view_btn)
        left_sidebar_layout.addWidget(self.meeting_mode_btn)
        left_sidebar_layout.addSpacing(20)
        left_sidebar_layout.addWidget(history_label)
        left_sidebar_layout.addWidget(self.history_list)

        # Center Content
        center_content = QFrame()
        center_content.setObjectName("center_content")
        center_content.setFrameShape(QFrame.StyledPanel)
        center_content_layout = QVBoxLayout(center_content)

        # --- Build RAG Section ---
        build_rag_group = QGroupBox("1. Build the RAG")
        build_rag_layout = QVBoxLayout()
        build_rag_group.setLayout(build_rag_layout)

        project_desc_layout = QHBoxLayout()
        self.project_desc_label = QLabel("Project Description: No project selected.")
        project_desc_layout.addWidget(self.project_desc_label)
        project_desc_layout.addStretch()

        build_buttons_layout = QHBoxLayout()
        self.add_files_btn = QPushButton(" add files")
        self.add_files_btn.setIcon(self.icons["add_file"])
        self.configure_build_btn = QPushButton(" configure")
        self.configure_build_btn.setIcon(self.icons["configure"])
        self.run_build_btn = QPushButton("Run Build")
        build_buttons_layout.addWidget(self.add_files_btn)
        build_buttons_layout.addWidget(self.configure_build_btn)
        build_buttons_layout.addWidget(self.run_build_btn)
        build_buttons_layout.addStretch()

        build_rag_layout.addLayout(project_desc_layout)
        build_rag_layout.addLayout(build_buttons_layout)

        # --- Query Section ---
        query_group = QGroupBox("2. Query")
        query_layout = QVBoxLayout()
        query_group.setLayout(query_layout)

        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Ask any questions:")

        query_buttons_layout = QHBoxLayout()
        self.configure_query_btn = QPushButton(" configure")
        self.configure_query_btn.setIcon(self.icons["configure"])
        self.run_query_btn = QPushButton("Run Query")
        query_buttons_layout.addWidget(self.configure_query_btn)
        query_buttons_layout.addWidget(self.run_query_btn)
        query_buttons_layout.addStretch()

        query_layout.addWidget(self.query_input)
        query_layout.addLayout(query_buttons_layout)

        # --- Output/Log Section ---
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()
        output_group.setLayout(output_layout)
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        output_layout.addWidget(self.output_console)

        center_content_layout.addWidget(build_rag_group)
        center_content_layout.addWidget(query_group)
        center_content_layout.addWidget(output_group)

        # Right part for settings button
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(self.icons["configure"])
        right_layout.addWidget(self.settings_btn)
        right_layout.addStretch()

        # Add widgets to splitter
        splitter.addWidget(left_sidebar)
        splitter.addWidget(center_content)
        main_layout.addWidget(right_panel)

        splitter.setSizes([200, 800])

        self.connect_signals()
        self.refresh_project_list()
        
        # 记录应用启动
        self.log_manager.log("应用启动")
    
    def connect_signals(self):
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        self.add_files_btn.clicked.connect(self.open_add_files_dialog)
        self.configure_build_btn.clicked.connect(self.open_build_config_dialog)
        self.configure_query_btn.clicked.connect(self.open_query_config_dialog)
        self.run_build_btn.clicked.connect(self.execute_build)
        self.run_query_btn.clicked.connect(self.execute_search)
        self.create_project_btn.clicked.connect(self.open_project_manager)  # 修改连接函数
        self.search_projects_btn.clicked.connect(self.open_search_project_dialog)
        self.history_list.itemClicked.connect(self.set_active_project)
        self.log_view_btn.clicked.connect(self.open_log_view)
    
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
        """打开项目管理对话框"""
        dialog = ProjectManagerDialog(self, self.history_root)
        dialog.exec()
        self.refresh_project_list()
    
    def open_search_project_dialog(self):
        dialog = ProjectManagerDialog(self, title="Search Project", prompt="Enter project name to search:")
        if dialog.exec():
            search_name = dialog.get_name()
            if search_name:
                items = self.history_list.findItems(search_name, Qt.MatchExactly)
                if items:
                    self.history_list.setCurrentItem(items[0])
                    self.set_active_project(items[0])
                    QMessageBox.information(self, "Found", f"Project '{search_name}' found and selected.")
                    self.log_manager.log(f"项目搜索: 找到项目 '{search_name}'")
                else:
                    QMessageBox.warning(self, "Not Found", f"Project '{search_name}' not found in history.")
                    self.log_manager.log(f"项目搜索: 未找到项目 '{search_name}'")
    
    def set_active_project(self, item):
        self.current_project = item.text()
        self.project_desc_label.setText(f"Project Description: {self.current_project}")
        self.output_console.append(f"Active project set to: '{self.current_project}'")
        self.log_manager.log(f"活动项目设置为: '{self.current_project}'")
    
    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.output_console.append("Settings updated.")
            self.log_manager.log("设置已更新")
    
    def open_add_files_dialog(self):
        dialog = AddFilesDialog(self)
        if dialog.exec():
            self.build_params = dialog.get_build_params()
            self.output_console.append("Files selected for the next build.")
            self.log_manager.log("已选择用于构建的文件")
    
    def open_build_config_dialog(self):
        dialog = BuildSettingsDialog(self, self.settings)
        if dialog.exec():
            config = dialog.get_build_config()
            self.settings['inference_mode'] = config['inference_mode']
            
            if config['inference_mode'] == 'local':
                self.settings['local_model'] = config['model']
            elif config['inference_mode'] == 'cloud':
                self.settings['cloud_model'] = config['model']
                if 'api_base' in config: self.settings['cloud_api_base'] = config['api_base']
                if 'api_key' in config: self.settings['cloud_api_key'] = config['api_key']
            
            self.output_console.append(f"Build configuration updated: Mode set to {config['inference_mode']}, model set to {config['model']}.")
            self.log_manager.log(f"构建配置更新: 模式设置为 {config['inference_mode']}, 模型设置为 {config['model']}")
    
    def open_query_config_dialog(self):
        """Opens the configuration dialog for the query-specific settings."""
        dialog = QuerySettingsDialog(self, self.settings)
        if dialog.exec():
            config = dialog.get_query_config()
            self.settings['inference_mode'] = config['inference_mode']
            
            if config['inference_mode'] == 'local':
                self.settings['local_model'] = config['model']
            elif config['inference_mode'] == 'cloud':
                self.settings['cloud_model'] = config['model']
                if 'api_base' in config: self.settings['cloud_api_base'] = config['api_base']
                if 'api_key' in config: self.settings['cloud_api_key'] = config['api_key']
            
            self.output_console.append(f"Query configuration updated: Mode set to {config['inference_mode']}, model set to {config['model']}.")
            self.log_manager.log(f"查询配置更新: 模式设置为 {config['inference_mode']}, 模型设置为 {config['model']}")
    
    def execute_build(self):
        if not self.build_params or (not self.build_params.get('dialogue') and not self.build_params.get('text_files')):
            QMessageBox.warning(self, "Build Error", "No files selected for build. Use 'add files' first.")
            self.log_manager.log("构建错误: 未选择用于构建的文件")
            return
        
        if not self.current_project:
            QMessageBox.warning(self, "Build Error", "No project selected. Please create or select a project first.")
            self.log_manager.log("构建错误: 未选择项目")
            return

        self.output_console.append(f"\n--- Running Build for project '{self.current_project}' ---")
        self.log_manager.log(f"开始为项目 '{self.current_project}' 执行构建")
        self.run_build_btn.setEnabled(False)
        self.run_query_btn.setEnabled(False)

        build_args = {**self.build_params, **self.settings, "name": self.current_project}

        self.worker = Worker(run_build, **build_args)
        self.worker.finished.connect(self.on_build_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.start()
    
    def execute_search(self):
        query = self.query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Query Error", "Query is empty.")
            self.log_manager.log("查询错误: 查询内容为空")
            return

        if not self.current_project:
            QMessageBox.warning(self, "Query Error", "No project selected. Please create or select a project first.")
            self.log_manager.log("查询错误: 未选择项目")
            return

        self.output_console.append(f"\n--- Running Query in project '{self.current_project}' ---")
        self.log_manager.log(f"开始在项目 '{self.current_project}' 中执行查询: {query}")
        self.query_input.clear()  # Clear input after running
        self.run_build_btn.setEnabled(False)
        self.run_query_btn.setEnabled(False)

        search_args = {**self.settings, "query": query, "name": self.current_project}

        self.worker = Worker(run_search, **search_args)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.start()
    
    def on_build_finished(self, result):
        self.output_console.append("--- Build Finished ---")
        self.output_console.append(str(result) if result else "Build process completed successfully.")
        self.log_manager.log("构建完成")
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def on_search_finished(self, result):
        self.output_console.append("--- Search Finished ---")
        self.output_console.append(result if result else "Search completed with no result.")
        self.log_manager.log(f"查询完成: {result[:50]}..." if result else "查询完成，无结果")
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def on_task_error(self, error_message):
        self.output_console.append(f"\n--- ERROR --- \n{error_message}")
        self.log_manager.log(f"任务错误: {error_message}")
        self.run_build_btn.setEnabled(True)
        self.run_query_btn.setEnabled(True)
        self.worker = None
    
    def open_log_view(self):
        """打开日志查看对话框"""
        dialog = LogViewDialog(self, self.log_manager)
        dialog.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # --- Modern Stylesheet ---
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
        QTextEdit, QListWidget, QLineEdit {
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
    
    # 记录应用启动完成
    window.log_manager.log("应用启动完成")
    
    sys.exit(app.exec())    