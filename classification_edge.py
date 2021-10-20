import json
import socket
import threading
import time

settings_file = open("../../settings.json")
settings_data = json.load(settings_file)
settings_file.close()

MAX_CAP = {'red': 10, 'yellow': 10, 'white': 10}

# current repository status 
storing = {'red': 0, 'yellow': 0, 'white': 0}

# accumulate updated item from ev3
item_update = {'red': 0, 'yellow': 0, 'white': 0}

server_connection = object()
EtoE_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lock = threading.Lock()


class edge_to_ev3(threading.Thread):
    def __init__(self, port_num=5003):
        super().__init__()
        self.port_num = port_num
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", self.port_num))
        self.client_socket = object()
        self.connection = 0
        print("init done")

    def run(self):
        self.server_socket.listen(5)
        print("port" + str(self.port_num) + " open & listening")
        self.client_socket, self.address = self.server_socket.accept()
        self.connection = 1
        print("I got a connection from ev3: ", self.address)
        while 1:
            self.ev3comm()
            time.sleep(0.1)

    def ev3comm(self):
        # communicate with ev3, update "storing" & "item_update" variable
        global server_connection
        global item_update
        global storing
        lego = self.wait_command()
        if lego['type'] == "sensor":
            server_connection.log_message(lego)
        elif lego['type'] == "request":
            if (MAX_CAP[lego] > storing[lego]):
                print("capacity available for color " + lego)
                lock.acquire()
                item_update[lego] += 1
                lock.release()
                self.message("True")
                EtoE_sock.send(lego.encode())
            else:
                print("not enough room")
                self.message("False")

    def wait_command(self):
        ret = self.client_socket.recv(512).decode()
        ret = json.loads(ret)
        return ret

    def message(self, data):
        print("edge->cloud : requesting repository status update: " + str(data))
        data_to_server = {'type': 'request', 'data': data}
        data_to_server = json.dumps(data_to_server)
        self.client_socket.send(data_to_server.encode())

    # def message(self, data):
    # 	self.client_socket.send(data.encode())

    def disconnect(self):
        # ASSERT(self.connection == 1)
        self.client_socket.close()
        self.connection = 0
        self.server_socket.close()
        print("socket to ev3: " + str(self.address) + "disconnected")
        self.exit()


class connect_to_server(threading.Thread):
    def __init__(self, port_num=5000):
        super().__init__()
        self.port_num = port_num
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection = 0
        print("init done")

    def run(self):
        self.client_socket.connect((settings_data['cloud']['address'], self.port_num))
        self.connection = 1
        print("connected to server")
        while 1:
            self.store_item()
            time.sleep(5)

    def store_item(self):
        global item_update
        global storing
        lock.acquire()
        storing['red'] += item_update['red']
        storing['white'] += item_update['white']
        storing['yellow'] += item_update['yellow']
        self.message(item_update)
        item_update = {'red': 0, 'yellow': 0, 'white': 0}
        lock.release()

    def message(self, data):
        print("edge->cloud : requesting repository update: " + str(data))
        data_to_server = {'type': 'request', 'data': data}
        data_to_server = json.dumps(data_to_server)
        self.client_socket.send(data_to_server.encode())

    def log_message(self, data):
        print("edge->cloud : log " + str(data))
        data_to_server = {'type': 'sensor', 'data': data}
        data_to_server = json.dumps(data_to_server)
        self.client_socket.send(data_to_server.encode())


def setInterval(interval, times=-1):
    # This will be the actual decorator,
    # with fixed interval and times parameter
    def outer_wrap(function):
        # This will be the function to be
        # called
        def wrap(*args, **kwargs):
            stop = threading.Event()

            # This is another function to be executed
            # in a different thread to simulate setInterval
            def inner_wrap():
                i = 0
                while i != times and not stop.isSet():
                    stop.wait(interval)
                    function(*args, **kwargs)
                    i += 1

            t = threading.Timer(0, inner_wrap)
            t.daemon = True
            t.start()
            return stop

        return wrap

    return outer_wrap


def init():
    # connection to ev3
    ev3_connection = edge_to_ev3(settings_data['classification_edge']['service_port'])
    ev3_connection.start()

    # connection to cloud
    global server_connection
    server_connection = connect_to_server(settings_data['cloud']['service_port_classification'])
    server_connection.start()

    # connect to repository edge server, check repository update
    EtoE_sock.connect(
        (settings_data['repository_edge']['address'], settings_data['repository_edge']['service_port_classification']))

    # edge connection managed in main thread
    while 1:
        data = EtoE_sock.recv(512).decode()
        if data == 'red':
            storing['red'] -= 1
        elif data == 'white':
            storing['white'] -= 1
        elif data == 'yellow':
            storing['yellow'] -= 1
        else:
            print("unreadable message from repository edge")
        print("repository update: " + str(storing))


if __name__ == '__main__':
    init()
