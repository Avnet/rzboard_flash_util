"""
This module contains unit tests for the FlashUtil class in the flash_utils.flash module.
"""

import sys

import pytest

from flash_utils.flash import FlashUtil


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
def test_good_params_missing_images(capsys: pytest.CaptureFixture[str], flash_option):
    """Test FlashUtil with good parameters, but missing flash files"""

    with pytest.raises(SystemExit):
        # SystemExit expected for missing flash file
        sys.argv = ["flash_util.py", flash_option]
        FlashUtil()
    output = capsys.readouterr()

    assert output is not None
    assert "missing" in output.err.lower() and "image" in output.err.lower()
