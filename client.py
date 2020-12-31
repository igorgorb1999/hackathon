import socket
import time
import getch
from select import select
import sys
from scapy.arch import get_if_addr
import struct

import termios
import tty

import traceback

UDP_PORT=13117
UDP_MAGIC_COOKIE=0xfeedbeef
UDP_OFFER_TYPE=0x02
UDP_OFFER_SIZE=7

grading=False

connect_to_only_my_server=False

#an initialization of the client
#return the name
def startup():
    print("Starting the client.")
    print("Please choose a name:")
    name=input()
    print("You chose a name: "+name)
    print("Client started")
    return name

#checks if an offer is legal
def is_legal_udp_offer(offer):
    if offer[0] != UDP_MAGIC_COOKIE:
        return False
    if offer[1] != UDP_OFFER_TYPE:
        return False
    #just for checking if MY server sends udp offers (debugging)
    if connect_to_only_my_server and offer[2] != 2151:
        return False
    return True

#gets a port from an offer
def decode_port_from_offer(offer):
    return offer[2]

#waits for a legal offer
#returns address and port
def look_for_servers():
    print("Looking for servers...")
    #make a udp socket
    udp_socket=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(1)
    #connect to a specific network
    #cant figure out how to do it properly
    binded=False
    #loop because the address might be occupied by a local client
    while not binded:
        try:
            if grading:
                #udp_socket.bind((get_if_addr("eth2"), UDP_PORT))
                udp_socket.bind(("", UDP_PORT))
            else:
                udp_socket.bind(("", UDP_PORT))
                #udp_socket.bind((get_if_addr("eth1"), UDP_PORT))
            binded=True
        except Exception as e:
            #print(e)
            pass
        time.sleep(0.1)
    udp_offer=(0, 0, 0)
    while not is_legal_udp_offer(udp_offer):
        try:
            udp_offer, address = udp_socket.recvfrom(1024)
            if len(udp_offer) == UDP_OFFER_SIZE:
                udp_offer = struct.unpack("!IBH", udp_offer)
            else:
                udp_offer=(0, 0, 0)
        except socket.error:
            udp_offer=(0, 0, 0)
    udp_socket.close()
    return (address, decode_port_from_offer(udp_offer))

#hmmm.. tries to connect to the server?
#returns a socket
#or None if failed
def try_connect_to_server(address, tcp_port):
    tcp_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.settimeout(2)
    try:
        tcp_socket.connect((address[0], tcp_port))
        return tcp_socket
    except socket.error:
        print("connection timed out")
        return None

#send a string message throgh tcp socket. closes the socket if an exception was thrown
def tcp_send(tcp_socket, msg):
    try:
        tcp_socket.send(str.encode(msg))
        return True
    except socket.error:
        tcp_socket.close()
        return False

#send a byte message throgh tcp socket without closing the socket if an exception was thrown
def tcp_send_byte(tcp_socket, msg):
    try:
        tcp_socket.send(msg)
        return True
    except socket.error:
        return False

#receives a message ffrom tcp socket
#returns empty string if timed out
#returns None if an exception was thrown
def tcp_receive(tcp_socket):
    try:
        msg=tcp_socket.recvfrom(1024)[0].decode()
        return msg
    except socket.timeout:
        return ""
    except socket.error as e:
        #print(e)
        return None

#checks if there is a pressed key
def isData():
        return select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

#function that maintains the play logic
def play(tcp_socket, old_settings):
    tcp_socket.settimeout(0.01)
    stop=False
    #for a non blocking getch
    tty.setcbreak(sys.stdin.fileno())
    while not stop:
        #check if some key is pressed
        if isData():
            pressed_key=getch.getch()[0]
            #try sending the key
            if not tcp_send_byte(tcp_socket, pressed_key.encode()):
                #print("connection to the server lost")
                tcp_socket.settimeout(2)
                stop=True
        #receive incoming messages
        msg=tcp_receive(tcp_socket)
        if msg == None:
            #print("connection to the server lost.")
            stop=True
        elif msg != "":
            print(msg)
            #enable this only if the server can only send 1 message:
            stop=True
        #check the connection by catching an exception when sending a message to a closed (by the server) socket
        #for some reson it refuses to send an empty string, which makes it unusable
        #if not tcp_send(""):
        #    print("server closed the connection.")
        #    stop=True
        #else:
        #    print("s")
    #restore the old settings of terminal
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    print("exited the server")
    #for manual exiting from the server
    #input()
    tcp_socket.close()
    #wait because the addres
    #time.sleep(1)

#function to handle the connection to the server
def connection_handle(tcp_socket, name):
    print("Connected to the server. Waiting for the game...")
    #try sending the name
    if not tcp_send(tcp_socket, name+"\n"):
        print("Failed to send the name")
        return
    #wait for the game start
    tcp_socket.settimeout(11)
    game_start_msg=tcp_receive(tcp_socket)
    if game_start_msg == None or game_start_msg == "":
        print("the server failed to start the game")
        return
    print(game_start_msg)
    #to save the old setting of terminal
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        play(tcp_socket, old_settings)
    except:
        #restore old settings of the terminal if crashed
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

#main function. duh
def main():
    name=startup()
    while True:
        address, tcp_port = look_for_servers()
        print("Received offer from "+address[0]+", attempting to connect...")
        tcp_socket=try_connect_to_server(address, tcp_port)
        if tcp_socket != None:
            connection_handle(tcp_socket, name)
        else:
            print("failed to connect to the server.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        #in case of ctrl+c that is not handled
        #for some reson it does not catch it...
        #termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    #    pass
        print("error:")
        print(e)
        print(traceback.format_exc())
        print("closing the client")