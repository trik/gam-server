import base64
import hashlib
import hmac
import random
import time

from gam.settings import SECRET_KEY
from gam.utils import force_bytes

try:
    random = random.SystemRandom()
    using_sysrandom = True
except NotImplementedError:
    import warnings
    warnings.warn('A secure pseudo-random number generator is not available '
                  'on your system. Falling back to Mersenne Twister.')

_DEFAULT_ALGORITHM = 'pbkdf2_sha256'
_DEFAULT_ITERATIONS = 120000
_DEFAULT_DIGEST = hashlib.sha256

def pbkdf2(password, salt, iterations, dklen=0, digest=None):
    """Return the hash of password using pbkdf2."""
    if digest is None:
        digest = hashlib.sha256
    dklen = dklen or None
    password = force_bytes(password)
    salt = force_bytes(salt)
    return hashlib.pbkdf2_hmac(digest().name, password, salt, iterations, dklen)

def encode_password(password, salt=None, iterations=None):
    assert password is not None
    assert salt and '$' not in salt
    iterations = iterations or _DEFAULT_ITERATIONS
    hash_str = pbkdf2(password, salt, iterations, digest=_DEFAULT_DIGEST)
    hash_str = base64.b64encode(hash_str).decode('ascii').strip()
    return "%s$%d$%s$%s" % (_DEFAULT_ALGORITHM, iterations, salt, hash_str)

def make_password(password):
    salt = get_random_string()
    return encode_password(password, salt)

def constant_time_compare(val1, val2):
    """Return True if the two strings are equal, False otherwise."""
    return hmac.compare_digest(force_bytes(val1), force_bytes(val2))

def verify_password(password, encoded):
    algorithm, iterations, salt, _ = encoded.split('$', 3)
    assert algorithm == _DEFAULT_ALGORITHM
    encoded_2 = encode_password(password, salt, int(iterations))
    return constant_time_compare(encoded, encoded_2)

def get_random_string(length=12,
                      allowed_chars='abcdefghijklmnopqrstuvwxyz'
                                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
    """
    Return a securely generated random string.
    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits
    """
    if not using_sysrandom:
        # This is ugly, and a hack, but it makes things better than
        # the alternative of predictability. This re-seeds the PRNG
        # using a value that is hard for an attacker to predict, every
        # time a random string is required. This may change the
        # properties of the chosen random sequence slightly, but this
        # is better than absolute predictability.
        random.seed(
            hashlib.sha256(
                ('%s%s%s' % (random.getstate(), time.time(), SECRET_KEY)).encode()
            ).digest()
        )
    return ''.join(random.choice(allowed_chars) for i in range(length))
