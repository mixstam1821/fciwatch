# Contributing

Thanks for helping! The most useful thing right now is **testing on real data** and reporting what breaks.

## Setup

```bash
pip install -e ".[dev]"      # add ,fetch,read if you want to test with real data
pytest
ruff check .
```

## Guidelines

* Keep the core (`boxes`, `stats`, `drift`, `report`) free of heavy dependencies: numpy and pandas only.
  Satpy, pyresample and eumdac are imported only inside the functions that need them.
* Write comments in simple English. Say **why**, not only what.
* Every change to the maths needs a test, ideally with synthetic data where you know the answer.
* Sign convention: `bias = FCI - SEVIRI`, in kelvin.
* Be honest in the README status table. Do not mark something "tested" unless it is.

## Bug reports

Please include: the command you ran, the full error, your package versions
(`pip list | grep -i -E "satpy|pyresample|eumdac|numpy|pandas"`) and the time period.
