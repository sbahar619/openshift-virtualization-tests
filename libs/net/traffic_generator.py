import logging
from typing import Any, Final

from ocp_utilities.exceptions import CommandExecFailed

from libs.vm.vm import BaseVirtualMachine

_DEFAULT_CMD_TIMEOUT_SEC: Final[int] = 10
_IPERF_BIN: Final[str] = "iperf3"


LOGGER = logging.getLogger(__name__)


class TrafficGenerator:
    """
    Base class for managing traffic generation on a virtual machine.

    Args:
        vm (BaseVirtualMachine): Virtual machine instance where the commands are executed.
        cmd (str): Command to execute for traffic generation.
    """

    def __init__(
        self,
        vm: BaseVirtualMachine,
        cmd: str,
    ):
        self._vm = vm
        self._cmd = cmd

    def start(self) -> None:
        self._vm.console(
            commands=[f"{self._cmd} &"],
            timeout=_DEFAULT_CMD_TIMEOUT_SEC,
        )

    def stop(self) -> None:
        self._vm.console(commands=[f"pkill -f '{self._cmd}'"], timeout=_DEFAULT_CMD_TIMEOUT_SEC)

    def is_running(self) -> bool:
        try:
            self._vm.console(
                commands=[f"pgrep -ofAx '{self._cmd}'"],
                timeout=_DEFAULT_CMD_TIMEOUT_SEC,
            )
            return True
        except CommandExecFailed as e:
            LOGGER.info(f"Process is not running on {self._vm.name}. Error: {str(e)}")
            return False


class TCPServer(TrafficGenerator):
    """
    Represents a TCP server for network performance testing. The server is implemented using iperf3 and listens on the
    specified port. It terminates after handling a single connection.

    Args:
        server_port (str): The port on which the server listens for client connections.
    """

    def __init__(
        self,
        server_port: str,
        **kwargs: Any,
    ):
        self._server_port = server_port
        cmd = f"{_IPERF_BIN} --server --port {self._server_port} --one-off"
        super().__init__(cmd=cmd, **kwargs)


class TCPClient(TrafficGenerator):
    """
    Represents a TCP client that connects to a server to test network performance.
    The client uses iperf3 to connect to a server at the specified IP address and port for performance measurement.

    Args:
        server_ip (str): The destination IP address of the server the client connects to.
        server_port (str): The port on which the server listens for connections.
    """

    def __init__(
        self,
        server_ip: str,
        server_port: str,
        **kwargs: Any,
    ):
        self._server_ip = server_ip
        self._server_port = server_port
        cmd = f"{_IPERF_BIN} --client {self._server_ip} --time 0 --port {self._server_port}"
        super().__init__(cmd=cmd, **kwargs)


class ConnectionSetupError(Exception):
    """Custom exception raised when connection setup fails."""


class Connection:
    """
    Orchestrates network testing between a server and a client.

    This class initializes a TCP network connection between server and client to perform performance testing.
    It manages their lifecycle, ensuring proper startup and cleanup.

    Args:
        server (TCPServer): The server instance used for network testing.
        client (TCPClient): The client instance used for network testing.
    """

    def __init__(
        self,
        server: TCPServer,
        client: TCPClient,
    ):
        self._server = server
        self._client = client

    def __enter__(self) -> "Connection":
        self._server.start()
        self._client.start()

        if not self.is_active():
            raise ConnectionSetupError("Connection setup failed")

        return self

    def __exit__(self, exc_type: BaseException, exc_value: BaseException, traceback: object) -> None:
        if self._client.is_running():
            self._client.stop()
        if self._server.is_running():
            self._server.stop()

    def is_active(self) -> bool:
        return self._server.is_running() and self._client.is_running()


def connection(
    server_vm: BaseVirtualMachine,
    client_vm: BaseVirtualMachine,
    server_ip: str,
    server_port: str,
) -> Connection:
    return Connection(
        server=TCPServer(vm=server_vm, server_port=server_port),
        client=TCPClient(vm=client_vm, server_ip=server_ip, server_port=server_port),
    )
