#!/usr/bin/python3
"""Platform agnostic utility to flash Avnet RZBoard V2L."""

from flash_utils.flash import FlashUtil

def main():
    """Construct FlashUtil, beginning the flashing process."""
    FlashUtil()


if __name__ == "__main__":
    main()
