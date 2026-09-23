#!/usr/bin/env python3
"""Compare browser endpoints with the independent Python figure implementation.

Run using the paper's Python environment, with Node.js on PATH.
"""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'analysis-code'))
from joint_capping import JointShift, capping_power_interval

cases = []
for head, tail in [([.5, .2, .15], .15), ([.7, .2, .1], 0), ([.25, .2], .55), ([1], 0)]:
    for budget in [0, .1, .3, 1]:
        for power in [1.1, 2, 3.5]:
            cases.append(dict(head=head, tail=tail, budget=budget, power=power))
script = '''const M=require('./webapp/metrics.js');
let s='';process.stdin.on('data', x=>s+=x);process.stdin.on('end',()=>
console.log(JSON.stringify(JSON.parse(s).map(c=>({
shift:M.jointShiftSp(c.head,c.tail,c.power,c.budget),
merge:M.jointMergeSp(c.head,c.tail,c.power,c.budget)})))));
'''
results = json.loads(subprocess.run(['node', '-e', script], input=json.dumps(cases), text=True,
                                    cwd=ROOT, check=True, capture_output=True).stdout)
for case, result in zip(cases, results):
    h = np.array(case['head']); t, b, p = case['tail'], case['budget'], case['power']
    lower, upper = JointShift(h, t, b).power_interval(p)
    np.testing.assert_allclose([result['shift']['lower'], result['shift']['upper']],
                               [lower, upper], rtol=1e-11, atol=1e-13)
    np.testing.assert_allclose([result['merge']['lower'], result['merge']['upper']],
                               [capping_power_interval(h, t, p)[0], upper], rtol=1e-11, atol=1e-13)
print(f'JavaScript/Python parity passed for {len(cases)} cases.')
