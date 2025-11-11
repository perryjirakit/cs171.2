import socket
import threading
import json
import time
import argparse
import sys

class Client:
    def __init__(self, client_id, port, other_ports):
        self.client_id = client_id
        self.port = port
        self.other_ports = other_ports
        self.dictionary = {}
        self.lamport_clock = 0
        self.request_queue = []  # (timestamp, client_id, request_type)
        self.replies_received = set()
        self.success_received = set()
        self.waiting_for_mutual_exclusion = False
        self.pending_insert = None
        self.lock = threading.Lock()
        
        # Socket connections
        self.server_socket = None
        self.client_sockets = {}
        self.master_connection = None
        
    def start_server(self):
        """Start listening for incoming connections"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        print(f"Client {self.client_id} listening on port {self.port}")
        
        while True:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_connection, args=(conn,), daemon=True).start()
            except:
                break
                
    def handle_connection(self, conn):
        """Handle incoming messages"""
        buffer = ""
        while True:
            try:
                data = conn.recv(4096).decode('utf-8')
                if not data:
                    break
                    
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        # Simulate network delay (3 seconds) for client-to-client messages
                        message = json.loads(line)
                        if message.get('type') not in ['MASTER_INSERT', 'MASTER_LOOKUP', 'MASTER_DICTIONARY']:
                            time.sleep(3)
                        self.process_message(message, conn)
            except Exception as e:
                print(f"Client {self.client_id} error handling connection: {e}")
                break
        conn.close()
        
    def connect_to_clients(self):
        """Connect to other clients"""
        time.sleep(2)  # Give other clients time to start
        for other_id, other_port in self.other_ports.items():
            while True:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', other_port))
                    self.client_sockets[other_id] = sock
                    print(f"Client {self.client_id} connected to Client {other_id}")
                    break
                except:
                    time.sleep(1)
                    
    def send_message(self, recipient_id, message):
        """Send message to another client"""
        try:
            if recipient_id == 'master':
                if self.master_connection:
                    msg = json.dumps(message) + '\n'
                    self.master_connection.sendall(msg.encode('utf-8'))
            else:
                sock = self.client_sockets.get(recipient_id)
                if sock:
                    msg = json.dumps(message) + '\n'
                    sock.sendall(msg.encode('utf-8'))
        except Exception as e:
            print(f"Client {self.client_id} error sending to {recipient_id}: {e}")
            
    def process_message(self, message, conn=None):
        """Process incoming messages"""
        msg_type = message.get('type')
        
        with self.lock:
            if msg_type == 'MASTER_INSERT':
                # Master wants us to insert
                self.master_connection = conn
                perm = message['perm']
                grade = message['grade']
                self.start_insert(perm, grade)
                
            elif msg_type == 'MASTER_LOOKUP':
                # Master wants us to lookup
                self.master_connection = conn
                perm = message['perm']
                result = self.dictionary.get(str(perm), 'NOT FOUND')
                response = {
                    'type': 'LOOKUP_RESULT',
                    'perm': perm,
                    'grade': result,
                    'clock': self.lamport_clock
                }
                self.send_message('master', response)
                
            elif msg_type == 'MASTER_DICTIONARY':
                # Master wants dictionary state
                self.master_connection = conn
                response = {
                    'type': 'DICTIONARY_RESULT',
                    'dictionary': self.dictionary,
                    'clock': self.lamport_clock
                }
                self.send_message('master', response)
                
            elif msg_type == 'REQUEST':
                # Another client wants mutual exclusion
                self.lamport_clock = max(self.lamport_clock, message['clock']) + 1
                print(f"Client {self.client_id} [Event - REQUEST] - [Clock - {message['clock']}] - [Received from Client {message['from']}]")
                print(f"Client {self.client_id} Clock Value {self.lamport_clock - 1} -> {self.lamport_clock}")
                
                # Add to queue
                self.request_queue.append((message['clock'], message['from']))
                self.request_queue.sort()
                
                # Send reply
                reply = {
                    'type': 'REPLY',
                    'from': self.client_id,
                    'clock': self.lamport_clock
                }
                print(f"Client {self.client_id} [Event - REPLY] - [Clock - {self.lamport_clock}] - [Sent to Client {message['from']}]")
                self.send_message(message['from'], reply)
                
            elif msg_type == 'REPLY':
                # Received reply for our request
                print(f"Client {self.client_id} [Event - REPLY] - [Clock - {message['clock']}] - [Received from Client {message['from']}]")
                self.replies_received.add(message['from'])
                
                # Check if we can proceed
                if len(self.replies_received) == 2 and self.check_queue_head():
                    self.execute_insert()
                    
            elif msg_type == 'INSERT':
                # Another client is broadcasting insert
                print(f"Client {self.client_id} [Event - INSERT] - [Clock - {self.lamport_clock}] - [Received from Client {message['from']}]")
                self.dictionary[str(message['perm'])] = message['grade']
                
                # Send success
                success = {
                    'type': 'SUCCESS',
                    'from': self.client_id,
                    'clock': self.lamport_clock
                }
                print(f"Client {self.client_id} [Event - SUCCESS] - [Clock - {self.lamport_clock}] - [Sent to Client {message['from']}]")
                self.send_message(message['from'], success)
                
            elif msg_type == 'SUCCESS':
                # Received success for our insert
                print(f"Client {self.client_id} [Event - SUCCESS] - [Clock - {message['clock']}] - [Received from Client {message['from']}]")
                self.success_received.add(message['from'])
                
                # Check if we got all success messages
                if len(self.success_received) == 2:
                    print(f"Client {self.client_id} Received all success messages: 2")
                    self.finish_insert()
                    
            elif msg_type == 'RELEASE':
                # Another client is releasing mutual exclusion
                print(f"Client {self.client_id} [Event - RELEASE] - [Clock - {self.lamport_clock}] - [Received from Client {message['from']}]")
                # Remove from queue
                self.request_queue = [(ts, cid) for ts, cid in self.request_queue if cid != message['from']]
                
    def start_insert(self, perm, grade):
        """Start insert operation"""
        print(f"Client {self.client_id} [Event - Master - INSERT_REQUEST] - [Clock - {self.lamport_clock}] - [Received from Master]")
        self.pending_insert = (perm, grade)
        self.lamport_clock += 1
        print(f"Client {self.client_id} Clock Value {self.lamport_clock - 1} -> {self.lamport_clock}")
        
        # Add our request to queue
        self.request_queue.append((self.lamport_clock, self.client_id))
        self.request_queue.sort()
        
        # Broadcast request
        request = {
            'type': 'REQUEST',
            'from': self.client_id,
            'clock': self.lamport_clock
        }
        print(f"Client {self.client_id} [Event - Broadcast - REQUEST] - [Clock - {self.lamport_clock}] - [Sent from Client {self.client_id}]")
        for other_id in self.other_ports.keys():
            self.send_message(other_id, request)
            
        self.replies_received = set()
        self.success_received = set()
        self.waiting_for_mutual_exclusion = True
        
    def check_queue_head(self):
        """Check if we're at the head of the queue"""
        if self.request_queue and self.request_queue[0][1] == self.client_id:
            return True
        return False
        
    def execute_insert(self):
        """Execute the insert operation"""
        if not self.pending_insert:
            return
            
        perm, grade = self.pending_insert
        
        # Insert locally
        self.dictionary[str(perm)] = grade
        
        # Broadcast insert to other clients
        insert_msg = {
            'type': 'INSERT',
            'from': self.client_id,
            'perm': perm,
            'grade': grade,
            'clock': self.lamport_clock
        }
        print(f"Client {self.client_id} [Event - Broadcast - INSERT] - [Clock - {self.lamport_clock}] - [Sent from Client {self.client_id}]")
        for other_id in self.other_ports.keys():
            self.send_message(other_id, insert_msg)
            
    def finish_insert(self):
        """Finish insert and release mutual exclusion"""
        # Remove ourselves from queue
        self.request_queue = [(ts, cid) for ts, cid in self.request_queue if cid != self.client_id]
        
        # Broadcast release
        release = {
            'type': 'RELEASE',
            'from': self.client_id,
            'clock': self.lamport_clock
        }
        print(f"Client {self.client_id} [Event - Broadcast - RELEASE] - [Clock - {self.lamport_clock}] - [Sent from Client {self.client_id}]")
        for other_id in self.other_ports.keys():
            self.send_message(other_id, release)
            
        # Notify master
        response = {
            'type': 'INSERT_SUCCESS',
            'perm': self.pending_insert[0],
            'grade': self.pending_insert[1],
            'clock': self.lamport_clock
        }
        print(f"Client {self.client_id} [Event - Master - INSERT_SUCCESS] - [Clock - {self.lamport_clock}] - [Sent to Master]")
        self.send_message('master', response)
        
        self.pending_insert = None
        self.waiting_for_mutual_exclusion = False
        self.replies_received = set()
        self.success_received = set()
        
    def run(self):
        """Run the client"""
        # Start server thread
        threading.Thread(target=self.start_server, daemon=True).start()
        
        # Connect to other clients
        self.connect_to_clients()
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"Client {self.client_id} shutting down")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-port', type=int, required=True)
    parser.add_argument('-client', type=int, required=True)
    args = parser.parse_args()
    
    # Define other client ports
    other_ports = {}
    base_port = args.port - args.client + 1
    for i in range(1, 4):
        if i != args.client:
            other_ports[i] = base_port + i - 1
    
    client = Client(args.client, args.port, other_ports)
    client.run()