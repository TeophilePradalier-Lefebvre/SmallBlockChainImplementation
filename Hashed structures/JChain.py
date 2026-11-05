# The state of the ledger at a given time is essentially a dictionary of
# variable name -> value pairs

class State(dict):
	
	pass


# Generic Operation class providing a blueprint for specific instances

class Operation():
	
	# Returns an instance of a specific Operation class from raw data
	
	def create(data):
		
		match data["op_type"]:
			
			case "Init":
				
				return Init(data)
			
			case "Transfer":
				
				return Transfer(data)

	# Is this Operation valid in a given State?

	def is_valid(self, state):
		
		return True

	# Applies this Operation to a given State and returns the updated State

	def apply(self, state):
	
		return state


# A ledger is just for now a list of Operations

class Ledger(list):
	
	# Constructor from raw data
	
	def __init__(self, data):
		
		for raw_op in data:
			
			self.append( Operation.create(raw_op) )
	
	# Computes the final state of the ledger starting from initial state
	
	def apply_ops(self, starting_state = State({}), bypass_checks = False):
		
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
				print(op.state)
				print(state)
				return False
			state = op.apply(state)
			
		return True
			

# Transferring tokens from one integer variable to another
		
class Transfer(Operation):
	
	# Constructor taking a dictionary as raw data
	
	def __init__(self, data):
	
		self.type = data["op_type"]
		self.source = data["source"]
		self.target = data["target"]
		self.amount = data["amount"]
	
	# Source must be defined and contains enough tokens
	
	def is_valid(self, state):
		
		return (self.source in state) and (state[self.source] >= self.amount)
	
	# Transfers tokens from source to target
	# Target variable is created is needed
	
	def apply(self, state):
		
		if self.target not in state:
			state[self.target] = 0
		
		state[self.source] -= self.amount		
		state[self.target] += self.amount
		
		return state
		
		
# Initialization of a new integer (account) variable
		
class Init(Operation):
	
	# Constructor taking a dictionary as raw data
	
	def __init__(self, data):
		
		self.type = data["op_type"]
		self.name = data["name"]
		self.value = data["value"]
		
	# Checks that the variable is not already defined
		
	def is_valid(self, state):
		
		return self.name not in state

	# Adds variable with given value to state

	def apply(self, state):
	
		state[self.name] = self.value

		return state
		
		
# Takes a snapshot of the current state

class Snapshot(Operation):
	
	def __init__(self, state):
		
		self.type = "Snapshot"
		self.state = state
	
	# Valid in a list of operations if it describes the current state
	
	def is_valid(self, current_state):
		
		return current_state == self.state
	
	# If checks are bypassed, this will restore the saved state
	
	def apply(self, current_state):
		
		return self.state
