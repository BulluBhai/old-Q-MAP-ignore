"""Small reusable tkinter widgets. Plain tkinter, no styling beyond status colours."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

OK_COLOR, ERROR_COLOR, WARN_COLOR, MUTED_COLOR = "#1a7f37", "#b42318", "#b54708", "#667085"
_SELF_SCROLLING = ("Text", "Listbox", "Treeview", "TCombobox", "Combobox")


def combobox_index(combo) -> int:
    """Index of the chosen entry of a ttk.Combobox, or -1 when nothing is chosen.

    Tk 9 answers "" (Tk 8.6: -1) when nothing is chosen; Python 3.11's ttk.Combobox.current() turns that "" into a
    TclError ("expected integer but got"). This reads the answer the way Python 3.12+ does, on every version.
    """
    answer = combo.tk.call(combo._w, "current")
    return -1 if answer == "" else combo.tk.getint(answer)


class ScrollFrame(tk.Frame):
    """A frame that scrolls vertically. Put everything into `.inner`."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)
        self._wheel_bound = False

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None):
        if not self._wheel_bound:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
            self.canvas.bind_all("<Button-4>", self._on_wheel)
            self.canvas.bind_all("<Button-5>", self._on_wheel)
            self._wheel_bound = True

    def _unbind_wheel(self, _event=None):
        if self._wheel_bound:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    self.canvas.unbind_all(seq)
                except tk.TclError:
                    pass
            self._wheel_bound = False

    def _on_wheel(self, event):
        if event.widget.winfo_class() in _SELF_SCROLLING:
            return  # text boxes, lists and tables scroll themselves
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        try:
            self.canvas.yview_scroll(step * 3, "units")
        except tk.TclError:
            pass

    def destroy(self):
        # Destroy the internal canvas first (avoids the Windows "ghost window" problem), then the frame.
        self._unbind_wheel()
        try:
            self.canvas.destroy()
        except tk.TclError:
            pass
        super().destroy()


class ReadOnlyText(tk.Frame):
    """A scrollable, read-only text box."""

    def __init__(self, master, height: int = 8, mono: bool = True, wrap: str = "word"):
        super().__init__(master)
        self.text = tk.Text(self, height=height, wrap=wrap, state="disabled", relief="solid", borderwidth=1)
        if mono:
            self.text.configure(font=tkfont.nametofont("TkFixedFont"))
        sb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for tag, color in (("error", ERROR_COLOR), ("warning", WARN_COLOR), ("ok", OK_COLOR), ("muted", MUTED_COLOR)):
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure("bold", font=tkfont.Font(font=self.text["font"], weight="bold"))

    def set(self, content: str, tag: str | None = None) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", content, tag or ())
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def set_parts(self, parts: list[tuple[str, str | None]]) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for content, tag in parts:
            self.text.insert("end", content, tag or ())
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")


class LogText(tk.Frame):
    """Terminal-style live log: dark, monospaced, scrolls to the newest line."""

    MAX_LINES = 5000

    def __init__(self, master, height: int = 10):
        super().__init__(master)
        self.text = tk.Text(self, height=height, wrap="none", state="disabled", background="#1e1e1e",
                            foreground="#d4d4d4", insertbackground="#d4d4d4", relief="solid", borderwidth=1,
                            font=tkfont.nametofont("TkFixedFont"))
        vsb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        hsb = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("error", foreground="#f97066")
        self.text.tag_configure("warning", foreground="#fdb022")

    def append(self, line: str) -> None:
        tag = "error" if (" ERROR" in line or "REJECTED" in line) else "warning" if " WARNING" in line else ()
        self.text.configure(state="normal")
        self.text.insert("end", line.rstrip("\n") + "\n", tag)
        extra = int(self.text.index("end-1c").split(".")[0]) - self.MAX_LINES
        if extra > 0:
            self.text.delete("1.0", f"{extra + 1}.0")
        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")


def section(parent, title: str) -> tk.LabelFrame:
    frame = tk.LabelFrame(parent, text=title, padx=8, pady=6, font=tkfont.Font(weight="bold", size=10))
    frame.pack(fill="x", padx=8, pady=4)
    return frame


