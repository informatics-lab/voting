"""Voting server application."""
import json

from flask import Flask
from flask_sockets import Sockets
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler


app = Flask(__name__)
sockets = Sockets(app)
votes_file = 'votes.json'

try:
    with open(votes_file) as data_file:
        votes = json.load(data_file)
except FileNotFoundError:
    votes = {}
open_sockets = []


def broadcast(sockets, response_type, message):
    if type(sockets) is not list:
        sockets = [sockets]
    for socket in sockets:
        socket.send(json.dumps({"type": response_type, "response": message}))


def count_votes():
    return {key: len(value) for (key, value) in votes.items()}


def count_challenge(challenge):
    return {challenge: count_votes()[challenge]}


def get_own_votes(voter):
    return [challenge for (challenge, votelist) in votes.items() if voter in votelist]


def handle_request(ws, request):
    if "challenge" in request and request["challenge"] not in votes.keys():
        votes[request["challenge"]] = []

    if request["type"] == "vote":
        if request["voter"] in votes[request["challenge"]]:
            votes[request["challenge"]].remove(request["voter"])
        else:
            votes[request["challenge"]].append(request["voter"])
        broadcast(open_sockets, "vote", count_challenge(request["challenge"]))

    if request["type"] == "own":
        broadcast(ws, "own", get_own_votes(request["voter"]))

    if request["type"] == "ping":
        broadcast(ws, "ping", "pong")

    if request["type"] == "sync":
        broadcast(ws, "sync", count_votes())


@sockets.route('/vote')
def vote_socket(ws):
    open_sockets.append(ws)

    while not ws.closed:
        message = ws.receive()
        if message is not None:
            try:
                request = json.loads(message)
            except json.JSONDecodeError:
                print("Bad json, ignoring")
                continue
            handle_request(ws, request)

    open_sockets.remove(ws)


@app.route('/')
def hello():
    return 'Try connecting a websocket to /vote and send some votes!'


if __name__ == "__main__":
    server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    print("Serving the server now.")
    try:
        server.serve_forever()
    finally:
        with open(votes_file, 'w') as outfile:
            json.dump(votes, outfile)
