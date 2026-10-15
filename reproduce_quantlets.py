"""Reproduce the five standalone AlphaLuck Quantlets offline."""
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
NAMES=['AlphaLuckRiskProfiles','AlphaLuckRiskReturn','AlphaLuckPnlAttribution',
       'AlphaLuckDenominatorSensitivity','AlphaLuckFrozenBenchmark']

if __name__=='__main__':
    for name in NAMES:
        print('Reproducing '+name,flush=True)
        subprocess.run([sys.executable,str(ROOT/name/(name+'.py'))],
                       cwd=ROOT/name,check=True)
    print('All five Quantlets reproduced.')
