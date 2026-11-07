from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtCore import QObject, Signal

SERVER_NAME = "Hotspot_SingleInstance_Lock_Kiesh628"

class SingleInstance(QObject):
    activate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None

    def is_already_running(self) -> bool:
        """
        Attempts to connect to an existing running instance of Hotspot.
        If found, sends a WAKEUP message and returns True.
        If not found, starts listening as the primary instance and returns False.
        """
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(400):
            # Another instance is already active: tell it to bring window to front
            socket.write(b"WAKEUP\n")
            socket.waitForBytesWritten(400)
            socket.disconnectFromServer()
            return True

        # Clean up any stale pipe/socket from a previous crash
        QLocalServer.removeServer(SERVER_NAME)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_new_connection)
        self.server.listen(SERVER_NAME)
        return False

    def _on_new_connection(self):
        client = self.server.nextPendingConnection()
        if client:
            client.readyRead.connect(lambda: self._handle_read(client))

    def _handle_read(self, client):
        data = client.readAll().data().decode("utf-8", errors="ignore")
        if "WAKEUP" in data:
            self.activate_requested.emit()
        client.disconnectFromServer()
