import logging
from typing import Final

from ocp_utilities.exceptions import CommandExecFailed

from libs.vm.vm import BaseVirtualMachine

_DEFAULT_CMD_TIMEOUT_SEC: Final[int] = 10
_IPERF_BIN: Final[str] = "iperf3"


LOGGER = logging.getLogger(__name__)


class Server:
    """
    Represents a server running on a virtual machine for testing network performance.
    Implemented with iperf3

    Args:
        name (str): The name of the server instance, used for identification.
        vm (BaseVirtualMachine): The virtual machine where the server runs.
        port (str): The port on which the server listens for client connections.
    """

    def __init__(
        self,
        name: str,
        vm: BaseVirtualMachine,
        port: str,
    ):
        self._name = name
        self._vm = vm
        self._port = port
        self._cmd = f"{_IPERF_BIN} --server --daemon --port {self._port} --one-off"

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        self._vm.console(
            commands=[self._cmd],
            timeout=_DEFAULT_CMD_TIMEOUT_SEC,
        )

    def stop(self) -> None:
        self._vm.console(commands=[f"pkill {_IPERF_BIN}"], timeout=_DEFAULT_CMD_TIMEOUT_SEC)

    def is_running(self) -> bool:
        return _is_process_running(vm=self._vm, cmd=self._cmd)


class Client:
    """
    Represents a client that connects to a server to test network performance.
    Implemented with iperf3

    Args:
        name (str): The name of the client instance, used for identification.
        vm (BaseVirtualMachine): The virtual machine where the client runs.
        server_ip (str): The destination IP address of the server the client connects to.
        server_port (str): The port on which the server listens for connections.
    """

    def __init__(
        self,
        name: str,
        vm: BaseVirtualMachine,
        server_ip: str,
        server_port: str,
    ):
        self._name = name
        self._vm = vm
        self._server_ip = server_ip
        self._server_port = server_port
        self._cmd = f"{_IPERF_BIN} --client {self._server_ip} --time 0 --port {self._server_port}"

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        self._vm.console(
            commands=[f"{self._cmd} &"],
            timeout=_DEFAULT_CMD_TIMEOUT_SEC,
        )

    def stop(self) -> None:
        self._vm.console(commands=[f"pkill {_IPERF_BIN}"], timeout=_DEFAULT_CMD_TIMEOUT_SEC)

    def is_running(self) -> bool:
        return _is_process_running(vm=self._vm, cmd=self._cmd)


class ConnectionSetupError(Exception):
    """Custom exception raised when connection setup fails."""


class Connection:
    """
    Orchestrates network testing between a server and a client.

    This class initializes a network testing server and client to perform
    performance testing.
    It manages their lifecycle, ensuring proper startup and cleanup.

    Args:
        server (Server): The server instance used for network testing.
        client (Client): The client instance used for network testing.
    """

    def __init__(
        self,
        server: Server,
        client: Client,
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


def _is_process_running(vm: BaseVirtualMachine, cmd: str) -> bool:
    try:
        vm.console(
            commands=[f"pgrep -ofAx '{cmd}'"],
            timeout=_DEFAULT_CMD_TIMEOUT_SEC,
        )
        return True
    except CommandExecFailed as e:
        LOGGER.info(f"Process is not running on VM {vm.name}. Error: {str(e)}")
        return False


def connection(
    server_name: str,
    client_name: str,
    server_vm: BaseVirtualMachine,
    client_vm: BaseVirtualMachine,
    server_ip: str,
    server_port: str,
) -> Connection:
    return Connection(
        server=Server(name=server_name, vm=server_vm, port=server_port),
        client=Client(name=client_name, vm=client_vm, server_ip=server_ip, server_port=server_port),
    )
