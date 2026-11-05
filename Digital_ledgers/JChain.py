import json, hashlib, random


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

	# Is this Operation valide?

	def is_valid(self, state):
		
		return self.is_signature_valid() and self.is_key_authorized(state) and self.is_logic_valid(state)
		
	# This checks for the validity of the logic of the operation
	
	def is_logic_valid(self, state):
		
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
	
	def is_logic_valid(self, state):
		
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
		
	def is_logic_valid(self, state):
		
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
	
	def is_logic_valid(self, current_state):
		
		return current_state == self.state
	
	# If checks are bypassed, this will restore the saved state
	
	def apply(self, current_state):
		
		return self.state


# Generic hashed block object

class Block():
	
	def __init__(self, content, prev_hashes):
		
		self.content = content
		self.prev_hashes = sorted(prev_hashes)
		
	def json(self):
		
		return json.dumps(self.__dict__, sort_keys=True, indent=2)
		
	def hash(self):
		
		return simple_hash(self.json())
		
	def __repr__(self):
		
		return " ".join(self.json().split())


##### Crypto


# 32-bit custom hash function

def simple_hash(S):
	return int(hashlib.sha256(bytes(S, "utf8")).digest().hex()[:8], 16)


# minimalistic elliptic curve support

def div_mod(a, b, p):
	
	return a * pow(b,-1,p) % p


# courbe elliptique mod p sous forme de Weierstrass

class EllipticCurve:
	
	def __init__(self, p, a, b):
			
		self.p = p
		self.a = a % p
		self.b = b % p
		
	def __repr__(self):
		
		return "Elliptic curve y^2 = x^3 + %sx + %s mod %s" % (self.a, self.b, self.p)
		
	def homog_def_equation(self, x, y, z = 1):
		
		return (y**2*z - x**3 - self.a*x*z**2 - self.b*z**3) % self.p
		
	def point(self, x, y, z = 1, trust = False):
	
		return EllipticPoint(self, x, y, z, trust)
		
	def zero(self):
		
		return EllipticPoint(self, 0, 1, 0, True)
		
	def add(self, P, Q):
		
		if P.E != self or Q.E != self:
			
			raise ValueError("Points must be on same curve")
			
		if P == self.zero():
			
			return Q
			
		if Q == self.zero():
			
			return P
		
		if P.x == Q.x:
			
			if P != Q:  # vertically aligned
				
				return self.zero()
				
			# doubling
			
			if P.y == 0:
				
				return self.zero()
			
			l = div_mod(3*P.x**2 + self.a, 2*P.y, self.p)
			
		else:  # generic case
			
			l = div_mod(Q.y - P.y, Q.x - P.x, self.p)
		
		x = l**2 - (P.x + Q.x)
		y = l * (x - P.x) + P.y
			
		return EllipticPoint(self, x, -y, True)
		
	def mul(self, m, P):
		
		res = self.zero()
		
		if m < 0:
			
			P = P.opp()
			m = -m
		
		for b in bin(m)[2:]:
			
			res = res + res
			if int(b):
				res = res + P
				
		return res


# point on a curve
		
class EllipticPoint:
	
	def __init__(self, E, x, y, z = 1, trust = True):

		if not trust:
			
			if E.homog_def_equation(x,y,z) != 0:
			
				raise ValueError("Point not on curve")
			
			if z % E.p != 0:
				
				x = div_mod(x, z, E.p)
				y = div_mod(y, z, E.p)
				z = 1
				
			else:
				
				x = 0
				y = 1
			
		self.E = E
		self.x = x % E.p
		self.y = y % E.p
		self.z = z % E.p  # assumed 0 or 1
		
	def __eq__(self, other):
	
		return (self.x, self.y, self.z) == (other.x, other.y, other.z)
		
	def __repr__(self):
		
		if self.z == 0:
			return "0"
		return "(%s,%s)" % (self.x, self.y)
			
	def __add__(self, other):
		
		return self.E.add(self, other)
		
	def __sub__(self, other):
		
		return self + other.opp()
		
	def opp(self):
		
		return EllipticPoint(self.E, self.x, -self.y, self.z, True)
		
	def __rmul__(self, m):
		
		return self.E.mul(m, self)
		

# fixed parameters (!INSECURE! for pedagogical purposes only)

EE = EllipticCurve(101239643, 29717072, 16741874)
GG = EllipticPoint(EE, 22861771, 7928731)
qq = 101246273


# packing/unpacking

def pack(x,y):
	
	return 2**32 * x + y

def point_to_int(point):
	
	return pack(point.x, point.y)
	
def unpack(n):
	
	return (n // 2**32, n % 2**32)
	
def int_to_point(n):
	
	(x,y) = unpack(n)
	return EllipticPoint(EE, x, y)


# signature scheme

def ExtractPublicKey(private_key):
	
	return point_to_int(private_key * GG)


def KeyGen():
	
	private_key = random.randrange(qq)
	public_key = ExtractPublicKey(private_key)
	return (private_key, public_key)
	

def Sign(private_key, message):
	
	r = random.randrange(qq)
	e = simple_hash(str(r * GG) + message)
	s = (r - private_key * e) % qq
	return pack(s,e)


def Verify(public_key, message, signature):
	
	(s,e) = unpack(signature)
	return simple_hash(str(s * GG + e * int_to_point(public_key)) + message) == e

print("JChain v0.3 loaded - now with basic signature support!")
