import argparse
import json
import threading
import time
from typing import List
import sys
import termios


import paho.mqtt.client as mqtt

class TicTacToePlayer:
    def __init__(self, broker, port, game_id, symbol, name, client_id=None):
        self.broker = broker
        self.port = port
        self.game_id = game_id
        self.symbol = symbol.upper()
        self.name = name
        self.moves_topic = f"tictactoe/{game_id}/moves"
        self.state_topic = f"tictactoe/{game_id}/state"
        self.client = mqtt.Client(client_id or f"player-{name}-{self.symbol}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.current_state = None
        self.lock = threading.Lock()
        self.waiting_for_input = False

    def connect(self):
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        self.client.subscribe(self.state_topic)
        print(f"[{self.name}] Connected and subscribed to {self.state_topic}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[{self.name}] Connected to broker (rc={rc})")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
        except Exception as e:
            print(f"[{self.name}] Received malformed message:", e)
            return

        if msg.topic == self.state_topic:
            with self.lock:
                self.current_state = data
            self.display_state()
            if data.get("status") == "ongoing" and data.get("turn") == self.symbol:
                if not self.waiting_for_input:
                    t = threading.Thread(target=self.prompt_move)
                    t.daemon = True
                    t.start()
        elif msg.topic == self.control_topic:
            print(f"[{self.name}] CONTROL: {data}")

    def display_state(self):
        s = self.current_state
        if s is None:
            return
        board = s.get("board", [])
        print(f"\n[{self.name}] Board (turn={s.get('turn')}, status={s.get('status')})")
        self.print_board(board)
        if s.get("status") == "finished":
            w = s.get("winner")
            if w:
                print(f"[{self.name}] Game finished. Winner: {w}")
            else:
                print(f"[{self.name}] Game finished. Draw.")

    def print_board(self, board):
        def cell(v): return v if v else "."
        rows = []
        for r in range(0,9,3):
            rows.append(" ".join(cell(board[r+i]) for i in range(3)))
        print("\n".join(rows))
        print()  # extra line

    def prompt_move(self):
        self.waiting_for_input = True
        try:
            while True:
                with self.lock:
                    s = self.current_state
                if s is None:
                    time.sleep(0.1)
                    continue
                if s.get("status") != "ongoing":
                    break
                if s.get("turn") != self.symbol:
                    break
                try:
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)
                    raw = input(f"[{self.name}] Your move (0-8): ").strip()
                except EOFError:
                    # input closed
                    break
                if raw == "":
                    continue
                if raw.lower() == "quit":
                    print(f"[{self.name}] Quitting.")
                    break
                if not raw.isdigit():
                    print("[Input] Must be a number 0-8.")
                    continue
                pos = int(raw)
                if pos < 0 or pos > 8:
                    print("[Input] Out of range 0-8.")
                    continue
                # check cell not occupied locally (optimistic check)
                with self.lock:
                    board = s.get("board", [])
                    if board and board[pos]:
                        print("[Input] Cell already occupied. Choose another.")
                        continue
                # publish move
                msg = {"player": self.symbol, "pos": pos, "player_name": self.name}
                self.client.publish(self.moves_topic, json.dumps(msg), qos=1)
                print(f"[{self.name}] Sent move {pos}")
                break
        finally:
            self.waiting_for_input = False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--game", default="game1", help="Game ID / topic namespace")
    parser.add_argument("--symbol", required=True, choices=["X","O","x","o"], help="Your symbol (X or O)")
    parser.add_argument("--name", default="Player", help="Player name")
    args = parser.parse_args()

    player = TicTacToePlayer(args.broker, args.port, args.game, args.symbol, args.name)

    player.connect()
    print(f"[{player.name}] Waiting for game state.")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
