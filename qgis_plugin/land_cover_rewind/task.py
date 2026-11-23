"""Background task that runs the Land Cover Rewind CLI in a separate process."""
import subprocess

from qgis.core import QgsTask, QgsMessageLog, Qgis

from . import core

MESSAGE_CATEGORY = "Land Cover Rewind"


class RunTask(QgsTask):
    """Runs the CLI, streams its progress, and keeps its log and output folder.

    The task only runs the process; loading the result layers happens on the main
    thread in the dialog, connected to taskCompleted / taskTerminated.
    """

    def __init__(self, command, out_dir, epochs, cwd=None):
        super().__init__("Land Cover Rewind run", QgsTask.CanCancel)
        self.command = list(command)
        self.out_dir = out_dir
        self.epochs = list(epochs)
        self.cwd = cwd
        self.log_lines = []
        self.returncode = None
        self.error = None
        self._proc = None

    def run(self):
        """Executed in a worker thread. Must not touch the GUI or the project."""
        QgsMessageLog.logMessage("Running: " + " ".join(self.command), MESSAGE_CATEGORY, Qgis.Info)
        try:
            self._proc = subprocess.Popen(
                self.command, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True,
            )
        except OSError as e:
            self.error = f"could not start the process: {e}"
            return False

        for line in self._proc.stdout:
            if self.isCanceled():
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                return False
            line = line.rstrip("\n")
            if not line:
                continue
            self.log_lines.append(line)
            if len(self.log_lines) > 1000:
                del self.log_lines[:500]
            pct, text = core.parse_progress(line)
            if pct is not None:
                self.setProgress(pct)
                QgsMessageLog.logMessage(f"{pct}% {text}", MESSAGE_CATEGORY, Qgis.Info)

        self.returncode = self._proc.wait()
        if self.returncode != 0:
            tail = "\n".join(self.log_lines[-15:])
            self.error = f"the process exited with code {self.returncode}.\n{tail}"
            return False
        self.setProgress(100)
        return True

    def cancel(self):
        QgsMessageLog.logMessage("Cancelling", MESSAGE_CATEGORY, Qgis.Warning)
        super().cancel()

    def log_text(self):
        return "\n".join(self.log_lines)
