import socket
import threading
import json
import time
import argparse
import sys

class Master:
    def __init__(self, port, input_file, output_file, client_ports):
        self.port = port
        self.input_file = input_file
        self.output_file = output_file
        self.client_ports = client_ports
        self.client_sockets = {}
        self.output_lines = []
        
    def connect_to_clients(self):
        """Connect to all three clients"""
        time.sleep(3)  # Give clients time to start
        for client_id in [1, 2, 3]:
            while True:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('127.0.0.1', self.client_ports[client_id]))
                    self.client_sockets[client_id] = sock
                    print(f"Master connected to Client {client_id}")
                    break
                except:
                    time.sleep(1)
                    
    def send_message(self, client_id, message):
        """Send message to a client"""
        try:
            sock = self.client_sockets.get(client_id)
            if sock:
                msg = json.dumps(message) + '\n'
                sock.sendall(msg.encode('utf-8'))
        except Exception as e:
            print(f"Master error sending to Client {client_id}: {e}")
            
    def receive_message(self, client_id):
        """Receive message from a client"""
        try:
            sock = self.client_sockets.get(client_id)
            if sock:
                buffer = ""
                while True:
                    data = sock.recv(4096).decode('utf-8')
                    if not data:
                        return None
                    buffer += data
                    if '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        return json.loads(line)
        except Exception as e:
            print(f"Master error receiving from Client {client_id}: {e}")
            return None
            
    def process_commands(self):
        """Process commands from input file"""
        try:
            with open(self.input_file, 'r') as f:
                commands = f.readlines()
        except FileNotFoundError:
            print(f"Error: Input file '{self.input_file}' not found")
            return
            
        for command in commands:
            command = command.strip()
            if not command:
                continue
                
            print(f"Master processing: {command}")
            parts = command.split()
            
            if parts[0].lower() == 'insert':
                perm = parts[1]
                grade = parts[2]
                client_id = int(parts[3])
                self.handle_insert(perm, grade, client_id)
                
            elif parts[0].lower() == 'lookup':
                perm = parts[1]
                client_id = int(parts[2])
                self.handle_lookup(perm, client_id)
                
            elif parts[0].lower() == 'dictionary':
                client_id = int(parts[1])
                self.handle_dictionary(client_id)
                
            elif parts[0].lower() == 'wait':
                wait_time = int(parts[1])
                print(f"Master [Event - WAIT] [TIME - {wait_time}]")
                time.sleep(wait_time)
                
    def handle_insert(self, perm, grade, client_id):
        """Handle insert command"""
        print(f"Master [Event - INSERT] [PERM - {perm}] [GRADE - {grade}] - [Sent to Client {client_id}]")
        
        message = {
            'type': 'MASTER_INSERT',
            'perm': perm,
            'grade': grade
        }
        self.send_message(client_id, message)
        
        # Wait for response
        response = self.receive_message(client_id)
        if response and response['type'] == 'INSERT_SUCCESS':
            print(f"Master [Event - INSERT_SUCCESS] - [Clock - {response['clock']}] - [Received from Client {client_id}]")
            output_line = f"SUCCESS <insert {perm} {grade} {client_id}>"
            self.output_lines.append(output_line)
            print(f"OUTPUT: {output_line}")
            
    def handle_lookup(self, perm, client_id):
        """Handle lookup command"""
        print(f"Master [Event - LOOKUP] [PERM - {perm}] - [Sent to Client {client_id}]")
        
        message = {
            'type': 'MASTER_LOOKUP',
            'perm': perm
        }
        self.send_message(client_id, message)
        
        # Wait for response
        response = self.receive_message(client_id)
        if response and response['type'] == 'LOOKUP_RESULT':
            print(f"Master [Event - LOOKUP_SUCCESS] - [Clock - {response['clock']}] - [Received from Client {client_id}]")
            grade = response['grade']
            if grade == 'NOT FOUND':
                output_line = f"LOOKUP <{perm}, NOT FOUND>"
            else:
                output_line = f"LOOKUP <{perm}, {grade}>"
            self.output_lines.append(output_line)
            print(f"OUTPUT: {output_line}")
            
    def handle_dictionary(self, client_id):
        """Handle dictionary command"""
        print(f"Master [Event - DICTIONARY] - [Sent to Client {client_id}]")
        
        message = {
            'type': 'MASTER_DICTIONARY'
        }
        self.send_message(client_id, message)
        
        # Wait for response
        response = self.receive_message(client_id)
        if response and response['type'] == 'DICTIONARY_RESULT':
            print(f"Master [Event - DICTIONARY_SUCCESS] - [Clock - {response['clock']}] - [Received from Client {client_id}]")
            dictionary = response['dictionary']
            # Format as dictionary
            output_line = str(dictionary).replace("'", "'")
            self.output_lines.append(output_line)
            print(f"OUTPUT: {output_line}")
            
    def write_output(self):
        """Write output to file"""
        try:
            with open(self.output_file, 'w') as f:
                for line in self.output_lines:
                    f.write(line + '\n')
            print(f"Output written to {self.output_file}")
        except Exception as e:
            print(f"Error writing output file: {e}")
            
    def run(self):
        """Run the master process"""
        print("Master starting...")
        
        # Connect to clients
        self.connect_to_clients()
        
        # Process commands
        self.process_commands()
        
        # Write output
        self.write_output()
        
        print("Master finished processing commands")
        
        # Give some time before closing
        time.sleep(2)
        
        # Close connections
        for sock in self.client_sockets.values():
            sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-port', type=int, required=True)
    parser.add_argument('-inputfile', type=str, required=True)
    parser.add_argument('-outputfile', type=str, required=True)
    args = parser.parse_args()

    base_port = args.port - 3
    client_ports = {
        1: base_port,
        2: base_port + 1,
        3: base_port + 2
    }
    
    master = Master(args.port, args.inputfile, args.outputfile, client_ports)
    master.run()