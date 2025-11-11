#!/usr/bin/env python3
# Identical implementation to client1.py — kept standalone per submission rule
import argparse
import socket
import threading
import time
from typing import List, Tuple, Set, Dict

CLIENT_PORTS = {'1': 8001, '2': 8002, '3': 8003}

MY_CLIENT_ID: str = None
MY_PORT: int = None

client_sockets: Dict[str, socket.socket] = {}

local_dictionary: Dict[str, str] = {}
local_dictionary_lock = threading.Lock()

lamport_clock = 0
lamport_clock_lock = threading.Lock()

client_state = "RELEASED"
client_state_lock = threading.Lock()

request_queue: List[Tuple[int, str]] = []
request_queue_lock = threading.Lock()

current_request_ts = -1
current_request_ts_lock = threading.Lock()

current_insert = None
current_insert_lock = threading.Lock()

replies_received: Set[str] = set()
replies_received_lock = threading.Lock()

success_received: Set[str] = set()
success_received_lock = threading.Lock()

my_turn_event = threading.Event()
all_success_event = threading.Event()

def send_line(sock: socket.socket, s: str):
    sock.sendall((s + "\n").encode("utf-8"))

def recv_line_file(f) -> str:
    line = f.readline()
    if not line:
        return ""
    return line.decode("utf-8").rstrip("\r\n")

def lamport_on_send_request() -> int:
    global lamport_clock
    with lamport_clock_lock:
        lamport_clock += 1
        return lamport_clock

def lamport_on_recv_request(incoming_ts: int) -> int:
    global lamport_clock
    with lamport_clock_lock:
        lamport_clock = max(lamport_clock, incoming_ts) + 1
        return lamport_clock

def queue_push(ts: int, cid: str):
    with request_queue_lock:
        request_queue.append((ts, cid))
        request_queue.sort(key=lambda x: (x[0], int(x[1])))

def queue_head() -> Tuple[int, str] | None:
    with request_queue_lock:
        return request_queue[0] if request_queue else None

def queue_remove(cid: str):
    with request_queue_lock:
        for i, (_, who) in enumerate(request_queue):
            if who == cid:
                request_queue.pop(i)
                break

def i_am_head() -> bool:
    h = queue_head()
    return bool(h and h[1] == MY_CLIENT_ID)

def have_all_replies() -> bool:
    with replies_received_lock:
        return len(replies_received) == 2

def have_all_success() -> bool:
    with success_received_lock:
        return len(success_received) == 2

def reset_barriers():
    with replies_received_lock:
        replies_received.clear()
    with success_received_lock:
        success_received.clear()
    my_turn_event.clear()
    all_success_event.clear()

def peers():
    return [cid for cid in CLIENT_PORTS if cid != MY_CLIENT_ID]

def broadcast_to_peers(msg: str):
    print(f"[C{MY_CLIENT_ID}] Broadcast: {msg}")
    for cid in peers():
        s = client_sockets.get(cid)
        if s is None:
            continue
        try:
            send_line(s, msg)
        except Exception as e:
            print(f"[C{MY_CLIENT_ID}] Send to {cid} failed: {e}")

def try_enter_cs():
    with client_state_lock:
        if client_state != "WANTED":
            return
    if i_am_head() and have_all_replies():
        my_turn_event.set()

def start_lamport_insert(perm: str, grade: str, master_conn: socket.socket):
    with current_insert_lock:
        global current_insert
        current_insert = (perm, grade)
    with client_state_lock:
        global client_state
        client_state = "WANTED"
    reset_barriers()

    ts = lamport_on_send_request()
    with current_request_ts_lock:
        global current_request_ts
        current_request_ts = ts
    queue_push(ts, MY_CLIENT_ID)

    broadcast_to_peers(f"REQUEST {ts} {MY_CLIENT_ID}")

    print(f"[C{MY_CLIENT_ID}] Waiting to enter CS...")
    my_turn_event.wait()
    with client_state_lock:
        client_state = "HELD"
    print(f"[C{MY_CLIENT_ID}] Entered CS")

    with current_insert_lock:
        p, g = current_insert
    broadcast_to_peers(f"INSERT {p} {g} {MY_CLIENT_ID}")

    with local_dictionary_lock:
        local_dictionary[p] = g

    all_success_event.wait()

    queue_remove(MY_CLIENT_ID)
    with client_state_lock:
        client_state = "RELEASED"
    broadcast_to_peers(f"RELEASE {MY_CLIENT_ID}")

    try:
        send_line(master_conn, "SUCCESS")
    except Exception as e:
        print(f"[C{MY_CLIENT_ID}] Failed to reply SUCCESS to master: {e}")

