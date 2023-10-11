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

FLASH_WRITER_FILE_DEFAULT = "Flash_Writer_SCIF_rzboard.mot"
BL2_FILE_DEFAULT = "bl2_bp-rzboard.srec"
FIP_FILE_DEFAULT = "fip-rzboard.srec"
CORE_IMAGE_FILE_DEFAULT = "avnet-core-image-rzboard.wic"


class FlashUtil:
    """
    A utility class for flashing an Avnet RZBoard with a bootloader and/or rootfs image.

    Usage:
    - Instantiate the class to parse command line arguments and flash the specified image(s).
    """

    # pylint: disable=too-many-instance-attributes
    # reasonable number of instance variables given the files we need to flash
    def __init__(self):
        self.__script_dir = os.getcwd()

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
                "Please specify which image(s) to flash.\n\nExamples:\n\t"
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
            None
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

        argparser.add_argument(
            "--debug", action="store_true", help="Enable debug output (buffer printing)"
        )

        self.__args = argparser.parse_args()
        self.handle_path_overrides()

        return argparser

    # Setup Serial Port
    def __setup_serial_port(self):
        # pylint: disable=locally-disabled, bare-except
        try:
            self.__serial_port = serial.Serial(
                port=self.__args.serialPort, baudrate=self.__args.baudRate
            )
        except:
            die(
                msg=(
                    "Unable to open serial port. "
                    "Do you have sufficient permissions? Is your device connected?"
                )
            )

    # Function to write bootloader
    def write_bootloader(self):
        """Write bootloader (flashWriter, bl2, fip images) to board."""

        self.check_bootloader_files()

        # Wait for device to be ready to receive image.
        print("Please power on board. Make sure boot2 is strapped.")
        self.__serial_port.read_until("please send !".encode())

        self.flash_flash_writer()

        if self.__args.qspi:
            self.flash_bootloader_qspi()
        else:
            self.flash_bootloader_emmc()
        
        print("Done flashing bootloader!")

    def flash_bootloader_emmc(self):
        """Flashes the bootloader to the eMMC memory.

        This method sends a series of commands to the serial port to flash the bootloader
        to the eMMC memory.
        """

        self.flash_erase_emmc()

        # pylint: disable=locally-disabled, fixme
        # TODO: Wait for '>' instead of just time based.
        time.sleep(1)
        self.__serial_port.write("\rEM_W\r".encode())

        time.sleep(1)
        self.__serial_port.write("1\r".encode())

        time.sleep(1)
        self.__serial_port.write("1\r".encode())

        time.sleep(1)
        self.__serial_port.write("11E00\r".encode())

        time.sleep(2)
        print("Writing bl2 image.")
        self.write_file_to_serial(self.bl2_image)

        time.sleep(2)
        self.__serial_port.write("\rEM_W\r".encode())

        time.sleep(1)
        self.__serial_port.write("1\r".encode())

        time.sleep(1)
        self.__serial_port.write("100\r".encode())

        time.sleep(1)
        self.__serial_port.write("00000\r".encode())

        time.sleep(2)
        print("Writing FIP image.")
        self.write_file_to_serial(self.fip_image)

        time.sleep(2)
        self.__serial_port.write("\rEM_SECSD\r".encode())

        time.sleep(1)
        self.__serial_port.write("B1\r".encode())

        time.sleep(1)
        self.__serial_port.write("2\r".encode())

        time.sleep(2)
        self.__serial_port.write("\rEM_SECSD\r".encode())

        time.sleep(1)
        self.__serial_port.write("B3\r".encode())

        time.sleep(1)
        self.__serial_port.write("8\r".encode())

    def flash_flash_writer(self):
        """
        Writes the Flash Writer application to the serial port.

        Note
        ----
        This operation is common to eMMC and QSPI flashing.
        """

        print("Writing Flash Writer application.")
        self.write_file_to_serial(self.flash_writer_image)
        time.sleep(1)
        print("Done writing Flash Writer application.")

    def flash_erase_emmc(self):
        """
        Erases the eMMC flash memory.
        """
        time.sleep(2)
        self.__serial_port.write("\rEM_E\r".encode())

        time.sleep(1)
        self.__serial_port.write("1\r".encode())

    def flash_bootloader_qspi(self):
        """
        Prepares QSPI for flashing before flashing bootloader files.

        returns:
            None
        """

        self.flash_erase_qspi()
        self.flash_bl2_image_qspi()
        self.flash_fip_image_qspi()

    def flash_erase_qspi(self):
        """
        Clears QSPI flash

        returns:
            None
        """
        print("Clearing QSPI flash")
        self.write_serial_cmd("XCS", prefix="\r")
        self.wait_for_serial_read("Clear OK?", print_buffer=self.__args.debug)
        self.write_serial_cmd("y")
        self.wait_for_serial_read(">", print_buffer=self.__args.debug)
        print("Done clearing QSPI flash")

    def flash_bl2_image_qspi(self):
        """
        Flashes bl2 image to QSPI

        returns:
            None
        """

        print("Flashing bl2 image to QSPI")
        self.write_serial_cmd("XLS2")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("11E00")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("00000")

        self.wait_for_serial_read("please send !", print_buffer=self.__args.debug)

        self.write_file_to_serial(self.bl2_image)
        print("Done flashing bl2 image to QSPI")

    def flash_fip_image_qspi(self):
        """
        Flashes fip image to QSPI

        returns:
            None
        """

        print("Flashing FIP image to QSPI")
        self.write_serial_cmd("XLS2")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("00000")

        self.wait_for_serial_read("Please Input : H'", print_buffer=self.__args.debug)
        self.write_serial_cmd("1D200")

        self.wait_for_serial_read("please send", print_buffer=self.__args.debug)

        self.write_file_to_serial(self.fip_image)
        print("Done flashing FIP image to QSPI")

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

        # Extract ADB tools
        self.__extract_adb()

        print("Power on board. Make sure boot2 strap is NOT on.")
        print("Waiting for device...")

        # Interrupt boot sequence
        self.__serial_port.read_until("Hit any key to stop autoboot:".encode())
        self.write_serial_cmd("y")

        # Wait a bit
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

        Returns:
            None
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
        # Extract platform tools if not already extracted
        if not os.path.exists(f"{self.__script_dir}/platform-tools"):
            archive_path = ""
            if sys.platform == "linux":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-linux.zip"
            elif sys.platform == "darwin":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-darwin.zip"
            elif sys.platform == "win32":
                archive_path = f"{self.__script_dir}/adb/platform-tools-latest-windows.zip"
            else:
                die("Unknown platform.")

        if not os.path.isfile(archive_path):
            die("Can't find adb for your system.")

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
