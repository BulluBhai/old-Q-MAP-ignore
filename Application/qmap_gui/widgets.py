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
