# Changelog

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-24

### Added

- Initial release 🌱 of the rzboard_flash_util  for [RZBoard](https://github.com/Avnet/RZ-V2L-HUB)
- Features include:
  - eMMC flashing
    - Bootloaders
    - Linux image
  - QSPI flashing
    - Bootloaders
  - Serial port configuration
  - RZBoard IP configuration for linux image flashing
  - Progress bars
  - Automated [testing / CI](https://github.com/Avnet/rzboard_flash_util/actions)
- Support for...
  - Windows, Mac, Linux (Assume Ubuntu)

### Changed

- Latest commits updated EMMC flashing to use serial handshaking and not sleeps. This means the flash utility waits for the RZBoard to send data before continuing the flash process.
