# Notebooks

For exploring the data and drafting figures. Start file names with your initials (sg_, jl_, rs_).

Loading the cleaned data (paths are relative to this folder):

```python
import pandas as pd

df = pd.read_parquet("../data/interim/requests_clean.parquet")
tracts = pd.read_parquet("../data/interim/acs_tracts_sf.parquet")
```

Please clear the outputs before committing a notebook.
