import sys
import os
import threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import requests
from dotenv import load_dotenv
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize

load_dotenv()

BTN_PRIMARY = """
    QPushButton {
        background: #4a7c65; color: white; border: none;
        border-radius: 8px; font-size: 13px; font-weight: 600;
    }
    QPushButton:hover { background: #3d6b56; }
"""
BTN_SECONDARY = """
    QPushButton {
        background: #eef5f1; color: #3d6b56;
        border: 1px solid #c6ddd3; border-radius: 8px;
        font-size: 13px; font-weight: 500;
    }
    QPushButton:hover { background: #d9ede4; }
"""
INPUT_STYLE = """
    QLineEdit, QTextEdit {
        border: 1px solid #e0e4ea; border-radius: 8px;
        padding: 0 12px; font-size: 13px;
        color: #1a2332; background: #fafbfc;
    }
    QLineEdit:focus, QTextEdit:focus { border-color: #4a7c65; }
"""


class ClickableCard(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, project_data, parent=None):
        super().__init__(parent)
        self.project_data = project_data
        self.setCursor(Qt.PointingHandCursor)
        self._setup(project_data)

    def _setup(self, data):
        self.setFixedHeight(140)
        self.setStyleSheet("""
            ClickableCard { background: white; border-radius: 12px; border: 1px solid #eef0f3; }
            ClickableCard:hover { border: 1px solid #c8d0dc; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(4)

        title = QLabel(data.get("name", "Untitled"))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        title.setWordWrap(True)

        date_label = QLabel(data.get("created_at", "")[:10])
        date_label.setStyleSheet("font-size: 11px; color: #8a95a3;")

        desc = QLabel(data.get("description", "")[:60])
        desc.setStyleSheet("font-size: 12px; color: #5a6472;")
        desc.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(date_label)
        layout.addWidget(desc)
        layout.addStretch()

    def mousePressEvent(self, event):
        self.clicked.emit(self.project_data)
        super().mousePressEvent(event)


class NavButton(QPushButton):
    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon_text}   {label}")
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet("""
            QPushButton { text-align: left; padding-left: 20px; color: #9ba8b5;
                font-size: 13px; font-weight: 500; border: none; background: transparent; }
            QPushButton:checked { background: #4a7c65; color: white; }
            QPushButton:hover:!checked { color: #dce4ed; background: rgba(255,255,255,0.05); }
        """)


# ── Worker thread for dataset loading so UI stays responsive ─────────────────
class DatasetLoaderWorker(QThread):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, api_base, payload):
        super().__init__()
        self.api_base = api_base
        self.payload = payload

    def run(self):
        try:
            # Kick off loading
            r = requests.post(f"{self.api_base}/projects/load_dataset/", json=self.payload, timeout=15)
            if r.status_code not in (200, 201):
                self.error.emit(f"Failed to start: {r.text}")
                return

            # Poll until done
            while True:
                self.msleep(2000)
                poll = requests.get(f"{self.api_base}/projects/dataset_status/", timeout=10)
                if poll.status_code == 200:
                    data = poll.json()
                    self.progress.emit(data)
                    if data.get("done") or data.get("error"):
                        self.finished.emit(data)
                        return
        except Exception as e:
            self.error.emit(str(e))


class BRDGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api")
        self.current_project = None
        self.selected_brd = None
        self._loader_worker = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("BRD Generator Pro")
        self.setGeometry(100, 80, 1280, 860)
        self.setStyleSheet("background: #f0f2f5;")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: #f0f2f5;")
        root_layout.addWidget(self.content_stack)

        self.pages = {
            "Projects":      self._build_projects_page(),
            "Dataset":       self._build_dataset_page(),
            "Data Sources":  self._build_data_sources_page(),
            "Requirements":  self._build_requirements_page(),
            "BRD Generation": self._build_brd_page(),
            "Analysis":      self._build_analysis_page(),
        }
        for page in self.pages.values():
            self.content_stack.addWidget(page)

        QTimer.singleShot(300, self._load_projects)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background: #1e2a35;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo_area = QWidget()
        logo_area.setFixedHeight(64)
        logo_area.setStyleSheet("background: #1a2430;")
        logo_layout = QHBoxLayout(logo_area)
        logo_layout.setContentsMargins(16, 0, 16, 0)
        icon_lbl = QLabel("≡")
        icon_lbl.setStyleSheet("color: #4a7c65; font-size: 20px; font-weight: bold;")
        title_lbl = QLabel("BRD Generator Pro")
        title_lbl.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        logo_layout.addWidget(icon_lbl)
        logo_layout.addWidget(title_lbl)
        logo_layout.addStretch()
        layout.addWidget(logo_area)
        layout.addSpacing(12)

        nav_items = [
            ("", "Projects"),
            ("", "Projects"),
            ("", "Data Sources"),
            ("", "Requirements"),
            ("", "BRD Generation"),
            ("", "Analysis"),
        ]

        self.nav_buttons = []
        for icon, label in nav_items:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, l=label: self._switch_page(l))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #5a6e7f; font-size: 10px; padding: 0 16px 12px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        return sidebar

    def _switch_page(self, label):
        for btn in self.nav_buttons:
            btn.setChecked(btn.text().strip().endswith(label))
        page = self.pages.get(label)
        if page:
            self.content_stack.setCurrentWidget(page)

    # ── PAGE: Projects ────────────────────────────────────────────────────────
    def _build_projects_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(24)

        top_bar = QHBoxLayout()
        page_title = QLabel("Projects")
        page_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        top_bar.addWidget(page_title)
        top_bar.addStretch()

        export_btn = QPushButton("Export Project ZIP")
        export_btn.setFixedHeight(36)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(BTN_SECONDARY)
        export_btn.clicked.connect(self._export_project_zip)
        top_bar.addWidget(export_btn)
        layout.addLayout(top_bar)

        create_card = QFrame()
        create_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        create_layout = QVBoxLayout(create_card)
        create_layout.setContentsMargins(24, 20, 24, 20)
        create_layout.setSpacing(12)

        create_layout.addWidget(self._label("Create New Project", 16, bold=True))

        name_row = QHBoxLayout()
        self.project_name_input = self._line_edit("Project Name")
        create_btn = QPushButton("Create Project")
        create_btn.setFixedHeight(42)
        create_btn.setFixedWidth(150)
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setStyleSheet(BTN_PRIMARY)
        create_btn.clicked.connect(self._create_project)
        name_row.addWidget(self.project_name_input)
        name_row.addWidget(create_btn)
        create_layout.addLayout(name_row)

        self.project_desc_input = self._line_edit("Description (optional)")
        create_layout.addWidget(self.project_desc_input)
        layout.addWidget(create_card)

        layout.addWidget(self._label("Existing Projects", 16, bold=True))

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(16)
        layout.addWidget(self.cards_container)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(38)
        refresh_btn.setFixedWidth(120)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(BTN_PRIMARY)
        refresh_btn.clicked.connect(self._load_projects)
        layout.addWidget(refresh_btn)
        layout.addStretch()
        return outer

    # ── PAGE: Dataset ─────────────────────────────────────────────────────────
    def _build_dataset_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        layout.addWidget(self._label("Load Enron Dataset", 22, bold=True))

        card = QFrame()
        card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(14)

        cl.addWidget(self._label(
            "Load the Enron email CSV into a project so the ML models can process it.",
            12, color="#5a6472"
        ))

        form = QFormLayout()
        form.setSpacing(10)

        self.ds_project_input = self._line_edit("e.g. Enron BRD Project")
        self.ds_csv_input = self._line_edit("emails.csv")
        self.ds_topic_input = self._line_edit("e.g. energy trading platform  (leave blank for all)")
        self.ds_limit_input = self._line_edit("300")

        form.addRow("Project Name:", self.ds_project_input)
        form.addRow("CSV filename (in dataset/):", self.ds_csv_input)
        form.addRow("Product Topic Filter:", self.ds_topic_input)
        form.addRow("Row Limit:", self.ds_limit_input)
        cl.addLayout(form)

        load_btn = QPushButton("Load Dataset into DB")
        load_btn.setFixedHeight(42)
        load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.setStyleSheet(BTN_PRIMARY)
        load_btn.clicked.connect(self._load_dataset)
        cl.addWidget(load_btn)

        self.ds_progress_bar = QProgressBar()
        self.ds_progress_bar.setRange(0, 0)   # indeterminate until we know total
        self.ds_progress_bar.setVisible(False)
        self.ds_progress_bar.setFixedHeight(10)
        self.ds_progress_bar.setStyleSheet("""
            QProgressBar { border: none; border-radius: 5px; background: #eef0f3; }
            QProgressBar::chunk { background: #4a7c65; border-radius: 5px; }
        """)
        cl.addWidget(self.ds_progress_bar)

        self.ds_status_label = QLabel("")
        self.ds_status_label.setStyleSheet("font-size: 12px; color: #5a6472;")
        self.ds_status_label.setWordWrap(True)
        cl.addWidget(self.ds_status_label)

        layout.addWidget(card)
        layout.addStretch()
        return outer

    # ── PAGE: Data Sources ────────────────────────────────────────────────────
    def _build_data_sources_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        layout.addWidget(self._label("Data Sources", 22, bold=True))

        sync_card = QFrame()
        sync_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        sync_layout = QVBoxLayout(sync_card)
        sync_layout.setContentsMargins(24, 20, 24, 20)
        sync_layout.setSpacing(12)
        sync_layout.addWidget(self._label("Sync External Sources", 14, bold=True))

        # Product topic field (applies to both Gmail and Slack)
        topic_row = QHBoxLayout()
        topic_row.addWidget(QLabel("Product Topic Filter:"))
        self.sync_topic_input = self._line_edit("e.g. Product A  (optional — for Slack multi-product channels)")
        topic_row.addWidget(self.sync_topic_input)
        sync_layout.addLayout(topic_row)

        # Multi-product list for Slack
        mp_row = QHBoxLayout()
        mp_row.addWidget(QLabel("All Products (comma-separated):"))
        self.multi_product_input = self._line_edit("e.g. Product A, Product B, Product C")
        mp_row.addWidget(self.multi_product_input)
        sync_layout.addLayout(mp_row)

        gmail_row = QHBoxLayout()
        self.gmail_query_input = self._line_edit("Gmail query: subject:requirements after:2024/01/01")
        gmail_btn = QPushButton("Sync Gmail")
        gmail_btn.setFixedHeight(38)
        gmail_btn.setFixedWidth(120)
        gmail_btn.setCursor(Qt.PointingHandCursor)
        gmail_btn.setStyleSheet(BTN_PRIMARY)
        gmail_btn.clicked.connect(self._sync_gmail)
        gmail_row.addWidget(self.gmail_query_input)
        gmail_row.addWidget(gmail_btn)
        sync_layout.addLayout(gmail_row)

        slack_row = QHBoxLayout()
        self.slack_channel_input = self._line_edit("Slack channel ID: C01234567")
        slack_btn = QPushButton("Sync Slack")
        slack_btn.setFixedHeight(38)
        slack_btn.setFixedWidth(120)
        slack_btn.setCursor(Qt.PointingHandCursor)
        slack_btn.setStyleSheet(BTN_PRIMARY)
        slack_btn.clicked.connect(self._sync_slack)
        slack_row.addWidget(self.slack_channel_input)
        slack_row.addWidget(slack_btn)
        sync_layout.addLayout(slack_row)

        upload_btn = QPushButton("Upload Document")
        upload_btn.setFixedHeight(38)
        upload_btn.setFixedWidth(160)
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setStyleSheet(BTN_SECONDARY)
        upload_btn.clicked.connect(self._upload_document)
        sync_layout.addWidget(upload_btn)
        layout.addWidget(sync_card)

        table_card = QFrame()
        table_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(24, 20, 24, 20)
        table_layout.setSpacing(12)
        table_layout.addWidget(self._label("Sources", 14, bold=True))

        self.sources_table = self._styled_table(["Type", "Identifier", "Relevant", "Score", "Date"])
        table_layout.addWidget(self.sources_table)

        process_btn = QPushButton("Process Sources & Extract Requirements")
        process_btn.setFixedHeight(40)
        process_btn.setCursor(Qt.PointingHandCursor)
        process_btn.setStyleSheet(BTN_PRIMARY)
        process_btn.clicked.connect(self._process_sources)
        table_layout.addWidget(process_btn)
        layout.addWidget(table_card)
        return outer

    # ── PAGE: Requirements ────────────────────────────────────────────────────
    def _build_requirements_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addWidget(self._label("Requirements", 22, bold=True))

        card = QFrame()
        card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        self.requirements_table = self._styled_table(
            ["Title", "Type", "Priority", "Stakeholder", "Confidence", "Source"]
        )
        card_layout.addWidget(self.requirements_table)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(38)
        refresh_btn.setFixedWidth(120)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(BTN_PRIMARY)
        refresh_btn.clicked.connect(self._load_requirements)
        card_layout.addWidget(refresh_btn)
        layout.addWidget(card)
        return outer

    # ── PAGE: BRD Generation ──────────────────────────────────────────────────
    def _build_brd_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addWidget(self._label("BRD Generation", 22, bold=True))

        options_card = QFrame()
        options_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(24, 20, 24, 20)
        options_layout.setSpacing(12)
        options_layout.addWidget(self._label("Generation Options", 14, bold=True))

        cb_style = "QCheckBox { font-size: 13px; color: #3a4554; spacing: 8px; }"
        self.include_conflicts_cb = QCheckBox("Include Conflict Analysis")
        self.include_conflicts_cb.setChecked(True)
        self.include_conflicts_cb.setStyleSheet(cb_style)
        self.include_traceability_cb = QCheckBox("Include Traceability Matrix")
        self.include_traceability_cb.setChecked(True)
        self.include_traceability_cb.setStyleSheet(cb_style)
        self.include_sentiment_cb = QCheckBox("Include Sentiment Analysis")
        self.include_sentiment_cb.setChecked(True)
        self.include_sentiment_cb.setStyleSheet(cb_style)

        options_layout.addWidget(self.include_conflicts_cb)
        options_layout.addWidget(self.include_traceability_cb)
        options_layout.addWidget(self.include_sentiment_cb)

        gen_btn = QPushButton("Generate BRD")
        gen_btn.setFixedHeight(44)
        gen_btn.setCursor(Qt.PointingHandCursor)
        gen_btn.setStyleSheet(BTN_PRIMARY.replace("border-radius: 8px", "border-radius: 10px"))
        gen_btn.clicked.connect(self._generate_brd)
        options_layout.addWidget(gen_btn)
        layout.addWidget(options_card)

        list_card = QFrame()
        list_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(24, 20, 24, 20)
        list_layout.setSpacing(12)
        list_layout.addWidget(self._label("Generated BRDs", 14, bold=True))

        self.brd_list = QListWidget()
        self.brd_list.setStyleSheet("""
            QListWidget { border: 1px solid #e0e4ea; border-radius: 8px;
                background: #fafbfc; padding: 4px; font-size: 13px; }
            QListWidget::item:selected { background: #eef5f1; color: #1a2332; border-radius: 6px; }
            QListWidget::item:hover { background: #f4f8f6; border-radius: 6px; }
        """)
        self.brd_list.setMinimumHeight(140)
        self.brd_list.itemClicked.connect(self._select_brd)
        list_layout.addWidget(self.brd_list)

        btn_row = QHBoxLayout()
        for label, slot in [("View", self._view_brd), ("Edit", self._edit_brd), ("Download", self._download_brd)]:
            b = QPushButton(label)
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(BTN_SECONDARY)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        list_layout.addLayout(btn_row)
        layout.addWidget(list_card)
        return outer

    # ── PAGE: Analysis ────────────────────────────────────────────────────────
    def _build_analysis_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addWidget(self._label("Analysis", 22, bold=True))

        conflicts_card = QFrame()
        conflicts_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        c_layout = QVBoxLayout(conflicts_card)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(12)
        c_layout.addWidget(self._label("Conflict Detection", 14, bold=True))

        detect_btn = QPushButton("Detect Conflicts")
        detect_btn.setFixedHeight(38)
        detect_btn.setFixedWidth(160)
        detect_btn.setCursor(Qt.PointingHandCursor)
        detect_btn.setStyleSheet(BTN_PRIMARY)
        detect_btn.clicked.connect(self._detect_conflicts)
        c_layout.addWidget(detect_btn)

        self.conflicts_table = self._styled_table(["Type", "Description", "Severity", "Status"])
        c_layout.addWidget(self.conflicts_table)
        layout.addWidget(conflicts_card)

        dashboard_card = QFrame()
        dashboard_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        d_layout = QVBoxLayout(dashboard_card)
        d_layout.setContentsMargins(24, 20, 24, 20)
        d_layout.setSpacing(12)
        d_layout.addWidget(self._label("Project Dashboard", 14, bold=True))

        self.dashboard_text = QTextEdit()
        self.dashboard_text.setReadOnly(True)
        self.dashboard_text.setFixedHeight(160)
        self.dashboard_text.setStyleSheet("""
            QTextEdit { border: 1px solid #e0e4ea; border-radius: 8px;
                padding: 10px; font-size: 13px; background: #fafbfc; color: #3a4554; }
        """)
        d_layout.addWidget(self.dashboard_text)
        layout.addWidget(dashboard_card)
        layout.addStretch()
        return outer

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _label(self, text, size=13, bold=False, color="#1a2332"):
        lbl = QLabel(text)
        weight = "700" if bold else "400"
        lbl.setStyleSheet(f"font-size: {size}px; font-weight: {weight}; color: {color};")
        lbl.setWordWrap(True)
        return lbl

    def _line_edit(self, placeholder):
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setFixedHeight(38)
        le.setStyleSheet(INPUT_STYLE)
        return le

    def _styled_table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setStyleSheet("""
            QTableWidget { border: 1px solid #e0e4ea; border-radius: 8px;
                background: #fafbfc; alternate-background-color: #f4f6f9;
                gridline-color: transparent; font-size: 13px; color: #3a4554; }
            QHeaderView::section { background: #f0f2f5; color: #8a95a3;
                font-size: 11px; font-weight: 600; border: none; padding: 8px 12px; }
            QTableWidget::item { padding: 8px 12px; }
            QTableWidget::item:selected { background: #eef5f1; color: #1a2332; }
        """)
        table.setMinimumHeight(200)
        return table

    # ── ACTIONS: Projects ─────────────────────────────────────────────────────
    def _create_project(self):
        name = self.project_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Field", "Please enter a project name")
            return
        try:
            r = requests.post(f"{self.api_base_url}/projects/",
                              json={"name": name, "description": self.project_desc_input.text().strip()})
            if r.status_code == 201:
                QMessageBox.information(self, "Success", "Project created")
                self.project_name_input.clear()
                self.project_desc_input.clear()
                self._load_projects()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _load_projects(self):
        try:
            r = requests.get(f"{self.api_base_url}/projects/", timeout=10)
            if r.status_code == 200:
                data = r.json()
                projects = data.get("results", []) if isinstance(data, dict) else data
                for i in reversed(range(self.cards_grid.count())):
                    w = self.cards_grid.itemAt(i).widget()
                    if w:
                        w.deleteLater()
                for idx, project in enumerate(projects):
                    card = ClickableCard(project)
                    card.clicked.connect(self._select_project)
                    row, col = divmod(idx, 2)
                    self.cards_grid.addWidget(card, row, col)
                self.status_label.setText(f"Loaded {len(projects)} projects")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _select_project(self, project_data):
        self.current_project = project_data
        self.status_label.setText(f"▶ {project_data['name']}")
        self._load_data_sources()
        self._load_requirements()
        self._load_brds()

    def _export_project_zip(self):
        """Download the entire project as a ZIP (BRDs + sources summary)."""
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project ZIP",
            f"Project_{self.current_project['name'].replace(' ', '_')}.zip",
            "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        try:
            import zipfile, json, io

            # Fetch all project data
            pid = self.current_project["id"]
            brds_r = requests.get(f"{self.api_base_url}/brd-documents/", params={"project": pid}, timeout=15)
            reqs_r = requests.get(f"{self.api_base_url}/requirements/", params={"project_id": pid}, timeout=15)
            sources_r = requests.get(f"{self.api_base_url}/data-sources/", params={"project": pid}, timeout=15)

            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Project metadata
                zf.writestr("project.json", json.dumps(self.current_project, indent=2))

                # Requirements JSON
                if reqs_r.status_code == 200:
                    reqs = reqs_r.json()
                    reqs_list = reqs.get("results", reqs) if isinstance(reqs, dict) else reqs
                    zf.writestr("requirements.json", json.dumps(reqs_list, indent=2))

                # Data sources summary JSON
                if sources_r.status_code == 200:
                    src = sources_r.json()
                    src_list = src.get("results", src) if isinstance(src, dict) else src
                    zf.writestr("data_sources.json", json.dumps(src_list, indent=2))

                # Each BRD: download the .docx and embed it
                if brds_r.status_code == 200:
                    brds = brds_r.json()
                    brd_list = brds.get("results", brds) if isinstance(brds, dict) else brds
                    zf.writestr("brd_index.json", json.dumps(brd_list, indent=2))
                    for brd in brd_list:
                        try:
                            doc_r = requests.get(
                                f"{self.api_base_url}/brd-documents/{brd['id']}/download/",
                                stream=True, timeout=30
                            )
                            if doc_r.status_code == 200:
                                fname = f"BRD_{brd['id']}_v{brd.get('version', 1)}.docx"
                                zf.writestr(fname, doc_r.content)
                        except Exception:
                            pass

            QMessageBox.information(self, "Exported", f"Project saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ── ACTIONS: Dataset ──────────────────────────────────────────────────────
    def _load_dataset(self):
        project_name = self.ds_project_input.text().strip() or "Enron Dataset Project"
        csv_filename  = self.ds_csv_input.text().strip() or "emails.csv"
        product_topic = self.ds_topic_input.text().strip() or None
        try:
            limit = int(self.ds_limit_input.text().strip())
        except ValueError:
            limit = 300

        payload = {
            "project_name": project_name,
            "csv_filename": csv_filename,
            "limit": limit,
        }
        if product_topic:
            payload["product_topic"] = product_topic

        self.ds_progress_bar.setVisible(True)
        self.ds_status_label.setText("Starting dataset load…")

        self._loader_worker = DatasetLoaderWorker(self.api_base_url, payload)
        self._loader_worker.progress.connect(self._on_dataset_progress)
        self._loader_worker.finished.connect(self._on_dataset_done)
        self._loader_worker.error.connect(self._on_dataset_error)
        self._loader_worker.start()

    def _on_dataset_progress(self, data):
        self.ds_status_label.setText(
            f"Processing… rows: {data.get('total',0)} | "
            f"imported: {data.get('imported',0)} | "
            f"requirements: {data.get('requirements',0)} | "
            f"skipped: {data.get('skipped',0)}"
        )

    def _on_dataset_done(self, data):
        self.ds_progress_bar.setVisible(False)
        if data.get("error"):
            QMessageBox.critical(self, "Dataset Error", data["error"])
            self.ds_status_label.setText(f"Error: {data['error']}")
        else:
            self.ds_status_label.setText(
                f"Done! Imported {data.get('imported',0)} emails → "
                f"{data.get('requirements',0)} requirements extracted. "
                f"Project ID: {data.get('project_id','?')}"
            )
            QMessageBox.information(self, "Dataset Loaded",
                f"Successfully loaded {data.get('imported',0)} emails.\n"
                f"Requirements extracted: {data.get('requirements',0)}\n\n"
                f"Go to Projects and select '{self.ds_project_input.text()}' to generate a BRD."
            )
            self._load_projects()

    def _on_dataset_error(self, msg):
        self.ds_progress_bar.setVisible(False)
        self.ds_status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Dataset Load Error", msg)

    # ── ACTIONS: Data Sources ─────────────────────────────────────────────────
    def _sync_gmail(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        payload = {"sync_gmail": True, "gmail_query": self.gmail_query_input.text()}
        topic = self.sync_topic_input.text().strip()
        if topic:
            payload["product_topic"] = topic
        try:
            r = requests.post(f"{self.api_base_url}/projects/{self.current_project['id']}/sync_data_sources/", json=payload)
            if r.status_code == 200:
                QMessageBox.information(self, "Success", "Gmail synced")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _sync_slack(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        channel = self.slack_channel_input.text().strip()
        if not channel:
            QMessageBox.warning(self, "Error", "Enter a Slack channel ID"); return

        payload = {"sync_slack": True, "slack_channel": channel, "days": 30}

        # Multi-product splitting takes priority over single topic filter
        multi = self.multi_product_input.text().strip()
        if multi:
            products = [p.strip() for p in multi.split(",") if p.strip()]
            payload["all_products"] = products
        else:
            topic = self.sync_topic_input.text().strip()
            if topic:
                payload["product_topic"] = topic

        try:
            r = requests.post(f"{self.api_base_url}/projects/{self.current_project['id']}/sync_data_sources/", json=payload)
            if r.status_code == 200:
                QMessageBox.information(self, "Success", "Slack synced")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _upload_document(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "Text Files (*.txt);;All Files (*.*)")
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    r = requests.post(f"{self.api_base_url}/data-sources/upload_document/",
                                      data={"project_id": self.current_project["id"]}, files={"file": f})
                if r.status_code == 200:
                    QMessageBox.information(self, "Success", "Document uploaded")
                    self._load_data_sources()
                else:
                    QMessageBox.warning(self, "Error", r.text)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _load_data_sources(self):
        if not self.current_project: return
        try:
            r = requests.get(f"{self.api_base_url}/data-sources/",
                             params={"project": self.current_project["id"]}, timeout=10)
            r.raise_for_status()
            data = r.json()
            sources = data.get("results", data) if isinstance(data, dict) else data
            self.sources_table.setRowCount(len(sources))
            for row, source in enumerate(sources):
                self.sources_table.setItem(row, 0, QTableWidgetItem(str(source.get("source_type", ""))))
                self.sources_table.setItem(row, 1, QTableWidgetItem(str(source.get("source_identifier", ""))[:50]))
                self.sources_table.setItem(row, 2, QTableWidgetItem("Yes" if source.get("is_relevant") else "No"))
                self.sources_table.setItem(row, 3, QTableWidgetItem(f"{source.get('relevance_score', 0):.2f}"))
                self.sources_table.setItem(row, 4, QTableWidgetItem(str(source.get("created_at", ""))[:10]))
        except Exception as e:
            print(f"Error loading sources: {e}")

    def _process_sources(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        payload = {"project_id": self.current_project["id"]}
        topic = self.sync_topic_input.text().strip()
        if topic:
            payload["product_topic"] = topic
        try:
            r = requests.post(f"{self.api_base_url}/data-sources/process_sources/", json=payload)
            if r.status_code == 200:
                result = r.json()
                QMessageBox.information(self, "Success",
                    f"Requirements extracted: {result.get('requirements_found', '?')}")
                self._load_requirements()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── ACTIONS: Requirements ─────────────────────────────────────────────────
    def _load_requirements(self):
        if not self.current_project: return
        try:
            r = requests.get(f"{self.api_base_url}/requirements/",
                             params={"project_id": self.current_project["id"]}, timeout=10)
            r.raise_for_status()
            data = r.json()
            reqs = data.get("results", data) if isinstance(data, dict) else data
            self.requirements_table.setRowCount(len(reqs))
            for row, req in enumerate(reqs):
                self.requirements_table.setItem(row, 0, QTableWidgetItem(str(req.get("title", ""))[:50]))
                self.requirements_table.setItem(row, 1, QTableWidgetItem(str(req.get("requirement_type", ""))))
                self.requirements_table.setItem(row, 2, QTableWidgetItem(str(req.get("priority", ""))))
                self.requirements_table.setItem(row, 3, QTableWidgetItem(str(req.get("stakeholder", ""))))
                self.requirements_table.setItem(row, 4, QTableWidgetItem(f"{req.get('confidence_score', 0):.2f}"))
                self.requirements_table.setItem(row, 5, QTableWidgetItem(str(req.get("data_source_type", ""))))
        except Exception as e:
            print(f"Error loading requirements: {e}")

    # ── ACTIONS: BRD ──────────────────────────────────────────────────────────
    def _generate_brd(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        try:
            r = requests.post(f"{self.api_base_url}/brd-documents/generate/", json={
                "project_id": self.current_project["id"],
                "include_conflicts": self.include_conflicts_cb.isChecked(),
                "include_traceability": self.include_traceability_cb.isChecked(),
                "include_sentiment": self.include_sentiment_cb.isChecked(),
            })
            if r.status_code == 200:
                QMessageBox.information(self, "Success", "BRD generated successfully")
                self._load_brds()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _load_brds(self):
        if not self.current_project: return
        try:
            r = requests.get(f"{self.api_base_url}/brd-documents/",
                             params={"project": self.current_project["id"]}, timeout=10)
            r.raise_for_status()
            data = r.json()
            brds = data.get("results", data) if isinstance(data, dict) else data
            self.brd_list.clear()
            for brd in brds:
                item = QListWidgetItem(
                    f"{brd.get('title','Untitled')}  —  v{brd.get('version',1)}  ({brd.get('status','?')})"
                )
                item.setData(Qt.UserRole, brd)
                self.brd_list.addItem(item)
        except Exception as e:
            print(f"Error loading BRDs: {e}")

    def _select_brd(self, item):
        self.selected_brd = item.data(Qt.UserRole)

    def _view_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Select a BRD first"); return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.selected_brd.get("title", "BRD"))
        dialog.setGeometry(180, 140, 860, 640)
        dialog.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 16)

        browser = QTextEdit()
        browser.setReadOnly(True)
        browser.setStyleSheet("background: white; border-radius: 10px; border: 1px solid #e0e4ea; padding: 16px; font-size: 13px;")
        browser.setHtml(f"""
            <h2>{self.selected_brd.get('title','')}</h2>
            <p><b>Version:</b> {self.selected_brd.get('version','')} &nbsp;|&nbsp; <b>Status:</b> {self.selected_brd.get('status','')}</p>
            <h3>Executive Summary</h3><p>{self.selected_brd.get('executive_summary','')}</p>
            <h3>Business Objectives</h3><p>{self.selected_brd.get('business_objectives','')}</p>
            <h3>Stakeholder Analysis</h3><p>{self.selected_brd.get('stakeholder_analysis','')}</p>
            <h3>Functional Requirements</h3><pre>{self.selected_brd.get('functional_requirements','')}</pre>
            <h3>Non-Functional Requirements</h3><pre>{self.selected_brd.get('non_functional_requirements','')}</pre>
        """)
        layout.addWidget(browser)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(38)
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(BTN_PRIMARY)
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        dialog.exec_()

    def _edit_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Select a BRD first"); return
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit BRD")
        dialog.setGeometry(220, 200, 560, 320)
        dialog.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        section_combo = QComboBox()
        section_combo.addItems([
            "executive_summary", "business_objectives", "stakeholder_analysis",
            "functional_requirements", "non_functional_requirements",
            "assumptions", "success_metrics", "timeline"
        ])
        section_combo.setFixedHeight(38)
        section_combo.setStyleSheet("QComboBox { border: 1px solid #e0e4ea; border-radius: 8px; padding: 0 12px; font-size: 13px; background: white; }")

        instruction_input = QTextEdit()
        instruction_input.setPlaceholderText("e.g. Add more detail about security requirements")
        instruction_input.setFixedHeight(90)
        instruction_input.setStyleSheet(INPUT_STYLE)

        layout.addWidget(self._label("Section to edit:", 13))
        layout.addWidget(section_combo)
        layout.addWidget(self._label("Edit instruction:", 13))
        layout.addWidget(instruction_input)

        btn_row = QHBoxLayout()

        def apply_edit():
            instruction = instruction_input.toPlainText().strip()
            if not instruction:
                QMessageBox.warning(dialog, "Error", "Enter an instruction"); return
            try:
                r = requests.post(
                    f"{self.api_base_url}/brd-documents/{self.selected_brd['id']}/edit/",
                    json={"brd_id": self.selected_brd["id"],
                          "section": section_combo.currentText(),
                          "edit_instruction": instruction}
                )
                if r.status_code == 200:
                    QMessageBox.information(dialog, "Success", "BRD updated")
                    self._load_brds()
                    dialog.close()
                else:
                    QMessageBox.warning(dialog, "Error", r.text)
            except Exception as e:
                QMessageBox.critical(dialog, "Error", str(e))

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedHeight(36)
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(BTN_PRIMARY)
        apply_btn.clicked.connect(apply_edit)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(BTN_SECONDARY)
        cancel_btn.clicked.connect(dialog.close)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _download_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Select a BRD first"); return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save BRD", f"BRD_{self.selected_brd['id']}.docx", "Word Documents (*.docx)")
        if file_path:
            try:
                r = requests.get(
                    f"{self.api_base_url}/brd-documents/{self.selected_brd['id']}/download/",
                    stream=True)
                if r.status_code == 200:
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    QMessageBox.information(self, "Saved", file_path)
                else:
                    QMessageBox.warning(self, "Error", r.text)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ── ACTIONS: Analysis ─────────────────────────────────────────────────────
    def _detect_conflicts(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Select a project first"); return
        try:
            r = requests.post(f"{self.api_base_url}/conflicts/detect_conflicts/",
                              json={"project_id": self.current_project["id"]})
            if r.status_code == 200:
                QMessageBox.information(self, "Success", r.json()["status"])
                self._load_conflicts()
            else:
                QMessageBox.warning(self, "Error", r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _load_conflicts(self):
        if not self.current_project: return
        try:
            r = requests.get(f"{self.api_base_url}/conflicts/",
                             params={"project": self.current_project["id"]}, timeout=10)
            r.raise_for_status()
            data = r.json()
            conflicts = data.get("results", data) if isinstance(data, dict) else data
            self.conflicts_table.setRowCount(len(conflicts))
            for i, c in enumerate(conflicts):
                self.conflicts_table.setItem(i, 0, QTableWidgetItem(c.get("conflict_type", "")))
                self.conflicts_table.setItem(i, 1, QTableWidgetItem(c.get("description", "")[:100]))
                self.conflicts_table.setItem(i, 2, QTableWidgetItem(c.get("severity", "")))
                self.conflicts_table.setItem(i, 3, QTableWidgetItem("Resolved" if c.get("resolved") else "Pending"))
        except Exception as e:
            print(f"Error loading conflicts: {e}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BRDGeneratorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
