# Miguel Delapaz - CS594 - IRC Server Project
import socket
import select
import sys
from enum import Enum
try:
    import queue
except ImportError:
    import Queue as queue

class Command(Enum):
    LOGIN = 1
    LOGOUT = 2
    ADD_CHANNEL = 3
    JOIN_CHANNEL = 4
    LEAVE_CHANNEL = 5
    LIST_ROOMS = 6
    LIST_USERS = 7
    MESSAGE = 8

class ResponseCodes(Enum):
    OK = 0
    ERROR = 4

class Server:
    def __init__(self):
        self.channelList = {}
        self.clientList = {}
        self.port = 6000
        self.readList = []
        self.writeList = []
        self.initialize_listen_socket()

    def initialize_listen_socket(self):
        self.listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listenSocket.setblocking(False)
        self.listenSocket.bind(('', self.port))
        self.listenSocket.listen(5)
        self.readList.append(self.listenSocket)
        print("Server listening socket created on port " + str(self.port))

    def process_add_channel(self, client, channelName):
        if len(channelName) > 10 or not channelName.isalnum():
            self.response(client, Command.ADD_CHANNEL, ResponseCodes.ERROR, "Invalid Channel - " + channelName + " - Must be alphanumeric and less than 10 characters")
        else:
            if channelName in self.channelList:
                self.send_response(client, Command.ADD_CHANNEL, ResponseCodes.ERROR, "Channel " + channelName + " already exists")
            else:
                newChan = Channel(channelName)
                self.channelList[channelName] = newChan
                self.send_response(client, Command.ADD_CHANNEL, ResponseCodes.OK, channelName)
                self.process_join_channel(client, channelName)

    def process_join_channel(self, client, channelName):
        if not channelName in self.channelList:
            self.send_response(client, Command.JOIN_CHANNEL, ResponseCodes.ERROR, "Channel " + channelName + " does not exist")
        else:
            channel = self.channelList[channelName]
            if client in channel.users:
                self.send_response(client, Command.JOIN_CHANNEL, ResponseCodes.ERROR, "Already in the channel " + channelName)
            else:
                channel.users.append(client)
                self.send_response(client, Command.JOIN_CHANNEL, ResponseCodes.OK, channelName)

    def process_leave_channel(self, client, channelName):
        if not channelName in self.channelList:
            self.send_response(client, Command.LEAVE_CHANNEL, ResponseCodes.ERROR, "Channel " + channelName + " does not exist")
        else:
            channel = self.channelList[channelName]
            if not client in channel.users:
                self.send_response(client, Command.LEAVE_CHANNEL, ResponseCodes.ERROR, "Not in the channel " + channelName)
            else:
                channel.users.remove(client)
                self.send_response(client, Command.LEAVE_CHANNEL, ResponseCodes.OK, channelName)

                # Remove channel if it is empty
                if not channel.users:
                    del(self.channelList[channelName])

    def process_list_rooms(self, client):
        response = ''
        for c in self.channelList:
            channel = self.channelList[c]
            response += channel.name + '\n'
        self.send_response(client, Command.LIST_ROOMS, ResponseCodes.OK, response)

    def process_list_participants(self, client, channelName):
        response = channelName + '\n'
        if not channelName in self.channelList:
            self.send_response(client, Command.LIST_USERS, ResponseCodes.ERROR, "Channel " + channelName + " does not exist")
        else:
            channel = self.channelList[channelName]
            for u in channel.users:
                response += u.name + '\n'
            self.send_response(client, Command.LIST_USERS, ResponseCodes.OK, response)

    def process_message_channel(self, client, data):
        channelName, message = data.split('\n', 1)
        if not channelName in self.channelList:
            self.send_response(client, Command.MESSAGE, ResponseCodes.ERROR, "Channel " + channelName + " does not exist")
        elif message == '':
            self.send_response(client, Command.MESSAGE, ResponseCodes.ERROR, "Cannot send empty message")
        else:
            channel = self.channelList[channelName]
            response = channelName + '\n' + client.name + '\n' + message
            for c in channel.users:
                self.send_response(c, Command.MESSAGE, ResponseCodes.OK, response)

    def process_leave_server(self, client):
        channelsToRemove = []
        for c in self.channelList:
            channel = self.channelList[c]
            if client in channel.users:
                channel.users.remove(client)
                # Remove channel if it is empty
                if not channel.users:
                    channelsToRemove.append(c)
        for c in channelsToRemove:
            del(self.channelList[c])
        if client.sock in self.writeList:
            self.writeList.remove(client.sock)
        self.readList.remove(client.sock)
        client.sock.close()
        del self.clientList[client.sock]

    def process_join_server(self, client, username):
        if len(username) > 10 or not username.isalnum():
            self.send_response(client, ResponseCodes.ERROR, "Invalid Username - Must be alphanumeric and less than 10 characters")
            return ResponseCodes.ERROR
        client.name = username
        client.LoggedIn = True
        self.send_response(client, Command.LOGIN, ResponseCodes.OK, None)

    def process_incoming_data(self, socket):
        client = self.clientList[socket]
        try:
            command = socket.recv(1)
        except:
            print("Client at " + str(client.addr) + " encounterd an error")
            self.process_leave_server(client)
            return

        if not command:
            # Client disconnected
            print("Client at " + str(client.addr) + " disconnected")
            self.process_leave_server(client)
            return
        else:
            try:
                command = int(command)
                length = int(socket.recv(5))
                if length > 0:
                    data = socket.recv(length)
            except:
                print("Client at " + str(client.addr) + " encounterd an error")
                self.process_leave_server(client)
                return

        if command == Command.LOGIN:
            self.process_join_server(client, data)
        elif not client.LoggedIn:
            send_response(client, command, ResponseCodes.ERROR, "Command not valid before login")
        elif command == Command.LOGOUT:
            self.process_leave_server(client)
        elif command == Command.ADD_CHANNEL:
            self.process_add_channel(client, data)
        elif command == Command.JOIN_CHANNEL:
            self.process_join_channel(client, data)
        elif command == Command.LEAVE_CHANNEL:
            self.process_leave_channel(client, data)
        elif command == Command.LIST_ROOMS:
            self.process_list_rooms(client)
        elif command == Command.LIST_USERS:
            self.process_list_participants(client, data)
        elif command == Command.MESSAGE:
            self.process_message_channel(client, data)
        elif command == Command.RESPONSE:
            # Client shouldn't be sending response messages
            send_response(client, command, ResponseCodes.ERROR, "Response messages are reserved for the server")
        else:
            # We don't know what this code is
            send_response(client, command, ResponseCodes.ERROR, "Unrecognized command code")

    def process_incoming_connection(self):
        c, addr = self.listenSocket.accept()
        c.setblocking(False)
        print("Received connection from client at " + str(addr))
        self.readList.append(c)
        server.clientList[c] = Client(c, addr)

    def process_client_exception(self, sock):
        client = self.clientList[socket]
        print("Client at " + client.addr + " encountered socket exception - closing")
        self.process_leave_server(client)

    def send_response(self, client, commandCode, responseCode, message):
        # Packet is one byte of command code, 5 bytes of length (string form)
        # followed by the data
        if message and len(message) >= 99999:
            print("Message too long")
        else:
            if message:
                length = len(str(responseCode)) + len(message)
            else:
                length = len(str(responseCode))
            data = str(commandCode) + str(length).rjust(5, '0') + str(responseCode)
            if message:
                data = data + message
            client.outbound.put(data)
            self.writeList.append(client.sock)

    def run(self):
        while self.readList:
            read, write, exception = select.select(self.readList, self.writeList, self.readList)

            for s in read:
                if s == self.listenSocket:
                    # A client is trying to connect
                    self.process_incoming_connection()
                else:
                    # Data coming in on a client socket
                    self.process_incoming_data(s)

            for s in write:
                if s in self.clientList:
                    client = self.clientList[s]
                    client.send_outgoing_data()
                    self.writeList.remove(s)

            for s in exception:
                if s == self.listenSocket:
                    print("Server listen socket encountered exception - reinitializing")
                    self.readList.remove(self.listenSocket)
                    self.listenSocket.close()
                    self.initialize_listen_socket()
                else:
                    self.process_client_exception(s)


class Channel:
    def __init__(self, name):
        self.name = name
        self.users = []

class Client:
    def __init__(self, socket, addr):
        self.name = None
        self.sock = socket
        self.addr = addr
        self.LoggedIn = False
        self.outbound = queue.Queue()

    def send_outgoing_data(self):
        while not self.outbound.empty():
            self.sock.send(self.outbound.get())

# Start of main server program
server = Server()

server.run()
