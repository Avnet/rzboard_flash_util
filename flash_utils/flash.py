#!/usr/bin/python3
"""Platform agnostic utility to flash Avnet RZBoard V2L."""

# Imports
import argparse
import os
import sys
import time
import zipfile
from subprocess import PIPE, Popen

import serial
from tqdm import tqdm

from . import __version__

FLASH_WRITER_FILE_DEFAULT = "Flash_Writer_SCIF_rzboard.mot"
BL2_FILE_DEFAULT = "bl2_bp-rzboard.srec"
FIP_FILE_DEFAULT = "fip-rzboard.srec"
CORE_IMAGE_FILE_DEFAULT = "avnet-core-image-rzboard.wic"


class FlashUtil:
    """
    A utility class for flashing an Avnet RZBoard with a bootloader
    and/or rootfs image.

    Usage:
    - Instantiate the class to parse command line arguments and flash
      the specified image(s).
    """

    # pylint: disable=too-many-instance-attributes
    # reasonable number of instance variables given the files we need to flash
    def __init__(self):
        # Get the absolute path to the main script,
        # that way you can call flash_rzboard.py from anywhere
        self.__script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.flash_writer_image = f"{self.__script_dir}/{FLASH_WRITER_FILE_DEFAULT}"
        self.bl2_image = f"{self.__script_dir}/{BL2_FILE_DEFAULT}"
        self.fip_image = f"{self.__script_dir}/{FIP_FILE_DEFAULT}"
        self.rootfs_image = f"{self.__script_dir}/{CORE_IMAGE_FILE_DEFAULT}"

        argparser = self.argparse_and_override_defaults()

        bootloader_override = (
            self.__args.flash_writer_image_override
            and self.__args.bl2_image_override
            and self.__args.fip_image_override
        )

        if self.__args.bootloader or bootloader_override:
            self.__setup_serial_port()
            self.write_bootloader()
        elif self.__args.rootfs or self.__args.rootfs_image_override:
            self.__setup_serial_port()
            self.write_system_image()
        elif self.__args.full:
            self.__setup_serial_port()
            self.write_bootloader()
            self.write_system_image()
        else:
            argparser.error(
                f"Please specify which image(s) to flash.\n\nv{__version__} Examples:\n\t"
                "\n\tUsing default path of files in flash_rzboard.py dir\n\t"
                "./flash_util.py --bootloader\n\t"
                "./flash_util.py --bootloader --qspi\n\t"
                "./flash_util.py --rootfs\n\t"
                "./flash_util.py --full\n\t"
                "\n\tSpecifying image path(s):\n\t"
                "./flash_util.py --image_rootfs <PATH_TO_ROOTFS_IMAGE>\n\t"
                "./flash_util.py --full --image_path <PATH_TO_IMAGES_DIR>\n\t"
                "\n\tNote: when providing writer/bl2/fip image paths, you must provide"
                " all three:\n\t"
                "./flash_util.py --image_writer <PATH> --image_bl2 <PATH> --image_fip <PATH>\n\t"
            )

    def handle_path_overrides(self):
        """
        Handles any path overrides specified via command line arg.
        """

        if self.__args.flash_writer_image_override:
            self.flash_writer_image = self.__args.flash_writer_image_override
        if self.__args.bl2_image_override:
            self.bl2_image = self.__args.bl2_image_override
        if self.__args.fip_image_override:
            self.fip_image = self.__args.fip_image_override
        if self.__args.rootfs_image_override:
            self.rootfs_image = self.__args.rootfs_image_override

        if self.__args.image_path:
            print(f"Overwriting default image paths with {self.__args.image_path}.")
            self.flash_writer_image = f"{self.__args.image_path}/{FLASH_WRITER_FILE_DEFAULT}"
            self.bl2_image = f"{self.__args.image_path}/{BL2_FILE_DEFAULT}"
            self.fip_image = f"{self.__args.image_path}/{FIP_FILE_DEFAULT}"
            self.rootfs_image = f"{self.__args.image_path}/{CORE_IMAGE_FILE_DEFAULT}"

    def argparse_and_override_defaults(self):
        """
        Sets up the argument parser before parsing the command line arguments
        and setting FlashUtil vars.

        Returns:
            argparse.ArgumentParser: The argument parser.
        """

        argparser = argparse.ArgumentParser(
            description="Utility to flash Avnet RZBoard.\n",
            epilog="Example:\n\t./flash_util.py --bootloader",
        )

        # Add arguments
        # Commands
        argparser.add_argument(
            "--bootloader",
            default=False,
            action="store_true",
            dest="bootloader",
            help=(
                "Flash bootloader only (assumes files in <SCRIPT_DIR>). Requires"
                f" {FLASH_WRITER_FILE_DEFAULT}, {BL2_FILE_DEFAULT}, and {FIP_FILE_DEFAULT}"
            ),
        )
        argparser.add_argument(
            "--rootfs",
            default=False,
            action="store_true",
            dest="rootfs",
            help=f"Flash rootfs only (defaults to: <SCRIPT_DIR>/{CORE_IMAGE_FILE_DEFAULT}).",
        )
        argparser.add_argument(
            "--full",
            default=False,
            action="store_true",
            dest="full",
            help=(
                "Flash bootloader and rootfs (assumes files in <SCRIPT_DIR>)."
                f" Requires {FLASH_WRITER_FILE_DEFAULT}, {BL2_FILE_DEFAULT}, {FIP_FILE_DEFAULT}"
                f" and {CORE_IMAGE_FILE_DEFAULT}"
            ),
        )

        # Serial port arguments
        argparser.add_argument(
            "--serial_port",
            default="/dev/ttyUSB0",
            dest="serialPort",
            action="store",
            help="Serial port used to talk to board (defaults to: /dev/ttyUSB0).",
        )
        argparser.add_argument(
            "--serial_port_baud",
            default=115200,
            dest="baudRate",
            action="store",
            type=int,
            help="Baud rate for serial port (defaults to: 115200).",
        )

        # Images
        argparser.add_argument(
            "--image_writer",
            dest="flash_writer_image_override",
            action="store",
            type=str,
            help="Path to Flash Writer image",
        )
        argparser.add_argument(
            "--image_bl2",
            dest="bl2_image_override",
            action="store",
            type=str,
            help="Path to bl2 image.",
        )
        argparser.add_argument(
            "--image_fip",
            dest="fip_image_override",
            action="store",
            type=str,
            help="Path to FIP image.",
        )
        argparser.add_argument(
            "--image_rootfs",
            dest="rootfs_image_override",
            action="store",
            type=str,
            help="Path to rootfs.",
        )
        argparser.add_argument(
            "--image_path",
            dest="image_path",
            action="store",
            type=str,
            help=(
                "Absolute path to images dir"
                "(used only with --bootloader, --rootfs, or --full to overwrite <SCRIPT_DIR>)."
            ),
        )

        # Networking
        argparser.add_argument(
            "--static_ip",
            default="",
            dest="staticIP",
            action="store",
            help="IP Address assigned to board during flashing.",
        )

        # Target
        argparser.add_argument(
            "--qspi",
            action="store_true",
            help="Flash to QSPI (default is eMMC).",
        )

        # Debug / help
        argparser.add_argument(
            "--debug", action="store_true", help="Enable debug output (buffer printing)"
        )
        argparser.add_argument(
            "--version", "-v", action="version",
            help="Show version.", version=f"%(prog)s {__version__},"
        )

        self.__args = argparser.parse_args()
        self.handle_path_overrides()

        return argparser

    # Setup Serial Port
    def __setup_serial_port(self):
        try:
            self.__serial_port = serial.Serial(
                port=self.__args.serialPort, baudrate=self.__args.baudRate
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            die(
                msg=(
                    f"Unable to open serial port. Error: {e}\n"
                    "Do you have sufficient permissions? Is your device connected?"
                )
            )

    # Function to write bootloader
    def write_bootloader(self):
        """Write bootloader (flashWriter, bl2, fip images) to board."""

        self.check_bootloader_files()

        # Wait for device to be ready to receive image.
        print("Please power on board. Make sure boot2 is strapped.")
        with tqdm(total=1) as progress_bar:
            self.__serial_port.read_until("please send !".encode())
            progress_bar.update(1)

        print("Flashing bootloader, this will take a few minutes...")
        with tqdm(total=4) as progress_bar:
            self.flash_flash_writer()
            progress_bar.update(1)

            if self.__args.qspi:
                self.flash_bootloader_qspi(progress_bar)
            else:
                self.flash_bootloader_emmc(progress_bar)

        print("Done flashing bootloader!")

    def flash_bootloader_emmc(self, progress_bar):
        """Flashes the bootloader to the eMMC memory."""

        self.flash_erase_emmc()
        self.setup_emmc_flash()
        progress_bar.update(1)
        self.flash_bl2_image_emmc()
        progress_bar.update(1)
        self.flash_fip_image_emmc()
        progress_bar.update(1)

    def flash_fip_image_emmc(self):
        """
        Flashes fip image to eMMC

        returns:
            None
        """

        self.write_serial_cmd("EM_W")

        self.wait_for_serial_read(")>", print_buffer=self.__args.debug)
        self.write_serial_cmd("1")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("100")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("00000")

        self.wait_for_serial_read("please send !", print_buffer=self.__args.debug)
        self.write_file_to_serial(self.fip_image)
        self.wait_for_serial_read("EM_W Complete!", print_buffer=self.__args.debug)

    def flash_bl2_image_emmc(self):
        """
        Flashes bl2 image to QSPI

        returns:
            None
        """

        self.write_serial_cmd("EM_W")

        self.wait_for_serial_read(">", print_buffer=self.__args.debug)
        self.write_serial_cmd("1")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("1")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("11E00")

        self.wait_for_serial_read("please send !", print_buffer=self.__args.debug)
        self.write_file_to_serial(self.bl2_image)
        self.wait_for_serial_read("EM_W Complete!", print_buffer=self.__args.debug)

    def flash_flash_writer(self):
        """
        Writes the Flash Writer application to the serial port.

        Note
        ----
        This operation is common to eMMC and QSPI flashing.
        """

        self.write_file_to_serial(self.flash_writer_image)
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)

    def setup_emmc_flash(self):
        """
        Modify EXT_CSD register of eMMC to enable eMMC boot

        Note
        ----
        Prerequisite for eMMC flashing bootloaders.
        """
        self.write_serial_cmd("EM_SECSD")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("b1")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("2")
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)
        self.write_serial_cmd("EM_SECSD")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("b3")
        self.wait_for_serial_read(":", print_buffer=self.__args.debug)
        self.write_serial_cmd("8")

    def flash_erase_emmc(self):
        """
        Erases the eMMC flash memory.
        """
        self.write_serial_cmd("EM_E")
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)
        self.write_serial_cmd("1")
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)

    def flash_bootloader_qspi(self, progress_bar):
        """
        Prepares QSPI for flashing before flashing bootloader files.
        """

        self.flash_erase_qspi()
        progress_bar.update(1)
        self.flash_bl2_image_qspi()
        progress_bar.update(1)
        self.flash_fip_image_qspi()
        progress_bar.update(1)

    def flash_erase_qspi(self):
        """
        Clears QSPI flash
        """
        self.write_serial_cmd("XCS", prefix="\r")
        self.wait_for_serial_read("Clear OK?", print_buffer=self.__args.debug)
        self.write_serial_cmd("y")
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)

    def flash_bl2_image_qspi(self):
        """
        Flashes bl2 image to QSPI
        """

        self.write_serial_cmd("XLS2")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("11E00")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("00000")

        self.wait_for_serial_read("please send !", print_buffer=self.__args.debug)

        self.write_file_to_serial(self.bl2_image)

    def flash_fip_image_qspi(self):
        """
        Flashes fip image to QSPI
        """

        self.write_serial_cmd("XLS2")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("00000")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("1D200")

        self.wait_for_serial_read("please send", print_buffer=self.__args.debug)

        self.write_file_to_serial(self.fip_image)

    def check_bootloader_files(self):
        """
        Checks if the required bootloader files exist in the specified file paths.
        Die if any of the files are missing.
        """

        if not os.path.isfile(self.flash_writer_image):
            die(f"Missing flash writer image: {self.flash_writer_image}")

        if not os.path.isfile(self.bl2_image):
            die(f"Missing bl2 image: {self.bl2_image}")

        if not os.path.isfile(self.fip_image):
            die(f"Missing FIP image: {self.fip_image}")

    # Function to write system image over fastboot
    def write_system_image(self):
        """Write system image (containing kernel, dtb, and rootfs) to board.)"""
        # Check for system image
        if self.rootfs_image is None:
            die("No rootfsImage argument")

        if not os.path.isfile(self.rootfs_image):
            die(f"Missing system image: {self.rootfs_image}")

        self.__extract_adb()

        print("Power on board. Make sure boot2 strap is NOT on.")
        print("Waiting for device...")

        # Interrupt boot sequence
        self.__serial_port.read_until("Hit any key to stop autoboot:".encode())
        self.write_serial_cmd("y")

        time.sleep(1)

        # Set static ip or attempt to get ip from dhcp
        if self.__args.staticIP:
            print(f"Setting static IP: {self.__args.staticIP}")
            self.write_serial_cmd(f"\rsetenv ipaddr {self.__args.staticIP}")
        else:
            print("Waiting for device to be assigned IP address...")
            self.write_serial_cmd("\rsetenv autoload no; dhcp")
            self.__serial_port.read_until("DHCP client bound".encode())

        time.sleep(1)

        # Put device into fastboot mode
        print("Putting device into fastboot mode")
        self.write_serial_cmd("\rfastboot udp")
        self.__serial_port.read_until("Listening for fastboot command on ".encode())
        print("Device in fastboot mode")
        self.__device_ip_address = (
            self.__serial_port.readline().decode().replace("\n", "").replace("\r", "")
        )

        fastboot_path = f"{self.__script_dir}/adb/platform-tools/fastboot"
        fastboot_args = f"-s udp:{self.__device_ip_address} -v flash rawimg {self.rootfs_image}"
        with Popen(
            fastboot_path + " " + fastboot_args,
            shell=True,
            stdout=PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as fastboot_process:
            for line in fastboot_process.stdout:
                print(line, end="")

        if fastboot_process.returncode != 0:
            die("Failed to flash rootfs.")

    def write_serial_cmd(self, cmd, prefix=""):
        """
        Writes a command to the serial port.

        Args:
            cmd (str): The command to write to the serial port.
            prefix (str): What to prepend before the command. Useful for prepending
                carriage returns.
        """
        self.__serial_port.write(f"{prefix}{cmd}\r".encode())

    # Function to write file over serial
    def write_file_to_serial(self, file):
        """
        Writes the contents of a file to the serial port.

        Args:
            file (str): The path to the file to be written.

        Returns:
            None
        """
        with open(file, "rb") as transmit_file:
            self.__serial_port.write(transmit_file.read())
            transmit_file.close()

    def wait_for_serial_read(self, cond="\n", print_buffer=False):
        """
        Reads data from the serial port until the specified condition is met.

        Args:
            cond (str): The condition to wait for before returning the data.
                Defaults to newline character.
            print_buffer (bool): Whether to print the read data to the console. Defaults to False.

        Returns:
            bytes: The data read from the serial port.
        """
        buf = self.__serial_port.read_until(cond.encode())

        if print_buffer:
            print(f"{buf.decode()}")

        return buf

    # Function to check and extract adb
    def __extract_adb(self):
        archive_path = ""
        # Extract platform tools if not already extracted
        if not os.path.exists(f"{self.__script_dir}/platform-tools"):
            if sys.platform == "linux":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-linux.zip"
            elif sys.platform == "darwin":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-darwin.zip"
            elif sys.platform == "win32":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-windows.zip"
            else:
                die("Unknown platform.")

        if not os.path.isfile(archive_path):
            die("Can't find adb for your system. \
                This util expects to be ran from the flash_rzboard.py dir.")

        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(f"{self.__script_dir}/adb")

        if sys.platform != "win32":
            os.chmod(f"{self.__script_dir}/adb/platform-tools/fastboot", 755)


def die(msg="", code=1):
    """
    Prints an error message and exits the program with the given exit code.
    """
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)
