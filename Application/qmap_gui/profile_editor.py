"""A small text editor for source profiles: check, then save into the user's own profile folder (never the repository)."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .services import list_profiles, profile_version_conflict, save_user_profile, validate_profile_text
from .widgets import ERROR_COLOR, OK_COLOR


class ProfileEditor(tk.Toplevel):
    def __init__(self, app, text: str, source_description: str, on_saved):
        super().__init__(app)
        self.app, self.on_saved = app, on_saved
        self.title("Edit source profile")
        self.geometry("760x640")
        tk.Label(self, anchor="w", justify="left", wraplength=720,
                 text=f"{source_description}\nSaving puts your profile in your own profiles folder, never in the Q-MAP "
                      "program folder. Give it your own profile_id, and raise profile_version whenever you change a "
                      "profile that has already been used.").pack(fill="x", padx=8, pady=6)
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.text = tk.Text(frame, wrap="none", undo=True, font=tkfont.nametofont("TkFixedFont"))
        vsb = tk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.insert("1.0", text)
        self.message = tk.Label(self, anchor="w", justify="left", wraplength=720)
        self.message.pack(fill="x", padx=8, pady=4)
        buttons = tk.Frame(self)
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        self.check_button = tk.Button(buttons, text="Check profile", command=self.check)
        self.save_button = tk.Button(buttons, text="Save to my profiles", command=self.save)
        self.close_button = tk.Button(buttons, text="Close", command=self.destroy)
        for b in (self.check_button, self.save_button, self.close_button):
            b.pack(side="left", padx=3)

    def content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _set(self, text: str, ok: bool) -> None:
        self.message.configure(text=text, fg=OK_COLOR if ok else ERROR_COLOR)

    def check(self) -> bool:
        settings = self.app.core_settings
        if settings is None:
            self._set("Choose your Q-MAP_DATA and Q-MAP_OUTPUT folders first.", False)
            return False
        profile, message = validate_profile_text(self.content(), settings)
        if profile is None:
            self._set(message, False)
            return False
        example_ids = {p.profile.profile_id for p in list_profiles(settings) if p.where == "example" and p.profile}
        if profile.profile_id in example_ids:
            self._set(f"'{profile.profile_id}' is the name of an example profile. Change profile_id to your own name.", False)
            return False
        conflict = profile_version_conflict(settings, profile)
        if conflict:
            self._set(conflict, False)
            return False
        self._set(message, True)
        return True

    def save(self) -> None:
        if not self.check():
            return
        path = save_user_profile(self.content(), self.app.store.profiles_dir)
        self._set(f"Saved: {path}", True)
        self.on_saved(path)
