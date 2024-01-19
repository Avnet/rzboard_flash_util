"""
This module contains unit tests for the FlashUtil class in the flash_utils.flash module.
"""

import sys
from unittest.mock import Mock, call

import pytest

from flash_utils.flash import (
    BL2_FILE_DEFAULT,
    CORE_IMAGE_FILE_DEFAULT,
    FIP_FILE_DEFAULT,
    FLASH_WRITER_FILE_DEFAULT,
    FlashUtil,
)

DEFAULT_BAUD_RATE = 115200
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"


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
    mock_serial_port.assert_called_once_with(port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE)

    assert output is not None
    assert "missing" in output.err.lower() and "image" in output.err.lower()


def setup_tmp_rootfs_dir_and_file(tmp_path):
    """
    Creates a temporary rootfs directory and file for testing purposes.

    Args:
        tmp_path: A pytest fixture that provides a temporary directory path.

    Returns:
        A tuple containing the path to the image directory and the path to the rootfs file.
    """

    rootfs_content = "TEMP ROOTFS FILE DATA"

    image_dir = tmp_path / "images"
    image_dir.mkdir()
    rootfs_file = image_dir / CORE_IMAGE_FILE_DEFAULT
    rootfs_file.write_text(rootfs_content)
    return image_dir, rootfs_file


def test_rootfs_write(
    capsys: pytest.CaptureFixture[str], tmp_path, mock_serial_port, mock_popen, monkeypatch
):
    """Test FlashUtil writing rootfs with temp path"""

    image_dir, _ = setup_tmp_rootfs_dir_and_file(tmp_path)

    # mock sleep to reduce test time
    monkeypatch.setattr("flash_utils.flash.time.sleep", Mock())

    # normal users probably dont pass image_path, but we are generating a temp path
    sys.argv = ["flash_util.py", "--rootfs", "--image_path", str(image_dir)]
    FlashUtil()

    output = capsys.readouterr()
    assert "Power on board. Make sure boot2 strap is NOT on." in output.out

    mock_serial_port.assert_called_once_with(port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE)
    mock_popen.assert_called_once()

    # assert fastboot setup (specific to rootfs flashing)
    mock_serial_port.return_value.write.assert_any_call("\rfastboot udp\r".encode())


def test_image_rootfs_write(
    capsys: pytest.CaptureFixture[str], tmp_path, mock_serial_port, mock_popen, monkeypatch
):
    """Test FlashUtil writing rootfs with --image_rootfs <PATH>"""

    _, rootfs_file = setup_tmp_rootfs_dir_and_file(tmp_path)

    # mock sleep to reduce test time
    monkeypatch.setattr("flash_utils.flash.time.sleep", Mock())

    # normal users probably dont pass image_path, but we are generating a temp path
    sys.argv = ["flash_util.py", "--image_rootfs", str(rootfs_file)]
    FlashUtil()

    output = capsys.readouterr()
    assert "Power on board. Make sure boot2 strap is NOT on." in output.out

    mock_serial_port.assert_called_once_with(port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE)
    mock_popen.assert_called_once()

    # assert fastboot setup (specific to rootfs flashing)
    mock_serial_port.return_value.write.assert_any_call("\rfastboot udp\r".encode())


def setup_tmp_bootloader_dir_and_files(tmp_path):
    """
    Creates temporary bootloader directory and files for testing
    """

    flash_writer_content = "TEMP FLASH WRITER FILE DATA"
    bl2_content = "TEMP BL2 FILE DATA"
    fip_content = "TEMP FIP IMAGE DATA"

    print(f"tmp_path type {type(tmp_path)}")

    image_dir = tmp_path / "images"
    image_dir.mkdir()

    flash_writer_image = image_dir / FLASH_WRITER_FILE_DEFAULT
    flash_writer_image.write_text(flash_writer_content)
    bl2_image = image_dir / BL2_FILE_DEFAULT
    bl2_image.write_text(bl2_content)
    fip_image = image_dir / FIP_FILE_DEFAULT
    fip_image.write_text(fip_content)

    return image_dir, flash_writer_image, bl2_image, fip_image


def test_flashing_emmc_bootloader(
    capsys: pytest.CaptureFixture[str], tmp_path, mock_serial_port, monkeypatch
):
    """Test FlashUtil writing bootloader to emmc with images from temp path"""

    image_dir, flash_writer_image, bl2_image, fip_image = setup_tmp_bootloader_dir_and_files(
        tmp_path
    )

    mock_file_write = Mock()
    monkeypatch.setattr("flash_utils.flash.FlashUtil.write_file_to_serial", mock_file_write)

    # mock sleep to reduce test time
    monkeypatch.setattr("flash_utils.flash.time.sleep", Mock())

    # normal users probably dont pass image_path, but we are generating a temp path
    sys.argv = ["flash_util.py", "--bootloader", "--image_path", str(image_dir)]
    FlashUtil()

    output = capsys.readouterr()

    assert "missing" not in output.err.lower()
    assert "Please power on board. Make sure boot2 is strapped.".lower() in output.out.lower()
    # tqdm progress bar prints to stderr by default
    assert "100%" in output.err

    mock_serial_port.assert_called_once_with(port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE)
    mock_serial_port.return_value.write.assert_any_call("EM_E\r".encode())
    mock_serial_port.return_value.write.assert_any_call("EM_SECSD\r".encode())
    mock_serial_port.return_value.write.assert_any_call("EM_W\r".encode())
    mock_serial_port.return_value.read_until.assert_any_call(">".encode())

    mock_file_write.assert_has_calls(
        [call(str(flash_writer_image)), call(str(bl2_image)), call(str(fip_image))]
    )


def test_flashing_qspi_bootloader(
    capsys: pytest.CaptureFixture[str], tmp_path, mock_serial_port, monkeypatch
):
    """Test FlashUtil writing bootloader to qspi with images from temp path"""

    image_dir, flash_writer_image, bl2_image, fip_image = setup_tmp_bootloader_dir_and_files(
        tmp_path
    )

    mock_file_write = Mock()
    monkeypatch.setattr("flash_utils.flash.FlashUtil.write_file_to_serial", mock_file_write)

    # mock sleep to reduce test time
    monkeypatch.setattr("flash_utils.flash.time.sleep", Mock())

    # normal users probably dont pass image_path, but we are generating a temp path
    sys.argv = ["flash_util.py", "--bootloader", "--qspi", "--image_path", str(image_dir)]
    FlashUtil()

    output = capsys.readouterr()

    assert "missing" not in output.err.lower()
    assert "Please power on board. Make sure boot2 is strapped.".lower() in output.out.lower()
    # tqdm progress bar prints to stderr by default
    assert "100%" in output.err

    mock_serial_port.assert_called_once_with(port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE)

    # assert QSPI cleared
    mock_serial_port.return_value.write.assert_any_call("\rXCS\r".encode())

    # assert QSPI Being written to
    mock_serial_port.return_value.write.assert_any_call("XLS2\r".encode())
    mock_serial_port.return_value.read_until.assert_any_call(">".encode())

    mock_file_write.assert_has_calls(
        [call(str(flash_writer_image)), call(str(bl2_image)), call(str(fip_image))]
    )
