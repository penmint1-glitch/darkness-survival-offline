import sys, struct
from capstone import *
from capstone.arm import *

D=open('apk/lib/armeabi/libcocos2dcpp.so','rb').read()
DYN=0x148; DYNSZ=407920; DSTR=0x63ab8
SYMS=[]; BYNAME={}
for i in range(DYNSZ//16):
    o=DYN+i*16
    n,v,s,info,other,sh=struct.unpack_from('<IIIBBH',D,o)
    if n==0: continue
    e=D.index(b'\0',DSTR+n); nm=D[DSTR+n:e].decode('utf-8','replace')
    if sh==8: SYMS.append((v&~1,s,nm)); BYNAME[nm]=v&~1
SYMS.sort()
START=[s[0] for s in SYMS]
import bisect
def sym_at(a):
    i=bisect.bisect_right(START,a)-1
    if i<0: return None
    v,s,n=SYMS[i]
    if a-v < max(s,4): return f"{n}+{a-v}" if a!=v else n
    return None
def bye(a):
    i=bisect.bisect_right(START,a)-1
    if i<0: return None
    return SYMS[i]
def dem(n):
    import re
    n=re.sub(r'^_Z','',n)
    return n
def find(name):
    if name in BYNAME: return BYNAME[name]
    for k in BYNAME:
        if name in k: return BYNAME[k]
    return None

md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def dump(name=None,addr=None,size=None,limit=None,show_bytes=True):
    if name:
        va=find(name)
        if va is None: print("!! not found:",name); return
        r=bye(va); nm=r[2]
    else:
        va=addr&~1; nm=hex(addr)
    code=D[va:va+size] if size else D[va:va+ (bye(va)[1] if bye(va) else 4096)]
    print(f"==== {nm} @0x{va:08x} ====")
    n=0
    for i in md.disasm(code, va):
        ann=''
        if i.mnemonic in ('bl','blx') and i.operands and i.operands[0].type==ARM_OP_IMM:
            s=sym_at(i.operands[0].imm)
            if s: ann='   ; -> '+s
        b=i.bytes.hex() if show_bytes else ''
        print(f"  0x{i.address:08x}: {b:<12} {i.mnemonic:<8} {i.op_str}{ann}")
        n+=1
        if limit and n>=limit: break

if __name__=='__main__':
    mode=sys.argv[1]
    for a in sys.argv[2:]:
        if mode=='sym': dump(name=a)
        else:
            ad,sz=a.split(','); dump(addr=int(ad,16),size=int(sz,16))
