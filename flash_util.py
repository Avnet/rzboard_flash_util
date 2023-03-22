#!/usr/bin/python3

# Imports
import serial
import argparse
import time
import os
from subprocess import Popen, PIPE, CalledProcessError

class FlashUtil:
	def __init__(self):
		self.__scriptDir = os.getcwd()
		
		self.__setupArgumentParser()
		self.__setupSerialPort()
		
		if self.__args.bootloader:
			self.__writeBootloader()
		elif self.__args.rootfs:
			self.__writeSystemImage()
		elif self.__args.full:
			self.__writeBootloader()
			self.__writeSystemImage()
		else:
			self.__interactive()
		
	# Setup CLI parser
	def __setupArgumentParser(self):
		# Create parser
		self.__parser = argparse.ArgumentParser(description='Utility to flash Avnet RZBoard.')
		
		# Add arguments
		
		# Serial port arguments
		self.__parser.add_argument('--serial_port', default="/dev/ttyUSB0", dest='serialPort', action='store')
		self.__parser.add_argument('--serial_port_baud', default=115200, dest='baudRate', action='store', type=int)
		
		# Images
		self.__parser.add_argument('--image_dir', default=f"{self.__scriptDir}/../../../build/tmp/deploy/images/rzboard/", dest="imageDir", action='store', type=str)
		self.__parser.add_argument('--image_writer', default="Flash_Writer_SCIF_rzboard.mot", dest="flashWriterImage", action="store", type=str)
		self.__parser.add_argument('--image_bl2', default="bl2_bp-rzboard.srec", dest="bl2Image", action="store", type=str)
		self.__parser.add_argument('--image_fip', default="fip-rzboard.srec", dest="fipImage", action="store", type=str)
		self.__parser.add_argument('--image_rootfs', default="avnet-core-image-rzboard.wic", dest="rootfsImage", action="store", type=str)
		
		# Networking 
		self.__parser.add_argument('--static_ip', default="", dest="staticIP", action='store')
		
		# Commands
		self.__parser.add_argument('--bootloader', default=False, action="store_true", dest="bootloader")
		self.__parser.add_argument('--rootfs', default=False, action="store_true", dest="rootfs")
		self.__parser.add_argument('--full', default=False, action="store_true", dest="full")
		
		# Parse arguments
		self.__args = self.__parser.parse_args()
	
	# Function to make script interactive
	def __interactive(self):
		print('Interactive mode.')
	
	# Setup Serial Port
	def __setupSerialPort(self):
		try:
			self.__serialPort = serial.Serial(port=self.__args.serialPort, baudrate = self.__args.baudRate)
		except:
			die(msg='Unable to open serial port.')

	# Function to write bootloader
	def __writeBootloader(self):
		print("Please power on board. Make sure boot2 is strapped.")
		
		# Read lines from serial port
		while True:
			line = self.__serialPort.readline()
			
			# Wait for serial to be ready to receive file
			if "please send !" in line.decode():
				break
			
		print('Writing Flash Writer application.')
		self.__writeFileToSerial(self.__args.imageDir + self.__args.flashWriterImage)
		
		# TODO: Wait for '>' instead of just time based.
		time.sleep(2)
		self.__serialPort.write("\rEM_E\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("1\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("\rEM_W\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("1\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("1\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("11E00\r".encode())
		
		time.sleep(2)
		print('Writing bl2 image.')
		self.__writeFileToSerial(self.__args.imageDir + self.__args.bl2Image)
		
		time.sleep(2)
		self.__serialPort.write("\rEM_W\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("1\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("100\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("00000\r".encode())
		
		time.sleep(2)
		print("Writing FIP image.")
		self.__writeFileToSerial(self.__args.imageDir + self.__args.fipImage)
		
		time.sleep(2)
		self.__serialPort.write("\rEM_SECSD\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("B1\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("2\r".encode())
		
		time.sleep(2)
		self.__serialPort.write("\rEM_SECSD\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("B3\r".encode())
		
		time.sleep(1)
		self.__serialPort.write("8\r".encode())
	
	# Function to write system image over fastboot
	def __writeSystemImage(self):
		print("Power on board. Make sure boot2 strap is NOT on.")
		print("Waiting for device...")
		
		# Interrupt boot sequence
		self.__serialPort.read_until("Hit any key to stop autoboot:".encode())
		self.__writeSerialCmd("y")

		# Wait a bit
		time.sleep(1)
		
		# Set static ip or attempt to get ip from dhcp
		if self.__args.staticIP:
			self.__writeSerialCmd("\rsetenv ipaddr {self.__args.staticIP}")
			time.sleep(1)
		else:
			print('Waiting for device to be assigned IP address...')
			self.__writeSerialCmd("\rsetenv autoload no; dhcp")
			self.__serialPort.read_until("DHCP client bound".encode())
			time.sleep(1)
			
		# Put device into fastboot mode
		print('Putting device into fastboot mode')
		self.__writeSerialCmd("\rfastboot udp")
		self.__serialPort.read_until("Listening for fastboot command on ".encode())
		self.__deviceIPAddr = self.__serialPort.readline().decode().replace('\n', '').replace('\r', '')
		
		# Run fastboot
		with Popen(f'{self.__scriptDir}/adb/platform-tools/fastboot -s udp:{self.__deviceIPAddr} -v flash rawimg {self.__args.imageDir + self.__args.rootfsImage}', shell=True, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
			for line in p.stdout:
				print(line, end='')
	
		if p.returncode != 0:
			die("Failed to flash rootfs.")
	
	def __writeSerialCmd(self, cmd):
		self.__serialPort.write(f'{cmd}\r'.encode())
		
	# Function to write file over serial
	def __writeFileToSerial(self, file):
		with open(file, "rb") as f:
			self.__serialPort.write(f.read())
			f.close()
	
	# Function to wait and print contents of serial buffer
	def __serialRead(self, cond="\n", print=False):
		buf = self.__serialPort.read_until(cond.encode())
		
		if print:
			print(f'{buf.decode()}')
			
# Util function to die with error
def die(msg="", code=1):
	print(f'Error: {msg}')
	exit(code)

def main():
	flashUtil = FlashUtil()
	
if __name__ == "__main__":
	main()