import sys

sys.path.append(".")
import fpml.confirmation as conf

try:
    print("\nCalculationPeriodDates types:")
    cls = getattr(conf, "CalculationPeriodDates")
    for fn, f in cls.__dataclass_fields__.items():
        print(f"  {fn}: {f.type}")
except Exception as e:
    print(e)
