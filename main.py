import os
import re
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QScrollArea,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# -------------------------------
# Asset locations
# -------------------------------

def app_dir():
    """Folder the app lives in: next to the .exe when frozen, else main.py."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def asset_path(name):
    return os.path.join(app_dir(), "_assets", name)


def find_icon():
    for candidate in (asset_path("icon.ico"), os.path.join(app_dir(), "icon.ico")):
        if os.path.exists(candidate):
            return candidate
    return None


# -------------------------------
# Metric Loading and Text Sizing
# -------------------------------

metrics = {}


def load_metrics():
    filepath = asset_path("strlength.txt")
    try:
        with open(filepath, encoding="utf8") as file:
            for record in file:
                record = record.strip()
                if not record or record.startswith("//"):
                    continue
                segments = record.split(",") if "," in record else record.split(None, 1)
                if len(segments) < 2:
                    continue
                char_symbol = segments[0]
                try:
                    width_value = float(segments[1])
                except Exception:
                    continue
                metrics[char_symbol] = width_value
    except Exception as err:
        print("Error loading metrics file:", err)


def skip_angle_bracket_block(text, start_index):
    """
    If text[start_index] == '<', skip until the next '>' (inclusive).
    The whole <...> block counts as 0 width for calculations.
    Returns the index just after '>' or start_index + 1 if no closing '>' exists.
    """
    end = text.find(">", start_index + 1)
    return end + 1 if end != -1 else start_index + 1


def measure_text(text):
    """
    Special handling:
      - any literal instance of "{n}" counts as width 343.6875
      - any "<...>" wrapped block counts as width 0
    Straight apostrophes are treated as a right single quotation mark for width purposes.
    """
    space_width = metrics.get(" ", 8.671875)
    fallback_digit = 15.0
    total_width = 0.0
    i = 0
    while i < len(text):
        if text[i] == "<":
            i = skip_angle_bracket_block(text, i)
            continue

        if text.startswith("{n}", i):
            total_width += 343.6875
            i += 3
            continue

        ch = text[i]
        if ch == "'":
            ch = "’"
        width = metrics.get(ch)
        if width is None or width == 0:
            width = fallback_digit if ch.isdigit() else space_width
        total_width += width
        i += 1
    return total_width


def find_overflow_index(text, limit_metric):
    """
    Returns the index in text where the cumulative metric exceeds limit_metric.
    Characters from that index onward are considered overflow.
    """
    space_width = metrics.get(" ", 8.671875)
    fallback_digit = 15.0
    total_width = 0.0
    i = 0
    while i < len(text):
        if text[i] == "<":
            i = skip_angle_bracket_block(text, i)
            continue

        if text.startswith("{n}", i):
            increment = 343.6875
            if total_width + increment > limit_metric:
                return i
            total_width += increment
            i += 3
            continue

        ch = text[i]
        if ch == "'":
            ch = "’"
        width = metrics.get(ch)
        if width is None or width == 0:
            width = fallback_digit if ch.isdigit() else space_width
        if total_width + width > limit_metric:
            return i
        total_width += width
        i += 1
    return len(text)


BASE_FONT_SIZE = 54
# Display scale is tied to canvas width: 0.75 at the old 1500px canvas,
# scaled by 1000/1500 for the current one.
TEXT_SCALE = 0.5
DEFAULT_FONT = "FOT-UDKakugoC80 Pro DB"

load_metrics()
base_metric = 650


def compute_font_for_text(text):
    current_metric = measure_text(text)
    if current_metric <= base_metric:
        return BASE_FONT_SIZE, current_metric
    scaled_size = int(BASE_FONT_SIZE * (base_metric / current_metric))
    return max(scaled_size, 1), current_metric


def auto_wrap_content(content):
    """Reflow lines so none exceeds base_metric, preferring to break at spaces."""
    new_lines = []
    for line in content.split("\n"):
        if line == "":
            new_lines.append("")
            continue
        remaining = line
        while remaining:
            cutoff = find_overflow_index(remaining, base_metric)
            if cutoff == 0:
                cutoff = 1  # avoid infinite loop on a single oversized char
            if cutoff < len(remaining):
                bp = remaining.rfind(" ", 0, cutoff)
                if bp > 0:
                    part = remaining[:bp].rstrip()
                    remaining = remaining[bp + 1:]
                else:
                    part = remaining[:cutoff]
                    remaining = remaining[cutoff:]
            else:
                part = remaining
                remaining = ""
            new_lines.append(part)
    return "\n".join(new_lines)


def separator_for_gap(gap_index):
    """Gap 0 (between line 1 and 2) is a Line Break, every later gap is a Scroll Line."""
    return r"\n" if gap_index == 0 else r"\f"


def build_macro(box_texts):
    """Join lines and boxes into the final macro string."""
    box_strings = []
    for text in box_texts:
        lines = text.split("\n")
        result = lines[0] if lines else ""
        for i in range(1, len(lines)):
            result += separator_for_gap(i - 1) + lines[i]
        box_strings.append(result)
    return r"\r".join(box_strings)


def parse_macro(macro):
    """
    Inverse of build_macro: split a macro string into a list of box texts.
    Boxes are separated by \\r; within a box, \\n and \\f both become new lines.
    """
    box_texts = []
    for box in macro.split(r"\r"):
        box_texts.append("\n".join(re.split(r"\\n|\\f", box)))
    return box_texts or [""]


# -------------------------------
# Dark theme
# -------------------------------

DARK_STYLESHEET = """
QWidget {
    background-color: #1b1d23;
    color: #d6d9e0;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #16181d;
}
QTabWidget::pane {
    border: 1px solid #2e323c;
    border-radius: 4px;
    top: -1px;
}
QTabBar::tab {
    background: #232733;
    color: #9aa0ae;
    padding: 6px 16px;
    border: 1px solid #2e323c;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #323848;
    color: #e8eaf0;
}
QTabBar::tab:hover:!selected {
    background: #2a2f3c;
}
QToolButton#tabClose {
    border: none;
    background: transparent;
    color: #9aa0ae;
    font-weight: bold;
    padding: 0px;
}
QToolButton#tabClose:hover {
    color: #e84545;
}
QPushButton {
    background-color: #2c313d;
    border: 1px solid #3c4250;
    border-radius: 4px;
    padding: 6px 14px;
    color: #d6d9e0;
}
QPushButton:hover {
    background-color: #363c4b;
}
QPushButton:pressed {
    background-color: #404757;
}
QPushButton:checked {
    background-color: #3d5a80;
    border-color: #5a7ba6;
    color: #ffffff;
}
QPushButton#danger {
    border-color: #6e3a3a;
    color: #e0b4b4;
}
QPushButton#danger:hover {
    background-color: #4a2e2e;
}
QPlainTextEdit {
    background-color: #14161b;
    border: 1px solid #2e323c;
    border-radius: 4px;
    color: #c9cdd6;
    selection-background-color: #3d5a80;
}
QLabel#sectionHeader {
    color: #8a93a8;
    font-weight: bold;
    letter-spacing: 1px;
}
QLabel#aboutBody {
    color: #c9cdd6;
}
"""

ABOUT_HTML = """
<h2 style="margin-bottom: 2px;">BDSP Message Previewer</h2>
<p>This tool previews how dialogue text renders in Pokémon Brilliant Diamond /
Shining Pearl, using the game's own character-width metrics, and produces the
macro-format string the game expects.</p>

