import pandas as pd
from tqdm import tqdm
import json

file = "./arxiv-metadata-oai-snapshot.json"

metadata  = []

lines = 10000    # 10k for testing

with open(file, 'r') as f:
    
    for line in tqdm(f):
        metadata.append(json.loads(line))
        lines -= 1
        if lines == 0: break
            
df = pd.DataFrame(metadata)
print(df.info())