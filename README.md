# RZBoard Flash Utility

This is a platform agnostic utility used to flash the [RZBoard](https://www.avnet.com/wps/portal/us/products/avnet-boards/avnet-board-families/rzboard-v2l/). It can be used to flash the eMMC with both the bootloader(s) and system image.

## Install Python

This utility is written in python3 with dependencies managed using pip. 

### Ubuntu Installation

On Ubuntu, python3 and pip can be installed by running:
```bash
sudo apt install -y python3 python3-pip
```

### Other OS

Mac and Windows can install by using one of the manage package managers for your platform or by downloading an installer from [https://www.python.org/downloads/](https://www.python.org/downloads/).

## Clone & Install Dependencies
```bash
git clone https://github.com/erstoddard/rzboard_flash_util.git
```

The script has a couple dependencies that can be installed by running the following:
```bash
cd rzboard_flash_util
pip3 install -r requirements.txt
```

## Usage

Running `./flash_util.py -h` will print usage information.  A more detailed description of the arguments is detailed below.

### Specifying What to Flash

The utility can be used to flash the bootloader, rootfs, or both at the same time:

```bash
./flash_util.py --bootloader # Flash bootloader only
./flash_util.py --rootfs     # Flash system image only
./flash_util.py --full       # Flash bootloader and system image
```

### Options

#### Serial Port
By default, the utility uses `/dev/ttyUSB0` as the serial port to communicate with the RZBoard. This can be changed with `--serial_port`.  Additionally the default baud rate of `115200` can be chaged with `--serial_port_baud`:

```bash
./flash_util --serial_port DESIRED_SERIAL_PORT --serial_port_baud DESIRED_BAUD_RATE
```

#### Image Locations

By default, the utility looks for the required images in the directory that `flash_util.py` is located. The required images, along with the override flag and default location and name is listed below:

| Image | Flag | Default | Description |
|-|-|-|-|
| Flash Image Writer | `--image_writer` | `<SCRIPT_DIR>/Flash_Writer_SCIF_rzboard.mot` | Application loaded in to received bootloader images over serial and write to eMMC |
| BL2 Image | `--image_bl2` | `<SCRIPT_DIR>/bl2_bp-rzboard.srec` | Bootloader |
| FIP Image | `--image_fip` | `<SCRIPT_DIR>/fip-rzboard.srec` | Bootloader, ARM TFA (Trusted Firmware-A) BL31, and u-boot in a combined image |
| System Image | `--image_rootfs` | `<SCRIPT_DIR>/avnet-core-image-rzboard.wic` | Contains the linux kernel, device tree (dtb), and to root filesystem (rootfs) in a minimized format. |

**NOTE:** If only flashing the system image, the image writer, bl2, and FIP images are not required/
