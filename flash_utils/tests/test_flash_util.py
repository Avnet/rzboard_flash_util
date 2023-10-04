"""
This module contains unit tests for the FlashUtil class in the flash_utils.flash module.
"""

import sys
from unittest.mock import Mock

import pytest

from flash_utils.flash import CORE_IMAGE_FILE_DEFAULT, FlashUtil


@pytest.fixture(name="mock_serial_port")
def fixture_serial_port(monkeypatch):
    """Mock the serial port for testing. Useful for testing on github actions."""

    serial_mock = Mock()
    monkeypatch.setattr("flash_utils.flash.serial.Serial", serial_mock)
    return serial_mock


@pytest.fixture(name="mock_popen")
def fixture_popen(monkeypatch):
    """Mock the subprocess.Popen call for testing"""

    # pylint: disable-next=too-few-public-methods
    class ContextBundle:
        """Mock the subprocess.Popen context manager return value"""
        def __init__(self, code, stdout):
            self.returncode = code
            self.stdout = stdout

    class MockPopen(Mock):
        """Mock the subprocess.Popen call."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.context = ContextBundle(code=0, stdout=[])

        def __enter__(self):
            return self.context

        def __exit__(self, *args, **kwargs):
            pass

    popen_mock = MockPopen()
    monkeypatch.setattr("flash_utils.flash.Popen", popen_mock)
    return popen_mock


@pytest.mark.parametrize("option", ("-h", "--help"))
def test_flash_util_help(capsys: pytest.CaptureFixture[str], option):
    """Test FlashUtil --help."""

    with pytest.raises(SystemExit) as excinfo:
        # --help will cause SystemExit 0
        sys.argv = ["flash_util.py", option]
        FlashUtil()

        assert excinfo.value == 0

    output = capsys.readouterr()
    assert output is not None

    assert "--help" in output.out
    assert "--bootloader" in output.out
    assert "--rootfs" in output.out
    assert "--full" in output.out


@pytest.mark.parametrize("flash_options", ("--bootloader", "--rootfs", "--full"))
def test_bad_bootloader_param(capsys: pytest.CaptureFixture[str], flash_options):
    """Test FlashUtil with bad parameter combinations."""

    with pytest.raises(SystemExit):
        # SystemExit expected for bad parameters
        sys.argv = ["flash_util.py", flash_options, "bad arg"]
        FlashUtil()
    output = capsys.readouterr()

    assert output is not None
    assert "unrecognized arguments" in output.err


@pytest.mark.parametrize("flash_option", ("--bootloader", "--rootfs", "--full"))
def test_good_params_missing_images(
    capsys: pytest.CaptureFixture[str], flash_option, mock_serial_port
):
    """Test FlashUtil with good parameters, but missing flash files"""

    with pytest.raises(SystemExit):
        # SystemExit expected for missing flash file
        sys.argv = ["flash_util.py", flash_option]
        FlashUtil()
    output = capsys.readouterr()
    mock_serial_port.assert_called_once_with(port="/dev/ttyUSB0", baudrate=115200)

    assert output is not None
    assert "missing" in output.err.lower() and "image" in output.err.lower()


def test_rootfs_write(capsys: pytest.CaptureFixture[str], tmp_path, mock_serial_port, mock_popen):
    """Test FlashUtil writing rootfs with temp path"""

    rootfs_content = "TEMP ROOTFS FILE DATA"

    images = tmp_path / "images"
    images.mkdir()
    rootfs_file = images / CORE_IMAGE_FILE_DEFAULT
    rootfs_file.write_text(rootfs_content)

    # normal users probably dont pass image_path, but we are generating a temp path
    sys.argv = ["flash_util.py", "--rootfs", "--image_path", str(images)]
    FlashUtil()

    output = capsys.readouterr()
    assert "Power on board. Make sure boot2 strap is NOT on." in output.out

    mock_serial_port.assert_called_once_with(port="/dev/ttyUSB0", baudrate=115200)
    mock_popen.assert_called_once()

    # assert fastboot setup (specific to rootfs flashing)
    mock_serial_port.return_value.write.assert_any_call("\rfastboot udp\r".encode())
