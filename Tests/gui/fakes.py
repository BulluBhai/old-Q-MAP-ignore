"""Stand-ins for the pop-up dialogs, so GUI tests never wait for a person."""

from qmap_gui.app import Dialogs


class FakeDialogs(Dialogs):
    def __init__(self):
        self.directories, self.files, self.file, self.strings = [], [], [], []
        self.yes = True
        self.messages = []  # (kind, title, message)

    def ask_directory(self, title, initial=""):
        return self.directories.pop(0) if self.directories else ""

    def ask_open_files(self, title, initial=""):
        return tuple(self.files.pop(0)) if self.files else ()

    def ask_open_file(self, title, initial="", types=None):
        return self.file.pop(0) if self.file else ""

    def ask_string(self, title, prompt):
        return self.strings.pop(0) if self.strings else None

    def yes_no(self, title, message):
        self.messages.append(("yes_no", title, message))
        return self.yes

    def info(self, title, message):
        self.messages.append(("info", title, message))

    def warn(self, title, message):
        self.messages.append(("warn", title, message))

    def error(self, title, message):
        self.messages.append(("error", title, message))
