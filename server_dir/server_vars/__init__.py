import struct
import netifaces as ni
import subprocess

subprocess.run(["package_install.bat", ''], shell=True)
result = subprocess.run('ipconfig', stdout=subprocess.PIPE, text=True).stdout.lower()
scan = 0
ip = ''
for i in result.split('\n'):
    if 'wireless' in i:
        scan = 1
    if scan:
        if 'ipv4' in i:
            ip = i.split(':')[1].strip()
            break

if ip == '':
    iface = ni.gateways()['default'][ni.AF_INET][1]
    ip = ni.ifaddresses(iface)[ni.AF_INET][0]['addr']

SERVER_IPV4_ADDRESS = ip
SERVER_PORT = 56432
SERVER_TCP_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT)
SERVER_UDP_VIDEO_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT + 1)
SERVER_UDP_AUDIO_ADDRESS = (SERVER_IPV4_ADDRESS, SERVER_PORT + 2)

BUFF_SIZE = 65000
HEADER_SIZE = struct.calcsize("HIBQQ")
CHUNK = 1024


"""
Length: short - 16
Offset: int - 32
More: byte - 8
Id: 128


"""
