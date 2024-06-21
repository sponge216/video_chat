import base64
import concurrent.futures
import socket
import threading
import uuid

import cv2

from server_vars import *
from numpy import zeros, uint8

RANDOM_SIZE = 8


class Server:

    def __init__(self):
        self.__tcp_socket_map = {}
        self.__udp_video_addr_list = []
        self.__udp_audio_addr_list = []
        self.__clients_count = 0
        self.__socket_id_map = {}
        self.__run = True
        self.__setup_sockets()

    def __setup_sockets(self):
        self.__tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__tcp_sock.bind(SERVER_TCP_ADDRESS)

        self.__udp_video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.__udp_video_sock.bind(SERVER_UDP_VIDEO_ADDRESS)

        self.__udp_audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_audio_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.__udp_audio_sock.bind(SERVER_UDP_AUDIO_ADDRESS)

        print(self.__tcp_sock)
        print(self.__udp_video_sock)
        print(self.__udp_audio_sock)

    def start(self):
        print("Booting up server")
        self.__tcp_sock.listen()
        self.__server_main()

    def close(self):
        self.__run = False
        self.__tcp_sock.close()
        self.__udp_video_sock.close()
        self.__udp_audio_sock.close()
        print("Shutting down server")

    def __tcp_accept(self):
        print("TCP accept is on")
        while self.__run:
            client = self.__tcp_sock.accept()
            print(f"New client: {client}")

            client_id = uuid.uuid4()
            client[0].send(client_id.bytes)

            for cl in self.__socket_id_map.items():
                cl[0].send(struct.pack('4sQQ', b'NEWC', client_id.int >> 64, client_id.int & ((1 << 64) - 1)))
                client[0].send(struct.pack('4sQQ', b'NEWC', cl[1].int >> 64, cl[1].int & ((1 << 64) - 1)))

            self.__socket_id_map.update({client[0]: client_id})
            self.__tcp_socket_map.update({client[0]: client[1]})
            self.__clients_count += 1

            tcp_recv_thread = threading.Thread(target=self.__tcp_recv, args=(client[0],))
            tcp_recv_thread.start()
        print("Stopped accepting TCP")

    def __tcp_recv(self, client_sock):
        print(f"TCP receive is on {client_sock}")
        try:
            msg = client_sock.recv(BUFF_SIZE)
        except:
            msg = None
        while msg:

            msg = struct.unpack('4sQQ', msg)
            if msg[0] == b'CLOS':
                black_image = cv2.imencode('.jpg', zeros((400, 400, 3), dtype=uint8))[1]
                black_image = base64.b64encode(black_image)
                black_image_size = len(black_image)
                img_msg = struct.pack('HIBQQ', black_image_size, 0, 0, msg[1],
                                      msg[2]) + black_image
                for cl_addr in self.__udp_video_addr_list:
                    self.__udp_video_sock.sendto(img_msg, cl_addr)

            try:
                msg = client_sock.recv(BUFF_SIZE)
            except:
                break

        print(f"TCP receive is off {client_sock}")

        del self.__tcp_socket_map[client_sock]
        client_id = self.__socket_id_map[client_sock].int
        for client in self.__tcp_socket_map.keys():
            client.send(struct.pack('4sQQ', b'LEFT', client_id >> 64, client_id & ((1 << 64) - 1)))
            del self.__socket_id_map[client_sock]

    def __udp_video_recv(self):
        print("Receiving video")
        while self.__run:
            try:
                data, addr = self.__udp_video_sock.recvfrom(BUFF_SIZE)
            except:
                continue
            if addr not in self.__udp_video_addr_list:
                self.__udp_video_addr_list.append(addr)
            for cl_addr in self.__udp_video_addr_list:
                if cl_addr != addr:
                    self.__udp_video_sock.sendto(data, cl_addr)
        print("Stopped receiving UDP")

    def __udp_audio_recv(self):
        print("Receiving audio")
        while self.__run:
            try:
                data, addr = self.__udp_audio_sock.recvfrom(BUFF_SIZE)
            except:
                continue
            if addr not in self.__udp_audio_addr_list:
                self.__udp_audio_addr_list.append(addr)
            for cl_addr in self.__udp_audio_addr_list:
                if cl_addr != addr:
                    self.__udp_audio_sock.sendto(data, cl_addr)
        print("Stopped receiving UDP")

    def __test_threads(self, t: list[concurrent.futures.Future]):
        print("GOT IN")
        while self.__run:
            for tt in t:
                print(tt)

    def __server_main(self):
        print("Server main is on")
        tcp_accept_thread = threading.Thread(target=self.__tcp_accept, args=())
        udp_video_recv_thread = threading.Thread(target=self.__udp_video_recv, args=())
        udp_audio_thread = threading.Thread(target=self.__udp_audio_recv, args=())

        tcp_accept_thread.start()
        udp_video_recv_thread.start()
        udp_audio_thread.start()


if __name__ == "__main__":
    serv = Server()
    serv.start()
