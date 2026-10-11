import struct, dz
D=dz.D
TEXT_OFF=0x2229a8; TEXT_SZ=5187288
def decode_bl(a, hi, lo):
    S=(hi>>10)&1; imm10=hi&0x3ff; J1=(lo>>13)&1; J2=(lo>>11)&1; imm11=lo&0x7ff
    I1=~(J1^S)&1; I2=~(J2^S)&1
    imm=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if S: imm-=1<<25
    return (a+4+imm)|1
CALLERS={}
end=TEXT_OFF+TEXT_SZ
for off in range(TEXT_OFF, end-4, 2):
    hi=struct.unpack_from('<H',D,off)[0]
    if (hi & 0xF800)!=0xF000: continue
    lo=struct.unpack_from('<H',D,off+2)[0]
    if (lo & 0xD000)!=0xD000: continue
    t=decode_bl(off,hi,lo)
    CALLERS.setdefault(t,set()).add(off)
def callers_of(name):
    v=dz.BYNAME.get(name)
    if v is None: return None,[]
    s=CALLERS.get(v|1,set())
    out=set()
    for a in s:
        out.add(dz.sym_at(a-1) or f"0x{a:x}")
    return v,sorted(out)
if __name__=='__main__':
    import sys
    names=sys.argv[1:]
    for n in names:
        v,cs=callers_of(n)
        print(f"### {n} @0x{v:08x}" if v else f"### {n} NOT FOUND")
        for c in cs: print("    ",c)
