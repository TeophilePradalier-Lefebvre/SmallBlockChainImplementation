import json, copy, JCrypto

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
	
	def __init__(self, ledger, prev_hash = None):
		
		self.operations = ledger
		self.prev_hash = prev_hash
		
	def json(self):
		
		return json.dumps(self.__dict__, sort_keys=True, indent=2, default=vars)
		
	def __repr__(self):
		
		return self.json()
		
	def hash(self):
		
		return JCrypto.simple_hash(self.json())

	# Reconstruire un Block a partir d'un dictionnaire, recu via le reseau
	def from_dict(d):
		ops = Ledger([operation_from_dict(o) for o in d["operations"]])
		# chaque operation (dict) redevient un objet Operation
		return Block(ops, d["prev_hash"])


# A blockchain is basically just an ordered list of blocks

class Blockchain(list):
	
	def check_hashes(self):
		
		prev_hash = None
		
		for b in self:
			if b.prev_hash != prev_hash:
				return False
			prev_hash = b.hash()
			
		return True
		
	def hash(self):
		
		if self != []:
			return self[-1].hash()


#### Specific Operations


# Transferring tokens from one integer variable to another
		
class Transfer(Operation):
	
	# Only owner of tokens can authorize a transfer
	
	def is_authorized(self, state):

		return self.public_key == self.content["source"]
	
	# Source must be defined and contains enough tokens
	
	def is_op_logic_valid(self, state):
		
		return (self.content["amount"] > 0) and (self.content["source"] in state) and (state[self.content["source"]] >= self.content["amount"]) 
		# On refuse les montants négatifs ou nuls. Avec un montant négatif, state[source] >= amount est toujours vrai et on volerait la cible
	
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
	
		state[self.content["name"]] = self.content["value"]
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
		return State(copy.deepcopy(self.content["state"])) 
	# deepcopy sinon une opération suivante modifierait le contenu du snapshot lui-même (et donc son hash)

OPERATION_TYPES = {
"Init": Init,
"Transfer": Transfer,
"EnrolAdminKey": EnrolAdminKey,
"Snapshot": Snapshot,
}


def operation_from_dict(d):
	
	content = d["content"]
	op_type = content.get("op_type")
	
	if op_type not in OPERATION_TYPES:
		raise ValueError("Type d'opération inconnu : %s" % op_type)
	
	cls = OPERATION_TYPES[op_type]
	return cls(content, d["public_key"], d["signature"])


print("JChain v0.4 loaded - now with signature support at the operation level")