def handle_peer_message(msg: str):
    time.sleep(3)

    parts = msg.split()
    if not parts:
        return
    kind = parts[0]

    if kind == "REQUEST":
        ts = int(parts[1]); other = parts[2]
        lamport_on_recv_request(ts)
        queue_push(ts, other)
        s = client_sockets.get(other)
        if s:
            send_line(s, f"REPLY {MY_CLIENT_ID}")
        try_enter_cs()

    elif kind == "REPLY":
        other = parts[1]
        with replies_received_lock:
            replies_received.add(other)
        try_enter_cs()

    elif kind == "INSERT":
        perm, grade, src = parts[1], parts[2], parts[3]
        with local_dictionary_lock:
            local_dictionary[perm] = grade
        s = client_sockets.get(src)
        if s:
            send_line(s, f"SUCCESS {MY_CLIENT_ID}")

    elif kind == "SUCCESS":
        other = parts[1]
        with success_received_lock:
            success_received.add(other)
            if have_all_success():
                all_success_event.set()

    elif kind == "RELEASE":
        other = parts[1]
        queue_remove(other)
        try_enter_cs()

def handle_connection(conn: socket.socket, addr):
    print(f"[C{MY_CLIENT_ID}] Incoming from {addr}")
    f = conn.makefile("rb", buffering=0)
    try:
        while True:
            line = recv_line_file(f)
            if not line:
                break
            parts = line.split()
            if not parts:
                continue
            cmd = parts[0]

            if cmd == "insert":
                perm, grade = parts[1], parts[2]
                start_lamport_insert(perm, grade, conn)

            elif cmd == "lookup":
                perm = parts[1]
                with local_dictionary_lock:
                    g = local_dictionary.get(perm)
                if g is None:
                    send_line(conn, "NOT FOUND")
                else:
                    send_line(conn, f"{perm}, {g}")

            elif cmd == "dictionary":
                with local_dictionary_lock:
                    items = sorted(local_dictionary.items(),
                                   key=lambda kv: (int(kv[0]) if kv[0].isdigit() else kv[0]))
                    body = "{" + ", ".join([f"'{k}': '{v}'" for k, v in items]) + "}"
                send_line(conn, body)

            elif cmd in ("REQUEST", "REPLY", "INSERT", "SUCCESS", "RELEASE"):
                handle_peer_message(line)
            else:
                pass
    except Exception as e:
        print(f"[C{MY_CLIENT_ID}] Handler error: {e}")
    finally:
        try: conn.close()
        except: pass
        print(f"[C{MY_CLIENT_ID}] Connection closed {addr}")

def run_server(port: int):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("localhost", port))
    srv.listen(8)
    print(f"[C{MY_CLIENT_ID}] Listening on {port}")
    try:
        while True:
            c, a = srv.accept()
            t = threading.Thread(target=handle_connection, args=(c, a), daemon=True)
            t.start()
    except Exception as e:
        print(f"[C{MY_CLIENT_ID}] Server error: {e}")
    finally:
        try: srv.close()
        except: pass

def connect_to_peers():
    for cid in peers():
        port = CLIENT_PORTS[cid]
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("localhost", port))
                client_sockets[cid] = s
                print(f"[C{MY_CLIENT_ID}] Connected to peer {cid} ({port})")
                break
            except ConnectionRefusedError:
                print(f"[C{MY_CLIENT_ID}] Peer {cid} not ready; retrying...")
                time.sleep(1)
            except Exception as e:
                print(f"[C{MY_CLIENT_ID}] Connect error to {cid}: {e}")
                time.sleep(1)

def main():
    global MY_CLIENT_ID, MY_PORT

    ap = argparse.ArgumentParser(description="CS171 PA2 Client")
    ap.add_argument("-port", type=int, required=True)
    ap.add_argument("-client", type=int, required=True, help="1, 2, or 3")
    args = ap.parse_args()

    MY_CLIENT_ID = str(args.client)
    if MY_CLIENT_ID not in CLIENT_PORTS:
        print(f"[Client] Invalid client id {MY_CLIENT_ID}")
        return

    MY_PORT = args.port

    t = threading.Thread(target=run_server, args=(MY_PORT,), daemon=True)
    t.start()
    time.sleep(1.5)

    connect_to_peers()

    print(f"[C{MY_CLIENT_ID}] Ready for Master.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print(f"[C{MY_CLIENT_ID}] Shutting down...")

if __name__ == "__main__":
    main()
