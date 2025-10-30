import argparse
import json
import threading
import time
from typing import List, Optional
import paho.mqtt.client as mqtt

WIN_LINES = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

class TicTacToeServer:
    def __init__(self, broker, port, game_id, client_id="tictactoe-server"):
        self.broker = broker
        self.port = port
        self.game_id = game_id
        self.moves_topic = f"tictactoe/{game_id}/moves"
        self.state_topic = f"tictactoe/{game_id}/state"

        self.client = mqtt.Client(client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.board  = [None]*9
        self.turn = "X"  
        self.status = "waiting"  # waiting, ongoing, finished
        self.winner = None
        self.players = {} 

    def start(self):
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        self.client.subscribe(self.moves_topic)
        time.sleep(0.1)
        self.status = "ongoing"
        self.publish_state()
        print(f"[Server] Started and subscribed to {self.moves_topic}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[Server] Connected to broker {self.broker}:{self.port} (rc={rc})")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
        except Exception as e:
            print("[Server] Received malformed message:", e)
            return

        if msg.topic == self.moves_topic:
            self.handle_move(data)

    def handle_move(self, data):
        required = {"player","pos"}
        if not required.issubset(data.keys()):
            print("[Server] Move missing fields:", data)
            return
        player = data["player"]
        pos = data["pos"]

        if player != self.turn:
            print(f"[Server] Not {player}'s turn (turn={self.turn}). Ignoring move.")
            return
        if not isinstance(pos, int) or pos < 0 or pos > 8:
            print("[Server] Invalid pos:", pos)
            return
        if self.board[pos] is not None:
            print("[Server] Cell already taken at", pos)
            return

        self.board[pos] = player
        print(f"[Server] Player {player} -> pos {pos}")
        self.evaluate_game()
        if self.status == "ongoing":
            self.turn = "O" if self.turn == "X" else "X"
        self.publish_state()

    def evaluate_game(self):
        b = self.board
        for a,c,d in WIN_LINES:
            if b[a] and b[a] == b[c] == b[d]:
                self.status = "finished"
                self.winner = b[a]
                print(f"[Server] Winner: {self.winner}")
                return
        if all(cell is not None for cell in b):
            self.status = "finished"
            self.winner = None  # draw
            print("[Server] Draw")
            return
        self.status = "ongoing"
        self.winner = None

    def publish_state(self):
        msg = {
            "board": [cell if cell is not None else "" for cell in self.board],
            "turn": self.turn,
            "status": self.status,
            "winner": self.winner
        }
        payload = json.dumps(msg)
        self.client.publish(self.state_topic, payload=payload, qos=1, retain=True)
        print("[Server] Published state:", payload)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--game", default="game1", help="Game ID / topic namespace")
    args = parser.parse_args()

    server = TicTacToeServer(args.broker, args.port, args.game)
    server.start()
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
