# usage: python Node.py <config.json>

import socket, threading, sys, json, JCrypto, JChain

## Utility functions

class Address:
		
	def couple(s):
		t = s.split(":")
		return (t[0], int(t[1]))
		
	def host(s):
		
		return Address.couple(s)[0]
		
	def port(s):
		
		return Address.couple(s)[1]
		
	def string(c):
		
		return c[0] + ":" + c[1]

## Main class

class Node:
	
	def from_json(data):
		
		self = Node()
		
		self.priv_key = data["priv_key"]
		self.pub_key = JCrypto.ExtractPublicKey(self.priv_key)
		
		self.address = data["address"]
		self.monitor = data["monitor"]
		
		self.peers = []
		self.max_peers = data["max_peers"]
		
		self.mempool = {}
		
		self.chain = JChain.Blockchain([JChain.Block.from_dict(data["genesis"])])
		self.state = self.chain.state({})
		
		return self

	def start(self):
		
		threading.Thread(target=self.listen, daemon=True).start()
		self.report_status()

	def report_status(self):
		self.log({"type": "STATUS", "from": self.pub_key, "address": self.address, "length": len(self.chain), "hash": self.chain.hash()})

	def listen(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.bind(("",Address.port(self.address)))
		s.listen()

		while True:
			conn, _ = s.accept()
			data = conn.recv(8192)
			if data:
				self.handle_message(json.loads(data.decode()))
			conn.close()
			
	def add_peer(self, peer, hello=True):
		
		if len(self.peers) < self.max_peers and peer not in self.peers and peer != self.address:
			self.peers.append(peer)
			if hello:
				self.send(peer, {"type": "HELLO", "from": self.address})

	def send(self, peer, message):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect(Address.couple(peer))
			s.send(json.dumps(message).encode())
			s.close()
		except:
			print(f"Communication error with peer {peer}; removing from list")
			self.peers.remove(peer)
			
	def log(self, message):
		if self.monitor:
			self.send(self.monitor, message)
			
	def broadcast(self, message):
		
		for peer in self.peers:
			self.send(peer, message)

	def handle_message(self, msg):
		t = msg["type"]
		
		if t == "CHAIN_REQUEST":
			peer = msg["from"]
			print(f"[+] Sending current chain to {peer}")
			node.send(peer, {"type": "NEW_CHAIN", "from": self.address, "chain": self.chain.json()})
		
		elif t == "HELLO":
			peer = msg["from"]
			print(f"[+] {peer} says HELLO")
			self.add_peer(peer, hello=False)
			
		elif t == "KNOWN_PEERS":
			print(f"[+] Received peer list from {msg["from"]}")
			for peer in msg["peers"]:
				self.add_peer(peer)
				
		elif t == "NEW_CHAIN":
			print(f"[+] Received new chain from {msg["from"]}")
			new_chain = JChain.Blockchain.from_json(msg["chain"])
			if len(new_chain) > len(self.chain) and new_chain.check_hashes():
				self.chain = new_chain
				self.state = self.chain.state({})
				self.report_status()
				node.broadcast({"type": "NEW_STATS", "from": node.address, "length": len(node.chain), "hash": node.chain.hash()})
			
		elif t == "NEW_OP":
			op = JChain.Operation.from_json(msg["op"])
			h = op.hash()
			print(f"[+] Operation {op.hash()} received from {msg["from"]}")
			if h not in self.mempool and op.is_signature_valid():
				self.mempool[h] = op
				node.broadcast({"type": "NEW_OP", "from": node.address, "op": op.json()})
				print(f"[+] Operation {op.hash()} added to pool")
				
		elif t == "NEW_STATS":
			peer = msg["from"]
			length = msg["length"]
			print(f"[+] Stats received from {peer}: length {length}, hash {msg["hash"]}")
			if length > len(self.chain):
				node.send(peer, {"type": "CHAIN_REQUEST", "from": self.address})
		
		elif t == "PEER_REQUEST":
			peer = msg["from"]
			print(f"[+] Peer request received from {peer}")
			self.send(peer, {"type": "KNOWN_PEERS", "peers": self.peers, "from": self.address})
			
		elif t == "PING":
			peer = msg["from"]
			print(f"[+] Ping received from {peer}")
			self.send(peer, {"type": "HELLO", "from": self.address})
			
		elif t == "STAT_REQUEST":
			peer = msg["from"]
			print(f"[+] Stat request received from {peer}")
			self.send(peer, {"type": "NEW_STATS", "from": self.address, "length": len(self.chain), "hash": self.chain.hash()})
			
		elif t == "TEST":
			print(f"[+] Test message received from {msg["from"]}")
			
		else:
			print(f"[+] Unknown message type {msg}")
			
	def __repr__(self):
		
		return f"Node {self.pub_key} running on {self.address}"

if __name__ == "__main__":
	
	with open(sys.argv[1]) as file:
		node = Node.from_json(json.load(file))
	
	node.start()
	print(node)

	while True:
		parse = input("> ").split()
		cmd = parse[0] if len(parse) else ""

		if cmd == "add_peer":
			node.add_peer(parse[1])
			
		elif cmd == "ask_peers":
			node.broadcast({"type": "PEER_REQUEST", "from": f"{node.address}"})
			
		elif cmd == "ask_stats":
			node.broadcast({"type": "STAT_REQUEST", "from": f"{node.address}"})
			
			
		elif cmd == "balance":
			if node.pub_key in node.state:
				print(node.state[node.pub_key])
			else:
				print(0)
				
		elif cmd == "block":
			print(node.chain[int(parse[1])])
			
		elif cmd == "chain":
			print(f"Length {len(node.chain)}, hash {node.chain.hash()}")
			
		elif cmd == "create_block":
			
			state = JChain.State(node.state)
			ops = []
			
			for op in node.mempool.values():
				
				if op.is_valid(state) and not node.chain.contains(op):
					ops.append(op)
					state = op.apply(state)
					
			node.mempool = {}
					
			node.chain.append( JChain.Block.create(ops, node.chain.hash(), node.priv_key) )
			node.state = state
			node.report_status()
			node.broadcast({"type": "NEW_STATS", "from": node.address, "length": len(node.chain), "hash": node.chain.hash()})

		elif cmd == "exit":
			exit()

		elif cmd == "full_chain":
			print(node.chain)

		elif cmd == "help":
			print()
			print("Known commands: ")
			print()
			print("add_peer <address>          - adds a new peer")
			print("ask_peers                   - asks peers for their list of peers")
			print("ask_stats                   - asks peers for the stats of their chains")
			print("balance                     - prints current number of tokens owned")
			print("block <num>                 - displays a given block from the current chain")
			print("chain                       - prints info on current chain")
			print("create_block                - creates new block with all valid pending operations")
			print("exit                        - shuts down the node")
			print("full_chain                  - displays current chain")
			print("help                        - prints known commands")
			print("mempool                     - prints current pending operations")
			print("peers                       - prints known peers")
			print("purge_pool                  - manually empties mempool")
			print("purge_peers                 - asks peers if they are still alive")
			print("state                       - prints current state of the chain")
			print("status                      - reports current status to monitor")
			print("test                        - broadcasts a test message")
			print("transfer <amount> <pub_key> - creates and broadcasts a Transfer operation")
			print("whoami                      - displays node information")
			print()

		elif cmd == "mempool":
			print(node.mempool)

		elif cmd == "purge_pool":
			node.mempool = {}

		elif cmd == "peers":
			print(node.peers)
			
		elif cmd == "purge_peers":
			node.broadcast({"type": "PING", "from": node.address})
			node.peers = []
			
		elif cmd == "req_chain":
			node.send(parse[1], {"type": "CHAIN_REQUEST", "from": node.address})
			
		elif cmd == "state":
			print(node.state)
			
		elif cmd == "status":
			node.report_status()
			
		elif cmd == "test":
			node.broadcast({"type": "TEST", "from": node.address, "content": "Broadcast message to all peers"})

		elif cmd == "transfer":
			op = JChain.Operation.create({"op_type": "Transfer", "source": node.pub_key, "target": int(parse[2]), "amount": int(parse[1])}, node.priv_key)
			node.mempool[op.hash()] = op
			node.broadcast({"type": "NEW_OP", "from": node.address, "op": op.json()})
			
		elif cmd == "whoami":
			print(node)
	
		elif cmd:
			print(f"Unrecognized command {cmd}")


