# Miguel Delapaz - CS594 - IRC Client Project
import socket
import select
import sys
import msvcrt
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

class Client:
    def __init__(self):
        self.addr = None
        self.port = None
        self.socket = None
        self.username = None
        self.LoggedIn = False
        self.readList = []
        self.writeList = []
        self.outbound = queue.Queue()
        self.keyboardInput = ''

    def process_logout(self):
        self.readList.remove(self.socket)
        if self.socket in self.writeList:
            self.writeList.remove(self.socket)
        self.LoggedIn = False

    def process_login_response(self, response):
        # Parse response into response code and message.  No message for success
        responseCode = int(response[0])
        errorMessage = response[1:]

        if self.LoggedIn:
            print("Received Login Response, but we're already logged in")
        elif responseCode == ResponseCodes.ERROR:
            print("Login Failure: " + errorMessage)
        elif responseCode == ResponseCodes.OK:
            self.LoggedIn = True
            print("Logged in to server " + self.addr + " as " + self.username)
        else:
            print("Login Response with Unexpected Code: " + str(responseCode))

    def process_add_response(self, response):
        # Parse response into response code and message.  Message is channel name on success
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("Add Channel Failure: " + message)
        else:
            print("Successfully Added Channel: " + message)

    def process_join_response(self, response):
        # Parse response into response code and message.  Message is channel name on success
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("Join Channel Failure: " + message)
        else:
            print("Successfully Joined Channel: " + message)

    def process_leave_response(self, response):
        # Parse response into response code and message.  Message is channel name on success
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("Leave Channel Failure: " + message)
        else:
            print("Successfully Left Channel: " + message)

    def process_list_rooms_response(self, response):
        # Parse response into response code and message.  Message is list of rooms on success
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("Error listing server rooms: " + message)
        else:
            rooms = message.splitlines()
            print("Available Rooms:")
            for r in rooms:
                print(">> " + r)

    def process_list_users_response(self, response):
        # Parse response into response code and message.
        # Message is channel name and list of users on success
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("List Users Failure: " + message)
        else:
            users = message.splitlines()
            channel = users.pop(0)
            print("Users in channel " + channel + ":")
            for u in users:
                print(">> " + u)

    def process_incoming_message(self, response):
        # Parse response into response code and message
        # if response is error, a message we sent failed
        # if response is OK, message is channel name, sending user name and message
        responseCode = int(response[0])
        message = response[1:]

        if responseCode == ResponseCodes.ERROR:
            print("Send Message Failure: " + message)
        else:
            channelName, clientName, userMessage = message.split(None, 2)
            print("[" + channelName + "]>>>(" + clientName + ") " + userMessage)

    def process_server_data(self):
        try:
            command = self.socket.recv(1)
        except:
            print("Connection encountered an error...Login again")
            self.process_logout()
            return

        if not command:
            # Server disconnected
            print("Server disconnected")
            self.process_logout()
            return
        else:
            command = int(command)
            try:
                length = int(self.socket.recv(5))
                data = self.socket.recv(length)
            except:
                print("Connection encountered an error...Login again")
                self.process_logout()
                return

        if command == Command.LOGIN:
            self.process_login_response(data)
        elif command == Command.ADD_CHANNEL:
            self.process_add_response(data)
        elif command == Command.JOIN_CHANNEL:
            self.process_join_response(data)
        elif command == Command.LEAVE_CHANNEL:
            self.process_leave_response(data)
        elif command == Command.LIST_ROOMS:
            self.process_list_rooms_response(data)
        elif command == Command.LIST_USERS:
            self.process_list_users_response(data)
        elif command == Command.MESSAGE:
            self.process_incoming_message(data)
        else:
            print("Unexpected command received from server: " + str(command))

    def login(self, data):
        if self.LoggedIn:
            print("Already logged into server: " + self.addr)
        else:
            if len(data.split()) < 3:
                print("Missing arguments on /login command")
                return

            self.addr, port, self.username = data.split(None, 2)

            self.port = int(port)

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.addr, self.port))
            self.socket = s
            self.socket.setblocking(False)
            self.readList = [self.socket]
            self.writeList = []

            self.send_network_data(Command.LOGIN, self.username)

    def logout(self):
        self.send_network_data(Command.LOGOUT, None)
        self.LoggedIn = False
        self.sock.close()
        print("Disconnected from server")

    def add_channel(self, channelName):
        if not channelName:
            print("Missing arguments on /add command")
            return
        self.send_network_data(Command.ADD_CHANNEL, channelName)

    def join_channel(self, channelName):
        if not channelName:
            print("Missing arguments on /join command")
            return
        self.send_network_data(Command.JOIN_CHANNEL, channelName)

    def leave_channel(self, channelName):
        if not channelName:
            print("Missing arguments on /leave command")
            return
        self.send_network_data(Command.LEAVE_CHANNEL, channelName)

    def list_rooms(self):
        self.send_network_data(Command.LIST_ROOMS, None)

    def list_users(self, channelName):
        if not channelName:
            print("Missing arguments on /users command")
            return
        self.send_network_data(Command.LIST_USERS, channelName)

    def send_message(self, input):
        if len(input.split()) < 2:
            print("Missing arguments on /message")
            return

        channel, message = input.split(None, 1)
        self.send_network_data(Command.MESSAGE, channel + '\n' + message)

    def send_network_data(self, code, data):
        # Packet is one byte of command code, 5 bytes of length (string form)
        # followed by the data
        if data and len(data) >= 99999:
            print("Message too long")
        else:
            if data:
                length = len(data)
            else:
                length = 0
            message = str(code) + str(length).rjust(5, '0')
            if data:
                message = message + data
        self.outbound.put(message)
        self.writeList.append(self.socket)

    def process_quit(self):
        print("Quitting...")
        sys.exit(0)

    def process_user_input(self, input):
        # Parse keyboard input
        if len(input.split()) < 2:
            command = input
        else:
            command, data = input.split(None, 1)

        command = command.lower()

        if not self.LoggedIn:
            if command == '/login':
                self.login(data)
            elif command == '/quit':
                self.process_quit()
            else:
                print("Command not valid before login")
        elif command == '/login':
            self.login(data)
        elif command == '/logout':
            self.logout()
        elif command == '/add':
            self.add_channel(data)
        elif command == '/join':
            self.join_channel(data)
        elif command == '/leave':
            self.leave_channel(data)
        elif command == '/rooms':
            self.list_rooms()
        elif command == '/users':
            self.list_users(data)
        elif command == '/message':
            self.send_message(data)
        elif command == '/quit':
            self.process_quit()
        else:
            print("Unknown command issued: " + command)

    def send_outgoing_data(self):
        while not self.outbound.empty():
            self.socket.send(self.outbound.get())

    def run(self):

        while True:
            if self.readList:
                # Is the server socket ready for reading or writing?
                read, write, exception = select.select(self.readList, self.writeList, self.readList, 1)

                for s in read:
                    if s == self.socket:
                        # A client is trying to connect
                        self.process_server_data()

                for s in write:
                    if s == self.socket:
                        self.send_outgoing_data()
                        self.writeList.remove(s)

                for s in exception:
                    if s == self.socket:
                        print("Server socket encountered exception.  Please login again")
                        self.readList.remove(self.socket)
                        if self.socket in self.writeList:
                            self.writeList.remove(self.socket)
                        self.socket.close()

            # Check for keyboard input
            while msvcrt.kbhit():
                newChar = msvcrt.getche()
                if newChar == '\r':
                    print('')
                    if self.keyboardInput != '':
                        self.process_user_input(self.keyboardInput)
                        self.keyboardInput = ''
                else:
                    self.keyboardInput = self.keyboardInput + newChar

# Start of main client program

client = Client()
client.run()
