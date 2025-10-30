# ACTIVIDAD_1.4
# Tic-Tac-Toe sobre MQTT

Este proyecto implementa un juego de Tres en Raya (Tic-Tac-Toe) multijugador utilizando el protocolo MQTT para la comunicación en tiempo real entre un servidor central y múltiples jugadores.

El sistema se divide en dos componentes principales:
* `game_server.py`: El árbitro y la fuente de verdad del juego.
* `player.py`: El cliente que un usuario ejecuta para jugar.

## Arquitectura de Comunicación

La comunicación se basa en un patrón de **Publicación/Suscripción (Pub/Sub)**, orquestado por un broker MQTT. Ni el servidor ni los jugadores se comunican directamente entre sí; toda la comunicación pasa a través del broker.

### 1. El Broker MQTT

Es el componente central. Debe estar ejecutándose para que el juego funcione (en este caso Mosquitto). Actúa como una central de correos.

### 2. Los canals (Canales)

El juego utiliza dos canales MQTT para separar la información:

* **Canal de Estado (`tictactoe/{game_id}/state`)**
    * **Quién publica:** Solo el **Servidor** (`game_server.py`).
    * **Quién se suscribe:** Todos los **Jugadores** (`player.py`).
    * **Propósito:** El servidor publica el estado completo del juego (tablero, turno, estado) en este canal. Lo publica con `retain=True`, lo que significa que cualquier jugador que se conecte tarde recibirá inmediatamente el estado más reciente.

* **Canal de Movimientos (`tictactoe/{game_id}/moves`)**
    * **Quién publica:** Solo los **Jugadores** (`player.py`).
    * **Quién se suscribe:** Solo el **Servidor** (`game_server.py`).
    * **Propósito:** Cuando un jugador decide un movimiento, envía un mensaje a este canal.

## Flujo del Juego: Paso a Paso

El proceso de comunicación sigue un ciclo claro:

1.  **Inicio del Servidor:**
    * El `game_server.py` se inicia.
    * Se conecta al broker y se suscribe al canal de movimientos (`.../moves`) para escuchar las jugadas.
    * Publica el estado inicial del juego (tablero vacío, turno 'X', estado 'ongoing') en el canal de estado (`.../state`).

2.  **Inicio del Jugador (ej. Jugador 'X'):**
    * `player.py` (con `--symbol X`) se inicia.
    * Se conecta al broker y se suscribe al canal de estado (`.../state`).
    * Gracias al `retain=True` del servidor, recibe inmediatamente el estado inicial del juego.

3.  **Recepción de Estado (Turno del Jugador):**
    * La función `on_message` del jugador 'X' se activa al recibir el estado.
    * El código comprueba si `data.get("turn") == self.symbol` (es decir, "es mi turno").
    * Si es su turno, **inicia un nuevo hilo** (`threading.Thread`) para ejecutar `prompt_move()`. Esto es crucial para no bloquear el hilo de red de MQTT.

4.  **Envío de Movimiento:**
    * El hilo `prompt_move` pide al usuario una casilla (ej. `4`).
    * Tras validar la entrada, el jugador publica un mensaje JSON en el canal de movimientos (`.../moves`).
    * **Payload del mensaje:** `{"player": "X", "pos": 4, "player_name": "Alice"}`.

5.  **Procesamiento del Servidor:**
    * El `game_server.py` (suscrito a `.../moves`) recibe el JSON de la jugada.
    * Valida la jugada (¿es el turno de 'X'?, ¿la casilla está vacía?).
    * Actualiza su tablero interno (`self.board[pos] = player`).
    * Comprueba si hay un ganador o empate (`evaluate_game()`).
    * Cambia el turno al siguiente jugador (`self.turn = "O"`).

6.  **Publicación del Nuevo Estado:**
    * El servidor publica el estado *actualizado* del juego (nuevo tablero, turno 'O') en el canal `.../state`.

7.  **El Ciclo se Repite:**
    * **Todos** los jugadores (incluido 'X' y ahora 'O') reciben el nuevo estado.
    * El jugador 'X' ve que ya no es su turno y simplemente espera.
    * El jugador 'O' ve que ahora `data.get("turn") == "O"` (es su turno) e inicia su propio hilo `prompt_move`.
    * El ciclo continúa hasta que el servidor publica un estado `status: "finished"`.

## Manejo de Hilos (Punto Clave)

El `player.py` utiliza `threading` para pedir la entrada del usuario (`input()`) en un hilo separado.

**¿Por qué?** La librería Paho-MQTT (`self.client.loop_start()`) usa su propio hilo en segundo plano para manejar la red (recibir mensajes, enviar *pings* de `keepalive`).

Si `input()` se llamara directamente en `on_message`, **bloquearía el hilo de red**. Si el jugador tardara más de 60 segundos (el `keepalive`) en escribir, el cliente no podría enviar su "ping" al broker, el broker asumiría que el cliente se ha desconectado y cerraría la conexión.

Al mover `input()` a un hilo separado, el hilo de red de MQTT sigue funcionando sin interrupciones.

## Cómo Jugar

1.  **Prerrequisito:** Para que se puedan ejecutar los programas es necesario tener instalado Mosquitto
    ```bash
    sudo apt install -y mosquitto
    sudo systemctl enable --now mosquitto
    ```

2.  **Terminal 1 (Servidor):** Inicia el servidor.
    ```bash
    python3 game_server.py --broker localhost --port 1883 --game game1
    ```

3.  **Terminal 2 (Jugador X):** Inicia el primer jugador.
    ```bash
    python3 player.py --broker localhost --port 1883 --game game1 --symbol X --name Alice
    ```

4.  **Terminal 3 (Jugador O):** Inicia el segundo jugador.
    ```bash
    python3 player.py --broker localhost --port 1883 --game game1 --symbol O --name Bob
    ```

5.  Juega siguiendo las instrucciones en las terminales de los jugadores.