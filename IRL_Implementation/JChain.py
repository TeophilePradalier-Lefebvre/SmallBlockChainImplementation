import json, JCrypto


#### Data structures


# The state of the chain at a given time is essentially a dictionary of
# variable name -> value pairs

class State(dict):
	
	pass


# Generic Operation class providing a blueprint for specific instances

class Operation():
	
	def __init__(self, content, public_key = None, signature = None):
		
		self.content = content
		self.public_key = public_key
		self.signature = signature
	
	# Returns an instance of a specific Operation class from raw data
	
	def create(data, private_key):
		
		op = eval("%s(data)" % data["op_type"])
		op.public_key = JCrypto.ExtractPublicKey(private_key)
		op.signature = JCrypto.Sign(private_key, op.json(include_signature = False))
		
		return op
		
	# Restores an Operation from (signed) raw data
	
	def from_json(json_str):
		
		return Operation.from_dict(json.loads(json_str))
		
	def from_dict(data):
		
		content = data["content"]
		op = eval("%s(content)" % content["op_type"])
		op.public_key = data["public_key"]
		op.signature = data["signature"]
		
		return op

	# Is this Operation valid in a given State?

	def is_valid(self, state):
		
		return self.is_signature_valid() and self.is_authorized(state) and self.is_op_logic_valid(state)

	# Is signature valid?
	
	def is_signature_valid(self):
		
		return JCrypto.Verify(self.public_key, self.json(include_signature = False), self.signature)

	# Is public key authorized to sign this transaction?
	
	def is_authorized(self, state):
		
		return False
		
	# Is the operation logic valid?
	
	def is_op_logic_valid(self, state):
		
		return False

	# Applies this Operation to a given State and returns the updated State

	def apply(self, state):
	
		return state
		
	# JSON canonical representation
	
	def json(self, include_signature = True):
		
		dico = self.__dict__ if include_signature else self.content
		
		return json.dumps(dico, sort_keys=True, indent=2)
	
	# Standard printing
	
	def __repr__(self):
		
		return self.json()
		
	def hash(self):
		
		return JCrypto.simple_hash(self.json())


# A ledger is just a list of Operations

class Ledger(list):
	
	# Computes the final state of the ledger starting from initial state
	
	def apply_ops(self, starting_state = State({}), bypass_checks = True):
		
		state = State(starting_state)
		
		for op in self:
			
			if bypass_checks or op.is_valid(state):
				state = op.apply(state)
				
		return state
		
	# Checks the validity of all operations
	
	def is_valid(self, starting_state = State({})):
		
		state = State(starting_state)
		
		for op in self:
			
			if not op.is_valid(state):
				return False
			state = op.apply(state)
			
		return True
		
	def json(self):
		
		return json.dumps(self, sort_keys=True, indent=2, default=vars)
		
	def __repr__(self):
		
		return self.json()


# Block with content + hash of previous block

class Block():
	
	def __init__(self, ops, prev_hash = None, public_key = None, signature = None):
		
		self.content = {"operations": ops, "prev_hash": prev_hash}
		self.public_key = public_key
		self.signature = signature
		
	def create(ops, prev_hash, private_key):
		
		block = Block(ops, prev_hash)
		block.public_key = JCrypto.ExtractPublicKey(private_key)
		block.signature = JCrypto.Sign(private_key, block.json(include_signature = False))
		
		return block
		
	def from_dict(data):

		return Block([ Operation.from_dict(op) for op in data["content"]["operations"]], data["content"]["prev_hash"], data["public_key"], data["signature"])
		
	def json(self, include_signature = True):
		
		dico = self.__dict__ if include_signature else self.content
		
		return json.dumps(dico, sort_keys=True, indent=2, default=vars)
		
	def __repr__(self):
		
		return self.json()
		
	def hash(self):
		
		return JCrypto.simple_hash(self.json())
		
	def is_signature_valid(self):
		
		return JCrypto.Verify(self.public_key, self.json(include_signature = False), self.signature)


# A blockchain is basically just an ordered list of blocks

class Blockchain(list):
	
	def check_hashes(self):
		
		prev_hash = None
		
		for b in self:
			if b.content["prev_hash"] != prev_hash:
				return False
			prev_hash = b.hash()
			
		return True
		
	def from_json(json_str):
		
		data = json.loads(json_str)
		return Blockchain.from_dict(data)
		
	def from_dict(data):
		
		return Blockchain([Block.from_dict(b) for b in data])
		
	def hash(self):
		
		if self != []:
			return self[-1].hash()
			
	def json(self):
		
		s = "[\n"

		for b in self:
			for line in b.json().split("\n"):
				s += "  " + line + "\n"
			s = s[:-1] + ",\n"
    
		s = s[:-2] + "\n]"
		
		return s
		
	def state(self, init_state):
	
		state = init_state
		
		for b in self:
			for op in b.content["operations"]:
				state = op.apply(state)
				
		return state
		
	# Checks if operation is present in current
	# Could be vastly optimized using Merkle trees!
	
	def contains(self, op):
		
		h = op.hash()
		
		for b in self:
			for o in b.content["operations"]:
				if o.hash() == h:
					return True
					
		return False


#### Specific Operations


# Transferring tokens from one integer variable to another
		
class Transfer(Operation):
	
	# Only owner of tokens can authorize a transfer
	
	def is_authorized(self, state):

		return self.public_key == self.content["source"]
	
	# Source must be defined and contains enough tokens
	
	def is_op_logic_valid(self, state):
		
		return (self.content["source"] in state) and (state[self.content["source"]] >= self.content["amount"])
	
	# Transfers tokens from source to target
	# Target variable is created is needed
	
	def apply(self, state):
		
		if self.content["target"] not in state:
			state[self.content["target"]] = 0
		
		state[self.content["source"]] -= self.content["amount"]
		state[self.content["target"]] += self.content["amount"]
		
		return state
		

# Initialization of a new integer (account) variable
		
class Init(Operation):
	
	# Checks that the variable is not already defined
		
	def is_op_logic_valid(self, state):
		
		return self.content["name"] not in state
		
	# Only allowed if comes from an Admin public key
	
	def is_authorized(self, state):
		
		return "admin_keys" in state and self.public_key in state["admin_keys"]

	# Adds variable with given value to state

	def apply(self, state):
	
		state[self.content["name"]] = self.content["amount"]
		return state


# Enrols a new admin key

class EnrolAdminKey(Operation):
	
	# Checks if key not already present
		
	def is_op_logic_valid(self, state):
		
		return ("admin_keys" not in state) or (self.content["key"] not in state["admin_keys"])

	# Only allowed if comes from an already established Admin public key
	
	def is_authorized(self, state):
		
		return ("admin_keys" not in state) or ("admin_keys" in state and self.public_key in state["admin_keys"])

	# Adds key to the list of admin keys

	def apply(self, state):
		
		if "admin_keys" not in state:
			state["admin_keys"] = []
		
		state["admin_keys"].append(self.content["key"])
		return state


# Takes a snapshot of the current state

class Snapshot(Operation):
	
	# Only allowed if comes from an already established Admin public key
	
	def is_authorized(self, state):
		
		return "admin_keys" in state and self.public_key in state["admin_keys"]
	
	# Valid in a list of operations if it describes the current state
	
	def is_op_logic_valid(self, current_state):
		
		return current_state == self.content["state"]
	
	# If checks are bypassed, this will restore the saved state
	
	def apply(self, current_state):
		
		return self.state


print("JChain v1.0 loaded - hopefully good enough for now!")