class CalendarPopup(tk.Toplevel):
    """A small month calendar (plain tkinter, no extra package). Picking a day calls on_pick(date) and closes."""

    WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")

    def __init__(self, master, initial, on_pick, on_clear, title: str = "Choose a date"):
        import calendar as _cal
        from datetime import date as _date

        super().__init__(master)
        self._cal, self._date = _cal, _date
        self.on_pick, self.on_clear = on_pick, on_clear
        self.selected = initial
        start = initial or _date.today()
        self.year, self.month = start.year, start.month
        self.title(title)
        self.resizable(False, False)
        try:
            self.transient(master.winfo_toplevel())
        except tk.TclError:
            pass
        head = tk.Frame(self)
        head.pack(fill="x", padx=6, pady=(6, 2))
        # << and >> move a whole year (same month), < and > one month
        self.prev_year_button = tk.Button(head, text="<<", width=3, command=lambda: self.shift(-12))
        self.prev_year_button.pack(side="left")
        self.prev_button = tk.Button(head, text="<", width=3, command=lambda: self.shift(-1))
        self.prev_button.pack(side="left", padx=(2, 0))
        self.month_label = tk.Label(head, text="", width=16, font=tkfont.Font(weight="bold"))
        self.month_label.pack(side="left", expand=True)
        self.next_year_button = tk.Button(head, text=">>", width=3, command=lambda: self.shift(12))
        self.next_year_button.pack(side="right")
        self.next_button = tk.Button(head, text=">", width=3, command=lambda: self.shift(1))
        self.next_button.pack(side="right", padx=(0, 2))
        self.grid_frame = tk.Frame(self)
        self.grid_frame.pack(padx=6, pady=2)
        foot = tk.Frame(self)
        foot.pack(fill="x", padx=6, pady=(2, 6))
        tk.Button(foot, text="Today", command=lambda: self.pick(_date.today())).pack(side="left")
        tk.Button(foot, text="Clear", command=self.clear).pack(side="left", padx=4)
        tk.Button(foot, text="Close", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        self.day_buttons: dict[int, tk.Button] = {}
        self.show_month(self.year, self.month)
        try:
            x = master.winfo_rootx()
            y = master.winfo_rooty() + master.winfo_height()
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass
        self.focus_set()

    def show_month(self, year: int, month: int) -> None:
        self.year, self.month = year, month
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.day_buttons.clear()
        self.month_label.configure(text=f"{self._cal.month_name[month]} {year}")
        for c, name in enumerate(self.WEEKDAYS):
            tk.Label(self.grid_frame, text=name, width=4, fg=MUTED_COLOR).grid(row=0, column=c)
        for r, week in enumerate(self._cal.Calendar(firstweekday=0).monthdayscalendar(year, month), start=1):
            for c, day in enumerate(week):
                if not day:
                    continue
                chosen = self.selected is not None and (self.selected.year, self.selected.month, self.selected.day) == (
                    year, month, day)
                b = tk.Button(self.grid_frame, text=str(day), width=3, relief="sunken" if chosen else "raised",
                              command=lambda d=day: self.pick(self._date(self.year, self.month, d)))
                b.grid(row=r, column=c, padx=1, pady=1)
                self.day_buttons[day] = b

    def shift(self, months: int) -> None:
        y, m = divmod(self.month - 1 + months, 12)
        self.show_month(self.year + y, m + 1)

    def pick(self, value) -> None:
        self.on_pick(value)
        self.destroy()

    def clear(self) -> None:
        self.on_clear()
        self.destroy()


class DateEntry(tk.Frame):
    """A date box that accepts typing AND a calendar, with a live confirmation of what was understood.

    `parse(text)` returns (date or None, problem text or None); `to_text(date)` writes a date into the box;
    `confirm(date)` gives the unambiguous confirmation shown next to it. The box itself stays an ordinary Entry, so
    typed text can be edited, selected, copied or cleared at any time.
    """

    def __init__(self, master, variable: tk.StringVar, parse, to_text, confirm, empty_note: str = "", width: int = 12):
        super().__init__(master)
        self.var, self.parse, self.to_text, self.confirm, self.empty_note = variable, parse, to_text, confirm, empty_note
        self.entry = tk.Entry(self, textvariable=variable, width=width)
        self.entry.pack(side="left")
        self.button = tk.Button(self, text="Calendar...", command=self.open_calendar)
        self.button.pack(side="left", padx=(3, 0))
        self.feedback = tk.Label(self, text="", anchor="w", justify="left", fg=MUTED_COLOR, wraplength=560)
        self.feedback.pack(side="left", padx=6)
        self.popup: CalendarPopup | None = None
        variable.trace_add("write", lambda *_a: self.update_feedback())
        self.update_feedback()

    def value(self):
        return self.parse(self.var.get())

    def update_feedback(self) -> None:
        try:
            d, problem = self.value()
        except tk.TclError:  # the window is closing
            return
        if problem:
            self.feedback.configure(text=problem, fg=ERROR_COLOR)
        elif d is None:
            self.feedback.configure(text=self.empty_note, fg=MUTED_COLOR)
        else:
            self.feedback.configure(text="= " + self.confirm(d), fg=OK_COLOR)

    def open_calendar(self) -> None:
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            return
        d, _problem = self.value()
        self.popup = CalendarPopup(self.entry, d, on_pick=lambda v: self.var.set(self.to_text(v)),
                                   on_clear=lambda: self.var.set(""))
