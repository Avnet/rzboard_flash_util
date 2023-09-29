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

    def __init__(self):
        self.__script_dir = os.getcwd()
        self.__setup_argument_parser()

        if self.__args.bootloader:
            self.__setup_serial_port()
            self.write_bootloader()
        elif self.__args.rootfs:
            self.__setup_serial_port()
            self.write_system_image()
        elif self.__args.full:
            self.__setup_serial_port()
            self.write_bootloader()
            self.write_system_image()
        else:
            self.__parser.error(
                "Please specify which image(s) to flash.\n\nExamples:\n\t"
                "./flash_util.py --bootloader\n\t"
                "./flash_util.py --rootfs\n\t"
                "./flash_util.py --full"
            )

    # Setup CLI parser
    def __setup_argument_parser(self):
        # Create parser
        self.__parser = argparse.ArgumentParser(
            description="Utility to flash Avnet RZBoard.\n",
            epilog="Example:\n\t./flash_util.py --bootloader",
        )

        # Add arguments
        # Commands
        self.__parser.add_argument(
            "--bootloader",
            default=False,
            action="store_true",
            dest="bootloader",
            help="Flash bootloader only.",
        )
        self.__parser.add_argument(
            "--rootfs",
            default=False,
            action="store_true",
            dest="rootfs",
            help="Flash rootfs only.",
        )
        self.__parser.add_argument(
            "--full",
            default=False,
            action="store_true",
            dest="full",
            help="Flash bootloader and rootfs.",
        )

        # Serial port arguments
        self.__parser.add_argument(
            "--serial_port",
            default="/dev/ttyUSB0",
            dest="serialPort",
            action="store",
            help="Serial port used to talk to board (defaults to: /dev/ttyUSB0).",
        )
        self.__parser.add_argument(
            "--serial_port_baud",
            default=115200,
            dest="baudRate",
            action="store",
            type=int,
            help="Baud rate for serial port (defaults to: 115200).",
        )

        # Images
        self.__parser.add_argument(
            "--image_writer",
            default=f"{self.__script_dir}/{FLASH_WRITER_FILE_DEFAULT}",
            dest="flashWriterImage",
            action="store",
            type=str,
            help="Path to Flash Writer image"
            f"(defaults to: <SCRIPT_DIR>/{FLASH_WRITER_FILE_DEFAULT}).",
        )
        self.__parser.add_argument(
            "--image_bl2",
            default=f"{self.__script_dir}/{BL2_FILE_DEFAULT}",
            dest="bl2Image",
            action="store",
            type=str,
            help=f"Path to bl2 image (defaults to: <SCRIPT_DIR>/{BL2_FILE_DEFAULT}).",
        )
        self.__parser.add_argument(
            "--image_fip",
            default=f"{self.__script_dir}/{FIP_FILE_DEFAULT}",
            dest="fipImage",
            action="store",
            type=str,
            help=f"Path to FIP image (defaults to: <SCRIPT_DIR>/{FIP_FILE_DEFAULT}).",
        )
        self.__parser.add_argument(
            "--image_rootfs",
            default=f"{self.__script_dir}/{CORE_IMAGE_FILE_DEFAULT}",
            dest="rootfsImage",
            action="store",
            type=str,
            help=f"Path to rootfs (defaults to: <SCRIPT_DIR>/{CORE_IMAGE_FILE_DEFAULT}).",
        )
        self.__parser.add_argument(
            "--image_path",
            dest="image_path",
            action="store",
            type=str,
            help="Absolute path to images dir" \
                 "(used only with --bootloader, --rootfs, or --full to overwrite <SCRIPT_DIR>).",
        )

        # Networking
        self.__parser.add_argument(
            "--static_ip",
            default="",
            dest="staticIP",
            action="store",
            help="IP Address assigned to board during flashing.",
        )

        self.__args = self.__parser.parse_args()

        if self.__args.image_path:
            print(f"Overwriting default image paths with {self.__args.image_path}.")
            self.__args.flashWriterImage = f"{self.__args.image_path}/{FLASH_WRITER_FILE_DEFAULT}"
            self.__args.bl2Image = f"{self.__args.image_path}/{BL2_FILE_DEFAULT}"
            self.__args.fipImage = f"{self.__args.image_path}/{FIP_FILE_DEFAULT}"
            self.__args.rootfsImage = f"{self.__args.image_path}/{CORE_IMAGE_FILE_DEFAULT}"

    # Setup Serial Port
    def __setup_serial_port(self):
        # pylint: disable=locally-disabled, bare-except
        try:
            self.__serial_port = serial.Serial(
                port=self.__args.serialPort, baudrate=self.__args.baudRate
            )
        except:
            die(
                msg="Unable to open serial port. "
                "Do you have sufficient permissions? Is your device connected?"
            )

    # Function to write bootloader
    def write_bootloader(self):
        """Write bootloader (flashWriter, bl2, fip images) to board."""

        # Check for files
        if not os.path.isfile(self.__args.flashWriterImage):
            die("Can't find flash writer image.")

        if not os.path.isfile(self.__args.bl2Image):
            die("Can't find bl2 image.")

        if not os.path.isfile(self.__args.fipImage):
            die("Can't find FIP image.")

        # Wait for device to be ready to receive image.
        print("Please power on board. Make sure boot2 is strapped.")
        self.__serial_port.read_until("please send !".encode())

        # Write flash writer application
        print("Writing Flash Writer application.")
        self.write_file_to_serial(self.__args.flashWriterImage)

        # pylint: disable=locally-disabled, fixme
        # TODO: Wait for '>' instead of just time based.
        time.sleep(2)
        self.__serial_port.write("\rEM_E\r".encode())

        time.sleep(1)
        self.__serial_port.write("1\r".encode())

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
        self.write_file_to_serial(self.__args.bl2Image)

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
        self.write_file_to_serial(self.__args.fipImage)

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

    # Function to write system image over fastboot
    def write_system_image(self):
        """Write system image (containing kernel, dtb, and rootfs) to board.)"""
        # Check for system image
        if self.__args.rootfsImage is None:
            die("No rootfsImage argument")

        if not os.path.isfile(self.__args.rootfsImage):
            die("Can't find system image.")

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
        fastboot_args = (
            f"-s udp:{self.__device_ip_address} " f"-v flash rawimg {self.__args.rootfsImage}"
        )
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

    def write_serial_cmd(self, cmd):
        """
        Writes a command to the serial port.

        Args:
            cmd (str): The command to write to the serial port.

        Returns:
            None
        """
        self.__serial_port.write(f"{cmd}\r".encode())

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

    def serial_read(self, cond="\n", print_buffer=False):
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
    print(f"Error: {msg}")
    sys.exit(code)


def main():
    """Construct FlashUtil, beginning the flashing process."""
    FlashUtil()


if __name__ == "__main__":
    main()
