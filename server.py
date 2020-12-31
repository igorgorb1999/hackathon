import socket
import time
import threading
import random
from scapy.arch import get_if_addr
import struct
from colorama import Fore
from colorama import Style
import sys

UDP_PORT=13117
TCP_PORT=2151

MAGIC_NUMBER=0xfeedbeef
MESSAGE_TYPE=0x02

MAX_PLAYERS=30
MAX_UDP_OFFERS=10
GAME_LENGTH=10

keys_buffer=([], [])

grading=False

team_colors=(Fore.CYAN, Fore.GREEN)

def set_color(msg, color):
    return color+msg+COLOR_END

#makes and returns a udp socket
def make_udp_socket():
    udp_socket=socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    #udp_socket.settimeout(0.2)
    return udp_socket

#makes and returns a tcp socket
def make_tcp_server_socket():
    tcp_server_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #for choosing a specific network
    #cant figure out how to do it
    #needs while so it will wait for an adress to be free
    binded=False
    while not binded:
        try:
            if grading:
                #tcp_server_socket.bind((get_if_addr("eth2"), TCP_PORT))
                tcp_server_socket.bind(("", TCP_PORT))
            else:
                tcp_server_socket.bind(("", TCP_PORT))
            binded=True
            time.sleep(1)
        except:
            pass
    print("opened the server socket")
    tcp_server_socket.listen(MAX_PLAYERS)
    return tcp_server_socket

#sends a message to a tcp socket
#closes the socket if an exception was thrown and returns False
def tcp_send(my_socket, msg):
    try:
        my_socket.send(str.encode(msg))
        return True
    except socket.error:
        my_socket.close()
        return False

#returns a game start message
def start_message():
    while not finished_accepting:
        time.sleep(0.1)
    result=f"\n{Fore.YELLOW}Welcome to Igor's Server!{Style.RESET_ALL}\n"
    result+=f"The game has started!\n{team_colors[0]}Team 1{Style.RESET_ALL}:\n"
    for client_name in player_names[0]:
        result+=client_name+"\n"
    result+=f"--------------\n{team_colors[1]}Team 2{Style.RESET_ALL}:\n"
    for client_name in player_names[1]:
        result+=client_name+"\n"
    result+="\nType as fast as you can!"
    return result

#client thread
def client_handler(client_socket, client_address, team_id):
    #get the name
    name=b""
    try:
        name, adress = client_socket.recvfrom(1024)
    except socket.error:
        print("a user lost connection")
        client_socket.close()
        return
    name=name.decode()
    name=name.replace("\n", "")
    print(name+" has connected")
    #add the player to the database
    player_names[team_id].append(name)
    #send a start message to the client
    client_socket.settimeout(0.1)
    if not tcp_send(client_socket, start_message()):
        return
    print("the game begins")
    #while he game is on add all the keys that the client sends
    while is_game:
        try:
            msg=client_socket.recvfrom(1024)[0].decode()
            #print(msg)
            if len(msg) != 0:
                keys_buffer[team_id].append(msg[0])
        except Exception:
            pass
        #print("1")
    #wait for the result to be calculated
    global game_result
    while game_result == "":
        time.sleep(0.01)
    tcp_send(client_socket, game_result)
    #time.sleep(1)
    print("the client disconected")
    client_socket.close()

#chooses team
def choose_team():
    return random.randint(0, 1)

#accepts all the replies and makes threads for each client
def accept_offer_replies(tcp_server_socket):
    global finished_accepting
    finished_accepting=False
    tcp_server_socket.settimeout(0.1)
    finished=False
    while not finished:
        try:
            client_socket, client_address=tcp_server_socket.accept()
            client_thread=threading.Thread(target=client_handler, args=(client_socket, client_address, choose_team()))
            client_thread.start()
        except socket.error:
            finished=True
    finished_accepting=True

#sends a usp offer
def send_offer(udp_socket):
    udp_socket.sendto(struct.pack("!IBH", MAGIC_NUMBER, MESSAGE_TYPE, TCP_PORT), ('<broadcast>', UDP_PORT))

#sends udp offers
def send_offers(udp_socket):
    print("starting to send offers.")
    for i in range(MAX_UDP_OFFERS):
        send_offer(udp_socket)
        #print("offer sent")
        time.sleep(1)

#what the main thread have to do while the game is on
def game(tcp_server_socket):
    global is_game
    try:
        time.sleep(GAME_LENGTH)
    except:
        is_game=False
        global game_result
        game_result="server terminated"
        tcp_server_socket.close()
        sys.exit()

#checks who won...
def check_who_won():
    if len(keys_buffer[0]) > len(keys_buffer[1]):
        return 0
    if len(keys_buffer[0]) < len(keys_buffer[1]):
        return 1
    if len(keys_buffer[0]) == len(keys_buffer[1]):
        return -1

#makes the result message
def make_result_message():
    winning_id=check_who_won()
    result="\n"
    if winning_id == -1:
        result+="It's a draw!\n"
    else:
        result+=f"The {team_colors[winning_id]}team "+str(winning_id+1)+f"{Style.RESET_ALL} won!\n"
    result+=f"{team_colors[0]}Team 1{Style.RESET_ALL}: "+str(len(keys_buffer[0]))+" keys\n"
    result+=f"{team_colors[1]}Team 2{Style.RESET_ALL}: "+str(len(keys_buffer[1]))+" keys\n\n"
    return result

#logic after the game
def post_game():
    global game_result
    game_result=make_result_message()
    
    print("the game has finished")
    print("the keys are:")
    print(keys_buffer)
    print("Game over, sending out offer requests...\n")

#main function
def main():
    udp_socket=make_udp_socket()
    tcp_server_socket=make_tcp_server_socket()
    global player_names
    global keys_buffer
    global is_game
    while True:
        #initialize
        is_game=False
        keys_buffer=([], [])
        player_names=([], [])
        #start broadcasting udps
        send_offers(udp_socket)
        #accepts clients
        is_game=True
        accept_offer_replies(tcp_server_socket)
        global game_result
        game_result=""
        #dont start the game if there are no players
        if len(player_names[0]) != 0 or len(player_names[1]) != 0:
            #game
            game(tcp_server_socket)
            post_game()
    input()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        #in case of ctrl+c that is not handled
        #for some reson it does not catch it...
        #termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("error:")
        print(e)
        print("closing the client")
    