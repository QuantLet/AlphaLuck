"""Regenerate the six maintained standalone FRL Quantlets."""
from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[2]
NAMES=['AlphaLuckRiskProfiles','AlphaLuckRiskReturn','AlphaLuckPnlAttribution','AlphaLuckDenominatorSensitivity','AlphaLuckFrozenBenchmark','AlphaLuckFormationHour']
if __name__=='__main__':
    for name in NAMES:
        folder=ROOT/'quantlets'/name if (ROOT/'quantlets'/name).is_dir() else ROOT/name
        subprocess.run([sys.executable,str(folder/(name+'.py'))],cwd=folder,check=True)
