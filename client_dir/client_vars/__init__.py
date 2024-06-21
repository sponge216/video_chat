import socket
import struct
import pyaudio
import subprocess

subprocess.run(["package_install.bat", ''], shell=True)

SERVER_IPV4_ADDRESS = socket.gethostbyname('your host')
SERVER_PORT = 56432
SERVER_TCP_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT)
SERVER_UDP_VIDEO_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT + 1)
SERVER_UDP_AUDIO_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT + 2)

BUFF_SIZE = 65000
ID_SIZE = 128
HEADER_SIZE = struct.calcsize("HIBQQ")
COMMAND_SIZE = 8
WIDTH = 400
HEIGHT = 400

FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024

"""
Length: short - 16
Offset: int - 32
More: byte - 8
Id: 128


"""
