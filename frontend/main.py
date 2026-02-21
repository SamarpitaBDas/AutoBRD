import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import requests
from dotenv import load_dotenv
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize

load_dotenv()


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
            ClickableCard {
                background: white;
                border-radius: 12px;
                border: 1px solid #eef0f3;
            }
            ClickableCard:hover {
                border: 1px solid #c8d0dc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(4)

        title = QLabel(data.get("name", "Untitled"))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        title.setWordWrap(True)

        date_str = data.get("created_at", "")[:10]
        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-size: 11px; color: #8a95a3;")

        desc = QLabel(data.get("description", "")[:60])
        desc.setStyleSheet("font-size: 12px; color: #5a6472;")
        desc.setWordWrap(True)

        status = data.get("status", "draft").capitalize()
        status_colors = {
            "Draft": ("#fff4e5", "#c97d00"),
            "Analysing": ("#e3f2fd", "#1565c0"),
            "Complete": ("#e8f5e9", "#2e7d32"),
        }
        bg, fg = status_colors.get(status, ("#f0f0f0", "#555"))
        badge = QLabel(status)
        badge.setFixedHeight(22)
        badge.setStyleSheet(f"""
            background: {bg};
            color: {fg};
            border-radius: 11px;
            padding: 0 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        badge.setAlignment(Qt.AlignCenter)
        badge.setMaximumWidth(90)

        layout.addWidget(title)
        layout.addWidget(date_label)
        layout.addWidget(desc)
        layout.addStretch()
        layout.addWidget(badge)

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
            QPushButton {
                text-align: left;
                padding-left: 20px;
                color: #9ba8b5;
                font-size: 13px;
                font-weight: 500;
                border: none;
                border-radius: 0;
                background: transparent;
            }
            QPushButton:checked {
                background: #4a7c65;
                color: white;
            }
            QPushButton:hover:!checked {
                color: #dce4ed;
                background: rgba(255,255,255,0.05);
            }
        """)


class BRDGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        #TO:DO add backend
        #expected URL
        #- projects	"http://127.0.0.1:8000/api/projects/"
        # - data-sources	"http://127.0.0.1:8000/api/data-sources/"
        # - requirements	"http://127.0.0.1:8000/api/requirements/"
        # - brd-documents	"http://127.0.0.1:8000/api/brd-documents/"
        # - conflicts	"http://127.0.0.1:8000/api/conflicts/"
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api")
        self.current_project = None
        self.selected_brd = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("BRD Generator Pro")
        self.setGeometry(100, 80, 1200, 820)
        self.setStyleSheet("background: #f0f2f5;")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: #f0f2f5;")
        root_layout.addWidget(self.content_stack)

        self.pages = {
            "Projects": self._build_projects_page(),
            "Data Sources": self._build_data_sources_page(),
            "Requirements": self._build_requirements_page(),
            "BRD Generation": self._build_brd_page(),
            "Analysis": self._build_analysis_page(),
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
        page_labels = ["Projects", "Projects", "Data Sources", "Requirements", "BRD Generation", "Analysis"]

        seen = set()
        unique_nav = []
        for icon, label in nav_items:
            if label not in seen:
                seen.add(label)
                unique_nav.append((icon, label))

        for icon, label in unique_nav:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, l=label: self._switch_page(l))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)

        layout.addStretch()

        self.status_label = QLabel("Loaded 0 projects • Last updated just now")
        self.status_label.setStyleSheet("color: #5a6e7f; font-size: 10px; padding: 0 16px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addSpacing(16)

        return sidebar

    def _switch_page(self, label):
        for btn in self.nav_buttons:
            btn.setChecked(btn.text().strip().endswith(label))
        page = self.pages.get(label)
        if page:
            self.content_stack.setCurrentWidget(page)

    def _scroll_area_wrap(self, inner_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        scroll.setWidget(inner_widget)
        return scroll

    def _build_projects_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(32, 28, 32, 28)
        outer_layout.setSpacing(24)

        top_bar = QHBoxLayout()
        page_title = QLabel("Projects")
        page_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        top_bar.addWidget(page_title)
        top_bar.addStretch()

        user_btn = QPushButton()
        user_btn.setIcon(QIcon("assets/user.svg"))
        user_btn.setIconSize(QSize(24, 24))
        user_btn.setFixedSize(36, 36)
        user_btn.setStyleSheet("border: 1px solid #dde2e8; border-radius: 18px; background: white; font-size: 14px;")
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon("assets/settings.svg"))
        settings_btn.setIconSize(QSize(24, 24))
        settings_btn.setFixedSize(36, 36)
        settings_btn.setStyleSheet("border: 1px solid #dde2e8; border-radius: 18px; background: white; font-size: 14px;")
        top_bar.addWidget(user_btn)
        top_bar.addWidget(settings_btn)
        outer_layout.addLayout(top_bar)

        create_card = QFrame()
        create_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        create_layout = QVBoxLayout(create_card)
        create_layout.setContentsMargins(24, 20, 24, 20)
        create_layout.setSpacing(12)

        create_title = QLabel("Create New Project")
        create_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #1a2332;")
        create_layout.addWidget(create_title)

        name_row = QHBoxLayout()
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Project Name")
        self.project_name_input.setFixedHeight(42)
        self.project_name_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 13px;
                color: #1a2332;
                background: #fafbfc;
            }
            QLineEdit:focus { border-color: #4a7c65; }
        """)

        create_btn = QPushButton("Create Project")
        create_btn.setFixedHeight(42)
        create_btn.setFixedWidth(140)
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 21px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        create_btn.clicked.connect(self._create_project)

        name_row.addWidget(self.project_name_input)
        name_row.addWidget(create_btn)
        create_layout.addLayout(name_row)

        self.project_desc_input = QLineEdit()
        self.project_desc_input.setPlaceholderText("Description")
        self.project_desc_input.setFixedHeight(42)
        self.project_desc_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 13px;
                color: #1a2332;
                background: #fafbfc;
            }
            QLineEdit:focus { border-color: #4a7c65; }
        """)
        create_layout.addWidget(self.project_desc_input)

        ai_label = QLabel("Description (AI-Assisted)")
        ai_label.setStyleSheet("font-size: 11px; color: #8a95a3;")
        create_layout.addWidget(ai_label)

        self.ai_desc_input = QTextEdit()
        self.ai_desc_input.setPlaceholderText("AI-generated description will appear here...")
        self.ai_desc_input.setFixedHeight(80)
        self.ai_desc_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: #1a2332;
                background: #fafbfc;
            }
            QTextEdit:focus { border-color: #4a7c65; }
        """)
        create_layout.addWidget(self.ai_desc_input)

        outer_layout.addWidget(create_card)

        existing_title = QLabel("Existing Projects")
        existing_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #1a2332;")
        outer_layout.addWidget(existing_title)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(16)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.cards_container)

        refresh_btn = QPushButton("Refresh Projects")
        refresh_btn.setFixedHeight(40)
        refresh_btn.setFixedWidth(160)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        refresh_btn.clicked.connect(self._load_projects)
        outer_layout.addWidget(refresh_btn)
        outer_layout.addStretch()

        return outer

    def _build_data_sources_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        title = QLabel("Data Sources")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        layout.addWidget(title)

        sync_card = QFrame()
        sync_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        sync_layout = QVBoxLayout(sync_card)
        sync_layout.setContentsMargins(24, 20, 24, 20)
        sync_layout.setSpacing(12)

        sync_title = QLabel("Sync Data Sources")
        sync_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        sync_layout.addWidget(sync_title)

        def _row(placeholder, btn_text, slot):
            row = QHBoxLayout()
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setFixedHeight(38)
            field.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #e0e4ea;
                    border-radius: 8px;
                    padding: 0 12px;
                    font-size: 13px;
                    background: #fafbfc;
                }
            """)
            btn = QPushButton(btn_text)
            btn.setFixedHeight(38)
            btn.setFixedWidth(120)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #4a7c65;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover { background: #3d6b56; }
            """)
            btn.clicked.connect(slot)
            row.addWidget(field)
            row.addWidget(btn)
            return row, field

        gmail_row, self.gmail_query_input = _row("Gmail query: subject:requirements after:2024/01/01", "Sync Gmail", self._sync_gmail)
        slack_row, self.slack_channel_input = _row("Slack channel ID: C01234567", "Sync Slack", self._sync_slack)
        sync_layout.addLayout(gmail_row)
        sync_layout.addLayout(slack_row)

        upload_btn = QPushButton("Upload Document")
        upload_btn.setFixedHeight(38)
        upload_btn.setFixedWidth(160)
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setStyleSheet("""
            QPushButton {
                background: #eef5f1;
                color: #4a7c65;
                border: 1px solid #c6ddd3;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #d9ede4; }
        """)
        upload_btn.clicked.connect(self._upload_document)
        sync_layout.addWidget(upload_btn)

        layout.addWidget(sync_card)

        table_card = QFrame()
        table_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(24, 20, 24, 20)
        table_layout.setSpacing(12)

        table_title = QLabel("Sources")
        table_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        table_layout.addWidget(table_title)

        self.sources_table = self._styled_table(["Type", "Identifier", "Relevant", "Score", "Date"])
        table_layout.addWidget(self.sources_table)

        process_btn = QPushButton("Process Sources & Extract Requirements")
        process_btn.setFixedHeight(40)
        process_btn.setCursor(Qt.PointingHandCursor)
        process_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        process_btn.clicked.connect(self._process_sources)
        table_layout.addWidget(process_btn)

        layout.addWidget(table_card)
        return outer

    def _build_requirements_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        title = QLabel("Requirements")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        layout.addWidget(title)

        card = QFrame()
        card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        self.requirements_table = self._styled_table(["Title", "Type", "Priority", "Stakeholder", "Confidence", "Source"])
        card_layout.addWidget(self.requirements_table)

        refresh_btn = QPushButton("Refresh Requirements")
        refresh_btn.setFixedHeight(38)
        refresh_btn.setFixedWidth(180)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        refresh_btn.clicked.connect(self._load_requirements)
        card_layout.addWidget(refresh_btn)

        layout.addWidget(card)
        return outer

    def _build_brd_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        title = QLabel("BRD Generation")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        layout.addWidget(title)

        options_card = QFrame()
        options_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(24, 20, 24, 20)
        options_layout.setSpacing(12)

        opt_title = QLabel("Generation Options")
        opt_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        options_layout.addWidget(opt_title)

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
        gen_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        gen_btn.clicked.connect(self._generate_brd)
        options_layout.addWidget(gen_btn)
        layout.addWidget(options_card)

        list_card = QFrame()
        list_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(24, 20, 24, 20)
        list_layout.setSpacing(12)

        list_title = QLabel("Generated BRDs")
        list_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        list_layout.addWidget(list_title)

        self.brd_list = QListWidget()
        self.brd_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                background: #fafbfc;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background: #eef5f1;
                color: #1a2332;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: #f4f8f6;
                border-radius: 6px;
            }
        """)
        self.brd_list.setMinimumHeight(140)
        self.brd_list.itemClicked.connect(self._select_brd)
        list_layout.addWidget(self.brd_list)

        btn_row = QHBoxLayout()
        for label, slot in [("View", self._view_brd), ("Edit", self._edit_brd), ("Download", self._download_brd)]:
            b = QPushButton(label)
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #eef5f1;
                    color: #3d6b56;
                    border: 1px solid #c6ddd3;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover { background: #d9ede4; }
            """)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        list_layout.addLayout(btn_row)
        layout.addWidget(list_card)
        return outer

    def _build_analysis_page(self):
        outer = QWidget()
        outer.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        title = QLabel("Analysis")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2332;")
        layout.addWidget(title)

        conflicts_card = QFrame()
        conflicts_card.setStyleSheet("background: white; border-radius: 14px; border: 1px solid #eef0f3;")
        c_layout = QVBoxLayout(conflicts_card)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(12)

        c_title = QLabel("Conflict Detection")
        c_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        c_layout.addWidget(c_title)

        detect_btn = QPushButton("Detect Conflicts")
        detect_btn.setFixedHeight(38)
        detect_btn.setFixedWidth(160)
        detect_btn.setCursor(Qt.PointingHandCursor)
        detect_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
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

        d_title = QLabel("Project Dashboard")
        d_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1a2332;")
        d_layout.addWidget(d_title)

        self.dashboard_text = QTextEdit()
        self.dashboard_text.setReadOnly(True)
        self.dashboard_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                background: #fafbfc;
                color: #3a4554;
            }
        """)
        self.dashboard_text.setFixedHeight(160)
        d_layout.addWidget(self.dashboard_text)
        layout.addWidget(dashboard_card)
        layout.addStretch()

        return outer

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
            QTableWidget {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                background: #fafbfc;
                alternate-background-color: #f4f6f9;
                gridline-color: transparent;
                font-size: 13px;
                color: #3a4554;
            }
            QHeaderView::section {
                background: #f0f2f5;
                color: #8a95a3;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                border: none;
                padding: 8px 12px;
            }
            QTableWidget::item {
                padding: 8px 12px;
            }
            QTableWidget::item:selected {
                background: #eef5f1;
                color: #1a2332;
            }
        """)
        table.setMinimumHeight(200)
        return table

    def _create_project(self):
        name = self.project_name_input.text().strip()
        description = self.project_desc_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing Field", "Please enter a project name")
            return

        try:
            response = requests.post(
                f"{self.api_base_url}/projects/",
                json={"name": name, "description": description}
            )
            if response.status_code == 201:
                QMessageBox.information(self, "Success", "Project created successfully")
                self.project_name_input.clear()
                self.project_desc_input.clear()
                self._load_projects()
            else:
                QMessageBox.warning(self, "Error", f"Failed to create project: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")

    def _load_projects(self):
        try:
            response = requests.get(f"{self.api_base_url}/projects/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                projects = data.get("results", []) if isinstance(data, dict) else data

                for i in reversed(range(self.cards_grid.count())):
                    self.cards_grid.itemAt(i).widget().deleteLater()

                for idx, project in enumerate(projects):
                    card = ClickableCard(project)
                    card.clicked.connect(self._select_project)
                    row, col = divmod(idx, 2)
                    self.cards_grid.addWidget(card, row, col)

                self.status_label.setText(f"Loaded {len(projects)} projects • Last updated just now")
            else:
                QMessageBox.warning(self, "Error", f"Failed to load projects (Status {response.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load projects:\n{str(e)}")

    def _select_project(self, project_data):
        self.current_project = project_data
        self.status_label.setText(f"Selected: {project_data['name']}")
        self._load_data_sources()
        self._load_requirements()
        self._load_brds()

    def _sync_gmail(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        query = self.gmail_query_input.text()
        try:
            response = requests.post(
                f"{self.api_base_url}/projects/{self.current_project['id']}/sync_data_sources/",
                json={"sync_gmail": True, "gmail_query": query}
            )
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Gmail synced successfully")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "Error", f"Failed to sync: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sync error: {str(e)}")

    def _sync_slack(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        channel = self.slack_channel_input.text()
        if not channel:
            QMessageBox.warning(self, "Error", "Please enter a Slack channel")
            return
        try:
            response = requests.post(
                f"{self.api_base_url}/projects/{self.current_project['id']}/sync_data_sources/",
                json={"sync_slack": True, "slack_channel": channel, "days": 30}
            )
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Slack synced successfully")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "Error", f"Failed to sync: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sync error: {str(e)}")

    def _upload_document(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "Text Files (*.txt);;All Files (*.*)")
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        f"{self.api_base_url}/data-sources/upload_document/",
                        data={"project_id": self.current_project["id"]},
                        files={"file": f}
                    )
                if response.status_code == 200:
                    QMessageBox.information(self, "Success", "Document uploaded successfully")
                    self._load_data_sources()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to upload: {response.text}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Upload error: {str(e)}")

    def _load_data_sources(self):
        if not self.current_project:
            return
        try:
            response = requests.get(
                f"{self.api_base_url}/data-sources/",
                params={"project": self.current_project["id"]},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            sources = data.get("results") or data.get("data") or [] if isinstance(data, dict) else data

            self.sources_table.setRowCount(len(sources))
            for row, source in enumerate(sources):
                self.sources_table.setItem(row, 0, QTableWidgetItem(str(source.get("source_type", ""))))
                self.sources_table.setItem(row, 1, QTableWidgetItem(str(source.get("source_identifier", ""))[:50]))
                self.sources_table.setItem(row, 2, QTableWidgetItem("Yes" if source.get("is_relevant") else "No"))
                self.sources_table.setItem(row, 3, QTableWidgetItem(f"{source.get('relevance_score', 0):.2f}"))
                self.sources_table.setItem(row, 4, QTableWidgetItem(str(source.get("created_at", ""))[:10]))
        except Exception as e:
            print(f"Error loading data sources: {e}")

    def _process_sources(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        try:
            response = requests.post(
                f"{self.api_base_url}/data-sources/process_sources/",
                json={"project_id": self.current_project["id"]}
            )
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Requirements extracted successfully")
                self._load_requirements()
            else:
                QMessageBox.warning(self, "Error", f"Failed to process: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Processing error: {str(e)}")

    def _load_requirements(self):
        if not self.current_project:
            return
        try:
            response = requests.get(
                f"{self.api_base_url}/requirements/",
                params={"project_id": self.current_project["id"]},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            requirements = data.get("results") or data.get("data") or [] if isinstance(data, dict) else data

            self.requirements_table.setRowCount(len(requirements))
            for row, req in enumerate(requirements):
                self.requirements_table.setItem(row, 0, QTableWidgetItem(str(req.get("title", ""))[:50]))
                self.requirements_table.setItem(row, 1, QTableWidgetItem(str(req.get("requirement_type", ""))))
                self.requirements_table.setItem(row, 2, QTableWidgetItem(str(req.get("priority", ""))))
                self.requirements_table.setItem(row, 3, QTableWidgetItem(str(req.get("stakeholder", ""))))
                self.requirements_table.setItem(row, 4, QTableWidgetItem(f"{req.get('confidence_score', 0):.2f}"))
                self.requirements_table.setItem(row, 5, QTableWidgetItem(str(req.get("data_source_type", ""))))
        except Exception as e:
            print(f"Error loading requirements: {e}")

    def _generate_brd(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        try:
            response = requests.post(
                f"{self.api_base_url}/brd-documents/generate/",
                json={
                    "project_id": self.current_project["id"],
                    "include_conflicts": self.include_conflicts_cb.isChecked(),
                    "include_traceability": self.include_traceability_cb.isChecked(),
                    "include_sentiment": self.include_sentiment_cb.isChecked(),
                }
            )
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "BRD generated successfully")
                self._load_brds()
            else:
                QMessageBox.warning(self, "Error", f"Failed to generate: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation error: {str(e)}")

    def _load_brds(self):
        if not self.current_project:
            return
        try:
            response = requests.get(
                f"{self.api_base_url}/brd-documents/",
                params={"project": self.current_project["id"]},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            brds = data.get("results") or data.get("data") or [] if isinstance(data, dict) else data

            self.brd_list.clear()
            for brd in brds:
                title = brd.get("title", "Untitled")
                version = brd.get("version", "1.0")
                status = brd.get("status", "unknown")
                item = QListWidgetItem(f"{title}  —  v{version}  ({status})")
                item.setData(Qt.UserRole, brd)
                self.brd_list.addItem(item)
        except Exception as e:
            print(f"Error loading BRDs: {e}")

    def _select_brd(self, item):
        self.selected_brd = item.data(Qt.UserRole)

    def _view_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Please select a BRD first")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.selected_brd.get("title", "BRD"))
        dialog.setGeometry(180, 140, 820, 620)
        dialog.setStyleSheet("background: #f0f2f5;")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 16)

        browser = QTextEdit()
        browser.setReadOnly(True)
        browser.setStyleSheet("background: white; border-radius: 10px; border: 1px solid #e0e4ea; padding: 16px; font-size: 13px;")
        browser.setHtml(f"""
            <h2>{self.selected_brd.get('title', '')}</h2>
            <p><b>Version:</b> {self.selected_brd.get('version', '')} &nbsp;|&nbsp; <b>Status:</b> {self.selected_brd.get('status', '')}</p>
            <h3>Executive Summary</h3><p>{self.selected_brd.get('executive_summary', '')}</p>
            <h3>Business Objectives</h3><p>{self.selected_brd.get('business_objectives', '')}</p>
            <h3>Stakeholder Analysis</h3><p>{self.selected_brd.get('stakeholder_analysis', '')}</p>
            <h3>Functional Requirements</h3><pre>{self.selected_brd.get('functional_requirements', '')}</pre>
            <h3>Non-Functional Requirements</h3><pre>{self.selected_brd.get('non_functional_requirements', '')}</pre>
        """)
        layout.addWidget(browser)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(38)
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        dialog.exec_()

    def _edit_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Please select a BRD first")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit BRD")
        dialog.setGeometry(220, 200, 560, 320)
        dialog.setStyleSheet("background: #f0f2f5;")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        section_label = QLabel("Section to edit:")
        section_label.setStyleSheet("font-size: 13px; color: #3a4554;")
        layout.addWidget(section_label)

        section_combo = QComboBox()
        section_combo.addItems([
            "executive_summary", "business_objectives", "stakeholder_analysis",
            "functional_requirements", "non_functional_requirements",
            "assumptions", "success_metrics", "timeline"
        ])
        section_combo.setFixedHeight(38)
        section_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                background: white;
            }
        """)
        layout.addWidget(section_combo)

        instr_label = QLabel("Edit instruction:")
        instr_label.setStyleSheet("font-size: 13px; color: #3a4554;")
        layout.addWidget(instr_label)

        instruction_input = QTextEdit()
        instruction_input.setPlaceholderText("e.g. Add more detail about security requirements")
        instruction_input.setFixedHeight(90)
        instruction_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                background: white;
            }
        """)
        layout.addWidget(instruction_input)

        btn_row = QHBoxLayout()

        def apply_edit():
            instruction = instruction_input.toPlainText().strip()
            if not instruction:
                QMessageBox.warning(dialog, "Error", "Please enter an instruction")
                return
            try:
                response = requests.post(
                    f"{self.api_base_url}/brd-documents/{self.selected_brd['id']}/edit/",
                    json={
                        "brd_id": self.selected_brd["id"],
                        "section": section_combo.currentText(),
                        "edit_instruction": instruction
                    }
                )
                if response.status_code == 200:
                    QMessageBox.information(dialog, "Success", "BRD updated successfully")
                    self._load_brds()
                    dialog.close()
                else:
                    QMessageBox.warning(dialog, "Error", f"Failed to edit: {response.text}")
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Edit error: {str(e)}")

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedHeight(36)
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet("""
            QPushButton {
                background: #4a7c65;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3d6b56; }
        """)
        apply_btn.clicked.connect(apply_edit)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #3a4554;
                border: 1px solid #dde2e8;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background: #f4f6f9; }
        """)
        cancel_btn.clicked.connect(dialog.close)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)
        dialog.exec_()

    def _download_brd(self):
        if not self.selected_brd:
            QMessageBox.warning(self, "Error", "Please select a BRD first")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save BRD", f"BRD_{self.selected_brd['id']}.docx", "Word Documents (*.docx)"
        )
        if file_path:
            try:
                response = requests.get(
                    f"{self.api_base_url}/brd-documents/{self.selected_brd['id']}/download/",
                    stream=True
                )
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    QMessageBox.information(self, "Success", f"Saved to {file_path}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to download: {response.text}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Download error: {str(e)}")

    def _detect_conflicts(self):
        if not self.current_project:
            QMessageBox.warning(self, "Error", "Please select a project first")
            return
        try:
            response = requests.post(
                f"{self.api_base_url}/conflicts/detect_conflicts/",
                json={"project_id": self.current_project["id"]}
            )
            if response.status_code == 200:
                QMessageBox.information(self, "Success", response.json()["status"])
                self._load_conflicts()
            else:
                QMessageBox.warning(self, "Error", f"Failed to detect conflicts: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Detection error: {str(e)}")

    def _load_conflicts(self):
        if not self.current_project:
            return
        try:
            response = requests.get(
                f"{self.api_base_url}/conflicts/",
                params={"project": self.current_project["id"]},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            conflicts = data.get("results") or data.get("data") or [] if isinstance(data, dict) else data

            self.conflicts_table.setRowCount(len(conflicts))
            for i, conflict in enumerate(conflicts):
                self.conflicts_table.setItem(i, 0, QTableWidgetItem(conflict.get("conflict_type", "Unknown")))
                self.conflicts_table.setItem(i, 1, QTableWidgetItem(conflict.get("description", "")[:100]))
                self.conflicts_table.setItem(i, 2, QTableWidgetItem(conflict.get("severity", "low")))
                self.conflicts_table.setItem(i, 3, QTableWidgetItem("Resolved" if conflict.get("resolved") else "Pending"))
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