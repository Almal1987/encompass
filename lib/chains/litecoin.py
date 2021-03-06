'''Chain-specific Litecoin code'''
from cryptocur import CryptoCur, hash_encode, hash_decode, rev_hex, int_to_hex, sha256, Hash
import os
try:
    from ltc_scrypt import getPoWHash
except ImportError:
    print("cannot import ltc_scrypt, using fallback")
    from scrypt import scrypt_1024_1_1_80 as getPoWHash

class Litecoin(CryptoCur):
    PoW = True
    chain_index = 2
    coin_name = 'Litecoin'
    code = 'LTC'
    p2pkh_version = 48
    p2sh_version = 5
    wif_version = 176

    block_explorers = {
        'explorer.litecoin.net': 'http://explorer.litecoin.net/tx/',
        'block-explorer.com': 'http://block-explorer.com/tx/',
        'Blockr.io': 'https://ltc.blockr.io/tx/info/'
    }

    base_units = {
        'LTC': 8,
        'mLTC': 5
    }


    DEFAULT_PORTS = {'t':'50001', 's':'50002', 'h':'8081', 'g':'8082'}

    DEFAULT_SERVERS = {
        'alocoin.org': DEFAULT_PORTS,
        'cltc.mooo.com': {'t':'50003', 's':'50004', 'h':'8083', 'g':'8084'},
        'electrum-a.cloudapp.net': DEFAULT_PORTS,
        'electrum-ltc.bysh.me': DEFAULT_PORTS,
        'electrum-ltc.koddos.com': DEFAULT_PORTS,
        'electrum-ltc.thwg.org': DEFAULT_PORTS,
        'electrum.litecoinguard.com': DEFAULT_PORTS,
        'electrum.ltc.xurious.com': DEFAULT_PORTS,
        'electrum.lurkmore.com': DEFAULT_PORTS,
        'electrum.mmitech.info': DEFAULT_PORTS,
        'electrum.snicter.com': DEFAULT_PORTS,
        'electrum.wmpb.tc': {'t':'50001', 's':'50002', 'h':'50081', 'g':'50082'},
        'electrum1.wemineltc.com': DEFAULT_PORTS,
        'explorer.litecoin.net': DEFAULT_PORTS,
        'ltc.electrum.in': DEFAULT_PORTS,
        'rho.hicapacity.org': DEFAULT_PORTS,
    }

    def set_headers_path(self, path):
        self.headers_path = path

    def path(self):
        return self.headers_path

    def verify_chain(self, chain):

        first_header = chain[0]
        prev_header = self.read_header(first_header.get('block_height') -1)

        for header in chain:

            height = header.get('block_height')

            prev_hash = self.hash_header(prev_header)
            bits, target = self.get_target(height/2016, chain)
            _hash = self.pow_hash_header(header)
            try:
                assert prev_hash == header.get('prev_block_hash')
                assert bits == header.get('bits')
                assert int('0x'+_hash,16) < target
            except Exception:
                return False

            prev_header = header

        return True

    def verify_chunk(self, index, hexdata):
        data = hexdata.decode('hex')
        height = index*2016
        num = len(data)/80

        if index == 0:  
            previous_hash = ("0"*64)
        else:
            prev_header = self.read_header(index*2016-1)
            if prev_header is None: raise
            previous_hash = self.hash_header(prev_header)

        bits, target = self.get_target(index)

        for i in range(num):
            height = index*2016 + i
            raw_header = data[i*80:(i+1)*80]
            header = self.header_from_string(raw_header)
            _hash = self.pow_hash_header(header)
            assert previous_hash == header.get('prev_block_hash')
            assert bits == header.get('bits')
            assert int('0x'+_hash,16) < target

            previous_header = header
            previous_hash = self.hash_header(header)

        self.save_chunk(index, data)

    def header_to_string(self, res):
        s = int_to_hex(res.get('version'),4) \
            + rev_hex(res.get('prev_block_hash')) \
            + rev_hex(res.get('merkle_root')) \
            + int_to_hex(int(res.get('timestamp')),4) \
            + int_to_hex(int(res.get('bits')),4) \
            + int_to_hex(int(res.get('nonce')),4)
        return s


    def header_from_string(self, s):
        hex_to_int = lambda s: int('0x' + s[::-1].encode('hex'), 16)
        h = {}
        h['version'] = hex_to_int(s[0:4])
        h['prev_block_hash'] = hash_encode(s[4:36])
        h['merkle_root'] = hash_encode(s[36:68])
        h['timestamp'] = hex_to_int(s[68:72])
        h['bits'] = hex_to_int(s[72:76])
        h['nonce'] = hex_to_int(s[76:80])
        return h

    def hash_header(self, header):
        return rev_hex(Hash(self.header_to_string(header).decode('hex')).encode('hex'))

    def pow_hash_header(self, header):
        return rev_hex(getPoWHash(self.header_to_string(header).decode('hex')).encode('hex'))


    def save_chunk(self, index, chunk):
        filename = self.path()
        f = open(filename,'rb+')
        f.seek(index*2016*80)
        h = f.write(chunk)
        f.close()

    def save_header(self, header):
        data = self.header_to_string(header).decode('hex')
        assert len(data) == 80
        height = header.get('block_height')
        filename = self.path()
        f = open(filename,'rb+')
        f.seek(height*80)
        h = f.write(data)
        f.close()

    def read_header(self, block_height):
        name = self.path()
        if os.path.exists(name):
            f = open(name,'rb')
            f.seek(block_height*80)
            h = f.read(80)
            f.close()
            if len(h) == 80:
                h = self.header_from_string(h)
                return h

    def get_target(self, index, chain=[]):

        max_target = 0x00000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        if index == 0: return 0x1e0ffff0, 0x00000FFFF0000000000000000000000000000000000000000000000000000000

        # Litecoin: go back the full period unless it's the first retarget
        if index == 1:
            first = self.read_header(0)
        else:
            first = self.read_header((index-1)*2016-1)
        last = self.read_header(index*2016-1)
        if last is None:
            for h in chain:
                if h.get('block_height') == index*2016-1:
                    last = h

        nActualTimespan = last.get('timestamp') - first.get('timestamp')
        nTargetTimespan = 84*60*60
        nActualTimespan = max(nActualTimespan, nTargetTimespan/4)
        nActualTimespan = min(nActualTimespan, nTargetTimespan*4)

        bits = last.get('bits')
        # convert to bignum
        MM = 256*256*256
        a = bits%MM
        if a < 0x8000:
            a *= 256
        target = (a) * pow(2, 8 * (bits/MM - 3))

        # new target
        new_target = min( max_target, (target * nActualTimespan)/nTargetTimespan )

        # convert it to bits
        c = ("%064X"%new_target)[2:]
        i = 31
        while c[0:2]=="00":
            c = c[2:]
            i -= 1

        c = int('0x'+c[0:6],16)
        if c >= 0x800000:
            c /= 256
            i += 1

        new_bits = c + MM * i
        return new_bits, new_target

