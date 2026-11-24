"""Background task that runs the Land Cover Rewind CLI in a separate process.

Uses Qt's QProcess (not the Python subprocess module) to launch the user-selected
Python interpreter with the CLI; QProcess runs in the worker thread using its
blocking waitFor* methods and needs no shell.
"""
from qgis.PyQt.QtCore import QProcess, QProcessEnvironment
from qgis.core import QgsTask, QgsMessageLog, Qgis

from . import core

MESSAGE_CATEGORY = "Land Cover Rewind"


class RunTask(QgsTask):
    """Runs the CLI, streams its progress, and keeps its log and output folder.

    The task only runs the process; loading the result layers happens on the main
    thread in the dialog, connected to taskCompleted / taskTerminated.
    """

    def __init__(self, command, out_dir, epochs, cwd=None, env=None, description=None):
        super().__init__(description or "Land Cover Rewind run", QgsTask.CanCancel)
        self.command = list(command)
        self.out_dir = out_dir
        self.epochs = list(epochs)
        self.cwd = cwd
        self.env = env
        self.log_lines = []
        self.returncode = None
        self.error = None
        self._proc = None

    def _emit_line(self, line):
        line = line.rstrip("\r\n")
        if not line:
            return
        self.log_lines.append(line)
        if len(self.log_lines) > 1000:
            del self.log_lines[:500]
        pct, text = core.parse_progress(line)
        if pct is not None:
            self.setProgress(pct)
            QgsMessageLog.logMessage(f"{pct}% {text}", MESSAGE_CATEGORY, Qgis.Info)

    def run(self):
        """Executed in a worker thread. Must not touch the GUI or the project."""
        QgsMessageLog.logMessage("Running: " + " ".join(self.command), MESSAGE_CATEGORY, Qgis.Info)
        program = self.command[0]
        arguments = self.command[1:]

        proc = QProcess()
        self._proc = proc
        proc.setProcessChannelMode(QProcess.MergedChannels)  # stdout + stderr together
        if self.cwd:
            proc.setWorkingDirectory(self.cwd)
        if self.env:
            qenv = QProcessEnvironment.systemEnvironment()
            for key, value in self.env.items():
                qenv.insert(str(key), str(value))
            proc.setProcessEnvironment(qenv)

        proc.start(program, arguments)
        if not proc.waitForStarted(15000):
            self.error = f"could not start the process: {program}"
            return False

        buffer = ""
        while True:
            if self.isCanceled():
                proc.kill()
                proc.waitForFinished(3000)
                return False
            proc.waitForReadyRead(200)
            data = proc.readAll()
            if len(data):
                buffer += bytes(data).decode("utf-8", "replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self._emit_line(line)
            elif proc.state() == QProcess.NotRunning:
                break

        data = proc.readAll()  # drain whatever is left after exit
        if len(data):
            buffer += bytes(data).decode("utf-8", "replace")
        for line in buffer.splitlines():
            self._emit_line(line)

        if proc.exitStatus() != QProcess.NormalExit:
            self.returncode = -1
            tail = "\n".join(self.log_lines[-15:])
            self.error = f"the process stopped unexpectedly.\n{tail}"
            return False
        self.returncode = proc.exitCode()
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