<p><b>It works on one message at a time.</b> A single NPC message can span
several on-screen text boxes — each page (tab) here is one of those boxes.
Compose one complete message, copy its macro, then clear and start the next
one.</p>

<h3>Composing</h3>
<p>Type into a page exactly as it should appear in game. Text that exceeds the
safe width turns <span style="color:#e84545;">red</span>, and the Line Metrics
panel shows each line's calculated length. The preview font shrinks
automatically the way the game shrinks oversized lines. <b>Auto Wrap</b>
reflows your text at word boundaries so no line overflows. Straight
apostrophes (') are converted to the game's typographic apostrophe (\u2019)
as you type.</p>

<h3>Separators (handled for you)</h3>
<p>You never type separators — they're derived from your layout:</p>
<ul>
<li>Line 2 of a page follows a <b>Line Break</b> (\\n)</li>
<li>Every later line in a page follows a <b>Scroll Line</b> (\\f)</li>
<li>Each new page is joined with <b>\\r</b></li>
</ul>

<h3>Importing an existing macro</h3>
<p>The Macro Format panel is editable. Paste an existing macro string into it
and the tool splits it back into pages and lines, so you can inspect or
reformat an old message. Edits flow both ways: typing in a page updates the
macro, and editing the macro rebuilds the pages.</p>

<h3>Output</h3>
<p><b>Copy Macro to Clipboard</b> copies the assembled string —
identical to what the Macro Format panel shows. <b>Clear All</b> resets the
tool to a single empty page for the next message.</p>
"""


# -------------------------------
# Overflow highlighting
# -------------------------------

class OverflowHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.fmt = QTextCharFormat()
        self.fmt.setForeground(QColor("#e84545"))

    def highlightBlock(self, text):
        idx = find_overflow_index(text, base_metric)
        if idx < len(text):
            self.setFormat(idx, len(text) - idx, self.fmt)


# -------------------------------
# About dialog
# -------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About — BDSP Message Previewer")
        self.setFixedSize(580, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        body = QLabel(ABOUT_HTML)
        body.setObjectName("aboutBody")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setContentsMargins(8, 0, 8, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(0)
        scroll.setWidget(body)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# -------------------------------
# Message box page (one per tab)
# -------------------------------

class MessageEdit(QTextEdit):
    """
    QTextEdit that never contains soft line separators (U+2028/U+2029).

    Pasted text and Shift+Enter can introduce these; visually they look like
    new lines, but they keep the text in a single document block, so the
    overflow highlighter would measure all those lines as one long string and
    paint a false red. Normalizing everything to real paragraph breaks keeps
    what the highlighter sees identical to what the metrics measure.
    """

    @staticmethod
    def _normalize(text):
        return (
            text.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\u2028", "\n")
            .replace("\u2029", "\n")
        )

    def insertFromMimeData(self, source):
        self.textCursor().insertText(self._normalize(source.text()))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Shift+Enter would insert U+2028; force a real paragraph break
            self.textCursor().insertText("\n")
            event.accept()
            return
        super().keyPressEvent(event)


class BoxCanvas(QWidget):
    """Draws the textbox background image (or a fallback panel) behind the editor."""

    CANVAS_W = 1000
    CANVAS_H = 300

    # Editor placement inside the textbox graphic — tweak these to line the
    # text area up with your textbox.png artwork.
    TEXT_X = 67
    TEXT_Y = 35
    TEXT_RIGHT_MARGIN = 40    # space reserved right of the text (advance arrow etc.)
    TEXT_BOTTOM_MARGIN = 35

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.CANVAS_W, self.CANVAS_H)
        self.bg = QPixmap(asset_path("textbox.png"))
        if not self.bg.isNull():
            self.bg = self.bg.scaled(
                self.CANVAS_W,
                self.CANVAS_H,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self.editor = MessageEdit(self)
        self.editor.setGeometry(
            self.TEXT_X,
            self.TEXT_Y,
            self.CANVAS_W - self.TEXT_X - self.TEXT_RIGHT_MARGIN,
            self.CANVAS_H - self.TEXT_Y - self.TEXT_BOTTOM_MARGIN,
        )
        self.editor.setFrameStyle(0)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setAcceptRichText(False)
        self.set_editor_font("Arial", int(BASE_FONT_SIZE * TEXT_SCALE))
        self.highlighter = OverflowHighlighter(self.editor.document())

    def set_editor_font(self, family, point_size):
        # Font goes through the stylesheet so the app-wide font-size rule can't override it.
        self.editor.setStyleSheet(
            "QTextEdit { background: transparent; color: #5a5a5a; "
            "selection-background-color: #b9d8f2; border: none; "
            f"font-family: '{family}'; font-size: {point_size}pt; }}"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#16181d"))
        if not self.bg.isNull():
            painter.drawPixmap(0, 0, self.bg)
        else:
            # Fallback: simple BDSP-style dialogue panel
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#f4f4f2"))
            painter.setPen(QColor("#5f9ea0"))
            painter.drawRoundedRect(60, 15, self.CANVAS_W - 120, self.CANVAS_H - 30, 18, 18)
        painter.end()


# -------------------------------
# Main Window
# -------------------------------

class PreviewerWindow(QMainWindow):
    SIDE_PANEL_W = 450

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BDSP Message Previewer")

        self.auto_wrap_enabled = False
        self._updating = False

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        # ============ LEFT COLUMN: tabs, canvas, line info ============
        left = QVBoxLayout()
        left.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_current_tab_changed)
        self.tabs.tabBarClicked.connect(self.on_tab_bar_clicked)

        # "+" pseudo-tab: always last, clicking it creates a new box.
        # Real tabs get a hand-made close button (see _new_page); the "+" gets none.
        self.tabs.addTab(QWidget(), "+")

        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 0, 4)
        corner_layout.setSpacing(6)

        self.auto_wrap_button = QPushButton("Auto Wrap: Off")
        self.auto_wrap_button.setCheckable(True)
        self.auto_wrap_button.toggled.connect(self.toggle_auto_wrap)
        corner_layout.addWidget(self.auto_wrap_button)

        about_btn = QPushButton("About")
        about_btn.clicked.connect(self.show_about)
        corner_layout.addWidget(about_btn)

        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        left.addWidget(self.tabs)

        info_header = QLabel("LINE METRICS")
        info_header.setObjectName("sectionHeader")
        left.addWidget(info_header)

        self.info_box = QPlainTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setFont(QFont("Consolas", 11))
        left.addWidget(self.info_box, stretch=1)

        outer.addLayout(left)

        # ============ RIGHT COLUMN: live previews ============
        right_widget = QWidget()
        right_widget.setFixedWidth(self.SIDE_PANEL_W)
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)

        full_header = QLabel("FULL MESSAGE — read only")
        full_header.setObjectName("sectionHeader")
        right.addWidget(full_header)

        self.full_preview = QPlainTextEdit()
        self.full_preview.setReadOnly(True)
        self.full_preview.setFont(QFont("Consolas", 11))
        right.addWidget(self.full_preview, stretch=3)

        macro_header = QLabel("MACRO FORMAT — paste to import")
        macro_header.setObjectName("sectionHeader")
        right.addWidget(macro_header)

        self.macro_edit = QPlainTextEdit()
        self.macro_edit.setFont(QFont("Consolas", 11))
        self.macro_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.macro_edit.textChanged.connect(self.on_macro_edited)
        right.addWidget(self.macro_edit, stretch=2)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.clear_button = QPushButton("Clear All")
        self.clear_button.setObjectName("danger")
        self.clear_button.clicked.connect(self.clear_all)
        action_row.addWidget(self.clear_button)

        self.copy_button = QPushButton("Copy Macro to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_macro_format)
        action_row.addWidget(self.copy_button, stretch=1)

        right.addLayout(action_row)

        outer.addWidget(right_widget)

        # Resolve the display font once
        global DEFAULT_FONT
        if DEFAULT_FONT not in QFontDatabase.families():
            DEFAULT_FONT = "Arial"

        self.add_box()
        self.setFixedSize(
            BoxCanvas.CANVAS_W + self.SIDE_PANEL_W + 40, 520
        )

    # --- Tab management ---
    # The last tab is always the "+" pseudo-tab; real boxes live before it.

    def real_count(self):
        return self.tabs.count() - 1

    def _make_close_button(self, page):
        """A close button nudged 6px in from the tab's right edge."""
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(0)
        btn = QToolButton()
        btn.setObjectName("tabClose")
        btn.setText("\u2715")
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.close_box(self.tabs.indexOf(page)))
        lay.addWidget(btn)
        return container

    def _new_page(self):
        """Create a page + tab (before the "+" tab) without changing focus."""
        page = BoxCanvas()
        page.editor.textChanged.connect(self.refresh_display)
        index = self.real_count()
        self.tabs.insertTab(index, page, f"Page {index + 1}")
        self.tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, self._make_close_button(page)
        )
        return page

    def _remove_last_page(self):
        index = self.real_count() - 1
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()

    def add_box(self):
        page = self._new_page()
        self.tabs.setCurrentWidget(page)
        page.editor.setFocus()
        self.refresh_display()

    def close_box(self, index):
        if self.real_count() <= 1 or index >= self.real_count():
            return  # always keep at least one box; ignore the "+" tab
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        self.renumber_tabs()
        self.refresh_display()

    def on_tab_bar_clicked(self, index):
        if index == self.real_count():  # the "+" tab
            self.add_box()

    def on_current_tab_changed(self, index):
        # Never let the "+" tab itself be the visible page
        if index == self.real_count() and self.real_count() > 0:
            self.tabs.setCurrentIndex(self.real_count() - 1)
            return
        self.refresh_display()

    def renumber_tabs(self):
        for i in range(self.real_count()):
            self.tabs.setTabText(i, f"Page {i + 1}")

    def current_editor(self):
        page = self.tabs.currentWidget()
        return page.editor if isinstance(page, BoxCanvas) else None

    def all_pages(self):
        return [self.tabs.widget(i) for i in range(self.real_count())]

    def all_editors(self):
        return [page.editor for page in self.all_pages()]

    # --- Behaviour ---

    def show_about(self):
        AboutDialog(self).exec()

    def toggle_auto_wrap(self, checked):
        self.auto_wrap_enabled = checked
        self.auto_wrap_button.setText("Auto Wrap: On" if checked else "Auto Wrap: Off")
        self.refresh_display()

    def clear_all(self):
        """Reset to a single empty box, ready for the next message."""
        self._updating = True
        try:
            while self.real_count() > 1:
                self._remove_last_page()
            self.tabs.setCurrentIndex(0)
            self.current_editor().clear()
            self.renumber_tabs()
            self.macro_edit.clear()
        finally:
            self._updating = False
        self.refresh_display()
        self.current_editor().setFocus()

    def line_details_for(self, content):
        """Per-line metrics text and the effective font size for a box."""
        lines = content.split("\n") or [""]
        details = []
        sizes = []
        for i, line in enumerate(lines, start=1):
            if line.strip():
                size, metric = compute_font_for_text(line)
            else:
                size, metric = BASE_FONT_SIZE, measure_text(line)
            sizes.append(size)
            too_long = " [TOO LONG]" if find_overflow_index(line, base_metric) < len(line) else ""
            remaining = round(base_metric - metric, 6)
            details.append(f"{i}. String Width: {metric}, Remaining Width: {remaining}{too_long}")
        base_size = min(sizes) if sizes else BASE_FONT_SIZE
        return details, max(1, int(base_size * TEXT_SCALE))

    def update_box_font(self, page):
        _, final_size = self.line_details_for(page.editor.toPlainText())
        page.set_editor_font(DEFAULT_FONT, final_size)

    def refresh_display(self):
        """Editor-driven refresh: normalize text, resize font, update both previews."""
        if self._updating:
            return
        editor = self.current_editor()
        if editor is None:
            return
        self._updating = True
        try:
            content = editor.toPlainText()

            # toPlainText() shows soft line separators (U+2028/U+2029) as \n,
            # but the document may still hold them inside a single block, which
            # would make the overflow highlighter measure those lines as one
            # long string. If any are present, force a document rebuild below.
            raw = editor.document().toRawText()
            has_soft_breaks = "\u2028" in raw or "\u2029" in raw

            # Replace straight apostrophes for display consistency
            new_content = content.replace("'", "’")
            if self.auto_wrap_enabled:
                new_content = auto_wrap_content(new_content)

            if new_content != content or has_soft_breaks:
                cursor_offset = editor.textCursor().position()
                editor.setPlainText(new_content)
                cursor = editor.textCursor()
                cursor.setPosition(min(cursor_offset, len(new_content)))
                editor.setTextCursor(cursor)
                content = new_content

            details, final_size = self.line_details_for(content)
            page = self.tabs.currentWidget()
            if page is not None:
                page.set_editor_font(DEFAULT_FONT, final_size)

            self.info_box.setPlainText("\n".join(details))
            self.update_previews(include_macro=True)
        finally:
            self._updating = False

    def on_macro_edited(self):
        """Macro-driven refresh: rebuild boxes from the pasted/edited macro string."""
        if self._updating:
            return
        self._updating = True
        try:
            box_texts = parse_macro(self.macro_edit.toPlainText())

            # Match the tab count to the parsed box count
            while self.real_count() < len(box_texts):
                self._new_page()
            while self.real_count() > len(box_texts):
                if self.tabs.currentIndex() == self.real_count() - 1:
                    self.tabs.setCurrentIndex(max(0, self.real_count() - 2))
                self._remove_last_page()
            self.renumber_tabs()

            for page, text in zip(self.all_pages(), box_texts):
                normalized = text.replace("'", "’")
                if self.auto_wrap_enabled:
                    normalized = auto_wrap_content(normalized)
                if page.editor.toPlainText() != normalized:
                    page.editor.setPlainText(normalized)
                self.update_box_font(page)

            # Update the line metrics for whichever tab is showing
            editor = self.current_editor()
            if editor is not None:
                details, _ = self.line_details_for(editor.toPlainText())
                self.info_box.setPlainText("\n".join(details))

            # Refresh the full-message view but leave the macro box untouched,
            # so the cursor doesn't jump while the user is typing/pasting in it.
            self.update_previews(include_macro=False)
        finally:
            self._updating = False

    def update_previews(self, include_macro=True):
        box_texts = [e.toPlainText() for e in self.all_editors()]

        # Full message: each box's lines, boxes separated by one blank line
        self.full_preview.setPlainText("\n\n".join(box_texts))

        if include_macro:
            self.macro_edit.setPlainText(build_macro(box_texts))

    def copy_to_macro_format(self):
        QApplication.clipboard().setText(
            build_macro([e.toPlainText() for e in self.all_editors()])
        )


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    icon_file = find_icon()
    if icon_file:
        app.setWindowIcon(QIcon(icon_file))
    window = PreviewerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
