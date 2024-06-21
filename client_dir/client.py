import base64
import socket
import threading
import time
from queue import Queue
import numpy as np
import cv2
import imutils
from numpy import uint8
from client_vars import *
from concurrent.futures import ThreadPoolExecutor


class Client:
    def __init__(self):
        self.__run = True
        self.__id = 0
        self.__p_audio = pyaudio.PyAudio()
        self.__video_frames = Queue()
        self.__cond_send_frame = threading.Condition()
        self.__is_mute = False
        self.__is_cam_close = False
        self.__cond_mute = threading.Condition()
        self.__cond_close_cam = threading.Condition()
        self.t = []
        self.__setup_sockets()

    def __setup_sockets(self):
        self.__tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__tcp_sock.connect(SERVER_TCP_ADDRESS)

        self.__udp_video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.__udp_video_sock.connect(SERVER_UDP_VIDEO_ADDRESS)

        self.__udp_audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_audio_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, CHUNK * 4)
        self.__udp_audio_sock.connect(SERVER_UDP_AUDIO_ADDRESS)

    def start(self):
        print("Booting up client")
        self.__client_main()

    def close(self):
        print("Shutting down client")
        self.__run = False
        self.__tcp_sock.close()
        self.__udp_video_sock.close()
        self.__udp_audio_sock.close()
        self.__p_audio.terminate()
        with self.__cond_send_frame:
            self.__cond_send_frame.notify()
        return

    def __commands_input(self):
        help = '\r\nList of commands:\nmute\nstopcam\nquit'

        while self.__run:
            command = input("\nEnter a command ('help' for help)\n")
            if len(command) > COMMAND_SIZE:
                print(f"No command is over {COMMAND_SIZE} letters, try again")
                continue
            command = command.strip().lower()
            if command == 'help':
                print(help)
                continue
            if command == 'mute':
                self.__mute()
                continue
            if command == 'stopcam':
                self.__turn_off_camera()
                continue
            if command == 'quit':
                self.close()
                break
        print("Stopped commands")
        return

    def __mute(self):
        print('Muted')
        unmute_command = 'unmute'
        self.__is_mute = True

        while self.__is_mute:
            msg = input(f"Type '{unmute_command}' to unmute\n")

            if len(msg) != len(unmute_command):
                print("Try again\n")
                continue
            if msg == unmute_command:
                self.__is_mute = False
                with self.__cond_mute:
                    self.__cond_mute.notify()
        return

    def __turn_off_camera(self):
        print("Closing camera")
        turn_on_command = "startcam"
        self.__is_cam_close = True
        pack_format = '4sQQ'
        self.__tcp_sock.send(struct.pack(pack_format, b'CLOS', self.__id >> 64, self.__id & ((1 << 64) - 1)))
        while self.__is_cam_close:
            msg = input(f"Type '{turn_on_command} to turn on the camera\n")

            if len(msg) != len(turn_on_command):
                print("Try again\n")
                continue
            if msg == turn_on_command:
                self.__is_cam_close = False
                with self.__cond_close_cam:
                    self.__cond_close_cam.notify()

        return

    def __tcp_recv(self):
        print("TCP receive is on")
        unpack_format = '4sQQ'
        msg = self.__tcp_sock.recv(BUFF_SIZE)
        while msg:
            data = struct.unpack(unpack_format, msg)
            client_id = data[1] << 64 | data[2]

            if data[0] == b'LEFT':
                print(f'deleting {client_id}')
                cv2.destroyWindow(f'{client_id}')
                cv2.waitKey(1)
            elif data[0] == b'NEWC':
                cv2.namedWindow(f'{client_id}')

            msg = self.__tcp_sock.recv(BUFF_SIZE)
        print("TCP receive is off")
        return

    def __udp_video_recv(self):
        print("UDP video receive is on")
        while self.__run:
            data = self.__udp_video_sock.recvfrom(BUFF_SIZE)[0]

            header = struct.unpack("HIBQQ", data[: HEADER_SIZE])
            client_id = header[3] << 64 | header[4]
            try:
                data = base64.b64decode(data[HEADER_SIZE:], ' /')
                data = np.frombuffer(data, dtype=uint8)
                frame = cv2.imdecode(data, 1)
                cv2.imshow(f'{client_id}', frame)
                cv2.waitKey(1)
            except:
                print('PACKET LOST')
        print("Stopped receiving video")
        return

    def __udp_send_video_frames(self):
        while self.__run:
            with self.__cond_send_frame:
                self.__cond_send_frame.wait()
            try:
                frame = self.__video_frames.get_nowait()
            except:
                continue
            dump, size = frame[0], frame[1]
            msg = struct.pack("HIBQQ", size, 0, 0, self.__id >> 64, self.__id & ((1 << 64) - 1)) + dump
            self.__udp_video_sock.sendto(msg, SERVER_UDP_VIDEO_ADDRESS)
        print("Stopped sending video")
        return

    def __audio_input(self):
        print("Audio input is on")
        stream = self.__p_audio.open(format=FORMAT, channels=CHANNELS,
                                     rate=RATE, input=True,
                                     frames_per_buffer=CHUNK)
        while self.__run:
            if self.__is_mute:
                stream.stop_stream()
                while self.__is_mute:
                    time.sleep(1)
                print('Unmuted')
                stream.start_stream()

            try:
                data = stream.read(CHUNK)
                self.__udp_audio_sock.sendto(base64.b64encode(data), SERVER_UDP_AUDIO_ADDRESS)

            except:
                print("Audio frame failed")
                continue
        print("Audio input is off")
        return

    def __audio_output(self):
        print("Audio output is on")
        stream = self.__p_audio.open(format=FORMAT, channels=CHANNELS,
                                     rate=RATE, output=True,
                                     frames_per_buffer=CHUNK)

        while self.__run:

            try:
                data = self.__udp_audio_sock.recvfrom(BUFF_SIZE)[0]
                data = base64.b64decode(data, ' /')
                stream.write(data)

            except:
                print('Audio packet failed')
        print("Audio output is off")
        return

    def __video_output(self):
        cap = cv2.VideoCapture(0)
        window_name = f'{self.__id}'
        cv2.namedWindow(window_name)
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 90]
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        processing_fps = 30
        skip_rate = 1
        frame_counter = 0

        if video_fps > processing_fps:
            skip_rate = round(video_fps / processing_fps)

        while self.__run:
            _ = cap.grab()
            frame_counter += 1

            if frame_counter % skip_rate != 0:
                continue

            _, frame = cap.retrieve()
            frame = imutils.resize(frame, width=WIDTH, height=HEIGHT)
            frame = cv2.flip(frame, 1)
            cv2.imshow(window_name, frame)
            cv2.waitKey(1)
            try:
                frame = base64.b64encode(
                    cv2.imencode('.jpg', frame, encode_param)[1])
                self.__video_frames.put_nowait((frame, len(frame)))
                with self.__cond_send_frame:
                    self.__cond_send_frame.notify()
            except:
                print("No space in frame queue")
            if self.__is_cam_close:
                cap.release()
                while self.__is_cam_close:
                    time.sleep(0.5)
                cap = cv2.VideoCapture(0)
                print("Camera back on")
                continue
        cap.release()
        cv2.destroyAllWindows()

        print("Camera stopped capturing")
        return

    def __thread_debug(self, t):
        while self.__run:
            for tr in t:
                if not tr.running():
                    print(tr)

    def __client_main(self):
        cv2.startWindowThread()
        print("Receiving ID")
        self.__id = int.from_bytes(self.__tcp_sock.recv(ID_SIZE), "big")

        thread_functions = [self.__video_output,
                            self.__tcp_recv,
                            self.__udp_video_recv,
                            self.__udp_send_video_frames,
                            self.__audio_output,
                            self.__audio_input,
                            self.__commands_input
                            ]
        t = []
        with ThreadPoolExecutor(max_workers=7) as executor:
            for func in thread_functions:
                t.append((executor.submit(func), str(func)))


if __name__ == "__main__":
    cl = Client()
    cl.start()
    print("Closing the client")
