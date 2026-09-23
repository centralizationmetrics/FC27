from fractions import Fraction as F
from itertools import product
from math import ceil

def comps(n,k):
 if k==1:
  yield (n,); return
 for j in range(n+1):
  for tail in comps(n-j,k-1): yield (j,)+tail

def partitions(n):
 def rec(j,bs):
  if j==n:
   yield tuple(tuple(b) for b in bs); return
  for b in bs:
   b.append(j); yield from rec(j+1,bs); b.pop()
  bs.append([j]); yield from rec(j+1,bs); bs.pop()
 yield from rec(0,[])

def cr(x,k): return sum(sorted(x,reverse=True)[:k],F(0))
def nc(x,t):
 if t<=0: return 1
 for k in range(1,len(x)+1):
  if cr(x,k)>=t:return k
 return float('inf')
def levelcap(x,a):
 if a==1:return (F(0),)*len(x)
 for h in range(1,len(x)+1):
  L=(sum(x[:h])-a)/h
  if L>=0 and (h==len(x) or L>=x[h]) and L<=x[h-1]:
   return tuple(min(v,L) for v in x)
 raise AssertionError((x,a))
def trim(y,a):
 y=list(y)
 for j in range(len(y)-1,-1,-1):
  d=min(a,y[j]); y[j]-=d; a-=d
 assert a==0
 return tuple(y)
def sp(x,p):return sum(v**p for v in x)
def dist(x,w):return sum(abs(v-u) for v,u in zip(x,w))/2

def moved_mass(x, pi):
 return sum((sum(x[i] for i in group)-max(x[i] for i in group) for group in pi), F(0))

def merge_subset_upper(x, rho, p):
 best=sp(x,p)
 for mask in product((0,1),repeat=len(x)-1):
  donors=tuple(v for v,chosen in zip(x[1:],mask) if chosen)
  mass=sum(donors,F(0))
  if mass<=rho:
   best=max(best,sp(x,p)+(x[0]+mass)**p-x[0]**p-sp(donors,p))
 return best

# Global moved mass, not a separate bound for each group.
example_rho=F(1,3)
example_x=(F(1,6),)*6
example_pairs=((0,1),(2,3),(4,5))
assert moved_mass(example_x,example_pairs)==F(1,2)>example_rho
example_feasible_partitions=0
for pi in partitions(len(example_x)):
 moved=moved_mass(example_x,pi)
 if moved>example_rho: continue
 w=[F(0)]*len(example_x)
 for group in pi:
  w[max(group,key=lambda i:example_x[i])]=sum(example_x[i] for i in group)
 assert dist(example_x,w)==moved<=example_rho
 assert sp(w,2)-sp(example_x,2)<=1-(1-example_rho)**2
 example_feasible_partitions+=1
assert example_feasible_partitions==81  # 1 singleton, 15 one-pair, 45 two-pair, 20 triple partitions.

# The receiving holding is not charged, and the old rho^2 bound is false.
recipient_x=(F(9,10),F(1,10))
assert moved_mass(recipient_x,((0,1),))==F(1,10)
assert sp((F(1),),2)-sp(recipient_x,2)>F(1,10)**2
# Whole-label restriction can make the exact Merge upper less than Shift's.
assert merge_subset_upper((F(3,5),F(2,5)),F(1,10),2)==F(13,25)
assert sp((F(7,10),F(3,10)),2)==F(29,50)>F(13,25)
# Joint introductory example: the packed completion attains the Shift bound.
toy=(F(1,2),F(1,5),F(3,20),F(3,20))
assert moved_mass(toy,((0,2,3),(1,)))==F(3,10)
assert merge_subset_upper(toy,F(3,10),2)==F(17,25)

D=8
orig=sorted({tuple(sorted((F(v,D) for v in c if v),reverse=True)) for c in comps(D,4)})
targets=[tuple(F(v,D) for v in c) for c in comps(D,5)]
shift_states=0
shift_cases=0
alias_cases=0
merge_cases=0
for x in orig:
 pad=x+(F(0),)*(5-len(x))
 for a in (F(j,D) for j in range(D+1)):
  h=levelcap(x,a)
  used=min(a,1-x[0])
  upper=(x[0]+used,)+trim(x[1:],used)
  found_cr=[F(-1)]*6
  found_sp={p:F(-1) for p in (2,3)}
  for w in targets:
   if dist(pad,w)>a:continue
   shift_states+=1
   for k in range(1,7):
    value=cr(w,k)
    assert cr(h,k)<=value<=min(1,cr(x,k)+a),(x,a,w,k)
    found_cr[k-1]=max(found_cr[k-1],value)
   for p in (2,3):
    value=sp(w,p)
    assert sp(h,p)<=value<=sp(upper,p),(x,a,w,p)
    found_sp[p]=max(found_sp[p],value)
   for tau in (F(1,4),F(1,2),F(3,4),F(1)):
    lo=nc(x,tau-a)
    hi=float('inf') if tau>1-a else nc(h,tau)
    assert lo<=nc(w,tau)<=hi,(x,a,w,tau)
  assert found_cr==[min(1,cr(x,k)+a) for k in range(1,7)]
  assert all(found_sp[p]==sp(upper,p) for p in (2,3))
  shift_cases+=1
 ps=list(partitions(len(x)))
 for s in (1,2,3):
  ws=[tuple(sorted((sum(x[i] for i in b) for b in pi),reverse=True)) for pi in ps if all(len(b)<=s for b in pi)]
  for k in range(1,6):
   assert min(cr(w,k) for w in ws)==cr(x,k)
   assert max(cr(w,k) for w in ws)==cr(x,s*k)
  for tau in (F(1,4),F(1,2),F(3,4),F(1)):
   assert min(nc(w,tau) for w in ws)==ceil(F(nc(x,tau),s))
   assert max(nc(w,tau) for w in ws)==nc(x,tau)
  for p in (2,3):
   assert min(sp(w,p) for w in ws)==sp(x,p)
   assert max(sp(w,p) for w in ws)<=s**(p-1)*sp(x,p)
  alias_cases+=1
 for rho in (F(j,D) for j in range(D+1)):
  best={p:sp(x,p) for p in (2,3)}
  a=min(rho,1-x[0])
  shift_upper=(x[0]+a,)+trim(x[1:],a)
  for pi in ps:
   moved=moved_mass(x,pi)
   if moved>rho:continue
   w=[F(0)]*len(x)
   for group in pi: w[max(group,key=lambda i:x[i])]=sum(x[i] for i in group)
   assert dist(x,w)==moved<=rho
   assert all(cr(w,k)>=cr(x,k) for k in range(1,len(x)+1))
   for p in (2,3):
    increase=sp(w,p)-sp(x,p)
    assert 0<=increase<=1-(1-rho)**p
    assert increase<=(x[0]+a)**p-x[0]**p
    assert sp(w,p)<=sp(shift_upper,p)
    best[p]=max(best[p],sp(w,p))
   merge_cases+=1
  for p in (2,3):
   assert best[p]==merge_subset_upper(x,rho,p),(x,rho,p)
print({'original_vectors':len(orig),'shift_cases':shift_cases,'feasible_shift_grid_states':shift_states,'alias_cap_cases':alias_cases,'feasible_merge_partitions_and_radii':merge_cases,'six_label_example_feasible_partitions':example_feasible_partitions,'result':'all exact rational checks passed'})
