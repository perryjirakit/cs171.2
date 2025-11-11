#!/usr/bin/env python3
import argparse
import socket
import time

CLIENT_PORTS = {
    '1': 8001,
    '2': 8002,
    '3': 8003,
}

def send_line(sock, s: str):
    sock.sendall((s + "\n").encode("utf-8"))

def recv_line(sock) -> str:
    f = sock.makefile("rb", buffering=0)
    line = f.readline()
    if not line:
        return ""
    return line.decode("utf-8").rstrip("\r\n")

def main():
    parser = argparse.ArgumentParser(description="CS171 PA2 Master")
    parser.add_argument("-port", type=int, required=True, help="(Unused; required by template)")
    parser.add_argument("-inputfile", type=str, required=True)
    parser.add_argument("-outputfile", type=str, required=True)
    args = parser.parse_args()

    # Fresh output file
    with open(args.outputfile, "w"):
        pass

    # Connect to all three clients
    client_socks = {}
    try:
        for cid, port in CLIENT_PORTS.items():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", port))
            client_socks[cid] = s
            print(f"[Master] Connected to client {cid} on {port}")
    except Exception as e:
        print(f"[Master] Failed to connect to clients: {e}")
        for s in client_socks.values():
            try: s.close()
            except: pass
        return

    try:
        with open(args.inputfile, "r") as fin:
            for raw in fin:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split()
                cmd = parts[0]
                if cmd == "wait":
                    # wait <x>
                    try:
                        wt = int(parts[1])
                    except:
                        wt = 1
                    print(f"[Master] wait {wt}s")
                    time.sleep(wt)
                    continue

                log_entry = None

                if cmd == "insert":
                    # insert <perm> <grade> <client id>
                    perm, grade, cid = parts[1], parts[2], parts[3]
                    s = client_socks[cid]
                    send_line(s, f"insert {perm} {grade}")
                    reply = recv_line(s)
                    if reply == "SUCCESS":
                        log_entry = f"SUCCESS <insert {perm} {grade} {cid}>"
                    else:
                        log_entry = f"FAILURE <insert {perm} {grade} {cid}>"

                elif cmd == "lookup":
                    # lookup <perm> <client id>
                    perm, cid = parts[1], parts[2]
                    s = client_socks[cid]
                    send_line(s, f"lookup {perm}")
                    reply = recv_line(s)
                    if reply == "NOT FOUND":
                        log_entry = "LOOKUP <NOT FOUND>"
                    else:
                        # reply format: "<perm>, <grade>"
                        log_entry = f"LOOKUP <{reply}>"

                elif cmd == "dictionary":
                    # dictionary <client id>
                    cid = parts[1]
                    s = client_socks[cid]
                    send_line(s, "dictionary")
                    reply = recv_line(s)
                    log_entry = reply

                else:
                    print(f"[Master] Unknown command: {line}")
                    continue

                print(f"[Master] Logging: {log_entry}")
                with open(args.outputfile, "a") as fout:
                    fout.write(log_entry + "\n")

    except FileNotFoundError:
        print(f"[Master] Input file not found: {args.inputfile}")
    except Exception as e:
        print(f"[Master] Error: {e}")
    finally:
        for s in client_socks.values():
            try: s.close()
            except: pass
        print("[Master] Done.")

if __name__ == "__main__":
    main()
