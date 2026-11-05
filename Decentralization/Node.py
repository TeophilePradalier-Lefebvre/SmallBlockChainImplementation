# usage: python Node.py <port> <peers>

import socket, threading, sys, json
import JChain, JCrypto

class Node:
	
	def __init__(self, host, port, peers):
		self.host = host
		self.port = port
		self.address = (host, port)
		self.peers = peers
		# Each node keeps its own copy of the chain. That is what replaces the central server. 
		self.chain = JChain.Blockchain()

		# Transactions received but not yet in a block
		self.pending = JChain.Ledger()

		# Without the private key, one cannot SIGN an operation.
		(self.private_key, self.public_key) = JCrypto.KeyGen()

		# The thread listening to the network and the terminal modify the same data (chain, pending).
		# The lock prevents them from modifying it simultaneously.
		self.lock = threading.RLock()

	def start(self):
		threading.Thread(target=self.listen, daemon=True).start()
		self.broadcast({"type": "HELLO", "from": self.address})

	# The old 'conn.recv(8192)' call only read 8,192 bytes. A block often exceeds this size (resulting in truncated JSON)
	#  So we are replacing it with a loop and assigning each connection to its own thread.

	def listen(self):  
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # We are relaunching without delay
		s.bind(self.address)
		s.listen()
		print(f"Node listening on {self.port}")

		while True:
			conn, _ = s.accept()
			# one thread per connection: a slow client does not block the others
			threading.Thread(target=self.handle_connection, args=(conn,), daemon=True).start()

	def handle_connection(self, conn):
		try:
			data = b""
			while True:
				chunk = conn.recv(4096)
				if not chunk:        # The sender has closed, the message is complete
					break
				data += chunk
			if data:
				self.handle_message(json.loads(data.decode()))
		except Exception as e:
			# A malformed message must never crash the node so we handle exceptions.
			print(f"Message ignore ({type(e).__name__}: {e})")
		finally:
			conn.close()

	# We display the error instead of accepting it silently, otherwise, we spend a long time trying to figure out why nothing is happening.
	def send(self, peer, message):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(2)                  # do not wait indefinitely for a dead peer
			s.connect(tuple(peer))           # tuple() : if a list (JSON) is received
			s.sendall(json.dumps(message).encode())   # sendall sends everything (send might stop early)
			s.close()
			return True
		except Exception:
			print(f"Pair injoignable : {tuple(peer)}")
			return False
			
	def broadcast(self, message):
		
		for peer in list(self.peers):
			self.send(peer, message)

	# JSON converts tuples into lists: ("localhost", 5001) arrives as ["localhost", 5001].
	# We convert it back to a tuple; otherwise, "peer in self.peers" would always be false (tuple != JSON format).
	# Returns True if the peer was unknown, False otherwise.
	def add_peer(self, peer):
		peer = tuple(peer)
		with self.lock:
			if peer != self.address and peer not in self.peers:   # neither me nor a duplicate
				self.peers.append(peer)
				return True
		return False

	# We request the peer list from all our peers. We include a "from" field so they know where to reply.
	# The protocol is one-way (we send and then close) so there is no return channel.
	# The peer will therefore send us back a new "PEERS" message.
	def discover(self):
		self.broadcast({"type": "GET_PEERS", "from": self.address})

	# All operations in the chain in order and laid out step-by-step
	# (Blockchain = list of blocks / each block = list of operations)	
	def chain_ops(self):
		return JChain.Ledger([op for block in self.chain for op in block.operations])

	# The state is always recalculated from scratch; it is never cached.
	# remark : EnrolAdminKey.apply appends to a list, if done on a "partial" copy, the original would be modified as well.
	def current_state(self):
		return self.chain_ops().apply_ops()

	# If is_valid crashes (absurd public key/missing field/ ...), the operation is treated as invalid instead of causing the node to crash.
	def safe_is_valid(self, op, state):
		try:
			return op.is_valid(state)
		except Exception:
			return False

	# The hashes are chained together, and each operation is valid—in sequence—within the state resulting from the preceding operations.
	def check_chain(self, chain = None):
		chain = self.chain if chain is None else chain

		if not chain.check_hashes():          # method already present in JChain
			return False

		state = JChain.State({})
		for block in chain:
			for op in block.operations:
				if not self.safe_is_valid(op, state):
					return False
				state = op.apply(state)       # The operation modifies the state for the next one.
		return True

	# Compare my terminal hash with that of each peer
	def compare(self):
		with self.lock:
			# Comparing via the latest hash only makes sense if one's own chain is coherent
			if not self.chain.check_hashes():
				print("La chaine est incoherente : comparaison peu fiable")
			print(f"Mon hash terminal : {self.chain.hash()} ({len(self.chain)} blocs)")
		# We request the terminal hash from all peers => they respond with "HASH".
		self.broadcast({"type": "GET_HASH", "from": self.address})

	# Is this operation already known (pending OR already in the chain)?
	# We compare using json()
	# Otherwise we would have a problem: an infinite rebroadcast loop between nodes, where an operation already added 
	# to the chain could return to a pending state and be replayed.
	def is_known_op(self, op):
		j = op.json()
		return any(p.json() == j for p in self.pending) or any(o.json() == j for o in self.chain_ops())

	# Add to the pending queue and then broadcast. Return False if already known => stop here.
	#  Thus each node retransmits an operation only once.
	def add_pending(self, op):
		with self.lock:
			if self.is_known_op(op):
				return False
			self.pending.append(op)
		# json.loads(op.json()) : we are sending a dictionary, absolutely not text within text.
		self.broadcast({"type": "OPERATION", "op": json.loads(op.json())})
		return True

	# Remove from 'pending' the operations that are now in a block
	def remove_from_pending(self, ops):
		done = {op.json() for op in ops}
		with self.lock:
			self.pending = JChain.Ledger([p for p in self.pending if p.json() not in done])

	# Creates an operation signed with our private key => then broadcasts it.
	# data must contain "op_type" (ex : "Transfer") and the operation's fields.
	def emit(self, data):
		op = JChain.Operation.create(data, self.private_key)   # signs off on the operation
		self.add_pending(op)
		print(f"Operation emise : {op.content}")

	# Keep valid operations, remove (and display) invalid ones.
	# The three checks performed by is_valid are the same as before: signature, authorization, and internal logic.
	def clean_pending(self):
		with self.lock:
			state = self.current_state()      # Starting point: the state of the chain
			kept = JChain.Ledger()

			for op in self.pending:           # In the correct order obviously.
				if self.safe_is_valid(op, state):
					state = op.apply(state)   # Apply immediately, the next operation may depend on this one.
					kept.append(op)
				else:
					print(f"Operation invalide retiree : {op.content}")

			self.pending = kept

		# Creates a block containing valid pending operations, adds it, and broadcasts it.
	def create_block(self):
		with self.lock:
			self.clean_pending()              # never put anything invalid in a block

			if len(self.pending) == 0:
				print("Aucune operation valide en attente : pas de bloc")
				return

			# prev_hash = hash of the previous block (None for the first one):
			# It is this link that "chains" the blocks together.
			block = JChain.Block(self.pending, self.chain.hash())
			self.chain.append(block)
			self.pending = JChain.Ledger()   # everything is in the block: clear the wait queue
			print(f"Bloc ajoute, hash terminal = {block.hash()}")

		self.broadcast({"type": "BLOCK", "from": self.address, "block": json.loads(block.json())})

	# Processes a block received from another node (reminder: d = dictionary from JSON)
	# Processes a block received from another node (d => dictionary from JSON / sender => who sent it)
	def receive_block(self, d, sender):
		block = JChain.Block.from_dict(d)    # dict -> Block object
		behind = False

		with self.lock:
			# Do I already have it (anywhere in my chain) ? -> we ignore it => This is what stops the propagation loop.
			if block.hash() in [b.hash() for b in self.chain]:
				return

			# The block does not attach to the end of my chain: I am late, or we diverged.
			# Instead of just rejecting it I ask the sender for its whole chain :
			if block.prev_hash != self.chain.hash():
				behind = True
			else:
				# Naturally you never trust someone else's block => double-check everything.
				state = self.current_state()
				for op in block.operations:
					if not self.safe_is_valid(op, state):
						print("Bloc recu contient une operation invalide : rejete")
						return
					state = op.apply(state)

				self.chain.append(block)
				self.remove_from_pending(block.operations)   # They are in the chain now
				print(f"Bloc recu et ajoute, hash terminal = {block.hash()}")

		if behind:
			print("Bloc recu ne se rattache pas a ma chaine : je demande sa chaine a l'expediteur")
			self.send(sender, {"type": "GET_CHAIN", "from": self.address})
		else:
			# We pass it on to others (in case not everyone is connected to everyone else)
			self.broadcast({"type": "BLOCK", "from": self.address, "block": d})

		# Synchronization: ask one peer by port (or all peers) for their whole chain
	def sync(self, port = None):
		request = {"type": "GET_CHAIN", "from": self.address}
		if port is None:
			self.broadcast(request)
		else:
			self.send(("localhost", port), request)

	# A whole chain received from a peer => We adopt it only if it is longer than mine and of course completely valid (hashes + every operation)
	def receive_chain(self, blocks):
		candidate = JChain.Blockchain([JChain.Block.from_dict(b) for b in blocks])

		with self.lock:
			if len(candidate) <= len(self.chain):
				print("Chaine recue pas plus longue que la mienne : ignoree")
				return
			if not self.check_chain(candidate):
				print("Chaine recue invalide : rejetee")
				return

			old_ops = self.chain_ops()
			self.chain = candidate
			new_ops = {op.json() for op in self.chain_ops()}

			# Operations of my old blocks that are not in the new chain => go back to pending
			for op in old_ops:
				if op.json() not in new_ops:
					self.pending.append(op)
			# Operations now in the chain no longer wait
			self.remove_from_pending(self.chain_ops())
			print(f"Chaine mise a jour : {len(self.chain)} blocs")

	# Add a peer by hand => we must be able to reach it
	def connect(self, port):
		peer = ("localhost", port)
		if peer == self.address or peer in self.peers:
			print("Pair deja connu ou adresse invalide")
			return
		if self.send(peer, {"type": "HELLO", "from": self.address}):
			self.add_peer(peer)
			print(f"Connecte a {peer}")

	# Remove a peer and tell it to forget us
	def disconnect(self, port):
		peer = ("localhost", port)
		with self.lock:
			if peer not in self.peers:
				print("Pair inconnu")
				return
			self.peers.remove(peer)
		self.send(peer, {"type": "BYE", "from": self.address})
		print(f"Deconnecte de {peer}")

	def handle_message(self, msg):
		t = msg["type"]

		if t == "HELLO":
			peer = tuple(msg["from"])
			if self.add_peer(peer):                     # add_peer prevents duplicates
				print(f"New node connected on {peer}")

		# Peer Discovery
		elif t == "GET_PEERS":                          # Someone is asking for my peers
			self.add_peer(msg["from"])                  # and by the way I know him
			self.send(msg["from"], {"type": "PEERS", "from": self.address, "peers": self.peers})

		elif t == "PEERS":                              # Response to my request
			for p in msg["peers"]:
				if self.add_peer(p):
					print(f"Nouveau pair decouvert : {tuple(p)}")
					self.send(p, {"type": "HELLO", "from": self.address})   # that he might know me too

		# Comparison of final hashes
		elif t == "GET_HASH":
			self.send(msg["from"], {"type": "HASH", "from": self.address,
				"hash": self.chain.hash(), "length": len(self.chain)})

		elif t == "HASH":
			same = (msg["hash"] == self.chain.hash())
			verdict = "IDENTIQUE" if same else "DIFFERENT"
			print(f"Pair {tuple(msg['from'])} : hash={msg['hash']} ({msg['length']} blocs) -> {verdict}")

		# Operation Received
		elif t == "OPERATION":
			op = JChain.operation_from_dict(msg["op"])  # dict -> Operation object
			if self.add_pending(op):                    # False if already known => we do not loop back.
				print(f"Operation recue : {op.content}")

		# Bloc Received
		elif t == "BLOCK":
			self.receive_block(msg["block"], msg["from"])

		elif t == "GET_CHAIN":                          # Someone asks for my whole chain
			self.send(msg["from"], {"type": "CHAIN", "from": self.address,
				"blocks": [json.loads(b.json()) for b in self.chain]})

		elif t == "CHAIN":                              # Response to my request
			self.receive_chain(msg["blocks"])

		elif t == "BYE":                                # A peer leaves
			peer = tuple(msg["from"])
			with self.lock:
				if peer in self.peers:
					self.peers.remove(peer)
					print(f"Pair deconnecte : {peer}")

		elif t == "TEST":
			print(f"Test message received: {msg}")

		else:
			print(f"Type de message inconnu : {t}")

	# "me" = my public key; otherwise an integer, or a text string. Useful for terminal commands: "transfer me 12345 30"
	def parse_value(self, token):
		if token == "me":
			return self.public_key
		try:
			return int(token)
		except ValueError:
			return token

	def show_chain(self):
		with self.lock:
			if not self.chain:
				print("(chaine vide)")
			for i, b in enumerate(self.chain):
				print(f"bloc {i} : hash={b.hash()} prev={b.prev_hash} ({len(b.operations)} operations)")
				for op in b.operations:
					print(f"    {op.content}")

	def show_pending(self):
		with self.lock:
			if not self.pending:
				print("(aucune operation en attente)")
			for op in self.pending:
				print(f"    {op.content}")

