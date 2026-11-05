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
	
	# Constructor from raw data
	
	def __init__(self, data):
		
		for raw_op in data:
			
			self.append( Operation.create(raw_op) )
	
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
	
	def __init__(self, content, prev_hash = 0, fuzz = None, public_key = None, signature = None):
		self.content = content
		self.prev_hash = prev_hash
		self.fuzz = fuzz
		self.public_key = public_key
		self.signature = signature

		
	# JSON canonical representation
	
	def json(self, include_signature = True):
		
		dico = self.__dict__.copy()
		if not include_signature:
			dico.pop("signature", None)
		
		return json.dumps(dico, sort_keys=True, indent=2, default=vars)
		
	def __repr__(self):
		
		return self.json()
		
	def hash(self):
		
		return JCrypto.simple_hash(self.json())

	def create(content, private_key, prev_hash = None, fuzz = None):
    	
		block = Block(content, prev_hash, fuzz)
		block.public_key = JCrypto.ExtractPublicKey(private_key)
		block.signature = JCrypto.Sign(private_key, block.json(include_signature = False))
		
		return block

	def is_signature_valid(self):
		
		return JCrypto.Verify(self.public_key, self.json(include_signature = False), self.signature)

	# Only allowed if comes from an Admin public key
	
	def is_authorized(self, state):
		
		return "admin_keys" in state and self.public_key in state["admin_keys"]

	# Gets the amount of tokens staked by the validator of this block
	def get_stake(self, state):

		if not self.public_key:
			return 0
		if f"stake_{self.public_key}" in state:
			return state[f"stake_{self.public_key}"]
		if "stakes" in state and isinstance(state["stakes"], dict):
			return state["stakes"].get(self.public_key, 0)
		return 0

	# Checks PoS condition: signature valid, stake > 0 and Hash(block) < target * stake
	def is_pos_valid(self, state, target):

		if not self.is_signature_valid():
			return False
		stake = self.get_stake(state)
		if stake <= 0:
			return False
		return self.hash() < target * stake

	def is_valid(self, state, target = None):
		
		if target is not None:
			return self.is_pos_valid(state, target)
		return self.is_signature_valid() and self.is_authorized(state)
	


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

	def is_valid(self, starting_state = State({}), target = None):
		state = State(starting_state)
		prev_hash = None
		
		for b in self:

			if b.prev_hash != prev_hash:
				return False

			if not b.is_valid(state, target = target):
				return False

			if hasattr(b.content, "is_valid") and not b.content.is_valid(state):
				return False

			if hasattr(b.content, "apply_ops"):
				state = b.content.apply_ops(state, bypass_checks=False)

			prev_hash = b.hash()
	
		return True





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
		

# Staking tokens to become a validator node

class Stake(Operation):

	# Only the owner of the tokens can authorize staking them
	def is_authorized(self, state):

		account = self.content.get("account", self.public_key)
		return self.public_key == account

	# Account must exist and have enough tokens to stake
	def is_op_logic_valid(self, state):

		account = self.content.get("account", self.public_key)
		amount = self.content.get("amount", 0)
		return (account in state) and (amount > 0) and (state[account] >= amount)

	# Moves staked tokens from account to a separate stake variable
	def apply(self, state):

		account = self.content.get("account", self.public_key)
		amount = self.content.get("amount", 0)
		stake_var = f"stake_{account}"
		if stake_var not in state:
			state[stake_var] = 0

		state[account] -= amount
		state[stake_var] += amount
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
		
		return self.state


print("JChain v0.5 loaded - now with fuzz parameter in blocks")
