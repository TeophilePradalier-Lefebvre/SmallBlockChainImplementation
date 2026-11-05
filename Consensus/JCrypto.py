import hashlib, random


# 32-bit custom hash function

def simple_hash(S):
	return int(hashlib.sha256(bytes(S, "utf8")).digest().hex()[:8], 16)


# Modular division

def div_mod(a, b, p):
	
	return a * pow(b,-1,p) % p


# Mod p elliptic curve in Weierstrass form

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


# Point on a curve
		
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


# Fixed custom 32-bit parameters

E = EllipticCurve(101239643, 29717072, 16741874)
G = EllipticPoint(E, 22861771, 7928731)
q = 101246273


# Packing/unpacking

def pack(x,y):
	
	return 2**32 * x + y

def point_to_int(point):
	
	return pack(point.x, point.y)
	
def unpack(n):
	
	return (n // 2**32, n % 2**32)
	
def int_to_point(n):
	
	(x,y) = unpack(n)
	return EllipticPoint(E, x, y)


# Derive public key from private key

def ExtractPublicKey(private_key):
	
	return point_to_int(private_key * G)
	

# Key pair generation

def KeyGen():
	
	private_key = random.randrange(q)
	public_key = ExtractPublicKey(private_key)
	return (private_key, public_key)


# Schnorr signature

def Sign(private_key, message):
	
	r = random.randrange(q)
	e = simple_hash(str(r * G) + message)
	s = (r - private_key * e) % q
	return pack(s,e)


# Signature verification

def Verify(public_key, message, signature):
	
	(s,e) = unpack(signature)
	return simple_hash(str(s * G + e * int_to_point(public_key)) + message) == e