if __name__ == "__main__":
	port = int(sys.argv[1])
	peers = [("localhost", int(p)) for p in sys.argv[2:]]

	node = Node("localhost", port, peers)
	node.start()

	while True:
		try:
			cmd = input("> ").split()      # split(): "transfer me 12 30" -> ["transfer","me","12","30"]
		except EOFError:
			break

		if not cmd:                        # empty line: ignore
			continue

		try:
			c = cmd[0]                     # the name of the command

			if c == "peers":
				print(node.peers)

			elif c == "discover":
				node.discover()

			elif c == "keys":
				print(f"cle publique : {node.public_key}")

			elif c == "chain":
				node.show_chain()

			elif c == "check":
				print("hashs coherents :", node.chain.check_hashes())
				print("chaine complete valide :", node.check_chain())

			elif c == "compare":
				node.compare()

			elif c == "enrol":
				key = node.parse_value(cmd[1]) if len(cmd) > 1 else node.public_key
				node.emit({"op_type": "EnrolAdminKey", "key": key})

			elif c == "init":
				node.emit({"op_type": "Init", "name": node.parse_value(cmd[1]), "value": int(cmd[2])})

			elif c == "transfer":
				node.emit({"op_type": "Transfer", "source": node.parse_value(cmd[1]),
					"target": node.parse_value(cmd[2]), "amount": int(cmd[3])})

			elif c == "pending":
				node.show_pending()

			elif c == "clean":
				node.clean_pending()

			elif c == "block":
				node.create_block()

			elif c == "test":
				node.broadcast({"type": "TEST", "content": "Broadcast message to all peers"})

			elif c == "sync":
				node.sync(int(cmd[1]) if len(cmd) > 1 else None)

			elif c == "connect":
				node.connect(int(cmd[1]))

			elif c == "disconnect":
				node.disconnect(int(cmd[1]))

			elif c == "state":
				print(node.current_state())

			elif c == "exit":
				break

			else:
				print("Commande inconnue")

		# Just in case: forgotten or non-numeric arguments (e.g., "transfer me") — do not crash.
		except (IndexError, ValueError):
			print("Arguments invalides")
