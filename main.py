import tkinter as tk
from tkinter import font as tkfont

# -------------------------------
# Metric Loading and Text Sizing
# -------------------------------

metrics = {}

def load_metrics():
    filepath = '_assets/strlength.txt'
    try:
        with open(filepath, encoding='utf8') as file:
            for record in file:
                record = record.strip()
                if not record or record.startswith("//"):
                    continue
                segments = record.split(',') if ',' in record else record.split(None, 1)
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

def measure_text(text):
    """
    Special handling: any literal instance of "{n}" counts as width 343.6875.
    Straight apostrophes in input are treated as left single quotation mark ’ for width purposes.
    """
    space_width = metrics.get(" ", 8.671875)
    fallback_digit = 15.0
    total_width = 0.0
    i = 0
    while i < len(text):
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
    Returns the index in text where cumulative metric exceeds limit_metric.
    Characters from that index onward are considered overflow.
    """
    space_width = metrics.get(" ", 8.671875)
    fallback_digit = 15.0
    total_width = 0.0
    i = 0
    while i < len(text):
        if text.startswith("{n}", i):
            increment = 343.6875
            if total_width + increment > limit_metric:
                return i
            total_width += increment
            i += 3
            continue
        ch = text[i]
        if ch == "'":
            ch = "‘"
        width = metrics.get(ch)
        if width is None or width == 0:
            width = fallback_digit if ch.isdigit() else space_width
        if total_width + width > limit_metric:
            return i
        total_width += width
        i += 1
    return len(text)

BASE_FONT_SIZE = 54
MAX_WIDTH = 1080

load_metrics()
base_phrase = "Oh. And it needs to be found and caught down"
base_metric = measure_text(base_phrase)

def compute_font_for_text(text):
    current_metric = measure_text(text)
    if current_metric <= base_metric:
        return BASE_FONT_SIZE, current_metric
    scaled_size = int(BASE_FONT_SIZE * (base_metric / current_metric))
    return max(scaled_size, 1), current_metric

# -------------------------------
# Globals for UI state
# -------------------------------

DEFAULT_FONT = "@FOT-UDKakugoC80 Pro DB"
TEXT_SCALE = 0.75  # scale factor
separator_list = []  # separators between lines
auto_wrap_enabled = False  # new: auto wrap toggle

# -------------------------------
# Refresh Display (Dynamic Font Sizing + Info Box)
# -------------------------------

def set_separator(idx, sep):
    if idx < 0 or idx >= len(separator_list):
        return
    separator_list[idx] = sep
    refresh_display()

def toggle_auto_wrap():
    global auto_wrap_enabled
    auto_wrap_enabled = not auto_wrap_enabled
    if auto_wrap_enabled:
        auto_wrap_button.config(text="Auto Wrap: On", relief="sunken")
    else:
        auto_wrap_button.config(text="Auto Wrap: Off", relief="raised")
    refresh_display()

def refresh_display(event=None):
    global separator_list

    # Capture original cursor position as character offset so we can restore it after modifications.
    try:
        cursor_offset = len(display_text.get("1.0", tk.INSERT))
    except Exception:
        cursor_offset = 0

    content = display_text.get("1.0", "end-1c")

    # Replace straight apostrophes with left single quotation mark for display consistency
    replaced = content.replace("'", "’")
    if replaced != content:
        display_text.delete("1.0", "end")
        display_text.insert("1.0", replaced)
        content = replaced

    # Auto-wrap logic: if enabled, reflow lines so no line exceeds base_metric, preferring breaks at spaces.
    if auto_wrap_enabled:
        original_lines = content.split("\n") or [""]
        new_lines = []
        for line in original_lines:
            if line == "":
                new_lines.append("")  # preserve blank line
                continue
            remaining = line
            while remaining:
                cutoff = find_overflow_index(remaining, base_metric)
                if cutoff == 0:
                    # Single character already exceeds; force one char to avoid infinite loop
                    cutoff = 1
                if cutoff < len(remaining):
                    # Prefer to wrap at last space before cutoff if possible
                    bp = remaining.rfind(' ', 0, cutoff)
                    if bp > 0:
                        line_part = remaining[:bp].rstrip()
                        remaining = remaining[bp+1:]
                    else:
                        line_part = remaining[:cutoff]
                        remaining = remaining[cutoff:]
                else:
                    line_part = remaining
                    remaining = ""
                new_lines.append(line_part)
        new_content = "\n".join(new_lines)
        if new_content != content:
            display_text.delete("1.0", "end")
            display_text.insert("1.0", new_content)
            content = new_content

    # Restore cursor position based on original offset (cap to content length)
    try:
        final_length = len(content)
        adjusted_offset = min(cursor_offset, final_length)
        insert_index = f"1.0 + {adjusted_offset} chars"
        display_text.mark_set(tk.INSERT, insert_index)
    except Exception:
        try:
            display_text.mark_set(tk.INSERT, "end-1c")
        except Exception:
            pass

    lines = content.split("\n") or [""]
    line_count = len(lines)

    # Info box height scaling based on number of lines (only info box scales)
    base_info_height = 2
    info_box_height = base_info_height + max(0, line_count - 2)
    info_box.config(height=info_box_height)

    effective_sizes = []
    details_lines = []

    for i, line in enumerate(lines, start=1):
        if line.strip():
            size, metric = compute_font_for_text(line)
        else:
            size, metric = BASE_FONT_SIZE, measure_text(base_phrase)
        effective_sizes.append(size)
        scale_factor = MAX_WIDTH / (BASE_FONT_SIZE * base_metric)
        approx_width = size * scale_factor * metric
        details_lines.append(f"Line {i}: Calc length = {metric}, Rendered ≈ {approx_width:.2f}px, Eff size = {size}")

    base_size = min(effective_sizes) if effective_sizes else BASE_FONT_SIZE
    final_size = int(base_size * TEXT_SCALE)
    new_font = tkfont.Font(family=DEFAULT_FONT, size=final_size)
    display_text.configure(font=new_font)

    # Apply overflow red coloring (tagging)
    display_text.tag_remove("overflow", "1.0", "end")
    display_text.tag_configure("overflow", foreground="red")
    for line_index, line in enumerate(lines):
        # Compute start index of this line
        line_start = f"{line_index + 1}.0"
        # Determine overflow point for the line (based on base_metric)
        overflow_idx = find_overflow_index(line, base_metric)
        if overflow_idx < len(line):
            # Tag from overflow_idx to end of line
            start = f"{line_index + 1}.{overflow_idx}"
            end = f"{line_index + 1}.{len(line)}"
            display_text.tag_add("overflow", start, end)

    # Update info box content.
    details = "\n".join(details_lines)
    info_box.config(state="normal")
    info_box.delete("1.0", tk.END)
    info_box.insert(tk.END, details)
    info_box.config(state="disabled")

    # Rebuild separator_list to match current number of gaps.
    needed_separators = max(0, line_count - 1)
    default_seps = []
    if needed_separators >= 1:
        default_seps.append(r"\n")
    for _ in range(needed_separators - 1):
        default_seps.append(r"\f")
    if len(separator_list) < needed_separators:
        for idx in range(len(separator_list), needed_separators):
            separator_list.append(default_seps[idx])
    elif len(separator_list) > needed_separators:
        separator_list = separator_list[:needed_separators]

    # Rebuild override controls in separators_frame to the right of info box
    for child in separators_frame.winfo_children():
        child.destroy()
    for gap_index in range(needed_separators):
        row = tk.Frame(separators_frame)
        row.pack(anchor="nw", pady=2)
        label = tk.Label(row, text=f"Gap {gap_index + 1}:")
        label.pack(side="left", padx=(0, 4))
        def make_setter(idx, sep):
            return lambda: set_separator(idx, sep)
        # Updated button labels per request
        for sep_candidate, display_label in [(r"\r", "New Line \\r"), (r"\n", "Line Break \\n"), (r"\f", "Scroll Line \\f")]:
            btn = tk.Button(row, text=display_label, width=14, command=make_setter(gap_index, sep_candidate))
            if separator_list[gap_index] == sep_candidate:
                btn.config(relief="sunken")
            btn.pack(side="left", padx=2)

    # Adjust application window height based on number of lines (scaling window size)
    base_window_height = 340
    extra_per_line = 30
    new_height = base_window_height + extra_per_line * max(0, line_count - 2)
    root.geometry(f"1520x{new_height}")

# -------------------------------
# Main Application
# -------------------------------

def main():
    global display_text, info_box, DEFAULT_FONT, root, canvas, separators_frame, auto_wrap_button

    root = tk.Tk()
    root.title("BDSP Message Previewer")
    root.geometry("1520x340")  # starting resolution
    root.resizable(False, False)

    if DEFAULT_FONT not in tkfont.families():
        DEFAULT_FONT = "Arial"

    canvas_width = 1500
    canvas_height = 230
    canvas = tk.Canvas(root, width=canvas_width, height=canvas_height)
    canvas.pack(pady=(10, 5))

    bg_image = tk.PhotoImage(file="_assets/textbox.png")
    canvas.create_image(0, 0, anchor="nw", image=bg_image)

    display_text = tk.Text(canvas, font=(DEFAULT_FONT, BASE_FONT_SIZE),
                           bd=0, highlightthickness=0, bg="white", fg="black", wrap="word")
    text_widget_width = canvas_width - 400
    text_widget_height = canvas_height - 60
    canvas.create_window(100, 40, anchor="nw", window=display_text,
                         width=text_widget_width, height=text_widget_height)

    display_text.bind("<KeyRelease>", refresh_display)

    # Info container centered
    info_container = tk.Frame(root)
    info_container.pack(pady=(5, 0), fill="x")
    inner = tk.Frame(info_container)
    inner.pack(anchor="center")

    info_box = tk.Text(inner, height=2, width=100, font=("Consolas", 12))
    info_box.pack(side="left")
    info_box.insert(tk.END, "Calculated info will appear here...")
    info_box.config(state="disabled")

    separators_frame = tk.Frame(inner)
    separators_frame.pack(side="left", padx=(10, 0))

    # Copy to macro format button
    def copy_to_macro_format():
        content = display_text.get("1.0", "end-1c")
        lines = content.split("\n")
        if not lines:
            return
        result = lines[0]
        for i in range(1, len(lines)):
            sep = separator_list[i - 1] if i - 1 < len(separator_list) else (r"\f" if i > 1 else r"\n")
            result += sep + lines[i]
        try:
            root.clipboard_clear()
            root.clipboard_append(result)
        except Exception:
            pass

    button_frame = tk.Frame(root)
    button_frame.pack(pady=(15, 0))  # moved slightly lower with top padding

    copy_button = tk.Button(button_frame, text="Copy Message to Macro Format", command=copy_to_macro_format)
    copy_button.pack(side="left", padx=4)

    auto_wrap_button = tk.Button(button_frame, text="Auto Wrap: Off", command=toggle_auto_wrap)
    auto_wrap_button.pack(side="left", padx=4)

    refresh_display()

    root.mainloop()

if __name__ == '__main__':
    main()
